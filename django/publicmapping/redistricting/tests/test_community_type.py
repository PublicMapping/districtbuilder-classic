from base import BaseTestCase

from redistricting.models import (Geolevel, LegislativeBody, Geounit, Plan,
                                  District)
from redistricting.calculators import (CommunityTypeCounter,
                                       CommunityTypeCompatible)


class CommunityTypeTestCase(BaseTestCase):
    """
    Unit tests to test detection of Community types in a district:
    """
    fixtures = [
        'redistricting_testdata.json', 'redistricting_testdata_geolevel2.json'
    ]

    def setUp(self):
        super(CommunityTypeTestCase, self).setUp()
        self.geolevel = Geolevel.objects.get(name='middle level')
        self.geolevels = Geolevel.objects.all().order_by('-id')
        self.legbod = LegislativeBody.objects.get(name='TestLegislativeBody')

        self.geounits = {}
        for gl in self.geolevels:
            self.geounits[gl.id] = list(
                Geounit.objects.filter(geolevel=gl).order_by('id'))

        # Create a standard district
        self.plan = Plan(
            name='political', owner=self.user, legislative_body=self.legbod)
        self.plan.save()

        # Create a community map with districts of varying types
        self.community = Plan(
            name='community', owner=self.user, legislative_body=self.legbod)
        self.community.save()

    def tearDown(self):
        self.geolevel = None
        self.geolevels = None
        self.legbod = None
        self.geounits = None
        self.plan.delete()
        self.community.delete()

        try:
            super(CommunityTypeTestCase, self).tearDown()
        except:
            import traceback
            print(traceback.format_exc())
            print('Couldn\'t tear down')

    def test_community_union(self):
        gl, gs = self.geolevel, list(
            Geounit.objects.filter(geolevel=self.geolevel).order_by("id"))
        p, c = self.plan, self.community

        # Create a basic district in the plan
        ids = map(lambda x: str(x.id), gs[21:24] + gs[30:33] + gs[39:42])
        p.add_geounits(1, ids, gl.id, p.version)
        d1 = max(
            District.objects.filter(plan=p, district_id=1),
            key=lambda d: d.version)

        # Check and make sure we get 0 intersections
        intersections = d1.count_community_type_union(c.id)
        self.assertNotEquals(0, d1.geom.area, 'District 1 has no area')
        self.assertEqual(
            0, intersections,
            'Detected community intersections when there are none a:%d' %
            intersections)

        # C1 intersects on the left, half-in and half-out of d1
        ids = map(lambda x: str(x.id), gs[29:31])
        c.add_geounits(1, ids, gl.id, c.version)
        c1 = max(
            District.objects.filter(plan=c, district_id=1),
            key=lambda d: d.version)
        c1.tags = 'type=type_a'
        intersections = d1.count_community_type_union(c.id)
        self.assertEqual(
            1, intersections,
            'detected incorrect number of community intersections. e:1;a:%d' %
            intersections)

        # C2 is inside of d1 and shares a border
        ids = [str(gs[32].id)]
        c.add_geounits(2, ids, gl.id, c.version)
        c2 = max(
            District.objects.filter(plan=c, district_id=2),
            key=lambda d: d.version)
        c2.tags = 'type=type_b'
        intersections = d1.count_community_type_union(c.id)
        self.assertEqual(
            2, intersections,
            'Detected incorrect number of community intersections. e:2;a:%d' %
            intersections)

        #C3 is outside of d1 and shares a border
        ids = [str(gs[56].id)]
        c.add_geounits(3, ids, gl.id, c.version)
        c3 = max(
            District.objects.filter(plan=c, district_id=3),
            key=lambda d: d.version)
        c3.tags = 'type=type_c'
        intersections = d1.count_community_type_union(c.id)
        self.assertEqual(
            2, intersections,
            'Detected incorrect number of community intersections. e:2;a:%d' %
            intersections)

        # C4 is entirely within d1 and shares no borders
        ids = [str(gs[31].id)]
        c.add_geounits(4, ids, gl.id, c.version)
        c4 = max(
            District.objects.filter(plan=c, district_id=4),
            key=lambda d: d.version)
        intersections = d1.count_community_type_union(c.id)
        self.assertEqual(
            2, intersections,
            'Detected incorrect number of community intersections. e:2;a:%d' %
            intersections)
        c4.tags = 'type=type_a type=type_b type=type_c'
        intersections = d1.count_community_type_union(c.id)
        self.assertEqual(
            3, intersections,
            'Detected incorrect number of community intersections. e:3;a:%d' %
            intersections)

    def test_community_union_calculator(self):
        calc = CommunityTypeCounter()
        gl, gs = self.geolevel, list(
            Geounit.objects.filter(geolevel=self.geolevel).order_by("id"))
        p, c = self.plan, self.community

        # Create a basic district in the plan
        ids = map(lambda x: str(x.id), gs[21:24] + gs[30:33] + gs[39:42])
        p.add_geounits(1, ids, gl.id, p.version)
        d1 = max(
            District.objects.filter(plan=p, district_id=1),
            key=lambda d: d.version)

        # Check and make sure we get 0 intersections
        calc.compute(district=d1, community_map_id=c.id, version=c.version)
        self.assertEqual(
            0, calc.result['value'],
            'Detected community intersections when there are none a:%s' %
            calc.result['value'])

        # C1 intersects on the left, half-in and half-out of d1
        ids = map(lambda x: str(x.id), gs[29:31])
        c.add_geounits(1, ids, gl.id, c.version)
        c1 = max(
            District.objects.filter(plan=c, district_id=1),
            key=lambda d: d.version)
        c1.tags = 'type=type_a'
        calc.compute(district=d1, community_map_id=c.id, version=c.version)
        self.assertEqual(
            1, calc.result['value'],
            'detected incorrect number of community calc.result. e:1;a:%s' %
            calc.result['value'])

        calc.compute(district=d1, community_map_id=-1, version=c.version)
        self.assertEqual('n/a', calc.result['value'],
                         'Did\'t get "n/a" when incorrect map_id used. a:%s' %
                         calc.result['value'])

    def test_community_intersection(self):
        calc = CommunityTypeCompatible()
        gl, gs = self.geolevel, list(
            Geounit.objects.filter(geolevel=self.geolevel).order_by("id"))
        p, c = self.plan, self.community

        # Create a basic district in the plan
        ids = map(lambda x: str(x.id), gs[21:24] + gs[30:33] + gs[39:42])
        p.add_geounits(1, ids, gl.id, p.version)

        ids = map(lambda x: str(x.id), gs[18:21] + gs[27:30] + gs[36:39])
        p.add_geounits(2, ids, gl.id, p.version)
        d1 = max(
            District.objects.filter(plan=p, district_id=1),
            key=lambda d: d.version)
        d2 = max(
            District.objects.filter(plan=p, district_id=2),
            key=lambda d: d.version)

        # Check and make sure we get 0 intersections
        calc.compute(plan=p, community_map_id=c.id, type='junk')
        self.assertFalse(
            calc.result['value'],
            'Detected community type compatibility when there is none a:%s' %
            calc.result['value'])

        # C1 intersects on the left, half-in and half-out of d1
        ids = map(lambda x: str(x.id), gs[29:31])
        c.add_geounits(1, ids, gl.id, c.version)
        c1 = max(
            District.objects.filter(plan=c, district_id=1),
            key=lambda d: d.version)
        c1.tags = 'type=type_a'
        calc.compute(plan=p, community_map_id=c.id, type='type_a')
        self.assertTrue(calc.result['value'],
                        'Detected no community type compatibility. a:%s' %
                        calc.result['value'])

        # C2 is inside of d1 and shares a border
        ids = [str(gs[32].id)]
        c.add_geounits(2, ids, gl.id, c.version)
        c2 = max(
            District.objects.filter(plan=c, district_id=2),
            key=lambda d: d.version)
        c2.tags = 'type=type_b type=type_a'
        calc.compute(plan=p, community_map_id=c.id, type='type_a')
        self.assertTrue(calc.result['value'],
                        'Detected no community type compatibility. a:%s' %
                        calc.result['value'])

        # C3 is outside of d1 and shares a border
        ids = [str(gs[56].id)]
        c.add_geounits(3, ids, gl.id, c.version)
        c3 = max(
            District.objects.filter(plan=c, district_id=3),
            key=lambda d: d.version)
        c3.tags = 'type=type_c type=type_a'
        calc.compute(plan=p, community_map_id=c.id, type='type_a')
        self.assertTrue(calc.result['value'],
                        'Detected no community type compatibility. a:%s' %
                        calc.result['value'])

        # C4 is entirely within d1 and shares no borders
        ids = [str(gs[31].id)]
        c.add_geounits(4, ids, gl.id, c.version)
        c4 = max(
            District.objects.filter(plan=c, district_id=4),
            key=lambda d: d.version)
        c4.tags = 'type=type_b type=type_c'
        calc.compute(plan=p, community_map_id=c.id, type='type_b')
        self.assertFalse(
            calc.result['value'],
            'Detected community compatibility when there is none. a:%s' %
            calc.result['value'])
