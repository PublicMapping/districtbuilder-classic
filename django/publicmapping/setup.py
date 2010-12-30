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
import traceback, pprint, os, sys, random

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
    parser.add_option('-v', '--views', dest="views",
            help="Create database views based on all geographies.",
            action='store_true', default=False)
    parser.add_option('-V', '--verbose', dest="verbose",
            help="Generate verbose debug output", default=False, 
            action='store_true')
    parser.add_option('-G', '--geoserver', dest="geoserver",
            help="Create spatial data layers in Geoserver.",
            default=False, action='store_true')
    parser.add_option('-t', '--templates', dest="templates",
            help="Create the system-wide templates.",
            default=False, action='store_true')

    (options, args) = parser.parse_args()

    allops = (not options.database) and (not options.geolevels) and (not options.views) and (not options.geoserver) and (not options.templates)

    if len(args) != 2:
        print """
ERROR:

    This script requires a configuration file and a schema. Please check
    the command line arguments and try again.
"""
        return

    config = validate_config(args[0], args[1], options.verbose)

    if not config:
       return

    print "Validated config."

    if merge_config(config, options.verbose):
        print "Generated django settings."
    else:
        return

    os.environ['DJANGO_SETTINGS_MODULE'] = 'publicmapping.settings'
    
    sys.path += ['.', '..']

    from django.core import management

    if allops or options.database:
        management.call_command('syncdb')

    if allops:
        geolevels = []
        views = True
        geoserver = True
        templates = True
    else:
        geolevels = options.geolevels
        views = options.views
        geoserver = options.geoserver
        templates = options.templates

    management.call_command('setup', config=args[1], debug=options.verbose, geolevels=geolevels, views=views, geoserver=geoserver, templates=templates)

    return


def validate_config(sch, cfg, verbose=False):
    """
    Open the configuration file and validate it.
    """
    if not exists(sch):
        print """
ERROR:

The validation schema file specified does not exist. Please check the
path and try again.
"""
        return False

    if not exists(cfg):
        print """
ERROR:

The configuration file specified does not exist. Please check the path
and try again.
"""
        return False

    try:
        schdoc = parse(sch)
    except Exception, ex:
        print """
ERROR:

The validation schema file specified could not be parsed. Please check
the contents of the file and try again.
"""
        if verbose:
            print "The following traceback may provide more information:"
            print traceback.format_exc()

        return False

    # Create a schema object
    schema = XMLSchema(schdoc)

    try:
        elem_tree = parse(cfg)
    except Exception, ex:
        print """
ERROR:

The configuration file specified could not be parsed. Please check the
contents of the file and try again.
"""
        if verbose:
            print "The following traceback may provide more information:"
            print traceback.format_exc()

        return False

    if not schema.validate(elem_tree):
        if verbose:
            print "Configuration is parsed, but is not valid."
            print schema.error_log.last_error
        return False

    if verbose:
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
            print """
ERROR:

The configuration file has mismatched ID and REF attributes. Please edit
the configuration file and make sure all <Subject> tags reference a
<Subject> tag defined in the <Subjects> section.
"""
            return False

    if verbose:
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

        for line in settings_in.readlines():
            settings_out.write(line)

        settings_in.close()

        cfg = config.xpath('//Project/Database')[0]
        settings_out.write('\n#\n# Automatically generated settings.\n#\n')
        settings_out.write("DATABASE_ENGINE = 'postgresql_psycopg2'\n")
        settings_out.write("DATABASE_NAME = '%s'\n" % cfg.get('name'))
        settings_out.write("DATABASE_USER = '%s'\n" % cfg.get('user'))
        settings_out.write("DATABASE_PASSWORD = '%s'\n" % cfg.get('password'))

        cfg = config.xpath('//MapServer')[0]
        settings_out.write("\nMAP_SERVER = '%s'\n" % cfg.get('hostname'))
        settings_out.write("MAP_SERVER_NS = '%s'\n" % cfg.get('ns'))
        settings_out.write("MAP_SERVER_NSHREF = '%s'\n" % cfg.get('nshref'))
        settings_out.write("FEATURE_LIMIT = %d\n" % int(cfg.get('maxfeatures')))
        
        cfg = config.xpath('//Admin')[0]
        settings_out.write("\nADMINS = (\n  ('%s',\n  '%s'),\n)" % (cfg.get('user'), cfg.get('email')))
        settings_out.write("\nMANAGERS = ADMINS\n")

        cfg = config.xpath('//Mailer')[0]
        settings_out.write("\nEMAIL_SERVER = '%s'\n" % cfg.get('server'))
        settings_out.write("EMAIL_PORT = %d\n" % int(cfg.get('port')))
        settings_out.write("EMAIL_HOST_USER = '%s'\n" % cfg.get('username'))
        settings_out.write("EMAIL_HOST_PASSWORD = '%s'\n" % cfg.get('password'))
        settings_out.write("EMAIL_SUBJECT_PREFIX = '%s '\n" % cfg.get('prefix'))

        settings_out.write("\nSECRET_KEY = '%s'\n" % "".join([random.choice("abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)") for i in range(50)]))

        cfg = config.xpath('//Project')[0]
        settings_out.write("\nMEDIA_ROOT = '%s/django/publicmapping/site-media/'\n" % cfg.get('root'))

        settings_out.write("\nTEMPLATE_DIRS = (\n  '%s/django/publicmapping/templates',\n)\n" % cfg.get('root'))
        settings_out.write("\nSLD_ROOT = '%s/sld/'\n" % cfg.get('root'))

        cfg = config.xpath('//Reporting')[0]
        settings_out.write("\nREPORTS_ENABLED = %s\n" % (cfg.get('enabled') == 'true'))
        if cfg.get('engine').lower() == 'bard':
            cfg = cfg.xpath('Data')[0]

            settings_out.write("\nBARD_BASESHAPE = '%s'\n" % cfg.get('shape'))
            settings_out.write("BARD_BASEMAP = '%s'\n" % cfg.get('map'))
            settings_out.write("BARD_TEMP = '%s'\n" % cfg.get('temp'))

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

        settings_out.close()
    except Exception, ex:
        print """
ERROR:

    The database settings could not be written. Please check the 
    permissions of the django directory and settings.py and try again.
"""
        if verbose:
            print traceback.format_exc()
        return False

    return True
if __name__ == "__main__":
    main()
