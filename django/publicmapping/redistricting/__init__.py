"""
Redistricting django application and supporting classes.

This file is part of The Public Mapping Project
https://github.com/PublicMapping/

License:
    Copyright 2010-2012 Micah Altman, Michael McDonald

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
from jinja2 import Environment, FileSystemLoader


class StoredConfig:
    """
    A class that is represented on disk by a configuration file. This class
    provides methods of reading the configuration file.

    An example configuration file for DistrictBuilder is in the github repository:
    U{https://github.com/PublicMapping/DistrictBuilder/blob/master/docs/config.dist.xml}
    """

    def __init__(self, data, schema_file=None):
        """
        Create a new StoredConfiguration on disk.

        @param data: An XML data document, optionally conforming to the schema_file.
        @keyword schema_file: Optional. An XSD schema document, describing the configuration.
        """
        if schema_file is not None:
            if not os.path.exists(schema_file):
                logging.warning(
                    'Configuration schema file could not be found. Please check the path and try again.'
                )
                raise Exception()

            self.schema_file = schema_file
        else:
            self.schema_file = None

        if not os.path.exists(data):
            logging.warning(
                'Configuration data could not be found. Please check the path and try again.'
            )
            raise Exception()

        self.datafile = data

        self.data = None

    def validate(self):
        """
        Validate the provided data file for correctness against the provided
        schema file.

        @return: A flag indicating if the data validates against the schema.
        """

        # clear any previous xml errors
        clear_error_log()
        if self.schema_file is not None:
            try:
                # Attempt parsing the schema file
                schdoc = parse(self.schema_file)
            except XMLSyntaxError, e:
                # The schema was not parsable XML
                logging.warning('The schema XML file could not be parsed.')
                for item in e.error_log:
                    logging.info(item)

                return False

            try:
                schema = XMLSchema(schdoc)
            except XMLSchemaParseError, e:
                # The schema document is XML, but it's not a schema
                logging.warning(
                    'The schema XML file was parsed, but it does not appear to be a valid XML Schema document.'
                )
                for item in e.error_log:
                    logging.info(item)

                return False

        try:
            # Attempt parsing the data file
            data = parse(self.datafile)
        except XMLSyntaxError, e:
            # The data was not parsable XML
            logging.warning('The data XML file could not be parsed.')
            for item in e.error_log:
                logging.info(item)

            return False

        if self.schema_file is not None:
            if schema.validate(data):
                self.data = data
                return True

            logging.warning(
                'The data does not conform to the provided schema.')
            for item in schema.error_log:
                logging.info(item)

            return False

        self.data = data

        return True


    def write_settings(self):
        """
        Write new settings file based off of the configuration provided, which
        will then be imported by the main settings file.

        @returns: A flag indicating if the merge was successful.
        """
        j2_env = Environment(loader=FileSystemLoader('publicmapping'),
                             trim_blocks=True)

        with open('publicmapping/config_settings.py', 'w') as config_settings:
            try:
                # TODO: Move settings templates into config/templates
                config_settings.write(
                    j2_env.get_template('config_settings.py.j2').render(
                        i18n=self.data.xpath('//Internationalization')[0],
                        map_server=self.data.xpath('//MapServer')[0],
                        adjacencies=self.data.xpath('//Adjacencies/*'),
                        convex=self.data.xpath(
                            '//Scoring/ScoreFunctions/ScoreFunction[@id="district_convex"]'
                        ),
                        mailer=self.data.xpath('//Mailer')[0],
                        project=self.data.xpath('//Project')[0],
                        google_analytics=self.data.xpath('//GoogleAnalytics'),
                        upload=self.data.xpath('//Upload'),
                        fix_unassigned=self.data.xpath('//FixUnassigned'),
                        max_undos=self.data.xpath('//MaxUndos'),
                        leaderboard=self.data.xpath('//Leaderboard'),
                    )
                )

                return True

            except Exception as ex:
                # An error occurred during the processing of the settings file
                logging.warning(traceback.format_exc())

                return False


    def get_node(self, node, parent=None):
        """
        Get a node in the XML data.

        @param node: The XPath to a node.
        @keyword parent: If provided, the XPath may be relative to this node.
        @returns: A single lxml.etree.Element object, or None if there are multiple or
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

        @param node_filter: The XPath to a list of nodes.
        @keyword parent: If provided, the XPath may be relative to this node.
        @returns: A list of lxml.etree.Element objects.
        """
        if self.data is None:
            return None

        if parent is None:
            return self.data.xpath(node_filter)
        else:
            return parent.xpath(node_filter)

    def get_geolevel(self, idattr):
        """
        Get the geolevel configuration item by ID.

        GeoLevel configuration reference: U{https://github.com/PublicMapping/DistrictBuilder/wiki/Configuration#wiki-geolevel}

        @param idattr: The ID of the GeoLevel node.
        @returns: The GeoLevel configuration node.
        """
        return self.get_node(
            '/DistrictBuilder/GeoLevels/GeoLevel[@id="%s"]' % idattr)

    def get_regional_geolevel(self, rnode, idattr):
        """
        Get the regional geolevel by reference.

        Region configuration reference: U{https://github.com/PublicMapping/DistrictBuilder/wiki/Configuration#wiki-region}

        @param rnode: The Region node.
        @param idattr: The ref ID of the GeoLevel node.
        @returns: The GeoLevel configuration node.
        """
        return self.get_node(
            'GeoLevels//GeoLevel[@ref="%s"]' % idattr, parent=rnode)

    def get_legislative_body(self, idattr):
        """
        Get the legislative body configuration item by ID.

        LegislativeBody configuration reference: U{https://github.com/PublicMapping/DistrictBuilder/wiki/Configuration#wiki-legislativebody}

        @param idattr: The ID of the LegislativeBody node.
        @returns: The LegislativeBody node.
        """
        return self.get_node('//LegislativeBody[@id="%s"]' % idattr)

    def get_subject(self, idattr):
        """
        Get the subject configuration item by ID.

        Subject configuration reference: U{https://github.com/PublicMapping/DistrictBuilder/wiki/Configuration#wiki-subject}

        @param idattr: The ID of the Subject node.
        @returns: The Subject node.
        """
        return self.get_node('//Subject[@id="%s"]' % idattr)

    def get_legislative_body_default_subject(self, lbody_node):
        """
        Get the default subject configuration for a legislative body.

        @param lbody_node: The LegisLativeBody parent node.
        @returns: The default subject node in a LegislativeBody.
        """
        return self.get_node(
            '//Subjects/Subject[@default="true"]', parent=lbody_node)

    def get_top_regional_geolevel(self, rnode):
        """
        Get the top level geolevel configuration for a region.

        @param rnode: The Region parent node.
        @returns: The topmost GeoLevel node for a Region.
        """
        return self.get_node('GeoLevels/GeoLevel', parent=rnode)

    def get_score_panel(self, idattr):
        """
        Get the score panel configuration node.

        ScorePanel configuration reference: U{https://github.com/PublicMapping/DistrictBuilder/wiki/Configuration#wiki-scorepanel}

        @param idattr: The ID of the ScorePanel node.
        @returns: The ScorePanel node.
        """
        return self.get_node('//ScorePanels/ScorePanel[@id="%s"]' % idattr)

    def get_score_function(self, idattr):
        """
        Get the score function configuration node.

        ScoreFunction configuration reference: U{https://github.com/PublicMapping/DistrictBuilder/wiki/Configuration#wiki-scorefunction}

        @param idattr: The ID of the ScoreFunction node.
        @returns: The ScoreFunction node.
        """
        return self.get_node(
            '//ScoreFunctions/ScoreFunction[@id="%s"]' % idattr)

    def get_criterion_score(self, crit_node):
        """
        Get the score for a given criterion from the XML data.

        Score configuration reference: U{https://github.com/PublicMapping/DistrictBuilder/wiki/Configuration#wiki-criteria-score}

        @param crit_node: The Criterion parent node.
        @returns: The Score node.
        """
        return self.get_node('Score', parent=crit_node)

    def get_mapserver(self):
        """
        Get the map server configuration node.

        MapServer configuration reference: U{https://github.com/PublicMapping/DistrictBuilder/wiki/Configuration#wiki-mapserver}

        @returns: The MapServer configuration node.
        """
        return self.get_node('//MapServer')

    def filter_regions(self):
        """
        Get all the region configurations from the XML data.

        @returns: A list of all the Region nodes.
        """
        return self.filter_nodes('/DistrictBuilder/Regions/Region')

    def filter_regional_geolevel(self, region_node):
        """
        Get all the geolevel configurations in a region from the XML data.

        @param region_node: The Region parent node.
        @returns: A list of all the GeoLevel nodes in a Region.
        """
        return self.filter_nodes('GeoLevels//GeoLevel', parent=region_node)

    def filter_regional_legislative_bodies(self, region_node):
        """
        Get all the legislative bodies in a region from the XML data.

        @param region_node: The Region parent node.
        @returns: A list of all the LegislativeBody nodes in a Region.
        """
        return self.filter_nodes(
            'LegislativeBodies/LegislativeBody', parent=region_node)

    def filter_legislative_bodies(self):
        """
        Get all the legislative body configurations from the XML data.

        LegislativeBody configuration reference: U{https://github.com/PublicMapping/DistrictBuilder/wiki/Configuration#wiki-legislativebody}

        @returns: A list of all the LegislativeBody nodes.
        """
        return self.filter_nodes('//LegislativeBody[@id]')

    def filter_subjects(self):
        """
        Get all the subject configurations from the XML data.

        Subject configuration reference: U{https://github.com/PublicMapping/DistrictBuilder/wiki/Configuration#wiki-subject}

        @returns: A list of all the Subject nodes.
        """
        return self.filter_nodes('//Subjects/Subject')

    def filter_geolevels(self):
        """
        Get all the geolevel configurations from the XML data.

        GeoLevel configuration reference: U{https://github.com/PublicMapping/DistrictBuilder/wiki/Configuration#wiki-geolevel}

        @returns: A list of all the GeoLevel nodes.
        """
        return self.filter_nodes('/DistrictBuilder/GeoLevels/GeoLevel')

    def filter_scoredisplays(self):
        """
        Get all the score display configurations from the XML data.

        ScoreDisplay configuration reference: U{https://github.com/PublicMapping/DistrictBuilder/wiki/Configuration#wiki-scoredisplay}

        @returns: A list of all the ScoreDisplay nodes.
        """
        return self.filter_nodes('//ScoreDisplays/ScoreDisplay')

    def filter_displayed_score_panels(self, disp_node):
        """
        Get all the score panels configured in a score display.

        ScorePanel configuration reference: U{https://github.com/PublicMapping/DistrictBuilder/wiki/Configuration#wiki-scorepanel}

        @param disp_node: The ScoreDisplay parent node.
        @returns: A list of ScorePanel nodes in a ScoreDisplay.
        """
        return self.filter_nodes('ScorePanel', parent=disp_node)

    def filter_paneled_score_functions(self, pnl_node):
        """
        Get all the score functions configured in a score panel.

        @param pnl_node: The ScorePanel parent node.
        @returns: A list of all the referenced Score nodes in a ScorePanel.
        """
        return self.filter_nodes('Score', parent=pnl_node)

    def filter_score_functions(self):
        """
        Get all the score functions from the XML data.

        ScoreFunction configuration reference: U{https://github.com/PublicMapping/DistrictBuilder/wiki/Configuration#wiki-scorefunction}

        @returns: A list of all the ScoreFunction nodes.
        """
        return self.filter_nodes('//ScoreFunctions/ScoreFunction')

    def filter_criteria(self):
        """
        Get all the validation criteria from the XML data.

        Validation configuration reference: U{https://github.com/PublicMapping/DistrictBuilder/wiki/Configuration#wiki-validation}

        @returns: A list of all Criteria nodes in the validation.
        """
        return self.filter_nodes('//Validation/Criteria')

    def filter_criteria_criterion(self, crit_node):
        """
        Get all the criterion for a given criteria from the XML data.

        @param crit_node: The Criteria parent node.
        @returns: A list of Criterion nodes.
        """
        return self.filter_nodes('Criterion', parent=crit_node)

    def filter_function_legislative_bodies(self, fn_node):
        """
        Get all the legislative bodies for a given score function from the XML data.

        @param fn_node: The ScoreFunction parent node.
        @returns: A list of referenced LegislativeBody nodes.
        """
        return self.filter_nodes('LegislativeBody', parent=fn_node)

    def filter_function_arguments(self, fn_node):
        """
        Get all the score function arguments from the XML data.

        @param fn_node: The ScoreFunction parent node.
        @returns: A list of referenced Argument nodes.
        """
        return self.filter_nodes('Argument', parent=fn_node)

    def filter_function_subject_arguments(self, fn_node):
        """
        Get all the score function subject arguments from the XML data.

        @param fn_node: The ScoreFunction parent node.
        @returns: A list of referenced SubjectArgument nodes.
        """
        return self.filter_nodes('SubjectArgument', parent=fn_node)

    def filter_function_score_arguments(self, fn_node):
        """
        Get all the score function subject arguments from the XML data.

        @param fn_node: The ScoreFunction parent node.
        @returns: A list of referenced ScoreArgument nodes.
        """
        return self.filter_nodes('ScoreArgument', parent=fn_node)

    def filter_contiguity_overrides(self):
        """
        Get all the contiguity overrides from the XML data.

        @returns: A list of all the ContiguityOverrid nodes.
        """
        return self.filter_nodes('//ContiguityOverrides/ContiguityOverride')

    def has_scoring(self):
        """
        Does the configuration contain any scoring nodes?

        @returns: A boolean flag indicating if the configuration
            contains a Scoring node.
        """
        return not self.get_node('//Scoring') is None

    def has_validation(self):
        """
        Does the configuration contain any validation nodes?

        @returns: A boolean flag indicating if the configuration
            contains a Validation node.
        """
        return not self.get_node('//Validation') is None

    def has_contiguity_overrides(self):
        """
        Does the configuration contain any contiguity override nodes?

        @returns: A boolean flag indicating if the configuration
            contains a ContiguityOverrides node.
        """
        return not self.get_node('//ContiguityOverrides') is None
