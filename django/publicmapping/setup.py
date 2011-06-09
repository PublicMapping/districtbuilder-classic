#!/usr/bin/python
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
from optparse import OptionParser, OptionGroup
from os.path import exists
from lxml.etree import parse, XMLSchema
from xml.dom import minidom
import traceback, os, sys, random

def main():
    """
    Main method to start the setup of District Builder.
    """
    usage = "usage: %prog [options] SCHEMA CONFIG"
    parser = OptionParser(usage=usage)
    parser.add_option('-d', '--database', dest="database",
            help="Generate the database schema", default=False,
            action='store_true')
    parser.add_option('-g', '--geolevel', dest="geolevels",
            help="Import the geography from the Nth GeoLevel.", 
            action="append", type="int")
    parser.add_option('-V', '--views', dest="views",
            help="Create database views based on all geographies.",
            action='store_true', default=False)
    parser.add_option('-G', '--geoserver', dest="geoserver",
            help="Create spatial data layers in Geoserver.",
            default=False, action='store_true')
    parser.add_option('-t', '--templates', dest="templates",
            help="Create the system-wide templates.",
            default=False, action='store_true')
    parser.add_option('-n', '--nesting', dest="nesting",
            help="Enforce nested geometries.",
            action='append', type="int")
    parser.add_option('-s', '--static', dest="static",
            help="Collect the static javascript and css files.",
            action='store_true', default=False),
    parser.add_option('-b', '--bard', dest="bard",
            help="Create a BARD map based on the imported spatial data.", 
            default=False, action='store_true'),
    parser.add_option('-B', '--bardtemplates', dest="bard_templates",
            help="Create the BARD reporting templates.",
            action='store_true', default=False),
    parser.add_option('-v', '--verbosity', dest="verbosity",
            help="Verbosity level; 0=minimal output, 1=normal output, 2=all output",
            default=1, type="int")


    (options, args) = parser.parse_args()

    allops = (not options.database) and (not options.geolevels) and (not options.views) and (not options.geoserver) and (not options.templates) and (not options.nesting) and (not options.bard) and (not options.static) and (not options.bard_templates)

    verbose = options.verbosity

    if len(args) != 2:
        if verbose > 0:
            print """
ERROR:

    This script requires a configuration file and a schema. Please check
    the command line arguments and try again.
"""
        return

    config = validate_config(args[0], args[1], verbose)

    if not config:
       return

    if verbose > 0:
        print "Validated config."

    if merge_config(config, verbose):
        if verbose > 0:
            print "Generated django settings."
    else:
        return

    os.environ['DJANGO_SETTINGS_MODULE'] = 'publicmapping.settings'
    
    sys.path += ['.', '..']

    from django.core import management

    if allops or options.database:
        management.call_command('syncdb', verbosity=verbose, interactive=False)

    if allops:
        geolevels = []
        views = True
        geoserver = True
        templates = True
        nesting = []
        static = True
        bard = True
        bard_templates = True
    else:
        geolevels = options.geolevels
        views = options.views
        geoserver = options.geoserver
        templates = options.templates
        nesting = options.nesting
        static = options.static
        bard = options.bard
        bard_templates = options.bard_templates

    management.call_command('setup', config=args[1], verbosity=verbose, geolevels=geolevels, views=views, geoserver=geoserver, templates=templates, nesting=nesting, static=static, bard=bard, bard_templates=bard_templates)

    return


def validate_config(sch, cfg, verbose):
    """
    Open the configuration file and validate it.
    """
    if not exists(sch):
        if verbose > 0:
            print """
ERROR:

The validation schema file specified does not exist. Please check the
path and try again.
"""
        return False

    if not exists(cfg):
        if verbose > 0:
            print """
ERROR:

The configuration file specified does not exist. Please check the path
and try again.
"""
        return False

    try:
        schdoc = parse(sch)
    except Exception, ex:
        if verbose > 0:
            print """
ERROR:

The validation schema file specified could not be parsed. Please check
the contents of the file and try again.
"""
        if verbose > 1:
            print "The following traceback may provide more information:"
            print traceback.format_exc()

        return False

    # Create a schema object
    schema = XMLSchema(schdoc)

    try:
        elem_tree = parse(cfg)
    except Exception, ex:
        if verbose > 0:
            print """
ERROR:

The configuration file specified could not be parsed. Please check the
contents of the file and try again.
"""
        if verbose > 1:
            print "The following traceback may provide more information:"
            print traceback.format_exc()

        return False

    if not schema.validate(elem_tree):
        if verbose > 0:
            print """
            
ERROR:

The configuration file specified was parsed successfully, but there are
validation errors.
"""
            if verbose > 2:
                print 'Error Log:'
                for error in schema.error_log:
                    print """
 Domain: %s
 Type: %s
 Message: %s
""" % (error.domain_name,error.type_name,error.message)
            else:
                print 'Last Error:'
                print schema.error_log.last_error

        return False

    if verbose > 0:
        print "Configuration is parsed and validated."

    # Document may be valid, but IDs may not match REFs.
    # Check them here
    ref_tags = elem_tree.xpath('//LegislativeBody[@ref]')
    id_tags = elem_tree.xpath('//LegislativeBody[@id]')

    for ref_tag in ref_tags:
        found = False
        for id_tag in id_tags:
            found = found or (ref_tag.get('ref') == id_tag.get('id'))

        if not found:
            if verbose > 1:
                print """
ERROR:

The configuration file has mismatched ID and REF attributes. Please edit
the configuration file and make sure all <LegislativeBody> tags 
reference a <LegislativeBody> tag defined in the <LegislativeBodies>
section.
"""
            return False

    ref_tags = elem_tree.xpath('//Subject[@ref]')
    id_tags = elem_tree.xpath('//Subject[@id]')

    for ref_tag in ref_tags:
        found = False
        for id_tag in id_tags:
            found = found or (ref_tag.get('ref') == id_tag.get('id'))

        if not found:
            if verbose > 1:
                print """
ERROR:

The configuration file has mismatched ID and REF attributes. Please edit
the configuration file and make sure all <Subject> tags reference a
<Subject> tag defined in the <Subjects> section.
"""
            return False

    if verbose > 0:
        print "Document validated."

    return elem_tree


