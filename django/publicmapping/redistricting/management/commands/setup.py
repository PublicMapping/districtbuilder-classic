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
from optparse import make_option
from os.path import exists
from lxml.etree import parse, XMLSchema
from xml.dom import minidom
from redistricting.models import *
import traceback

class Command(BaseCommand):
    """
    Set up District Builder.
    """
    args = '<config>'
    help = 'Sets up District Builder based on the main XML configuration.'
    option_list = BaseCommand.option_list + (
        make_option('-c', '--config', dest="config",
            help="Use configuration file CONFIG", metavar="CONFIG"),
        make_option('-s', '--schema', dest="schema",
            help="Use validation SCHEMA", metavar="SCHEMA"),
        make_option('-d', '--debug', dest="debug",
            help="Generate verbose debug output", default=False, 
            action='store_true'),
    )

    config = None

    def validate_config(self, sch, cfg, verbose=False):
        """
        Open the configuration file and validate it.
        """
        if not exists(sch):
            print """
ERROR:

    The validation schema file specified does not exist. Please check the
    path and try again.
"""
            return false

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
        if options.get('schema') is None:
            print """
ERROR:

    This management command requires the -s or --schema option. This option
    specifies the configuration schema that is used for validation.
"""
            return

        verbose = options.get('debug')

        if not self.validate_config(options.get('schema'), options.get('config'), verbose):
            return

