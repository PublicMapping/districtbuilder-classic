"""
Redistricting django app.

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
    Andrew Jennings, David Zwarg 
"""

import os, traceback, random, logging
from lxml.etree import parse, clear_error_log, XMLSchema, XMLSyntaxError, XMLSchemaParseError

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
                logging.warning('Configuration schema could not be found. Please check the path and try again.')
                raise Exception()

            self.schemafile = schema
        else:
            self.schemafile = None

        if not os.path.exists(data):
            logging.warning('Configuration data could not be found. Please check the path and try again.')
            raise Exception()

        self.datafile = data

        self.data = None


    def validate(self):
        """
        Validate the provided data file for correctness against the provided
        schema file.

        Returns:
           A flag indicating if the data validates against the schema. 
        """
         
        # clear any previous xml errors
        clear_error_log()
        if self.schemafile is not None:
            try:
                # Attempt parsing the schema file
                schdoc = parse(self.schemafile)
            except XMLSyntaxError, e:
                # The schema was not parsable XML
                logging.warning('The schema XML file could not be parsed.')
                for item in e.error_log:
                    logging.info(item)

                return False

            try:
                theschema = XMLSchema(schdoc)
            except XMLSchemaParseError, e:
                # The schema document is XML, but it's not a schema
                logging.warning('The schema XML file was parsed, but it does not appear to be a valid XML Schema document.')
                for item in e.error_log:
                    logging.info(item)

                return False

        try:
            # Attempt parsing the data file
            thedata = parse(self.datafile)
        except XMLSyntaxError, e:
            # The data was not parsable XML
            logging.warning('The data XML file could not be parsed.')
            for item in e.error_log:
                logging.info(item)

            return False

        if self.schemafile is not None:
            if theschema.validate(thedata):
                self.data = thedata
                return True

            logging.warning('The data does not conform to the provided schema.')
            for item in theschema.error_log:
                logging.info(item)

            return False

        self.data = thedata

        return True


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

        if settings == 'settings.py' or settings == 'reporting_settings.py':
            if not self._merge_common_settings(settings_out):
                return False

            if settings == 'settings.py':
                return self._merge_publicmapping_settings(settings_out)
            else:
                return self._merge_report_settings(settings_out)
        else:
            logging.warning('The settings file was not recognized.')

            return False


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

            return True

        except Exception, ex:
            # An error occurred during the processing of the settings file
            logging.warning(traceback.format_exc())

            return False


    def _merge_publicmapping_settings(self, output):
        try:
            cfg = self.data.xpath('//Internationalization')[0]
            output.write("TIME_ZONE = '%s'\n" % cfg.get('timezone'))
            output.write("LANGUAGES = (\n")
            for language in cfg.xpath('Language'):
                output.write("    ('%s', '%s'),\n" % (language.get('code'), language.get('label')))
            output.write(")\n")
            output.write("# Modify to change the language of the application\n")
            if not cfg.get('default') is None:
                output.write("LANGUAGE_CODE = '%s'\n\n" % cfg.get('default'))
            else:
                output.write("LANGUAGE_CODE = '%s'\n\n" % cfg[0].get('code'))

            cfg = self.data.xpath('//Project/Database')[0]
            output.write('\n#\n# Automatically generated settings.\n#\n')

            output.write("DATABASES = {\n")
            output.write("    'default': {\n")
            output.write("        'ENGINE': 'django.contrib.gis.db.backends.postgis',\n")
            output.write("        'NAME': '%s',\n" % cfg.get('name'))
            output.write("        'USER': '%s',\n" % cfg.get('user'))
            output.write("        'PASSWORD': '%s',\n" % cfg.get('password'))
            output.write("        'HOST': '%s',\n" % cfg.get('host'))
            output.write("    }\n")
            output.write("}\n")

            cfg = self.data.xpath('//MapServer')[0]
            output.write("\nMAP_SERVER = '%s'\n" % cfg.get('hostname'))
            protocol = cfg.get('protocol')
            if protocol:
                output.write("MAP_SERVER_PROTOCOL = '%s'\n" % protocol)
            output.write("BASE_MAPS = '%s'\n" % cfg.get('basemaps'))
            output.write("MAP_SERVER_NS = '%s'\n" % cfg.get('ns'))
            output.write("MAP_SERVER_NSHREF = '%s'\n" % cfg.get('nshref'))
            output.write("FEATURE_LIMIT = %d\n" % int(cfg.get('maxfeatures')))
            output.write("MAP_SERVER_USER = '%s'\n" % cfg.get('adminuser'))
            output.write("MAP_SERVER_PASS = '%s'\n" % cfg.get('adminpass'))

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

            return True

        except Exception, ex:
            # An error occurred during the processing of the settings file
            logging.warning(traceback.format_exc())

            return False

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
            logging.warning(traceback.format_exc())

            return False


    def get_node(self, node, parent=None):
        """
        Get a node in the XML data.

        Returns:
            A single lxml.etree.Element object, or None if there are multiple or
            zero nodes found.
        """
        if self.data is None:
            return None

        if parent is None:
            nodes = self.data.xpath(node)
        else:
            nodes = parent.xpath(node)
        if len(nodes) != 1:
            return None

        return nodes[0]
       

    def filter_nodes(self, node_filter, parent=None):
        """
        Get a list of nodes from the XML data.

        Returns:
            A list of lxml.etree.Element objects.
        """
        if self.data is None:
            return None

        if parent is None:
            return self.data.xpath(node_filter)
        else:
            return parent.xpath(node_filter)


    def get_admin(self):
        """
        Get the administrative user configuration node.
        """
        return self.get_node('//Project/Admin')

    def get_geolevel(self, idattr):
        """
        Get the geolevel configuration item by ID.
        """
        return self.get_node('/DistrictBuilder/GeoLevels/GeoLevel[@id="%s"]' % idattr)

    def get_regional_geolevel(self, rnode, idattr):
        """
        Get the regional geolevel by reference.
        """
        return self.get_node('GeoLevels//GeoLevel[@ref="%s"]' % idattr, parent=rnode)

    def get_legislative_body(self, idattr):
        """
        Get the legislative body configuration item by ID.
        """
        return self.get_node('//LegislativeBody[@id="%s"]' % idattr)

    def get_subject(self, idattr):
        """
        Get the subject configuration item by ID.
        """
        return self.get_node('//Subject[@id="%s"]' % idattr)

    def get_legislative_body_default_subject(self, lbody_node):
        """
        Get the default subject configuration for a legislative body.
        """
        return self.get_node('//Subjects/Subject[@default="true"]', parent=lbody_node)

    def get_top_regional_geolevel(self, rnode):
        """
        Get the top level geolevel configuration for a region.
        """
        return self.get_node('GeoLevels/GeoLevel', parent=rnode)

    def get_score_panel(self, idattr):
        """
        Get the score panel configuration node.
        """
        return self.get_node('//ScorePanels/ScorePanel[@id="%s"]' % idattr)

    def get_score_function(self, idattr):
        """
        Get the score function configuration node.
        """
        return self.get_node('//ScoreFunctions/ScoreFunction[@id="%s"]' % idattr)

    def get_criterion_score(self, crit_node):
        """
        Get the score for a given criterion from the XML data.
        """
        return self.get_node('Score', parent=crit_node)

    def get_mapserver(self):
        """
        Get the map server configuration node.
        """
        return self.get_node('//MapServer')

    def get_database(self):
        """
        Get the database configuration node.
        """
        return self.get_node('//Database')

    def filter_regions(self):
        """
        Get all the region configurations from the XML data.
        """
        return self.filter_nodes('/DistrictBuilder/Regions/Region')

    def filter_regional_geolevel(self, region_node):
        """
        Get all the geolevel configurations in a region from the XML data.
        """
        return self.filter_nodes('GeoLevels//GeoLevel', parent=region_node)

    def filter_regional_legislative_bodies(self, region_node):
        """
        Get all the legislative bodies in a region from the XML data.
        """
        return self.filter_nodes('LegislativeBodies/LegislativeBody', parent=region_node)

    def filter_legislative_bodies(self):
        """
        Get all the legislative body configurations from the XML data.
        """
        return self.filter_nodes('//LegislativeBody[@id]')

    def filter_subjects(self):
        """
        Get all the subject configurations from the XML data.
        """
        return self.filter_nodes('//Subjects/Subject')

    def filter_geolevels(self):
        """
        Get all the geolevel configurations from the XML data.
        """
        return self.filter_nodes('/DistrictBuilder/GeoLevels/GeoLevel')

    def filter_scoredisplays(self):
        """
        Get all the score display configurations from the XML data.
        """
        return self.filter_nodes('//ScoreDisplays/ScoreDisplay')

    def filter_displayed_score_panels(self, disp_node):
        """
        Get all the score panels configured in a score display.
        """
        return self.filter_nodes('ScorePanel', parent=disp_node)

    def filter_paneled_score_functions(self, pnl_node):
        """
        Get all the score functions configured in a score panel.
        """
        return self.filter_nodes('Score', parent=pnl_node)

    def filter_score_functions(self):
        """
        Get all the score functions from the XML data.
        """
        return self.filter_nodes('//ScoreFunctions/ScoreFunction')

    def filter_criteria(self):
        """
        Get all the validation criteria from the XML data.
        """
        return self.filter_nodes('//Validation/Criteria')

    def filter_criteria_criterion(self, crit_node):
        """
        Get all the criterion for a given criteria from the XML data.
        """
        return self.filter_nodes('Criterion', parent=crit_node)

    def filter_function_legislative_bodies(self, fn_node):
        """
        Get all the legislative bodies for a given score function from the XML data.
        """
        return self.filter_nodes('LegislativeBody', parent=fn_node)

    def filter_function_arguments(self, fn_node):
        """
        Get all the score function arguments from the XML data.
        """
        return self.filter_nodes('Argument', parent=fn_node)

    def filter_function_subject_arguments(self, fn_node):
        """
        Get all the score function subject arguments from the XML data.
        """
        return self.filter_nodes('SubjectArgument', parent=fn_node)

    def filter_function_score_arguments(self, fn_node):
        """
        Get all the score function subject arguments from the XML data.
        """
        return self.filter_nodes('ScoreArgument', parent=fn_node)

    def filter_contiguity_overrides(self):
        """
        Get all the contiguity overrides from the XML data.
        """
        return self.filter_nodes('//ContiguityOverrides/ContiguityOverride')

    def has_scoring(self):
        """
        Does the configuration contain any scoring nodes?
        """
        return not self.get_node('//Scoring') is None

    def has_validation(self):
        """
        Does the configuration contain any validation nodes?
        """
        return not self.get_node('//Validation') is None

    def has_contiguity_overrides(self):
        """
        Does the configuration contain any contiguity override nodes?
        """
        return not self.get_node('//ContiguityOverrides') is None
