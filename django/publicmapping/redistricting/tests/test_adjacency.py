from base import BaseTestCase

import unittest
from redisutils import key_gen
import itertools

import redis

from redistricting.models import Geolevel, Geounit, District
from redistricting.calculators import Adjacency
from django.conf import settings


@unittest.skipIf('calculators' not in settings.CACHES,
                 'Calculator cache is not configured in settings.')
class AdjacencyTestCase(BaseTestCase):
    """
    Unit tests for the adjacency calculator

    Note, this is split off from other scoring test cases since it requires
    connecting to redis and other functionality not required by any other
    calculators
    """

    def setUp(self):
        super(AdjacencyTestCase, self).setUp()

        # Create some districts, add some geounits
        geolevel = Geolevel.objects.get(name='middle level')
        geounits = list(
            Geounit.objects.filter(geolevel=geolevel).order_by('id'))

        dist1units = geounits[0:3] + geounits[9:12]
        dist2units = geounits[18:21] + geounits[27:30] + geounits[36:39]

        dist1ids = map(lambda x: str(x.id), dist1units)
        dist2ids = map(lambda x: str(x.id), dist2units)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               geolevel.id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids,
                               geolevel.id, self.plan.version)

        self.district1 = max(
            District.objects.filter(
                plan=self.plan, district_id=self.district1.district_id),
            key=lambda d: d.version)
        self.district2 = max(
            District.objects.filter(
                plan=self.plan, district_id=self.district2.district_id),
            key=lambda d: d.version)

        # Get redis in order to set upload values for testing
        redis_settings = settings.KEY_VALUE_STORE
        self.r = redis.StrictRedis(
            host=redis_settings['HOST'],
            port=int(redis_settings['PORT']),
            password=redis_settings['PASSWORD'],
            db=15)

        base_geolevel = Geolevel.objects.get(name='smallest level')
        base_geounits = Geounit.objects.filter(
            geolevel=base_geolevel).order_by('portable_id')
        base_geounit_combos = itertools.combinations(base_geounits, 2)
        redis_dict = {}
        region_sum = 0
        geounit_count = 0
        for combo in base_geounit_combos:
            geounit_count += 1
            key = key_gen(**{
                'geounit1': combo[0].portable_id,
                'geounit2': combo[1].portable_id
            })
            value = round(combo[0].center.distance(combo[1].center) * 100, 12)
            redis_dict[key] = value
            region_sum += value
        self.r.mset(redis_dict)
        region_cost = region_sum / geounit_count
        key = key_gen(**{'region': self.plan.legislative_body.region.name})
        self.r.set(key, region_cost)

    def tearDown(self):
        self.r.flushdb()
        super(AdjacencyTestCase, self).tearDown()

    def testAdjacencyScores(self):
        adj = Adjacency()
        adj.compute(**{'district': self.district1, 'db': 15})
        self.assertAlmostEqual(14.7671977211, adj.result['value'], 9,
                               'Adjacency score for district was incorrect: %f'
                               % adj.result['value'])

        # Test computing a plan's score
        adj.compute(**{'plan': self.plan, 'db': 15})
        self.assertAlmostEqual(
            0.29712390062, adj.result['value'], 9,
            'Adjacency score for plan was incorrect %f' % adj.result['value'])
