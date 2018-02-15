from base import BaseTestCase

from django.contrib.gis.gdal import DataSource
from redistricting.models import *

from redistricting.management.commands.setup import Command
from redistricting.config import ConfigImporter
from district_builder_config import StoredConfig


class RegionConfigTest(BaseTestCase):
    """
    Test the configuration options
    """

    fixtures = []

    def setUp(self):
        self.store = StoredConfig('./config/config.dist.xml')
        self.store.validate()
        self.cmd = Command()

    def test_get_largest_geolevel(self):
        region1 = self.store.filter_regions()[0]
        region2 = self.store.filter_regions()[1]

        def get_largest_geolevel(region_node):
            def get_youngest_child(node):
                if len(node) == 0:
                    return node
                else:
                    return get_youngest_child(node[0])

            geolevels = self.store.get_top_regional_geolevel(region_node)
            if len(geolevels) > 0:
                return get_youngest_child(geolevels[0]).get('ref')

        bg1 = get_largest_geolevel(region1)
        bg2 = get_largest_geolevel(region2)

        self.assertEqual('county', bg1, "Didn't get correct geolevel")
        self.assertEqual('vtd', bg2, "Didn't get correct geolevel")

    def test_get_or_create_regional_geolevels(self):
        self.cmd.import_prereq(ConfigImporter(self.store), False)

        expected_geolevels = [
            'county', 'vtd', 'block', 'va_county', 'va_vtd', 'va_block',
            'dc_vtd', 'dc_block'
        ]
        all_geolevels = Geolevel.objects.all()

        self.assertEqual(
            len(expected_geolevels), len(all_geolevels),
            "Didn't return correct number of geolevels")
        for geolevel in expected_geolevels:
            self.assertTrue(
                reduce(lambda x, y: x or y.name == geolevel, all_geolevels,
                       False), "Regional geolevel %s not created" % geolevel)

    def test_filter_functions(self):
        function_dict = self.cmd.create_filter_functions(self.store)
        self.assertEqual(2, len(function_dict), 'No filter functions found')

        shapefile = 'redistricting/testdata/test_data.shp'
        test_layer = DataSource(shapefile)[0]

        va = dc = 0
        for feat in test_layer:
            geolevels = []
            for key, value in function_dict.iteritems():
                for filter_function in value:
                    if filter_function(feat):
                        geolevels.append(key)
                        break

            if len(geolevels) == 2:
                self.assertTrue(
                    'dc' in geolevels,
                    "Regional feature not found in unfiltered geolevel")
                self.assertTrue(
                    'va' in geolevels,
                    "Unfiltered feature not found in unfiltered geolevel")
                va += 1
                dc += 1
            elif len(geolevels) == 1:
                self.assertTrue(
                    'va' in geolevels,
                    "Regional feature not found in unfiltered geolevel")
                va += 1
            else:
                self.fail(
                    "Incorrect number of geolevels returned - should never get"
                    + " here")
        self.assertEqual(1, dc,
                         "Incorrect number of geolevels found for region")
        self.assertEqual(
            3, va, "Incorrect number of geolevels found for unfiltered region")

    def tearDown(self):
        self.region_tree = None
