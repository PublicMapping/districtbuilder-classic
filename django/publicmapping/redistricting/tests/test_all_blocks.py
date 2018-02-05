from base import BaseTestCase

from redistricting.models import Geolevel, Geounit, Plan
from redistricting.calculators import AllBlocksAssigned


class AllBlocksTestCase(BaseTestCase):
    fixtures = [
        'redistricting_testdata.json',
        'redistricting_testdata_geolevel2.json',
        'redistricting_testdata_geolevel3.json',
    ]

    def setUp(self):
        super(AllBlocksTestCase, self).setUp()
        self.geolevel = Geolevel.objects.get(name='middle level')
        self.geounits = list(
            Geounit.objects.filter(geolevel=self.geolevel).order_by('id'))

    def tearDown(self):
        self.geolevel = None
        self.geounits = None
        super(AllBlocksTestCase, self).tearDown()

    def test_allblocks(self):
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[6:9] + self.geounits[15:18]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids,
                               self.geolevel.id, self.plan.version)

        allblocks = AllBlocksAssigned()
        allblocks.arg_dict['threshold'] = ('literal', 0.1)

        plan = Plan.objects.get(pk=self.plan.id)
        allblocks.compute(plan=plan)
        actual = allblocks.result['value']
        self.assertEqual(False, actual,
                         'Incorrect value during plan allblocks. (e:%s,a:%s)' %
                         (False, actual))

        remainderids = plan.get_unassigned_geounits(0.1)
        remainderids = map(lambda x: str(x[0]), remainderids)
        plan.add_geounits(self.district2.district_id, remainderids,
                          self.geolevel.id, plan.version)

        plan = Plan.objects.get(pk=plan.id)
        allblocks.compute(plan=plan)
        actual = allblocks.result['value']
        self.assertEqual(True, actual,
                         'Incorrect value during plan allblocks. (e:%s,a:%s)' %
                         (True, actual))
