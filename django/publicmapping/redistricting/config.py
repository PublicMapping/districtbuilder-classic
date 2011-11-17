"""
Configuration module for DistrictBuilder

This file handles many common operations that operate on the application
configuration and setup.

This file is part of The Public Mapping Project
https://github.com/PublicMapping/

License:
    Copyright 2010-2011 Micah Altman, Michael McDonald

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

import os
from lxml.etree import parse, clear_error_log, XMLSchema, XMLSyntaxError, XMLSchemaParseError
import traceback
import random
if 'DJANGO_SETTINGS_MODULE' in os.environ and os.environ['DJANGO_SETTINGS_MODULE'] != '':
    from models import *

class StoredConfig:
    """
    A class that is represented on disk by a configuration file. This class
    provides methods of reading and writing the configuration file.
    """

    def __init__(self, data, schema=None):
        """
        Create a new StoredConfiguration on disk.

        Parameters:
            data -- An XML data document, optionally conforming to the schema.
            schema -- Optional. An XSD schema document, describing the configuration.
        """
        if schema is not None:
            if not os.path.exists(schema):
                raise Exception('schema', 'Configuration schema could not be found. Please check the path and try again.')

            self.schemafile = schema
        else:
            self.schemafile = None

        if not os.path.exists(data):
            raise Exception('data', 'Configuration data could not be found. Please check the path and try again.')
        self.datafile = data

        self.data = None


    def validate(self):
        """
        Validate the provided data file for correctness against the provided
        schema file.

        Returns:
           (valid, messages,) -- A tuple with a flag indicating if the data
           validates against the schema. If the validation fails, then 'messages'
           contains relevant parsing errors or validation failure messages.
        """
         
        # clear any previous xml errors
        clear_error_log()
        if self.schemafile is not None:
            try:
                # Attempt parsing the schema file
                schdoc = parse(self.schemafile)
            except XMLSyntaxError, e:
                # The schema was not parsable XML
                return (False, ['The schema XML file could not be parsed.'] + list(e.error_log),)

            try:
                theschema = XMLSchema(schdoc)
            except XMLSchemaParseError, e:
                # The schema document is XML, but it's not a schema
                return (False, ['The schema XML file was parsed, but it does not appear to be a valid XML Schema document.'] + list(e.error_log),)

        try:
            # Attempt parsing the data file
            thedata = parse(self.datafile)
        except XMLSyntaxError, e:
            # The data was not parsable XML
            return (False, ['The data XML file could not be parsed.'] + list(e.error_log),)

        if self.schemafile is not None:
            if theschema.validate(thedata):
                self.data = thedata
                return (True, [],)

            return (False, ['The data does not conform to the provided schema.'] + list(theschema.error_log),)

        return (True, [],)


    def merge_settings(self, settings):
        """
        Take the default settings from the input file, and write a django settings file.
        The django settings file receives database connection settings, etc from the 
        DistrictBuilder configuration file.

        Parameters:
            settings - The name of the settings file that should be merged. Currently
            supported settings are "settings.py" and "reporting_settings.py"
        Returns:
        """
        settings_in = open(settings+'.in','r')
        settings_out = open(settings,'w')

        # Copy input settings for district builder
        for line in settings_in.readlines():
            settings_out.write(line)

        settings_in.close()

        status = (False, [],)
        if settings == 'settings.py' or settings == 'reporting_settings.py':
            (status, msgs,) = self._merge_common_settings(settings_out)

            if not status:
                return (status, msgs,)

            if settings == 'settings.py':
                return self._merge_publicmapping_settings(settings_out)
            else:
                return self._merge_report_settings(settings_out)
        else:
            return (False, ['The settings file was not recognized.'],)


    def _merge_common_settings(self, output):
        try:
            cfg = self.data.xpath('//Admin')[0]
            output.write("\nADMINS = (\n  ('%s',\n  '%s'),\n)" % (cfg.get('user'), cfg.get('email')))
            output.write("\nMANAGERS = ADMINS\n")

            output.write("\nSECRET_KEY = '%s'\n" % "".join([random.choice("abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)") for i in range(50)]))

            cfg = self.data.xpath('//Project')[0]
            root_dir = cfg.get('root')

            # Consolidated web-readable temp directory
            webtmp = cfg.get('temp')
            if not webtmp:
                webtmp = '%s/../local/reports/' % root_dir

            output.write("\nWEB_TEMP = '%s'\n" % webtmp)

            # Reporting is optional
            cfg = self.data.xpath('//Reporting')
            if cfg is not None:
                bardcfg = cfg[0].find('BardConfigs/BardConfig')
                calccfg = cfg[0].find('CalculatorReports')

                # BARD
                if bardcfg is not None:
                    cfg = bardcfg
                    output.write("\nREPORTS_ENABLED = 'BARD'\n")

                # Calculator reports
                elif calccfg is not None:
                    output.write("\nREPORTS_ENABLED = 'CALC'\n")
                else:
                    output.write("\nREPORTS_ENABLED = None\n")
            else:
                # Write this setting to the settings.
                output.write("\nREPORTS_ENABLED = None\n")

            return (True, [],)

        except Exception, ex:
            # An error occurred during the processing of the settings file
            return (False, [traceback.format_exc()],)


    def _merge_publicmapping_settings(self, output):
        try:
            cfg = self.data.xpath('//Project/Database')[0]
            output.write('\n#\n# Automatically generated settings.\n#\n')
            output.write("DATABASE_ENGINE = 'postgresql_psycopg2'\n")
            output.write("DATABASE_NAME = '%s'\n" % cfg.get('name'))
            output.write("DATABASE_USER = '%s'\n" % cfg.get('user'))
            output.write("DATABASE_PASSWORD = '%s'\n" % cfg.get('password'))
            output.write("DATABASE_HOST = '%s'\n" % cfg.get('host',''))

            cfg = self.data.xpath('//MapServer')[0]
            output.write("\nMAP_SERVER = '%s'\n" % cfg.get('hostname'))
            protocol = cfg.get('protocol')
            if protocol:
                output.write("MAP_SERVER_PROTOCOL = '%s'\n" % protocol)
            output.write("BASE_MAPS = '%s'\n" % cfg.get('basemaps'))
            output.write("MAP_SERVER_NS = '%s'\n" % cfg.get('ns'))
            output.write("MAP_SERVER_NSHREF = '%s'\n" % cfg.get('nshref'))
            output.write("FEATURE_LIMIT = %d\n" % int(cfg.get('maxfeatures')))

            cfg = self.data.xpath('//Mailer')[0]
            output.write("\nEMAIL_HOST = '%s'\n" % cfg.get('server'))
            output.write("EMAIL_PORT = %d\n" % int(cfg.get('port')))
            output.write("EMAIL_HOST_USER = '%s'\n" % cfg.get('username'))
            output.write("EMAIL_HOST_PASSWORD = '%s'\n" % cfg.get('password'))
            output.write("EMAIL_SUBJECT_PREFIX = '%s '\n" % cfg.get('prefix'))
            use_tls = cfg.get('use_tls')
            if use_tls:
                output.write("EMAIL_USE_TLS = %s\n" % ((use_tls == 'true'),))
            submission_email = cfg.get('submission_email')
            if submission_email:
                output.write("EMAIL_SUBMISSION = '%s'\n" % submission_email)

            cfg = self.data.xpath('//Project')[0]
            root_dir = cfg.get('root')

            output.write("\nMEDIA_ROOT = '%s/django/publicmapping/site-media/'\n" % root_dir)
            output.write("\nSTATIC_ROOT = '%s/django/publicmapping/static-media/'\n" % root_dir)

            output.write("\nTEMPLATE_DIRS = (\n  '%s/django/publicmapping/templates',\n)\n" % root_dir)
            output.write("\nSLD_ROOT = '%s/sld/'\n" % root_dir)

            quota = cfg.get('sessionquota')
            if not quota:
                quota = 5
            output.write("\nCONCURRENT_SESSIONS = %d\n" % int(quota))

            timeout = cfg.get('sessiontimeout')
            if not timeout:
                timeout = 15
            output.write("\nSESSION_TIMEOUT = %d\n" % int(timeout))

            # If banner image setting does not exist, defaults to:
            # '/static-media/images/banner-home.png'
            banner = cfg.get('bannerimage')
            if banner:
                output.write("\nBANNER_IMAGE = '%s'\n" % banner)

            # Reporting is optional
            cfg = self.data.xpath('//Reporting')
            if cfg is not None:
                bardcfg = cfg[0].find('BardConfigs/BardConfig')
                calccfg = cfg[0].find('CalculatorReports')
                # BARD
                if bardcfg is not None:
                    cfg = bardcfg

                    output.write("BARD_TRANSFORM = '%s'\n" % cfg.get('transform'))
                    server = cfg.get('server')
                    if server:
                        output.write("BARD_SERVER = '%s'\n" % server)
                    else:
                        output.write("BARD_SERVER = 'http://localhost/reporting'\n")
                    
            cfg = self.data.xpath('//GoogleAnalytics')
            if len(cfg) > 0:
                cfg = cfg[0]
                output.write("\nGA_ACCOUNT = '%s'\n" % cfg.get('account'))
                output.write("GA_DOMAIN = '%s'\n" % cfg.get('domain'))
            else:
                output.write("\nGA_ACCOUNT = None\nGA_DOMAIN = None\n")

            cfg = self.data.xpath('//Upload')
            if len(cfg) > 0:
                cfg = cfg[0]
                output.write("\nMAX_UPLOAD_SIZE = %s * 1024\n" % cfg.get('maxsize'))
            else:
                output.write("\nMAX_UPLOAD_SIZE = 5000 * 1024\n")

            # Fix unassigned parameters
            minpercent = 99
            comparatorsubject = 'poptot'
            cfg = self.data.xpath('//FixUnassigned')
            if len(cfg) > 0:
                cfg = cfg[0]
                minpercent = cfg.get('minpercent') or minpercent
                comparatorsubject = cfg.get('comparatorsubject') or comparatorsubject
            output.write("\nFIX_UNASSIGNED_MIN_PERCENT = %d\n" % int(minpercent))
            output.write("\nFIX_UNASSIGNED_COMPARATOR_SUBJECT = '%s'\n" % comparatorsubject)

            # Undo restrictions
            maxundosduringedit = 0
            maxundosafteredit = 0
            cfg = self.data.xpath('//MaxUndos')
            if len(cfg) > 0:
                cfg = cfg[0]
                maxundosduringedit = cfg.get('duringedit') or 0
                maxundosafteredit = cfg.get('afteredit') or 0
            output.write("\nMAX_UNDOS_DURING_EDIT = %d\n" % int(maxundosduringedit))
            output.write("\nMAX_UNDOS_AFTER_EDIT = %d\n" % int(maxundosafteredit))

            # Leaderboard
            maxranked = 10
            cfg = self.data.xpath('//Leaderboard')
            if len(cfg) > 0:
                cfg = cfg[0]
                maxranked = cfg.get('maxranked') or 10
            output.write("\nLEADERBOARD_MAX_RANKED = %d\n" % int(maxranked))
       
            output.close()

            return (True, [],)

        except Exception, ex:
            # An error occurred during the processing of the settings file
            return (False, [traceback.format_exc()],)

    def _merge_report_settings(self, output):
        try:
            cfg = self.data.xpath('//Reporting')
            if cfg is not None:
                bardcfg = cfg[0].find('BardConfigs/BardConfig')
                calccfg = cfg[0].find('CalculatorReports')
                # BARD
                if bardcfg is not None:
                    cfg = bardcfg

                    output.write("BARD_BASESHAPE = '%s'\n" % cfg.get('shape'))

            output.close()

            os.rename(output.name, '../reporting/settings.py')

            return (True, [],)
        except Exception, ex:
            # An error occurred during the processing of the settings file
            return (False, [traceback.format_exc()],)

