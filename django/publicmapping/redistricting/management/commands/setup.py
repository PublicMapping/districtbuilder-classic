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
from django.contrib.gis.gdal import *
from django.contrib.gis.geos import *
from django.contrib.gis.db.models import Sum, Union
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import simplejson as json
from django.utils import translation
from optparse import make_option
from os.path import exists
from lxml.etree import parse, XSLT
from xml.dom import minidom
import redistricting
from redistricting.models import *
from redistricting.tasks import *
from redistricting.config import *
import traceback, logging, time, subprocess, multiprocessing

logger = logging.getLogger()

class Command(BaseCommand):
    """
    Set up DistrictBuilder.
    """
    args = '<config>'
    help = 'Sets up DistrictBuilder based on the main XML configuration.'
    option_list = BaseCommand.option_list + (
        make_option('-c', '--config', dest="config",
            help="Use configuration file CONFIG", metavar="CONFIG"),
        make_option('-d', '--database', dest="database",
            help="Generate the base data objects.", default=False,
            action='store_true'),
        make_option('-f', '--force', dest="force",
            help="Force changes if config differs from database", default=False,
            action='store_true'),
        make_option('-g', '--geolevel', dest="geolevels",
            action="append", help="Geolevels to import",
            type='int'),
        make_option('-n', '--nesting', dest="nesting",
            action='append', help="Enforce nested geometries.",
            type='int'),
        make_option('-V', '--views', dest="views", default=False,
            action="store_true", help="Create database views."),
        make_option('-G', '--geoserver', dest="geoserver",
            action="store_true", help="Create spatial layers in Geoserver.",
            default=False),
        make_option('-t', '--templates', dest="templates",
            action="store_true", help="Create system templates based on district index files.", default=False),
        make_option('-b', '--bard', dest="bard",
            action='store_true', help="Create a BARD map based on the imported spatial data.", default=False),
        make_option('-s', '--static', dest="static",
            action='store_true', help="Collect and compress the static javascript and css files.", default=False),
        make_option('-l', '--languages', dest="languages",
            action='store_true', help="Create and compile a message file for each language defined.", default=False),
        make_option('-B', '--bardtemplates', dest="bard_templates",
            action='store_true', help="Create the BARD reporting templates.", default=False),
    )


    force = False

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

        translation.activate('en')

        if options.get('config') is None:
            logger.warning("""
ERROR:

    This management command requires the -c or --config option. This option
    specifies the main configuration file.
""")
            sys.exit(1)


        try:
            store = redistricting.StoredConfig( options.get('config') )
        except Exception, ex:
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

        force = options.get('force')

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

                for i,geolevel in enumerate(geolevels):
                    if not optlevels is None:
                        importme = len(optlevels) == 0
                        importme = importme or (i in optlevels)
                        if importme:
                            self.import_geolevel(options.get('config'), geolevel, i)

                    if not nestlevels is None:
                        nestme = len(nestlevels) == 0
                        nestme = nestme or (i in nestlevels)
                        if nestme:
                            geoutil.renest_geolevel(geolevel)
        except:
            all_ok = False
            logger.info('ERROR importing geolevels.')
            logger.debug(traceback.format_exc())
         

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
                    logger.info("Geoserver configuration could not be cleaned.")
            except:
                logger.info('ERROR configuring geoserver.')
                logger.info(traceback.format_exc())
                all_ok = False

        if options.get("templates"):
            try:
                self.create_template(store.data)
            except:
                logger.info('ERROR creating templates.')
                logger.debug(traceback.format_exc())
                all_ok = False
       
        if options.get("static"):
            call_command('collectstatic', interactive=False, verbosity=options.get('verbosity'))
            call_command('compress', interactive=False, verbosity=options.get('verbosity'), force=True)

        if options.get("languages"):
            call_command('makelanguagefiles', interactive=False, verbosity=options.get('verbosity'))

        if options.get("bard_templates"):
            try:
                self.create_report_templates(store.data)
            except:
                logger.info('ERROR creating BARD template files.')
                logger.debug(traceback.format_exc())
                all_ok = False
    
        if options.get("bard"):
            all_ok = all_ok * self.build_bardmap(store.data)

        # For our return value, a 0 (False) means OK, any nonzero (i.e., True or 1)
        # means that  an error occurred - the opposite of the meaning of all_ok's bool
        sys.exit(not all_ok)

    
    def import_geolevel(self, configfile, geolevel, glidx):
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
            log.info("""
ERROR:

    The geographic level setup routine needs either a Shapefile or a
    set of Files/Geography elements in the configuration in order to
    import geographic levels.""")
            return

        gconfig = {
            'shapefiles': shapeconfig,
            'attributes': attrconfig
        }

        self.import_shape(configfile, gconfig, glidx)


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

    def import_shape(self, configfile, config, glidx):
        """
        Import a shapefile, based on a config.

        Parameters:
            config -- A dictionary with 'shapepath', 'geolevel', 'name_field', 'region_filters' and 'subject_fields' keys.
        """
        
        # Make sure celery is running
        try:
            pidfile = open('/var/run/celery/celeryd.pid', 'r')
            pid = int(pidfile.read())
            pidfile.close()
        
            p1 = subprocess.Popen(['ps', '-eaf'], stdout=subprocess.PIPE)
            p2 = subprocess.Popen(['awk', '$2 ~ /%d/' % pid], stdin=p1.stdout, stdout=subprocess.PIPE)
            out = p2.communicate()[0]
        
            if len(out.split('\n')) != 2:
                logger.error('Could not find a running celery process. Please start the celery service.');
        except:
            logger.error('Could not find a running celery process. Please start the celery service.')
            return

        for sidx,shapefile in enumerate(config['shapefiles']):
            if not exists(shapefile.get('path')):
                logger.info("""
ERROR:

    The filename specified by the configuration:

    %s

    Could not be found. Please check the configuration and try again.
""", shapefile.get('path'))
                raise IOError('Cannot find the file "%s"' % shapefile.get('path'))

            ds = DataSource(shapefile.get('path'))
            logger.debug('Importing from %s, %d of %d shapefiles...', ds, sidx+1, len(config['shapefiles']))
            lyr = ds[0]
            logger.debug('%d objects in shapefile', len(lyr))
            logger.info('0% .. ')
            
            lyr = None
            ds = None
            
            queue = ShapeQueue(shapefile.get('path'),
                    nworkers=multiprocessing.cpu_count() * 2,
                    configfile=configfile,
                    geolevel_idx=glidx,
                    shape_idx=sidx,
                    attr_idx=None)
                    
            grpResult = queue.load()
            
            while not grpResult.ready():
                time.sleep(10)

            if grpResult.failed():
                logger.warn('Some tasks failed!')
                for item in grpResult.results:
                    if item.failed():
                        logger.debug(item.traceback)

            logger.info('100%')

        if config['attributes']:
            progress = 0
            logger.info("Assigning subject values to imported geography...")
            logger.info('0% .. ')
            for attridx,attrconfig in enumerate(config['attributes']):
                if not exists(attrconfig.get('path')):
                    logger.info("""
ERROR:

    The filename specified by the configuration:

    %s

    Could not be found. Please check the configuration and try again.
""", attrconfig.get('path'))
                    raise IOError('Cannot find the file "%s"' % attrconfig.get('path'))

                queue = ShapeQueue(attrconfig.get('path'),
                        nworkers=multiprocessing.cpu_count() * 2,
                        configfile=configfile,
                        geolevel_idx=glidx,
                        shape_idx=None,
                        attr_idx=attr_idx)
                        
                results = queue.load()
            
                while not results.ready():
                    time.sleep(10)

                logger.info('100%')


    def create_template(self, config):
        """
        Create the templates that are defined in the configuration file.
        In addition to creating templates explicitly specified, this
        will also create a blank template for each LegislativeBody.

        Parameters:
            config - The XML configuration.
        """
        admin = User.objects.filter(is_staff=True)
        if admin.count() == 0:
            logger.info("Creating templates requires at least one admin user.")
            return

        admin = admin[0]

        templates = config.xpath('/DistrictBuilder/Templates/Template')
        async_ops = []
        for template in templates:
            lbconfig = config.xpath('//LegislativeBody[@id="%s"]' % template.xpath('LegislativeBody')[0].get('ref'))[0]
            query = LegislativeBody.objects.filter(name=lbconfig.get('id')[:256])
            if query.count() == 0:
                logger.info("LegislativeBody '%s' does not exist, skipping.", lbconfig.get('ref'))
                continue
            else:
                legislative_body = query[0]

            plan_name = template.get('name')[:200]
            query = Plan.objects.filter(name=plan_name, legislative_body=legislative_body, owner=admin, is_template=True)
            if query.count() > 0:
                logger.info("Plan '%s' exists, skipping.", plan_name)
                continue

            fconfig = template.xpath('Blockfile')[0]
            path = fconfig.get('path')

            # Import these templates asynchronously
            async_ops.append(DistrictIndexFile.index2plan.delay(plan_name, legislative_body.id, path, owner=admin, template=True, purge=False, email=None))

        # Only notify once per template, but wait for all templates to load before proceeding
        notified = [False] * len(async_ops)
        working = len(async_ops) > 0
        while working:
            time.sleep(5)
            for i,op in enumerate(async_ops):
                if op.ready() and not notified[i]:
                    logger.debug('Created template plan "%s"', op.result)
                    notified[i] = True
            working = len([x for x in notified if x]) != len(async_ops)

        lbodies = config.xpath('//LegislativeBody[@id]')
        for lbody in lbodies:
            owner = User.objects.filter(is_staff=True)[0]
            legislative_body = LegislativeBody.objects.get(name=lbody.get('id')[:256])
            plan,created = Plan.objects.get_or_create(name='Blank',legislative_body=legislative_body,owner=owner,is_template=True, processing_state=ProcessingState.READY)
            if created:
                logger.debug('Created Plan named "Blank" for LegislativeBody "%s"', legislative_body.name)
            else:
                logger.debug('Plan named "Blank" for LegislativeBody "%s" already exists', legislative_body.name)


    def create_report_templates(self, config):
        """
        This object takes the full configuration element and the path
        to an XSLT and does the transforms necessary to create templates
        for use in BARD reporting
        """
        xslt_path = settings.BARD_TRANSFORM
        template_dir = '%s/django/publicmapping/redistricting/templates' % config.xpath('//Project')[0].get('root')

        # Open up the XSLT file and create a transform
        f = file(xslt_path)
        xml = parse(f)
        transform = XSLT(xml)

        # For each legislative body, create the reporting step HTML 
        # template. If there is no config for a body, the XSLT transform 
        # should create a "Sorry, no reports" template
        bodies = config.xpath('//DistrictBuilder/LegislativeBodies/LegislativeBody')
        for body in bodies:
            # Name  the template after the body's name
            body_id = body.get('id')
            body_name = body.get('name')[:256]

            logger.info("Creating BARD reporting template for %s", body_name)

            body_name = body_name.lower()
            template_path = '%s/bard_%s.html' % (template_dir, body_name)

            # Pass the body's identifier in as a parameter
            xslt_param = XSLT.strparam(body_id)
            result = transform(config, legislativebody = xslt_param) 

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
        gconfig = config.xpath('//GeoLevels/GeoLevel[@name="%s"]' % basegl.name)[0]
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
            sdf = r.readShapePoly(shapefile,proj4string=r.CRS(srs.proj))
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
            bardmap = r.spatialDataFrame2bardBasemap(sdf,keepgeom=r(False))


            logger.debug("Created bardmap.")
            r.writeBardMap(bconfig.get('shape'), bardmap)
            logger.debug("Wrote bardmap to disk.")
        except:
            logger.info("""
ERROR:

The BARD map could not be computed. Please check the configuration settings
and try again.
""")
            logger.debug("The following traceback may provide more information:")
            logger.debug(traceback.format_exc())
            return False
        return True

