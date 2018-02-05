from base import BaseTestCase

from redistricting.models import (Geolevel, Geounit, Region, LegislativeBody,
                                  District, Plan)


class NestingTestCase(BaseTestCase):
    """
    Unit tests to test Legislative chamber nesting
    """
    fixtures = [
        'redistricting_testdata.json', 'redistricting_testdata_geolevel2.json',
        'redistricting_testdata_geolevel3.json'
    ]

    def setUp(self):
        super(NestingTestCase, self).setUp()
        self.geolevel = Geolevel.objects.get(name='middle level')
        self.geolevels = self.plan.legislative_body.get_geolevels()

        self.geounits = {}
        for gl in self.geolevels:
            self.geounits[gl.id] = list(
                Geounit.objects.filter(geolevel=gl).order_by('id'))

        # Create 3 nested legislative bodies
        self.region = Region(name='Nesting', sort_key=2)
        self.region.save()
        self.bottom = LegislativeBody(
            name="bottom", max_districts=100, region=self.region)
        self.bottom.save()
        self.middle = LegislativeBody(
            name="middle", max_districts=20, region=self.region)
        self.middle.save()
        self.top = LegislativeBody(
            name="top", max_districts=4, region=self.region)
        self.top.save()

        # Create references for plans and districts
        self.plan = Plan.objects.get(name='testPlan')
        self.plan2 = Plan.objects.get(name='testPlan2')
        self.p1d1 = District.objects.get(
            long_label='District 1', plan=self.plan)
        self.p1d2 = District.objects.get(
            long_label='District 2', plan=self.plan)
        self.p2d1 = District(
            long_label='District 1', district_id=1, version=0, plan=self.plan2)
        self.p2d1.simplify()
        self.p2d2 = District(
            long_label='District 2', district_id=2, version=0, plan=self.plan2)
        self.p2d2.simplify()

    def tearDown(self):
        self.geolevel = None
        self.geolevels = None
        self.geounits = None
        try:
            super(NestingTestCase, self).tearDown()
        except:
            import traceback
            print(traceback.format_exc())
            print('Couldn\'t tear down')

    def test_child_parent(self):
        # Try out each permutation of nested districts
        self.assertFalse(
            self.bottom.is_below(self.bottom), "Bottom was below Bottom")
        self.assertTrue(
            self.bottom.is_below(self.middle), "Bottom wasn't below Middle")
        self.assertTrue(
            self.bottom.is_below(self.top), "Bottom wasn't below Top")
        self.assertFalse(
            self.middle.is_below(self.bottom), "Middle was below Bottom")
        self.assertFalse(
            self.middle.is_below(self.middle), "Middle was below Middle")
        self.assertTrue(
            self.middle.is_below(self.top), "Middle wasn't below Top")
        self.assertFalse(
            self.top.is_below(self.bottom), "Top was below Bottom")
        self.assertFalse(
            self.top.is_below(self.middle), "Top was below Middle")
        self.assertFalse(self.top.is_below(self.top), "Top was below Top")

    def test_relationships_identical_districts(self):
        gl, gs = self.geolevel, list(
            Geounit.objects.filter(geolevel=self.geolevel).order_by("id"))
        p1, p1d1, p1d2 = self.plan, self.p1d1, self.p1d2
        p2, p2d1, p2d2 = self.plan2, self.p2d1, self.p2d2

        dist1ids = gs[0:2] + gs[9:11]
        dist1ids = map(lambda x: str(x.id), dist1ids)

        p1.add_geounits(p1d1.district_id, dist1ids, gl.id, p1.version)
        p1d1 = max(
            District.objects.filter(plan=p1, district_id=p1d1.district_id),
            key=lambda d: d.version)

        dist2ids = gs[19:21] + gs[38:40]
        dist2ids = map(lambda x: str(x.id), dist2ids)

        p1.add_geounits(p1d2.district_id, dist2ids, gl.id, p1.version)
        p1d2 = max(
            District.objects.filter(plan=p1, district_id=p1d2.district_id),
            key=lambda d: d.version)

        # Identical
        p2.add_geounits(p2d1.district_id, dist1ids, gl.id, p2.version)
        p2d1 = max(
            District.objects.filter(plan=p2, district_id=p2d1.district_id),
            key=lambda d: d.version)
        p2.add_geounits(p2d2.district_id, dist2ids, gl.id, p2.version)
        p2d2 = max(
            District.objects.filter(plan=p2, district_id=p2d2.district_id),
            key=lambda d: d.version)

        # Test splits
        splits = p1.find_plan_splits(p2)
        self.assertEqual(len(splits), 0, "Found splits in identical plans")

        # Test contains -- two districts should each contain each other
        contains = p1.find_plan_components(p2)
        self.assertEqual(len(contains), 2, "Didn't find 2 contained districts")
        self.assertEqual(contains[0][:2], (1, 1),
                         "Didn't find p1d1 to contain p2d1")
        self.assertEqual(contains[1][:2], (2, 2),
                         "Didn't find p1d2 to contain p2d1")

    def test_relationships_bottom_district_smaller(self):
        gl, gs = self.geolevel, list(
            Geounit.objects.filter(geolevel=self.geolevel).order_by("id"))
        p1, p1d1, p1d2 = self.plan, self.p1d1, self.p1d2
        p2, p2d1, p2d2 = self.plan2, self.p2d1, self.p2d2

        dist1ids = gs[0:2] + gs[9:11]
        dist1ids = map(lambda x: str(x.id), dist1ids)

        p1.add_geounits(p1d1.district_id, dist1ids, gl.id, p1.version)
        p1d1 = max(
            District.objects.filter(plan=p1, district_id=p1d1.district_id),
            key=lambda d: d.version)

        dist2ids = gs[19:21] + gs[38:40]
        dist2ids = map(lambda x: str(x.id), dist2ids)

        p1.add_geounits(p1d2.district_id, dist2ids, gl.id, p1.version)
        p1d2 = max(
            District.objects.filter(plan=p1, district_id=p1d2.district_id),
            key=lambda d: d.version)

        # 38, 39 not included in bottom plan
        p2.add_geounits(p2d1.district_id, dist1ids, gl.id, p2.version)
        p2d1 = max(
            District.objects.filter(plan=p2, district_id=p2d1.district_id),
            key=lambda d: d.version)

        dist2ids = gs[19:21]
        dist2ids = map(lambda x: str(x.id), dist2ids)

        p2.add_geounits(p2d2.district_id, dist2ids, gl.id, p2.version)
        p2d2 = max(
            District.objects.filter(plan=p2, district_id=p2d2.district_id),
            key=lambda d: d.version)

        # Test splits
        splits = p1.find_plan_splits(p2)
        self.assertEqual(
            len(splits), 0,
            "Found splits when bottom plan had a smaller district")

        # Test contains -- top two districts should contain bottom two
        contains = p1.find_plan_components(p2)
        self.assertEqual(len(contains), 2, "Didn't find 2 contained districts")
        self.assertEqual(contains[0][:2], (1, 1),
                         "Didn't find p1d1 to contain p2d1")
        self.assertEqual(contains[1][:2], (2, 2),
                         "Didn't find p1d2 to contain p2d1")

    def test_relationships_top_district_smaller(self):
        gl, gs = self.geolevel, list(
            Geounit.objects.filter(geolevel=self.geolevel).order_by("id"))
        p1, p1d1, p1d2 = self.plan, self.p1d1, self.p1d2
        p2, p2d1, p2d2 = self.plan2, self.p2d1, self.p2d2

        # 38, 39 not included in top plan
        dist1ids = gs[0:2] + gs[9:11]
        dist1ids = map(lambda x: str(x.id), dist1ids)

        p1.add_geounits(p1d1.district_id, dist1ids, gl.id, p1.version)
        p1d1 = max(
            District.objects.filter(plan=p1, district_id=p1d1.district_id),
            key=lambda d: d.version)

        dist2ids = gs[19:21]
        dist2ids = map(lambda x: str(x.id), dist2ids)

        p1.add_geounits(p1d2.district_id, dist2ids, gl.id, p1.version)
        p1d2 = max(
            District.objects.filter(plan=p1, district_id=p1d2.district_id),
            key=lambda d: d.version)

        p2.add_geounits(p2d1.district_id, dist1ids, gl.id, p2.version)
        p2d1 = max(
            District.objects.filter(plan=p2, district_id=p2d1.district_id),
            key=lambda d: d.version)

        dist2ids = gs[19:21] + gs[28:30]
        dist2ids = map(lambda x: str(x.id), dist2ids)

        p2.add_geounits(p2d2.district_id, dist2ids, gl.id, p2.version)
        p2d2 = max(
            District.objects.filter(plan=p2, district_id=p2d2.district_id),
            key=lambda d: d.version)

        # Test splits
        splits = p1.find_plan_splits(p2)
        self.assertEqual(len(splits), 1, "Didn't find 1 split")
        self.assertEqual(splits[0][:2], (2, 2),
                         "Didn't find p1d2 to split p2d2")

        # Test contains -- one of the bottom districts should contain the other
        # one
        contains = p1.find_plan_components(p2)
        self.assertEqual(len(contains), 1, "Didn't find 1 contained districts")
        self.assertEqual(contains[0][:2], (1, 1),
                         "Didn't find p1d1 to contain p2d1")

    def test_relationships_move_diagonally(self):
        gl, gs = self.geolevel, list(
            Geounit.objects.filter(geolevel=self.geolevel).order_by("id"))
        p1, p1d1, p1d2 = self.plan, self.p1d1, self.p1d2
        p2, p2d1, p2d2 = self.plan2, self.p2d1, self.p2d2

        # Offset plan one unit diagonally down-left
        ids = map(lambda x: str(x.id), gs[0:1])
        p1.add_geounits(p1d1.district_id, ids, gl.id, p1.version)
        p1d1 = max(
            District.objects.filter(plan=p1, district_id=p1d1.district_id),
            key=lambda d: d.version)
        ids = map(lambda x: str(x.id), gs[9:11] + gs[18:20])
        p1.add_geounits(p1d2.district_id, ids, gl.id, p1.version)
        p1d2 = max(
            District.objects.filter(plan=p1, district_id=p1d2.district_id),
            key=lambda d: d.version)

        ids = map(lambda x: str(x.id), gs[0:2] + gs[9:11])
        p2.add_geounits(p2d1.district_id, ids, gl.id, p2.version)
        p2d1 = max(
            District.objects.filter(plan=p2, district_id=p2d1.district_id),
            key=lambda d: d.version)
        ids = map(lambda x: str(x.id), gs[19:21] + gs[28:30])
        p2.add_geounits(p2d2.district_id, ids, gl.id, p2.version)
        p2d2 = max(
            District.objects.filter(plan=p2, district_id=p2d2.district_id),
            key=lambda d: d.version)

        # Test splits
        splits = p1.find_plan_splits(p2)
        self.assertEqual(len(splits), 3, "Didn't find 3 splits")
        self.assertEqual(splits[0][:2], (1, 1),
                         "Didn't find p1d1 to split p2d1")
        self.assertEqual(splits[1][:2], (2, 1),
                         "Didn't find p1d2 to split p2d1")
        self.assertEqual(splits[2][:2], (2, 2),
                         "Didn't find p1d2 to split p2d2")

        # Test contains -- shouldn't be any districts fully contained
        contains = p1.find_plan_components(p2)
        self.assertEqual(
            len(contains), 0,
            "Found contained districts when there should be none.")
