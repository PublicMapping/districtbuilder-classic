from base import BaseTestCase

from redistricting.models import Geolevel, Plan, District


class IterativeSimplificationTest(BaseTestCase):
    """
    Unit tests for iterative simplification of complex districts
    """
    fixtures = [
        'redistricting_testdata.json',
        'redistricting_testdata_toughtosimplify.json'
    ]

    def setUp(self):
        """
        Set up the geolevels and proper tolerances
        """
        g1 = Geolevel.objects.get(name='smallest level')
        g1.tolerance = 100.0
        g1.save()

        g2 = Geolevel.objects.get(name='middle level')
        g2.tolerance = 160.0
        g2.save()

        g3 = Geolevel.objects.get(name='biggest level')
        g3.tolerance = 250.0
        g3.save()

        self.plan = Plan.objects.get(name='testPlan')

    def test_iterative_simplification(self):
        """
        This tests the iterative simplification.  District 16 in Ohio failed
        to simplify at the desired
        tolerance so this feature was added.  If a district can't be
        simplified in a given number of
        attempts (5 by default), the full geometry is used and an error is
        output

        This district doesn't simplify at 250 or 180 but does at 160.
        The sixth poly of the multipoly
        is the most complex so we check that one for simplification
        """
        d = District.objects.get(long_label='District 16 from Ohio')

        [geolevel2, geolevel1,
         geolevel0] = self.plan.legislative_body.get_geolevels()

        # geolevel2, geolevel1, and geolevel0 are offset indexes of d.simple
        # d.simple is the GEOSGeometry object that represents the geometry
        # collection of the simplified district. The indexes of d.simple
        # directly relate to the geolevel ID. However, since GEOS 0-indexes
        # this collection, and postgis 1-indexes the collection, we have to
        # -1 the value when checking the simple collection

        d.simplify(attempts_allowed=0)
        self.assertTrue(
            d.geom.equals(d.simple[geolevel0.id - 1]),
            "District was simplified when it shouldn't have been")
        self.assertTrue(
            d.geom.equals(d.simple[geolevel1.id - 1]),
            "District was simplified when it shouldn't have been")
        self.assertTrue(
            d.geom.equals(d.simple[geolevel2.id - 1]),
            "District was simplified when it shouldn't have been")

        d.simplify(attempts_allowed=1)
        self.assertTrue(
            len(d.geom.coords[6][0]) > len(
                d.simple[geolevel0.id - 1].coords[0]),
            "District wasn't simplified")
        self.assertTrue(
            len(d.geom.coords[6][0]) > len(
                d.simple[geolevel1.id - 1].coords[0]),
            "District wasn't simplified")
        self.assertTrue(
            d.geom.equals(d.simple[geolevel2.id - 1]),
            "District was simplified when it shouldn't have been")

        d.simplify(attempts_allowed=3)
        self.assertTrue(
            len(d.geom.coords[6][0]) > len(
                d.simple[geolevel0.id - 1].coords[6][0]),
            "District wasn't simplified")
        self.assertTrue(
            len(d.geom.coords[6][0]) > len(
                d.simple[geolevel1.id - 1].coords[6][0]),
            "District wasn't simplified")
        self.assertTrue(
            len(d.geom.coords[6][0]) > len(
                d.simple[geolevel2.id - 1].coords[6][0]),
            "District wasn't simplified")
