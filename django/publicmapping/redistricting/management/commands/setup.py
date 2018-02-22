"""
Set up DistrictBuilder.

This management command will examine the main configuration file for
correctness, import geographic levels, create spatial views, create
geoserver layers, and construct a default plan.

This file is part of The Public Mapping Project
https://github.com/PublicMapping/

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
    Andrew Jennings, David Zwarg, Kenny Shepard
"""

from decimal import Decimal
from django.contrib.gis.gdal import (DataSource, SpatialReference)
from django.contrib.gis.geos import (MultiPolygon, LineString, MultiLineString)
from django.contrib.auth.models import User
from django.core.cache import caches
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import translation
from django.utils.translation import ugettext as _, activate
from os.path import exists
from lxml.etree import parse, XSLT
from redistricting.config import Utils, SpatialUtils
from redistricting.models import (Geolevel, Geounit, Subject, Characteristic,
                                  LegislativeBody, Plan, ProcessingState,
                                  configure_views)
from redistricting.config import ConfigImporter
from district_builder_config import StoredConfig
from redistricting.tasks import DistrictIndexFile
import traceback
import logging
import sys
import csv
import types

from redisutils import key_gen

logger = logging.getLogger()
logger.addHandler(logging.StreamHandler())


class Command(BaseCommand):
    """
    Set up DistrictBuilder.
    """
    args = '<config>'
    help = 'Sets up DistrictBuilder based on the main XML configuration.'

    force = False

    def add_arguments(self, parser):
        """Add arguments and options to the base command parser"""
        parser.add_argument(
            'config', help="Use configuration file CONFIG", metavar="CONFIG"),
        parser.add_argument(
            '-f',
            '--force',
            dest="force",
            help="Force changes if config differs from database",
            default=False,
            action='store_true'),
        parser.add_argument(
            '-g',
            '--geolevel',
            dest="geolevels",
            action="append",
            help="Geolevels to import",
            type=int),
        parser.add_argument(
            '-n',
            '--nesting',
            dest="nesting",
            action='append',
            help="Enforce nested geometries.",
            type=int),
        parser.add_argument(
            '-V',
            '--views',
            dest="views",
            default=False,
            action="store_true",
            help="Create database views."),
        parser.add_argument(
            '-G',
            '--geoserver',
            dest="geoserver",
            action="store_true",
            help="Create spatial layers in Geoserver.",
            default=False),
        parser.add_argument(
            '-t',
            '--templates',
            dest="templates",
            action="store_true",
            help="Create system templates based on district index files.",
            default=False),
        parser.add_argument(
            '-a',
            '--adjacency',
            dest="adjacency",
            help="Import adjacency data",
            default=False,
            action='store_true'),
        parser.add_argument(
            '-s',
            '--static',
            dest="static",
            action='store_true',
            help="Collect and compress the static javascript and css files.",
            default=False),
        parser.add_argument(
            '-l',
            '--languages',
            dest="languages",
            action='store_true',
            help="Create and compile a message file for each language defined.",
            default=False)

    def setup_logging(self, verbosity):
        """
        Setup the logging facility.
        """
        if verbosity > 1:
            logger.setLevel(logging.DEBUG)
        elif verbosity > 0:
            logger.setLevel(logging.INFO)

    def handle(self, *args, **options):
        """
        Perform the command.
        """
        self.setup_logging(int(options.get('verbosity')))
        force = options.get('force')

        translation.activate('en')

        if options.get('config') is None:
            logger.warning("""
ERROR:

    This management command requires the -c or --config option. This option
    specifies the main configuration file.
""")
            sys.exit(1)

        try:
            store = StoredConfig(options.get('config'))
        except Exception:
            logger.info("""
ERROR:

The configuration file specified could not be parsed. Please check the
contents of the file and try again.
""")
            # Indicate that an error has occurred
            sys.exit(1)

        if not store.validate():
            logger.info("""
ERROR:

The configuration file was not valid. Please check the contents of the
file and try again.
""")
            # Indicate that an error has occurred
            sys.exit(1)

        # Create an importer for use in importing the config objects
        config = ConfigImporter(store)

        # When the setup script is run, it re-computes the secret key
        # used to secure session data. Blow away any old sessions that
        # were in the DB.
        success = Utils.purge_sessions()

        if not success:
            sys.exit(1)

        # When configuring, we want to keep track of any failures so we can
        # return the correct exit code.  Since False evaluates to a 0, we can
        # multiply values by all_ok so that a single False value means all_ok
        # will remain false
        all_ok = True

        success = config.import_superuser(force)

        all_ok = success
        try:
            all_ok = all_ok * self.import_prereq(config, force)
        except:
            all_ok = False
            logger.info('Error importing configuration.')
            logger.info(traceback.format_exc())

        # Create the utilities for spatial operations (renesting and geoserver)
        geoutil = SpatialUtils(store)

        try:
            optlevels = options.get("geolevels")
            nestlevels = options.get("nesting")

            if (not optlevels is None) or (not nestlevels is None):
                # Begin the import process
                geolevels = store.filter_geolevels()

                for i, geolevel in enumerate(geolevels):
                    if optlevels is not None:
                        importme = len(optlevels) == 0 or (i in optlevels)
                        if importme:
                            self.import_geolevel(store, geolevel)

                    if nestlevels is not None:
                        nestme = len(nestlevels) == 0
                        nestme = nestme or (i in nestlevels)
                        if nestme:
                            geoutil.renest_geolevel(geolevel)
        except:
            all_ok = False
            logger.info('ERROR importing geolevels.')
            logger.info(traceback.format_exc())

        # Do this once after processing the geolevels
        config.import_contiguity_overrides()

        # Save any changes to the config locale files
        config.save()

        if options.get("views"):
            # Create views based on the subjects and geolevels
            try:
                configure_views()
            except:
                logger.info(traceback.format_exc())
                all_ok = False

        if options.get("geoserver"):
            try:
                all_ok = all_ok * geoutil.purge_geoserver()
                if all_ok:
                    logger.info("Geoserver configuration cleaned.")
                    all_ok = all_ok * geoutil.configure_geoserver()
                else:
                    logger.info(
                        "Geoserver configuration could not be cleaned.")
            except:
                logger.info('ERROR configuring geoserver.')
                logger.info(traceback.format_exc())
                all_ok = False

        if options.get("templates"):
            try:
                self.create_template(store.data)
            except:
                logger.info('ERROR creating templates.')
                logger.info(traceback.format_exc())
                all_ok = False

        if options.get("static"):
            call_command(
                'collectstatic',
                interactive=False,
                verbosity=options.get('verbosity'))
            call_command(
                'compress',
                interactive=False,
                verbosity=options.get('verbosity'),
                force=True)

        if options.get("languages"):
            call_command(
                'makelanguagefiles',
                interactive=False,
                verbosity=options.get('verbosity'))

        if options.get("adjacency"):
            self.import_adjacency(store.data)

        # For our return value, a 0 (False) means OK, any nonzero (i.e., True or 1)
        # means that  an error occurred - the opposite of the meaning of all_ok's bool
        sys.exit(not all_ok)

    def import_geolevel(self, store, geolevel):
        """
        Import the geography at a geolevel.

        Parameters:
            config - The configuration dict of the geolevel
            geolevel - The geolevel node in the configuration
        """

        shapeconfig = geolevel.xpath('Shapefile')
        attrconfig = None
        if len(shapeconfig) == 0:
            shapeconfig = geolevel.xpath('Files/Geography')
            attrconfig = geolevel.xpath('Files/Attributes')

        if len(shapeconfig) == 0:
            logger.info("""
ERROR:

    The geographic level setup routine needs either a Shapefile or a
    set of Files/Geography elements in the configuration in order to
    import geographic levels.""")
            return

        region_filters = self.create_filter_functions(store)

        gconfig = {
            'shapefiles': shapeconfig,
            'attributes': attrconfig,
            'geolevel': geolevel.get('name')[:50],
            'subject_fields': [],
            'tolerance': geolevel.get('tolerance'),
            'region_filters': region_filters
        }

        sconfigs = store.filter_subjects()
        for sconfig in sconfigs:
            if 'aliasfor' in sconfig.attrib:
                salconfig = store.get_subject(sconfig.get('aliasfor'))
                sconfig.append(salconfig)
            gconfig['subject_fields'].append(sconfig)

        self.import_shape(store, gconfig)

    def import_prereq(self, config, force):
        """
        Import the required support data prior to importing.

        Import the LegislativeBody, Subject, Geolevel, and associated
        relationships prior to loading all the geounits.
        """

        # Import the regions first
        success = config.import_regions(force)

        success = success * config.import_legislative_bodies(force)

        success = success * config.import_subjects(force)

        success = success * config.import_geolevels(force)

        success = success * config.import_regional_geolevels(force)

        success = success * config.import_scoring(force)

        return success

    def import_shape(self, store, config):
        """
        Import a shapefile, based on a config.

        Parameters:
            config -- A dictionary with 'shapepath', 'geolevel', 'name_field', 'region_filters' and 'subject_fields' keys.
        """

        def get_shape_tree(shapefile, feature):
            shpfields = shapefile.xpath('Fields/Field')
            builtid = ''
            for idx in range(0, len(shpfields)):
                idpart = shapefile.xpath(
                    'Fields/Field[@type="tree" and @pos=%d]' % idx)
                if len(idpart) > 0:
                    idpart = idpart[0]
                    part = feature.get(idpart.get('name'))
                    # strip any spaces in the treecode
                    if not (isinstance(part, types.StringTypes)):
                        part = '%d' % part
                    part = part.strip(' ')
                    width = int(idpart.get('width'))
                    builtid = '%s%s' % (builtid, part.zfill(width))
            return builtid

        def get_shape_portable(shapefile, feature):
            field = shapefile.xpath('Fields/Field[@type="portable"]')[0]
            portable = feature.get(field.get('name'))
            if not (isinstance(portable, types.StringTypes)):
                portable = '%d' % portable
            return portable

        def get_shape_name(shapefile, feature):
            field = shapefile.xpath('Fields/Field[@type="name"]')[0]
            strname = feature.get(field.get('name'))
            if type(strname) == str:
                return strname.decode('latin-1')
            else:
                return str(strname)

        for h, shapefile in enumerate(config['shapefiles']):
            if not exists(shapefile.get('path')):
                logger.info("""
ERROR:

    The filename specified by the configuration:

    %s

    Could not be found. Please check the configuration and try again.
""", shapefile.get('path'))
                raise IOError(
                    'Cannot find the file "%s"' % shapefile.get('path'))

            ds = DataSource(shapefile.get('path'))

            logger.info('Importing from %s, %d of %d shapefiles...', ds, h + 1,
                        len(config['shapefiles']))

            lyr = ds[0]
            logger.info('%d objects in shapefile', len(lyr))

            level = Geolevel.objects.get(name=config['geolevel'].lower()[:50])
            # Create the subjects we need
            subject_objects = {}
            for sconfig in config['subject_fields']:
                attr_name = sconfig.get('field')
                foundalias = False
                for elem in sconfig.getchildren():
                    if elem.tag == 'Subject':
                        foundalias = True
                        sub = Subject.objects.get(
                            name=elem.get('id').lower()[:50])
                if not foundalias:
                    sub = Subject.objects.get(
                        name=sconfig.get('id').lower()[:50])
                subject_objects[attr_name] = sub
                subject_objects['%s_by_id' % sub.name] = attr_name

            progress = 0.0
            logger.info('0% .. ')
            for i, feat in enumerate(lyr):
                if (float(i) / len(lyr)) > (progress + 0.1):
                    progress += 0.1
                    logger.info('%2.0f%% .. ', progress * 100)

                levels = [level]
                for region, filter_list in config[
                        'region_filters'].iteritems():
                    # Check for applicability of the function by examining the config
                    geolevel_xpath = '/DistrictBuilder/GeoLevels/GeoLevel[@name="%s"]' % config[
                        'geolevel']
                    geolevel_config = store.data.xpath(geolevel_xpath)
                    geolevel_region_xpath = '/DistrictBuilder/Regions/Region[@name="%s"]/GeoLevels//GeoLevel[@ref="%s"]' % (
                        region, geolevel_config[0].get('id'))
                    if len(store.data.xpath(geolevel_region_xpath)) > 0:
                        # If the geolevel is in the region, check the filters
                        for f in filter_list:
                            if f(feat) is True:
                                levels.append(
                                    Geolevel.objects.get(
                                        name='%s_%s' % (region, level.name)))
                shape_name = get_shape_name(shapefile, feat)
                shape_portable_id = get_shape_portable(shapefile, feat)
                shape_tree_code = get_shape_tree(shapefile, feat)
                prefetch = Geounit.objects.filter(
                    name=shape_name,
                    geolevel__in=levels,
                    portable_id=shape_portable_id,
                    tree_code=shape_tree_code)
                should_create = prefetch.count() == 0
                if should_create:
                    try:
                        # Store the geos geometry
                        # Buffer by 0 to get rid of any self-intersections which may make this geometry invalid.
                        geos = feat.geom.geos.buffer(0)
                        # Coerce the geometry into a MultiPolygon
                        if geos.geom_type == 'MultiPolygon':
                            my_geom = geos
                        elif geos.geom_type == 'Polygon':
                            my_geom = MultiPolygon(geos)
                        simple = my_geom.simplify(
                            tolerance=Decimal(config['tolerance']),
                            preserve_topology=True)
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
                            centerline = LineString((min_x, my_y),
                                                    (max_x, my_y))
                            # Get the intersection of that line and the poly
                            intersection = centerline.intersection(first_poly)
                            if type(intersection) is MultiLineString:
                                intersection = intersection[0]
                            # the center of that line is my within-the-poly centroid.
                            center = intersection.centroid
                            first_poly = first_poly_extent = min_x = max_x = my_y = centerline = intersection = None
                        g = Geounit(
                            geom=my_geom,
                            name=shape_name,
                            simple=simple,
                            center=center,
                            portable_id=shape_portable_id,
                            tree_code=shape_tree_code)
                        g.save()
                        g.geolevel = levels
                        g.save()

                    except:
                        logger.info('Failed to import geometry for feature %d',
                                    feat.fid)
                        logger.info(traceback.format_exc())
                        continue
                else:
                    g = prefetch[0]
                    g.geolevel = levels
                    g.save()

                if not config['attributes']:
                    # If we created a new Geounit, we can let this function know that it doesn't
                    # need to check for existing Characteristics, which will speed things up
                    # significantly.
                    self.set_geounit_characteristic(
                        g,
                        subject_objects,
                        feat,
                        updates_possible=not should_create)

            logger.info('100%')

        if config['attributes']:
            progress = 0
            logger.info("Assigning subject values to imported geography...")
            logger.info('0% .. ')
            for h, attrconfig in enumerate(config['attributes']):
                if not exists(attrconfig.get('path')):
                    logger.info("""
ERROR:

    The filename specified by the configuration:

    %s

    Could not be found. Please check the configuration and try again.
""", attrconfig.get('path'))
                    raise IOError(
                        'Cannot find the file "%s"' % attrconfig.get('path'))

                lyr = DataSource(attrconfig.get('path'))[0]

                for i, feat in enumerate(lyr):
                    if (float(i) / len(lyr)) > (progress + 0.1):
                        progress += 0.1
                        logger.info('%2.0f%% .. ', progress * 100)

                    gid = get_shape_tree(attrconfig, feat)
                    g = Geounit.objects.filter(tree_code=gid)

                    if g.count() > 0:
                        self.set_geounit_characteristic(
                            g[0], subject_objects, feat)

            logger.info('100%')

    def set_geounit_characteristic(self,
                                   g,
                                   subject_objects,
                                   feat,
                                   updates_possible=True):
        to_be_inserted = []
        for attr, obj in subject_objects.iteritems():
            if attr.endswith('_by_id'):
                continue
            try:
                value = Decimal(str(feat.get(attr))).quantize(
                    Decimal('000000.0000', 'ROUND_DOWN'))
            except:

                # logger.info('No attribute "%s" on feature %d' , attr, feat.fid)
                continue
            percentage = '0000.00000000'
            if obj.percentage_denominator:
                denominator_field = subject_objects[
                    '%s_by_id' % obj.percentage_denominator.name]
                denominator_value = Decimal(str(
                    feat.get(denominator_field))).quantize(Decimal('000000.0000', 'ROUND_DOWN'))
                if denominator_value > 0:
                    percentage = value / denominator_value

            should_create = True
            if updates_possible:
                query = Characteristic.objects.filter(subject=obj, geounit=g)
                if query.count() > 0:
                    should_create = False
                    c = query[0]
                    c.number = value
                    c.percentage = percentage
                    try:
                        c.save()
                    except:
                        c.number = '0.0'
                        c.save()
                        logger.info(
                            'Failed to set value "%s" to %d in feature "%s"',
                            attr, feat.get(attr), g.name)
                        logger.info(traceback.format_exc())
            if should_create:
                to_be_inserted.append(
                    Characteristic(
                        subject=obj,
                        geounit=g,
                        number=value,
                        percentage=percentage))
        if to_be_inserted:
            Characteristic.objects.bulk_create(to_be_inserted)

    def create_filter_functions(self, store):
        """
        Given a Regions node, create a dictionary of functions that can
        be used to filter a feature from a shapefile into the correct
        region.  The dictionary keys are region ids from the config, the
        values are lists of functions which return true when applied to
        a feature that should be in the region
        """

        def get_filter_lambda(region_code):
            attribute = region_code.get('attr')
            pattern = region_code.get('value')
            start = region_code.get('start')
            if start is not None:
                start = int(start)
            end = region_code.get('width')
            if end is not None:
                end = int(end)
            return lambda feature: feature.get(attribute)[start:end] == pattern

        function_dict = {}
        regions = store.filter_regions()
        for region in regions:
            key = region.get('name')
            values = []
            filters = region.xpath('RegionFilter/RegionCode')
            if len(filters) == 0:
                values.append(lambda feature: True)
            else:
                for f in filters:
                    values.append(get_filter_lambda(f))
            function_dict[key] = values
        return function_dict

    def create_template(self, config):
        """
        Create the templates that are defined in the configuration file.
        In addition to creating templates explicitly specified, this
        will also create a blank template for each LegislativeBody.

        Parameters:
            config - The XML configuration.
        """
        admins = User.objects.filter(is_staff=True)
        if admins.count() == 0:
            logger.info("Creating templates requires at least one admin user.")
            return

        admin = admins[0]

        default_language = 'en'
        try:
            default_language = config.xpath('//Internationalization')[0].get(
                'default')
            activate(default_language)
        except:
            pass

        templates = config.xpath('/DistrictBuilder/Templates/Template')
        for template in templates:
            lbconfig = config.xpath(
                '//LegislativeBody[@id="%s"]' %
                template.xpath('LegislativeBody')[0].get('ref'))[0]
            query = LegislativeBody.objects.filter(
                name=lbconfig.get('id')[:256])
            if query.count() == 0:
                logger.info("LegislativeBody '%s' does not exist, skipping.",
                            lbconfig.get('ref'))
                continue
            else:
                legislative_body = query[0]

            plan_name = template.get('name')[:200]
            query = Plan.objects.filter(
                name=plan_name,
                legislative_body=legislative_body,
                owner=admin,
                is_template=True)
            if query.count() > 0:
                logger.info("Plan '%s' exists, skipping.", plan_name)
                continue

            fconfig = template.xpath('Blockfile')[0]
            path = fconfig.get('path')

            DistrictIndexFile.index2plan(
                plan_name,
                legislative_body.id,
                path,
                owner_id=admin.pk,
                template=True,
                purge=False,
                email=None,
                language=default_language)

            logger.info('Created template plan "%s"', plan_name)

        lbodies = config.xpath('//LegislativeBody[@id]')
        for lbody in lbodies:
            owner = User.objects.filter(is_staff=True)[0]
            legislative_body = LegislativeBody.objects.get(
                name=lbody.get('id')[:256])
            plan, created = Plan.objects.get_or_create(
                name=_('Blank'),
                legislative_body=legislative_body,
                owner=owner,
                is_template=True,
                processing_state=ProcessingState.READY)
            if created:
                logger.info(
                    'Created Plan named "Blank" for LegislativeBody "%s"',
                    legislative_body.name)
            else:
                logger.info(
                    'Plan named "Blank" for LegislativeBody "%s" already exists',
                    legislative_body.name)

    def import_adjacency(self, config):
        """
        Imports adjacency files into database using settings from the xml config.

        Writes a temporary template with SQL commands for the import
        """
        logger.info("Loading adjacency data")
        adjacencies = config.xpath('//DistrictBuilder/Adjacencies/*')

        # Instantiate redis connection with settings from XML config
        cache = caches['default']

        # Read and load data into redis #
        data_dict = {}
        file_numbers = len(adjacencies)
        for counter, adjacency in enumerate(adjacencies):
            path = adjacency.get('path')
            logger.info('Processing file %s of %s (%s)' % (counter + 1,
                                                           file_numbers, path))
            region = adjacency.get(
                'regionref')  # Grab region id to cache avg. cost for region
            f = open(path, 'r')
            csv_reader = csv.reader(f, delimiter='\t')
            c = 0  # Row counter to keep track of when to load data
            region_sum = 0
            for row in csv_reader:
                c += 1
                region_sum += float(row[2])
                if c % 10000 == 0:
                    # Upload 10,000 at a time, otherwise redis complains
                    cache.set_many(data_dict)
                    data_dict = {}
                key = key_gen(**{'geounit1': row[0], 'geounit2': row[1]})
                data_dict[key] = row[2]

            # Need to send left over data < 10000 to redis
            cache.set_many(data_dict)

            # Cache region totals in redis
            region_cost = region_sum / float(c)
            key = key_gen(**{'region': region})
            cache.set(key, region_cost)

        logger.info(
            'Finished processing files and loading data into key value store')

    def create_report_templates(self, config):
        """
        This object takes the full configuration element and the path
        to an XSLT and does the transforms necessary to create templates
        for use in BARD reporting
        """
        xslt_path = settings.BARD_TRANSFORM
        template_dir = '%s/django/publicmapping/redistricting/templates' % config.xpath(
            '//Project')[0].get('root')

        # Open up the XSLT file and create a transform
        f = file(xslt_path)

        xml = parse(f)
        transform = XSLT(xml)

        # For each legislative body, create the reporting step HTML
        # template. If there is no config for a body, the XSLT transform
        # should create a "Sorry, no reports" template
        bodies = config.xpath(
            '//DistrictBuilder/LegislativeBodies/LegislativeBody')
        for body in bodies:
            # Name  the template after the body's name
            body_id = body.get('id')
            body_name = body.get('name')[:256]

            logger.info("Creating BARD reporting template for %s", body_name)

            body_name = body_name.lower()
            template_path = '%s/bard_%s.html' % (template_dir, body_name)

            # Pass the body's identifier in as a parameter
            xslt_param = XSLT.strparam(body_id)
            result = transform(config, legislativebody=xslt_param)

            f = open(template_path, 'w')
            f.write(str(result))
            f.close()

    def build_bardmap(self, config):
        """
        Build the BARD reporting base maps.

        Parameters:
            config - The XML configuration.
        """

        # The first geolevel is the base geolevel of EVERYTHING
        lbody = LegislativeBody.objects.all()[0]
        basegl = Geolevel.objects.get(id=lbody.get_base_geolevel())
        gconfig = config.xpath(
            '//GeoLevels/GeoLevel[@name="%s"]' % basegl.name)[0]
        shapefile = gconfig.xpath('Shapefile')[0].get('path')
        srs = DataSource(shapefile)[0].srs
        bconfig = config.find('//Reporting/BardConfigs/BardConfig')
        if srs.name == 'WGS_1984_Web_Mercator_Auxiliary_Sphere':
            # because proj4 doesn't have definitions for this ESRI def,
            # but it does understand 3785
            srs = SpatialReference(3785)

        try:
            # We don't need to install rpy unless we're doing this
            from rpy2.robjects import r
            r.library('rgeos')
            logger.debug("Loaded rgeos library.")
            r.library('BARD')
            logger.debug("Loaded BARD library.")
            sdf = r.readShapePoly(shapefile, proj4string=r.CRS(srs.proj))
            logger.debug("Read shapefile '%s'.", shapefile)

            # The following lines perform the bard basemap computation
            # much faster, but require vast amounts of memory. Disabled
            # by default.
            #fib = r.poly_findInBoxGEOS(sdf)
            #logger.debug("Created neighborhood index file.")
            #nb = r.poly2nb(sdf,foundInBox=fib)

            # nb = r.poly2nb(sdf)
            # logger.debug("Computed neighborhoods.")
            # bardmap = r.spatialDataFrame2bardBasemap(sdf)
            bardmap = r.spatialDataFrame2bardBasemap(sdf, keepgeom=r(False))

            logger.debug("Created bardmap.")
            r.writeBardMap(bconfig.get('shape'), bardmap)
            logger.debug("Wrote bardmap to disk.")
        except:
            logger.info("""
ERROR:

The BARD map could not be computed. Please check the configuration settings
and try again.
""")
            logger.debug(
                "The following traceback may provide more information:")
            logger.debug(traceback.format_exc())
            return False
        return True