def merge_config(config, verbose):
    """
    Set up the database connection, based on the values in the provided
    configuration file.
    """

    try:
        settings_in = open('settings.py.in','r')
        settings_out = open('settings.py','w')

        # Copy input settings for district builder
        for line in settings_in.readlines():
            settings_out.write(line)

        settings_in.close()

        rsettings_in = open('reporting_settings.py.in', 'r')
        rsettings_out = open('reporting_settings.py', 'w')

        # Copy input settings for reporting
        for line in rsettings_in.readlines():
            rsettings_out.write(line)

        rsettings_in.close()

        cfg = config.xpath('//Project/Database')[0]
        settings_out.write('\n#\n# Automatically generated settings.\n#\n')
        settings_out.write("DATABASE_ENGINE = 'postgresql_psycopg2'\n")
        settings_out.write("DATABASE_NAME = '%s'\n" % cfg.get('name'))
        settings_out.write("DATABASE_USER = '%s'\n" % cfg.get('user'))
        settings_out.write("DATABASE_PASSWORD = '%s'\n" % cfg.get('password'))
        settings_out.write("DATABASE_HOST = '%s'\n" % cfg.get('host',''))

        cfg = config.xpath('//MapServer')[0]
        settings_out.write("\nMAP_SERVER = '%s'\n" % cfg.get('hostname'))
        protocol = cfg.get('protocol')
        if protocol:
            settings_out.write("MAP_SERVER_PROTOCOL = '%s'\n" % protocol)
        settings_out.write("BASE_MAPS = '%s'\n" % cfg.get('basemaps'))
        settings_out.write("MAP_SERVER_NS = '%s'\n" % cfg.get('ns'))
        settings_out.write("MAP_SERVER_NSHREF = '%s'\n" % cfg.get('nshref'))
        settings_out.write("FEATURE_LIMIT = %d\n" % int(cfg.get('maxfeatures')))
        
        cfg = config.xpath('//Admin')[0]
        settings_out.write("\nADMINS = (\n  ('%s',\n  '%s'),\n)" % (cfg.get('user'), cfg.get('email')))
        settings_out.write("\nMANAGERS = ADMINS\n")

        rsettings_out.write("\nADMINS = (\n  ('%s',\n  '%s'),\n)" % (cfg.get('user'), cfg.get('email')))
        rsettings_out.write("\nMANAGERS = ADMINS\n")

        cfg = config.xpath('//Mailer')[0]
        settings_out.write("\nEMAIL_HOST = '%s'\n" % cfg.get('server'))
        settings_out.write("EMAIL_PORT = %d\n" % int(cfg.get('port')))
        settings_out.write("EMAIL_HOST_USER = '%s'\n" % cfg.get('username'))
        settings_out.write("EMAIL_HOST_PASSWORD = '%s'\n" % cfg.get('password'))
        settings_out.write("EMAIL_SUBJECT_PREFIX = '%s '\n" % cfg.get('prefix'))

        settings_out.write("\nSECRET_KEY = '%s'\n" % "".join([random.choice("abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)") for i in range(50)]))

        cfg = config.xpath('//Project')[0]
        root_dir = cfg.get('root')
        settings_out.write("\nMEDIA_ROOT = '%s/django/publicmapping/site-media/'\n" % root_dir)
        settings_out.write("\nSTATIC_ROOT = '%s/django/publicmapping/static-media/'\n" % root_dir)

        settings_out.write("\nTEMPLATE_DIRS = (\n  '%s/django/publicmapping/templates',\n)\n" % root_dir)
        settings_out.write("\nSLD_ROOT = '%s/sld/'\n" % root_dir)

        quota = cfg.get('sessionquota')
        if not quota:
            quota = 5
        settings_out.write("\nCONCURRENT_SESSIONS = %d\n" % int(quota))

        timeout = cfg.get('sessiontimeout')
        if not timeout:
            timeout = 15
        settings_out.write("\nSESSION_TIMEOUT = %d\n" % int(timeout))

        istoposimplified = cfg.get('istoposimplified')
        if not istoposimplified:
            istoposimplified = False
        else:
            istoposimplified = True if istoposimplified == 'true' else False
        settings_out.write("\nIS_TOPO_SIMPLIFIED = %s\n" % istoposimplified)

        # If banner image setting does not exist, defaults to:
        # '/static-media/images/banner-home.png'
        banner = cfg.get('bannerimage')
        if banner:
            settings_out.write("\nBANNER_IMAGE = '%s'\n" % banner)

        cfg = config.xpath('//Reporting')[0]
        cfg = cfg.find('BardConfigs/BardConfig')
        if cfg != None:
            # Write these settings to the report settings.
            rsettings_out.write("\nREPORTS_ENABLED = True\n")
            rsettings_out.write("BARD_BASESHAPE = '%s'\n" % cfg.get('shape'))
            rsettings_out.write("BARD_TEMP = '%s'\n" % cfg.get('temp'))

            # Write these settings to the district builder settings.
            settings_out.write("\nREPORTS_ENABLED = True\n")
            settings_out.write("BARD_TRANSFORM = '%s'\n" % cfg.get('transform'))
            settings_out.write("BARD_TEMP = '%s'\n" % cfg.get('temp'))
            server = cfg.get('server')
            if server:
                settings_out.write("BARD_SERVER = '%s'\n" % server)
            else:
                settings_out.write("BARD_SERVER = 'https://localhost/reporting'\n")

        else:
            # Write this setting to the report settings.
            rsettings_out.write("\nREPORTS_ENABLED = False\n")

            # Write this setting to the district builder settings.
            settings_out.write("\nREPORTS_ENABLED = False\n")

        
        cfg = config.xpath('//GoogleAnalytics')
        if len(cfg) > 0:
            cfg = cfg[0]
            settings_out.write("\nGA_ACCOUNT = '%s'\n" % cfg.get('account'))
            settings_out.write("GA_DOMAIN = '%s'\n" % cfg.get('domain'))
        else:
            settings_out.write("\nGA_ACCOUNT = None\nGA_DOMAIN = None\n")

        cfg = config.xpath('//Upload')
        if len(cfg) > 0:
            cfg = cfg[0]
            settings_out.write("\nMAX_UPLOAD_SIZE = %s * 1024\n" % cfg.get('maxsize'))
        else:
            settings_out.write("\nMAX_UPLOAD_SIZE = 5000 * 1024\n")

        # Fix unassigned parameters
        minpercent = 99
        comparatorsubject = 'poptot'
        cfg = config.xpath('//FixUnassigned')
        if len(cfg) > 0:
            cfg = cfg[0]
            minpercent = cfg.get('minpercent') or minpercent
            comparatorsubject = cfg.get('comparatorsubject') or comparatorsubject
        settings_out.write("\nFIX_UNASSIGNED_MIN_PERCENT = %d\n" % int(minpercent))
        settings_out.write("\nFIX_UNASSIGNED_COMPARATOR_SUBJECT = '%s'\n" % comparatorsubject)

        cfg = config.xpath('//FixUnassigned')
        if len(cfg) > 0:
            cfg = cfg[0]
            minpercent = cfg.get('minpercent') or minpercent
        settings_out.write("\nFIX_UNASSIGNED_MIN_PERCENT = %d\n" % int(minpercent))

        # Undo restrictions
        maxundosduringedit = 0
        maxundosafteredit = 0
        cfg = config.xpath('//MaxUndos')
        if len(cfg) > 0:
            cfg = cfg[0]
            maxundosduringedit = cfg.get('duringedit') or 0
            maxundosafteredit = cfg.get('afteredit') or 0
        settings_out.write("\nMAX_UNDOS_DURING_EDIT = %d\n" % int(maxundosduringedit))
        settings_out.write("\nMAX_UNDOS_AFTER_EDIT = %d\n" % int(maxundosafteredit))

        # Leaderboard
        maxranked = 10
        cfg = config.xpath('//Leaderboard')
        if len(cfg) > 0:
            cfg = cfg[0]
            maxranked = cfg.get('maxranked') or 10
        settings_out.write("\nLEADERBOARD_MAX_RANKED = %d\n" % int(maxranked))
        
        settings_out.close()
        rsettings_out.close()

        os.rename('reporting_settings.py', '../reporting/settings.py')
    except Exception, ex:
        if verbose > 0:
            print """
ERROR:

    The database settings could not be written. Please check the 
    permissions of the django directory and settings.py and try again.
"""
        if verbose > 1:
            print traceback.format_exc()
        return False

    return True


if __name__ == "__main__":
    main()
