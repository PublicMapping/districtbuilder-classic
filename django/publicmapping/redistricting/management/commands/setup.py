"""
Set up District Builder.

This management command will examine the main configuration file for 
correctness, import geographic levels, create spatial views, create 
geoserver layers, and construct a default plan.

This file is part of The Public Mapping Project
http://sourceforge.net/projects/publicmapping/

License:
    Copyright 2010 Micah Altman, Michael McDonald

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

Author: 
    Andrew Jennings, David Zwarg
"""

from decimal import Decimal
from django.contrib.gis.gdal import *
from django.contrib.gis.geos import *
from django.contrib.gis.db.models import Union 
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import simplejson as json
from optparse import make_option
from os.path import exists
from lxml.etree import parse
from xml.dom import minidom
from redistricting.models import *
from redistricting.utils import *
import traceback, pprint, httplib, string, base64, json

class Command(BaseCommand):
    """
    Set up District Builder.
    """
    args = '<config>'
    help = 'Sets up District Builder based on the main XML configuration.'
    option_list = BaseCommand.option_list + (
        make_option('-c', '--config', dest="config",
            help="Use configuration file CONFIG", metavar="CONFIG"),
        make_option('-d', '--debug', dest="debug",
            help="Generate verbose debug output", default=False, 
            action='store_true'),
        make_option('-g', '--geolevel', dest="geolevels",
            action="append", help="Geolevels to import"),
        make_option('-n', '--nesting', dest="nesting",
            action='store_true', default=False, help="Enforce nested geometries."),
        make_option('-v', '--views', dest="views", default=False,
            action="store_true", help="Create database views."),
        make_option('-G', '--geoserver', dest="geoserver",
            action="store_true", help="Create spatial layers in Geoserver.",
            default=False),
        make_option('-t', '--templates', dest="templates",
            action="store_true", help="Create system templates based on district index files.", default=False),
    )


    def handle(self, *args, **options):
        """
        Perform the command. 
        """
        if options.get('config') is None:
            print """
ERROR:

    This management command requires the -c or --config option. This option
    specifies the main configuration file.
"""
            return

        verbose = options.get('debug')

        try:
            config = parse( options.get('config') )
        except Exception, ex:
            print """
ERROR:

The configuration file specified could not be parsed. Please check the
contents of the file and try again.
"""
            if verbose:
                print "The following traceback may provide more information:"
                print traceback.format_exc()
            return

        #
        # config is now a XSD validated and id-ref checked configuration
        #

        self.import_prereq(config, verbose)

        optlevels = options.get("geolevels")
        nesting = options.get("nesting")
        if not optlevels is None:
            # Begin the import process
            geolevels = config.xpath('/DistrictBuilder/GeoLevels/GeoLevel')

            for i,geolevel in enumerate(geolevels):
                importme = len(optlevels) == 0
                importme = importme or (i in optlevels)
                if importme:
                    self.import_geolevel(config, geolevel, verbose)

                    #if nesting:
                    #    self.renest_geolevel(i, verbose)

        if options.get("views"):
            # Create views based on the subjects and geolevels
            self.create_views(verbose)

        if options.get("geoserver"):
            extent = Geounit.objects.all().extent()
            self.configure_geoserver(config, extent, verbose)

        if options.get("templates"):
            self.create_template(config, verbose)

    def configure_geoserver(self, config, extent, verbose):
        """
        Create the workspace and layers in geoserver, based on the
        imported data.
        """

        # Get the workspace information
        mapconfig = config.xpath('//MapServer')[0]

        host = mapconfig.get('hostname')
        if host == '':
            host = 'localhost'
        namespace = mapconfig.get('ns')
        namespacehref = mapconfig.get('nshref')

        user_pass = '%s:%s' % (mapconfig.get('adminuser'), mapconfig.get('adminpass'))
        auth = 'Basic %s' % string.strip(base64.encodestring(user_pass))
        headers = {'Authorization': auth, 'Content-Type': 'application/json', 'Accepts':'application/json'}

        def create_geoserver_object_if_necessary(url, name, dictionary, type_name=None, update=False):
            """ 
            This method will check geoserver for the existence of an object.
            It will create the object if it doesn't exist and let the user
            know the outcome via the print() statement
            """
            verbose_name = '%s:%s' % ('Geoserver object' if type_name is None else type_name, name)
            if self.rest_check(host,'%s/%s.json' % (url, name), headers):
                if verbose:
                    print "%s already exists" % verbose_name
                if update:
                    if not self.rest_config( 'PUT', host, url, json.dumps(dictionary), headers, 'Could not create %s' % verbose_name):
                        print "%s couldn't be updated." % verbose_name
                        return False
                    
            else:
                if not self.rest_config( 'POST', host, url, json.dumps(dictionary), headers, 'Could not create %s' % verbose_name):
                    return False

                if verbose:
                    print 'Created %s' % verbose_name

        # Create our namespace
        namespace_url = '/geoserver/rest/namespaces'
        namespace_obj = { 'namespace': { 'prefix': namespace, 'uri': namespacehref } }
        create_geoserver_object_if_necessary(namespace_url, namespace, namespace_obj, 'Namespace')

        # Create our DataStore
        dbconfig = config.xpath('//Database')[0]

        data_store_url = '/geoserver/rest/workspaces/%s/datastores' % namespace
        data_store_name = 'PostGIS'

        dbconn_obj = {
            'host': host,
            'port': 5432,
            'database': dbconfig.get('name'),
            'user': dbconfig.get('user'),
            'passwd': dbconfig.get('password'),
            'dbtype': 'postgis',
            'namespace': namespace,
            'schema': dbconfig.get('user')
        }
        data_store_obj = {'dataStore': {
             'name': data_store_name,
             'connectionParameters': dbconn_obj
        } }

        create_geoserver_object_if_necessary(data_store_url, data_store_name, data_store_obj, 'Data Store')

        # Create the identify, simple, and demographic layers
        def get_feature_type_obj (name, extent, title=None):
            feature_type_obj = { 'featureType': {
                'name': name,
                'title': name if title is None else title,
                'nativeBoundingBox': {
                    'minx': '%0.1f' % extent[0],
                    'miny': '%0.1f' % extent[1],
                    'maxx': '%0.1f' % extent[2],
                    'maxy': '%0.1f' % extent[3]
                },
                'maxFeatures': settings.FEATURE_LIMIT + 1
            } }
            return feature_type_obj

        # Make a list of layers
        feature_type_names = ['identify_geounit']
        for geolevel in Geolevel.objects.all():
            feature_type_names.append('simple_%s' % geolevel.name)

            for subject in Subject.objects.all():
                feature_type_names.append('demo_%s_%s' % (geolevel.name, subject.name))

        # Check for each layer in the list.  If it doesn't exist, make it
        feature_type_url = '/geoserver/rest/workspaces/%s/datastores/%s/featuretypes' % (namespace, data_store_name)
        for feature_type_name in feature_type_names:
            feature_type_obj = get_feature_type_obj(feature_type_name, extent)
            create_geoserver_object_if_necessary(feature_type_url, feature_type_name, feature_type_obj, 'Feature Type')

        # Create the styles for the demographic layers
        styledir = mapconfig.get('styles')
        style_url = '/geoserver/rest/styles'

        sld_headers = {
            'Authorization': auth,
            'Content-Type': 'application/vnd.ogc.sld+xml',
            'Accepts':'application/xml'
        }

        for geolevel in Geolevel.objects.all():
            is_first_subject = True

            for subject in Subject.objects.all():

                # This helper method is used for each layer
                def publish_and_assign_style(style_name, style_type):
                    """
                    A method to assist in publishing styles to geoserver and configuring the layers
                    to have a default style
                    """

                    if not style_type:
                        style_type = subject.name
                    if not style_name:
                        style_name = 'demo_%s_%s' % (geolevel.name, subject.name)

                    style_obj = { 'style': {
                        'name': style_name,
                        'filename': '%s.sld' % style_name
                    } }

                    # Get the SLD file
                    sld = self.get_style_contents( styledir, geolevel.name, style_type )

                    if sld is None:
                        print 'No style file found for %s' % style_name
                        return False

                    # Create the style object on the geoserver
                    create_geoserver_object_if_necessary(style_url, style_name, style_obj, 'Map Style')

                    # Update the style with the sld file contents

                    self.rest_config( 'PUT', host, '/geoserver/rest/styles/%s' % style_name, sld, \
                        sld_headers, "Could not upload style file '%s.sld'" % style_name)

                    if verbose:
                        print "Uploaded '%s.sld' file." % style_name

                    # Apply the uploaded style to the demographic layers
                    layer = { 'layer' : {
                        'defaultStyle': {
                            'name': style_name
                        },
                        'enabled': True
                    } }

                    
                    if not self.rest_config( 'PUT', host, '/geoserver/rest/layers/%s:%s' % (namespace, style_name), \
                        json.dumps(layer), headers, "Could not assign style to layer '%s'." % style_name):
                            return False

                    if verbose:
                        print "Assigned style '%s' to layer '%s'." % (style_name, style_name )


                # Create the style for the demographic layer
                publish_and_assign_style(None, None)

                if is_first_subject:
                    is_first_subject = False

                    # Create NONE demographic layer, based on first subject
                    feature_type_obj = get_feature_type_obj('demo_%s' % geolevel.name, extent)
                    feature_type_obj['featureType']['nativeName'] = 'demo_%s_%s' % (geolevel.name, subject.name)
                    create_geoserver_object_if_necessary(feature_type_url, 'demo_%s' % geolevel.name, feature_type_obj, 'Feature Type')
                    publish_and_assign_style('demo_%s' % geolevel.name, 'none')

                    # Create boundary layer, based on geographic boundaries
                    feature_name = '%s_boundaries' % geolevel.name
                    feature_type_obj = get_feature_type_obj(feature_name , extent)
                    feature_type_obj['featureType']['nativeName'] = 'demo_%s_%s' % (geolevel.name, subject.name)
                    create_geoserver_object_if_necessary(feature_type_url, feature_name, feature_type_obj, 'Feature Type')
                    publish_and_assign_style('%s_boundaries' % geolevel.name, 'boundaries')

        # finished configure_geoserver
        return True

    def get_style_contents(self, styledir, geolevel, subject):
        path = '%s/%s_%s.sld' % (styledir, geolevel, subject) 
        try:
            stylefile = open(path)
            sld = stylefile.read()
            stylefile.close()

            return sld
        except:
            print """
ERROR:

        The style file %s colud not be loaded. Please confirm that the
        style files are named according to the "geolevel_subject.sld"
        convention, and try again.
""" % path
            return None

    def rest_check(self, host, url, headers):
        try:
            conn = httplib.HTTPConnection(host, 8080)
            conn.request('GET', url, None, headers)
            rsp = conn.getresponse()
            rsp.read() # and discard
            conn.close()
            return rsp.status == 200
        except:
            return False

    def rest_config(self, method, host, url, data, headers, msg):
        try:
            # print('url: %s; data: %s' % (url, data))
            conn = httplib.HTTPConnection(host, 8080)
            conn.request(method, url, data, headers)
            rsp = conn.getresponse()
            rsp.read() # and discard
            conn.close()
            if rsp.status != 201 and rsp.status != 200:
                print """
ERROR:

        Could not configure geoserver: 

        %s 

        Please check the configuration settings, and try again.
""" % msg
                print "HTTP Status: %d" % rsp.status
                return False
        except Exception, ex:
            print """
ERROR:

        Exception thrown while configuring geoserver.
"""
            return False

        return True

    @transaction.commit_manually
    def create_views(self, verbose):
        """
        Create specialized views for GIS and mapping layers.

        This creates views in the database that are used to map the features
        at different geographic levels, and for different choropleth map
        visualizations. All parameters for creating the views are saved
        in the database at this point.
        """
        cursor = connection.cursor()
        
        sql = "CREATE OR REPLACE VIEW identify_geounit AS SELECT rg.id, rg.name, rg.geolevel_id, rg.geom, rc.number, rc.percentage, rc.subject_id FROM redistricting_geounit rg JOIN redistricting_characteristic rc ON rg.id = rc.geounit_id;"
        cursor.execute(sql)
        transaction.commit()
        if verbose:
            print 'Created identify_geounit view ...'

        for geolevel in Geolevel.objects.all():
            sql = "CREATE OR REPLACE VIEW simple_%s AS SELECT id, name, geolevel_id, simple as geom FROM redistricting_geounit WHERE geolevel_id = %d;" % (geolevel.name, geolevel.id,)
            cursor.execute(sql)
            transaction.commit()
            if verbose:
                print 'Created simple_%s view ...' % geolevel.name
            
            for subject in Subject.objects.all():
                sql = "CREATE OR REPLACE VIEW demo_%s_%s AS SELECT rg.id, rg.name, rg.geolevel_id, rg.geom, rc.number, rc.percentage FROM redistricting_geounit rg JOIN redistricting_characteristic rc ON rg.id = rc.geounit_id WHERE rc.subject_id = %d AND rg.geolevel_id = %d;" % \
                    (geolevel.name, subject.name, 
                     subject.id, geolevel.id,)
                cursor.execute(sql)
                transaction.commit()
                if verbose:
                    print 'Created demo_%s_%s view ...' % \
                        (geolevel.name, subject.name)

    def import_geolevel(self, config, geolevel, verbose):
        """
        Import the geography at a geolevel.

        Parameters:
            config - The configuration dict of the geolevel
            geolevel - The geolevel node in the configuration
        """
        gconfig = {
            'shapepath': geolevel.get('shapefile'),
            'geolevel': geolevel.get('name'),
            'name_field': geolevel.get('namefield'),
            'supplemental_id_field': geolevel.get('supplementfield'),
            'subject_fields': [],
            'tolerance': geolevel.get('tolerance')
        }

        trefs = geolevel.xpath('LegislativeBodies/LegislativeBody/LegislativeTargets/LegislativeTarget')
        for tref in trefs:
            tconfig = config.xpath('//Target[@id="%s"]' % tref.get('ref'))[0]

            sconfig = config.xpath('//Subject[@id="%s"]' % tconfig.get('subjectref'))[0]
            if 'aliasfor' in sconfig.attrib:
                salconfig = config.xpath('//Subject[@id="%s"]' % sconfig.get('aliasfor'))[0]
                sconfig.append(salconfig)
            gconfig['subject_fields'].append( sconfig )

        self.import_shape(gconfig, verbose)

    def renest_geolevel(self, geolevel_id, verbose):
        """
        Perform a re-nesting of the geography in the geographic levels.

        Renesting the geometry works with Census Geography only that
        has supplemental_ids.

        Parameters:
            geolevel - The configuration geolevel
            verbose - A flag indicating verbose output messages.
        """
        if geolevel_id > 0:
            geolevel = Geolevel.objects.get(id=geolevel_id+1).name


    def import_prereq(self, config, verbose):
        """
        Import the required support data prior to importing.

        Import the LegislativeBody, Subject, Geolevel, and associated
        relationships prior to loading all the geounits.
        """

        # Import legislative bodies first.
        bodies = config.xpath('//LegislativeBody[@id]')
        for body in bodies:
            obj, created = LegislativeBody.objects.get_or_create(
                name=body.get('name'), 
                member=body.get('member'), 
                max_districts=body.get('maxdistricts'))
            if verbose:
                if created:
                    print 'Created LegislativeBody "%s"' % body.get('name')
                else:
                    print 'LegislativeBody "%s" already exists' % body.get('name')


        # Import subjects second
        subjs = config.xpath('//Subject[@id]')
        for subj in subjs:
            if 'aliasfor' in subj.attrib:
                continue
            obj, created = Subject.objects.get_or_create(
                name=subj.get('id'), 
                display=subj.get('name'), 
                short_display=subj.get('short_name'), 
                is_displayed=(subj.get('displayed')=='true'), 
                sort_key=subj.get('sortkey'))

            if verbose:
                if created:
                    print 'Created Subject "%s"' % subj.get('name')
                else:
                    print 'Subject "%s" already exists' % subj.get('name')

        # Import targets third
        targs = config.xpath('//Targets/Target')

        for targ in targs:
            # get subject
            subconfig = config.xpath('//Subject[@id="%s"]' % (targ.get('subjectref')))[0]
            if not subconfig.get('aliasfor') is None:
                # dereference any subject alias
                subconfig = config.xpath('//Subject[@id="%s"]' % (subconfig.get('aliasfor')))[0]
            subject = Subject.objects.filter(name=subconfig.get('id'))[0]

            obj, created = Target.objects.get_or_create(
                subject=subject,
                value=targ.get('value'),
                range1=targ.get('range1'),
                range2=targ.get('range2'))

            if verbose:
                if created:
                    print 'Created Target "%s"' % obj
                else:
                    print 'Target "%s" already exists' % obj
            
        # Import geolevels fourth
        # Note that geolevels may be added in any order, but the geounits
        # themselves need to be imported top-down (smallest area to biggest)
        geolevels = config.xpath('//GeoLevels/GeoLevel')
        for geolevel in geolevels:
            glvl,created = Geolevel.objects.get_or_create(name=geolevel.get('name'),min_zoom=geolevel.get('min_zoom'),sort_key=geolevel.get('sort_key'),tolerance=geolevel.get('tolerance'))

            if verbose:
                if created:
                    print 'Created GeoLevel "%s"' % glvl.name
                else:
                    print 'GeoLevel "%s" already exists' % glvl.name

            # Map the imported geolevel to a legislative body
            lbodies = geolevel.xpath('LegislativeBodies/LegislativeBody')
            for lbody in lbodies:
                # de-reference
                lbconfig = config.xpath('//LegislativeBody[@id="%s"]' % lbody.get('ref'))[0]
                legislative_body = LegislativeBody.objects.get(name=lbconfig.get('name'))
                
                # Add a mapping for the targets in this GL/LB combo.
                targs = lbody.xpath('LegislativeTargets/LegislativeTarget')
                for targ in targs:
                    tconfig = config.xpath('//Target[@id="%s"]' % targ.get('ref'))[0]
                    sconfig = config.xpath('//Subject[@id="%s"]' % tconfig.get('subjectref'))[0]
                    if not sconfig.get('aliasfor') is None:
                        # dereference any subject alias
                        sconfig = config.xpath('//Subject[@id="%s"]' % (sconfig.get('aliasfor')))[0]
                    subject = Subject.objects.get(name=sconfig.get('id'))

                    target = Target.objects.get(
                        subject=subject,
                        value=tconfig.get('value'),
                        range1=tconfig.get('range1'),
                        range2=tconfig.get('range2')) 

                    if not targ.get('default') is None:
                        # get or create won't work here, as it requires a
                        # target, which may be different from the item
                        # we want to retrieve
                        obj = LegislativeDefault.objects.filter(legislative_body=legislative_body)
                        if len(obj) == 0:
                            obj = LegislativeDefault(legislative_body=legislative_body, target=target)
                            created = True
                        else:
                            obj = obj[0]
                            obj.target = target
                            created = False

                        obj.save()

                        if verbose:
                            if created:
                                print 'Set default target for LegislativeBody "%s"' % legislative_body.name
                            else:
                                print 'Changed default target for LegislativeBody "%s"' % legislative_body.name

                    pconfig = lbody.xpath('Parent')
                    if len(pconfig) == 0:
                        parent = None
                    else:
                        pconfig = config.xpath('//GeoLevel[@id="%s"]' % pconfig[0].get('ref'))[0]
                        plvl = Geolevel.objects.get(name=pconfig.get('name'))
                        parent = LegislativeLevel.objects.get(
                            legislative_body=legislative_body, 
                            geolevel=plvl, 
                            target=target)

                    obj, created = LegislativeLevel.objects.get_or_create(
                        legislative_body=legislative_body, 
                        geolevel=glvl, 
                        target=target, 
                        parent=parent)

                    if verbose:
                        if created:
                            print 'Created LegislativeBody/GeoLevel mapping "%s/%s"' % (legislative_body.name, glvl.name)
                        else:
                            print 'LegislativeBody/GeoLevel mapping "%s/%s" already exists' % (legislative_body.name, glvl.name)

        # Create an anonymous user
        anon,created = User.objects.get_or_create(username='anonymous')

        if not created:
            anon.set_password('anonymous')
            anon.save()

        return True

    def import_shape(self,config,verbose):
        """
        Import a shapefile, based on a config.

        Parameters:
            config -- A dictionary with 'shapepath', 'geolevel', 'name_field', and 'subject_fields' keys.
        """
        ds = DataSource(config['shapepath'])

        if verbose:
            print 'Importing from ', ds

        lyr = ds[0]
        if verbose:
            print '%d objects in shapefile' % len(lyr)

        level = Geolevel.objects.get(name=config['geolevel'])
        supplemental_id_field = config['supplemental_id_field']

        # Create the subjects we need
        subject_objects = {}
        for sconfig in config['subject_fields']:
            foundalias = False
            for elem in sconfig.getchildren():
                if elem.tag == 'Subject':
                    foundalias = True
                    sub = Subject.objects.get(name=elem.get('id'))
            if not foundalias:
                sub = Subject.objects.get(name=sconfig.get('id'))
            subject_objects[sconfig.get('field')] = sub

        progress = 0.0
        if verbose:
            sys.stdout.write('0% .. ')
            sys.stdout.flush()
        for i,feat in enumerate(lyr):
            if (float(i) / len(lyr)) > (progress + 0.1):
                progress += 0.1
                if verbose:
                    sys.stdout.write('%2.0f%% .. ' % (progress * 100))
                    sys.stdout.flush()

            prefetch = Q(name=feat.get(config['name_field'])) & Q(geolevel=level)
            if supplemental_id_field:
                prefetch = prefetch & Q(supplemental_id=feat.get(supplemental_id_field))
            prefetch = Geounit.objects.filter(prefetch) 
            if prefetch.count() == 0:
                try :

                    # Store the geos geometry
                    geos = feat.geom.geos
                    # Coerce the geometry into a MultiPolygon
                    if geos.geom_type == 'MultiPolygon':
                        my_geom = geos
                    elif geos.geom_type == 'Polygon':
                        my_geom = MultiPolygon(geos)
                    simple = my_geom.simplify(tolerance=config['tolerance'],preserve_topology=True)
                    if simple.geom_type != 'MultiPolygon':
                        simple = MultiPolygon(simple)
                    center = my_geom.centroid

                    geos = None

                    # Ensure the centroid is within the geometry
                    if not center.within(my_geom):
                        # Get the first polygon in the multipolygon
                        first_poly = my_geom[0]
                        # Get the extent of the first poly
                        first_poly_extent = first_poly.extent
                        min_x = first_poly_extent[0]
                        max_x = first_poly_extent[2]
                        # Create a line through the bbox and the poly center
                        my_y = first_poly.centroid.y
                        centerline = LineString( (min_x, my_y), (max_x, my_y))
                        # Get the intersection of that line and the poly
                        intersection = centerline.intersection(first_poly)
                        if type(intersection) is MultiLineString:
                            intersection = intersection[0]
                        # the center of that line is my within-the-poly centroid.
                        center = intersection.centroid
                        first_poly = first_poly_extent = min_x = max_x = my_y = centerline = intersection = None

                    if verbose:
                        if not my_geom.simple:
                            print 'Geometry %d is not simple.\n' % feat.fid
                        if not my_geom.valid:
                            print 'Geometry %d is not valid.\n' % feat.fid
                        if not simple.simple:
                            print 'Simplified Geometry %d is not simple.\n' % feat.fid
                        if not simple.valid:
                            print 'Simplified Geometry %d is not valid.\n' % feat.fid

                    g = Geounit(geom = my_geom, name = feat.get(config['name_field']), geolevel = level, simple = simple, center = center)
                    if supplemental_id_field:
                        g.supplemental_id = feat.get(supplemental_id_field)
                    g.save()
                except:
                    print 'Failed to import geometry for feature %d' % feat.fid
                    if verbose:
                        traceback.print_exc()
                        print ''
                    continue
            else:
                g = prefetch[0]

            for attr, obj in subject_objects.iteritems():
                value = Decimal(str(feat.get(attr))).quantize(Decimal('000000.0000', 'ROUND_DOWN'))
                c, created = Characteristic.objects.get_or_create(subject=obj, geounit=g)
                try:
                    c.number = value
                    c.save()
                except:
                    c.number = '0.0'
                    c.save()
                    print 'Failed to set value "%s" to %d in feature "%s"' % (attr, feat.get(attr), feat.get(config['name_field']),)
                    if verbose:
                        traceback.print_exc()
                        print ''


        if verbose:
            sys.stdout.write('100%\n')

    def create_template(self, config, verbose):
        """
        Create the templates that are defined in the configuration file.
        In addition to creating templates explicitly specified, this
        will also create a blank template for each LegislativeBody.

        Parameters:
            config - The XML configuration.
            verbose - A flag for outputting messages during the process.
        """
        admin = User.objects.filter(is_staff=True)
        if admin.count() == 0:
            print "Creating templates requires at least one admin user."
            return

        admin = admin[0]

        templates = config.xpath('/DistrictBuilder/Templates/Template')
        for template in templates:
            lbconfig = config.xpath('//LegislativeBody[@id="%s"]' % template.xpath('LegislativeBody')[0].get('ref'))[0]
            query = LegislativeBody.objects.filter(name=lbconfig.get('name'))
            if query.count() == 0:
                if verbose:
                    print "LegislativeBody '%s' does not exist, skipping." % lbconfig.get('ref')
                continue
            else:
                legislative_body = query[0]

            query = Plan.objects.filter(name=template.get('name'), legislative_body=legislative_body, owner=admin, is_template=True)
            if query.count() > 0:
                if verbose:
                    print "Plan '%s' exists, skipping." % template.get('name')
                continue

            fconfig = template.xpath('Blockfile')[0]
            path = fconfig.get('path')

            DistrictIndexFile.index2plan( template.get('name'), legislative_body.id, path, owner=admin, template=True, purge=False, email=None)

            if verbose:
                print 'Created template plan "%s"' % template.get('name')

        lbodies = config.xpath('//LegislativeBody[@id]')
        for lbody in lbodies:
            owner = User.objects.get(is_staff=True)
            legislative_body = LegislativeBody.objects.get(name=lbody.get('name'))
            plan,created = Plan.objects.get_or_create(name='Blank',legislative_body=legislative_body,owner=owner,is_template=True)
            if verbose:
                if created:
                    print 'Created Plan named "Blank" for LegislativeBody "%s"' % legislative_body.name
                else:
                    print 'Plan named "Blank" for LegislativeBody "%s" already exists' % legislative_body.name
