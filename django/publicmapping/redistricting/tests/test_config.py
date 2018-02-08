from django.test import TestCase
import tempfile
import os
import logging

from district_builder_config import StoredConfig


class ConfigTestCase(TestCase):
    good_data_filename = './config/config.dist.xml'
    good_schema_filename = './config/config.xsd'
    bad_data_filename = '/tmp/bad_data.xsd'
    bad_schema_filename = '/tmp/bad_schema.xsd'

    def setUp(self):
        logging.basicConfig(level=logging.ERROR)

    def make_simple_schema(self):
        test_schema = tempfile.NamedTemporaryFile(delete=False)
        test_schema.write('<?xml version="1.0" encoding="utf-8"?>\n')
        test_schema.write(
            '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">\n')
        test_schema.write('<xs:element name="DistrictBuilder"/>\n')
        test_schema.write('</xs:schema>')
        test_schema.close()

        return test_schema

    """
    Test the Config classes.
    """

    def test_constructor_missing_schema(self):
        try:
            x = StoredConfig(
                self.bad_data_filename, schema_file=self.bad_schema_filename)
            self.fail('Expected failure when passing nonexistant filenames to '
                      + 'constructor.')
        except:
            pass

    def test_construct_missing_data(self):
        try:
            x = StoredConfig(
                self.bad_data_filename, schema_file=self.good_schema_filename)
            self.fail('Expected failure when passing nonexistant filenames to '
                      + 'constructor.')
        except:
            pass

    def test_construct_okay(self):
        x = StoredConfig(
            self.good_data_filename, schema_file=self.good_schema_filename)

        self.assertEqual(x.datafile, self.good_data_filename,
                         'Configuration data is not correct.')
        self.assertEqual(x.schema_file, self.good_schema_filename,
                         'Configuration schema is not correct.')

    def test_validation_schema_xml_parser(self):
        test_schema = tempfile.NamedTemporaryFile(delete=False)
        test_schema.write('<?xml version="1.0" encoding="utf-8"?>\n')
        test_schema.write('<DistrictBuilder><junk></DistrictBuilder>\n')
        test_schema.close()

        x = StoredConfig(self.good_data_filename, schema_file=test_schema.name)
        is_valid = x.validate()

        os.remove(test_schema.name)

        self.assertFalse(is_valid, 'Configuration schema was not valid.')

    def test_validation_schema_xml_wellformed(self):
        test_schema = tempfile.NamedTemporaryFile(delete=False)
        test_schema.write('<?xml version="1.0" encoding="utf-8"?>\n')
        test_schema.write('<DistrictBuilder><junk/></DistrictBuilder>\n')
        test_schema.close()

        x = StoredConfig(self.good_data_filename, schema_file=test_schema.name)
        is_valid = x.validate()

        os.remove(test_schema.name)

        self.assertFalse(is_valid, 'Configuration schema was not valid.')

    def test_validation_schema_xml(self):
        test_schema = self.make_simple_schema()

        x = StoredConfig(self.good_data_filename, schema_file=test_schema.name)
        is_valid = x.validate()

        os.remove(test_schema.name)

        self.assertTrue(is_valid, 'Configuration schema should be valid.')

    def test_validation_data_xml_parser(self):
        test_schema = self.make_simple_schema()

        test_data = tempfile.NamedTemporaryFile(delete=False)
        test_data.write('<?xml version="1.0" encoding="utf-8"?>\n')
        test_data.write('<DistrictBuilder><junk></DistrictBuilder>\n')
        test_data.close()

        x = StoredConfig(test_data.name, schema_file=test_schema.name)
        is_valid = x.validate()

        os.remove(test_data.name)
        os.remove(test_schema.name)

        self.assertFalse(is_valid, 'Configuration data was not valid.')

    def test_validation_data_xml_wellformed(self):
        test_schema = self.make_simple_schema()
        test_data = tempfile.NamedTemporaryFile(delete=False)
        test_data.write('<?xml version="1.0" encoding="utf-8"?>\n')
        test_data.write('<DistrictBuilder><junk/></DistrictBuilder>\n')
        test_data.close()

        x = StoredConfig(test_data.name, schema_file=test_schema.name)
        is_valid = x.validate()

        os.remove(test_data.name)
        os.remove(test_schema.name)

        self.assertTrue(is_valid, 'Configuration data was not valid.')

    def test_validation(self):
        x = StoredConfig(
            self.good_data_filename, schema_file=self.good_schema_filename)

        is_valid = x.validate()

        self.assertTrue(
            is_valid,
            'Configuration schema and data should be valid and should validate'
            + ' successfully.')
