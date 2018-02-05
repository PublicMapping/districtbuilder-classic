from base import BaseTestCase

from django.contrib.gis.geos import (
    MultiPolygon,
    Polygon,
    Point,
    LinearRing,
)
from redistricting.models import Geolevel, Geounit, LegislativeBody


class GeounitMixTestCase(BaseTestCase):
    """
    Unit tests to test the mixed geounit spatial queries.
    """

    def setUp(self):
        super(GeounitMixTestCase, self).setUp()
        self.geolevels = Geolevel.objects.all().order_by('-id')
        self.geounits = {}
        for gl in self.geolevels:
            self.geounits[gl.id] = list(
                Geounit.objects.filter(geolevel=gl).order_by('id'))
        self.legbod = LegislativeBody.objects.get(name='TestLegislativeBody')

    def tearDown(self):
        self.geolevels = None
        self.geounits = None
        self.legbod = None
        super(GeounitMixTestCase, self).tearDown()

    def test_numgeolevels(self):
        """
        Test the number of geolevels created.
        """
        self.assertEqual(
            3, len(self.geolevels),
            'Number of geolevels for mixed geounits is incorrect.')

    def test_numgeounits1(self):
        """
        Test the number of geounits in the first tier of geounits.
        """
        self.assertEqual(9, len(self.geounits[self.geolevels[0].id]),
                         'Number of geounits at geolevel "%s" is incorrect.' %
                         self.geolevels[0].name)

    def test_numgeounits2(self):
        """
        Test the number of geounits in the second tier of geounits.
        """
        self.assertEqual(81, len(self.geounits[self.geolevels[1].id]),
                         'Number of geounits at geolevel "%s" is incorrect.' %
                         self.geolevels[1].name)

    def test_numgeounits3(self):
        """
        Test the number of geounits in the third tier of geounits.
        """
        self.assertEqual(729, len(self.geounits[self.geolevels[2].id]),
                         'Number of geounits at geolevel "%s" is incorrect.' %
                         self.geolevels[2].name)

    def test_allunitscount(self):
        """
        Test that known geounits are spatially contained within other geounits.
        """
        unit1 = self.geounits[self.geolevels[0].id][0]

        unit2 = self.geounits[self.geolevels[1].id][0]

        self.assertTrue(
            unit1.geom.contains(unit2.geom),
            'First unit does not contain secont unit.')

        unit3 = self.geounits[self.geolevels[2].id][0]

        self.assertTrue(
            unit1.geom.contains(unit3.geom),
            'First unit does not contain second unit.')
        self.assertTrue(
            unit2.geom.contains(unit3.geom),
            'Second unit does not contain third unit.')

    def test_get_all_in(self):
        """
        Test the spatial query to get geounits within a known boundary.
        """
        level = self.geolevels[0]
        units = self.geounits[level.id]

        units = Geounit.objects.filter(
            geom__within=units[0].geom, geolevel__lt=level.id)

        numunits = len(units)
        self.assertEqual(
            90, numunits,
            'Number of geounits within a high-level geounit is incorrect. (%d)'
            % numunits)

    def test_get_in_gu0(self):
        """
        Test the spatial query to get geounits within a known boundary.
        """
        level = self.plan.legislative_body.get_geolevels()[0]
        units = self.geounits[level.id]

        units = Geounit.objects.filter(
            geom__within=units[0].geom, geolevel=level.id - 1)
        numunits = len(units)
        self.assertEqual(
            9, numunits,
            'Number of geounits within geounit 1 is incorrect. (%d)' %
            numunits)

    def test_get_base(self):
        """
        Test the spatial query to get all geounits at the base geolevel within
        a boundary.
        """
        level = self.plan.legislative_body.get_geolevels()[0]
        units = self.geounits[level.id]
        geounit_ids = tuple([units[0].id, units[1].id])
        base_level = self.legbod.get_base_geolevel()

        units = Geounit.objects.filter(
            geom__within=units[0].geom, geolevel=base_level)

        numunits = len(units)
        self.assertEqual(
            81, numunits,
            'Number of geounits within a high-level geounit is incorrect. (%d)'
            % numunits)

    def test_get_mixed1(self):
        """
        Test the logic for getting mixed geounits inside a boundary at the
        highest geolevel.
        """
        level = self.plan.legislative_body.get_geolevels()[0]
        bigunits = self.geounits[level.id]
        ltlunits = self.geounits[self.geolevels[1].id]
        boundary = bigunits[0].geom.difference(ltlunits[9].geom)

        units = Geounit.get_mixed_geounits([str(bigunits[0].id)], self.legbod,
                                           level.id, boundary, True)
        numunits = len(units)
        self.assertEqual(
            8, numunits,
            'Number of geounits inside boundary is incorrect. (%d)' % numunits)

    def test_get_imixed1(self):
        """
        Test the logic for getting mixed geounits outside a boundary at the
        highest geolevel.
        """
        level = self.geolevels[0]
        bigunits = self.geounits[level.id]
        ltlunits = self.geounits[self.geolevels[1].id]
        boundary = bigunits[0].geom.difference(ltlunits[9].geom)

        units = Geounit.get_mixed_geounits([str(bigunits[0].id)], self.legbod,
                                           level.id, boundary, False)
        numunits = len(units)
        self.assertEqual(
            1, numunits,
            'Number of geounits outside boundary is incorrect. (%d)' %
            numunits)

    def test_get_mixed2(self):
        """
        Test the logic for getting mixed geounits inside a boundary at the
        middle geolevel.
        """
        level = self.geolevels[1]
        bigunits = self.geounits[level.id]
        ltlunits = self.geounits[self.geolevels[2].id]
        boundary = bigunits[0].geom.difference(ltlunits[27].geom)

        units = Geounit.get_mixed_geounits([str(bigunits[0].id)], self.legbod,
                                           level.id, boundary, True)
        numunits = len(units)
        self.assertEqual(
            8, numunits,
            'Number of geounits inside boundary is incorrect. (%d)' % numunits)

    def test_get_imixed2(self):
        """
        Test the logic for getting mixed geounits outside a boundary at the
        middle geolevel.
        """
        level = self.geolevels[1]
        bigunits = self.geounits[level.id]
        ltlunits = self.geounits[self.geolevels[2].id]
        boundary = bigunits[0].geom.difference(ltlunits[27].geom)

        units = Geounit.get_mixed_geounits([str(bigunits[0].id)], self.legbod,
                                           level.id, boundary, False)
        numunits = len(units)
        self.assertEqual(
            1, numunits,
            'Number of geounits outside boundary is incorrect. (%d)' %
            numunits)

    def test_get_mixed3(self):
        """
        Test the logic for getting mixed geounits inside a boundary at the
        lowest geolevel.
        """
        level = self.geolevels[0]
        bigunits = self.geounits[level.id]
        boundary = MultiPolygon(
            Polygon(
                LinearRing(
                    Point((0, 0)), Point((1, 0)), Point((1, 1)), Point((0,
                                                                        0)))))
        boundary.srid = 3785

        units = Geounit.get_mixed_geounits(
            [str(bigunits[1].id),
             str(bigunits[2].id),
             str(bigunits[5].id)], self.legbod, level.id, boundary, True)
        numunits = len(units)
        self.assertEqual(
            3, numunits,
            'Number of geounits inside boundary is incorrect. (%d)' % numunits)

        units = Geounit.get_mixed_geounits(
            [str(bigunits[0].id),
             str(bigunits[4].id),
             str(bigunits[8].id)], self.legbod, level.id, boundary, True)
        numunits = len(units)
        self.assertEqual(
            63, numunits,
            'Number of geounits inside boundary is incorrect. (%d)' % numunits)

    def test_get_imixed3(self):
        """
        Test the logic for getting mixed geounits outside a boundary at the
        lowest geolevel.
        """
        level = self.geolevels[0]
        bigunits = self.geounits[level.id]
        boundary = MultiPolygon(
            Polygon(
                LinearRing(
                    Point((0, 0)), Point((1, 0)), Point((1, 1)), Point((0,
                                                                        0)))))
        boundary.srid = 3785

        units = Geounit.get_mixed_geounits(
            [str(bigunits[3].id),
             str(bigunits[6].id),
             str(bigunits[7].id)], self.legbod, level.id, boundary, False)
        numunits = len(units)
        # this test should return 3, for the large geounits are completely
        # without yet intersect at the corner. the net geometry from this
        # set of mixed geounits is correct, though
        self.assertEqual(
            3, numunits,
            'Number of geounits outside boundary is incorrect. (%d)' %
            numunits)

        units = Geounit.get_mixed_geounits(
            [str(bigunits[0].id),
             str(bigunits[4].id),
             str(bigunits[8].id)], self.legbod, level.id, boundary, False)
        numunits = len(units)
        self.assertEqual(
            63, numunits,
            'Number of geounits outside boundary is incorrect. (%d)' %
            numunits)
