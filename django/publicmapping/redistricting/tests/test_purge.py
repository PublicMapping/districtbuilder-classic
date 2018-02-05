from base import BaseTestCase

from redistricting.models import Geolevel, Geounit
from django.conf import settings


class PurgeTestCase(BaseTestCase):
    """
    Unit tests to test the methods for purging extra districts off a plan.
    """
    fixtures = [
        'redistricting_testdata.json', 'redistricting_testdata_geolevel2.json'
    ]

    def setUp(self):
        super(PurgeTestCase, self).setUp()

        # create a new buch of districts for this test case
        self.plan.district_set.all().delete()
        self.geolevel = Geolevel.objects.get(name='middle level')
        self.geounits = list(
            Geounit.objects.filter(geolevel=self.geolevel).order_by('id'))

        # create Districts
        for i in range(0, 9):
            start = 9 * i
            end = 9 * (i + 1)

            # overlap the previous assignment to create multiple versions
            # of districts
            if i > 0:
                start -= 1
            if i < 8:
                end += 1

            geounits = self.geounits
            geounits = map(lambda x: str(x.id), geounits)

            self.plan.add_geounits((i + 1), geounits, self.geolevel.id,
                                   self.plan.version)

    def tearDown(self):
        self.geounits = None
        self.geolevel = None
        self.plan = None
        super(PurgeTestCase, self).tearDown()

    def test_purge_lt_zero(self):
        self.plan.purge(before=-1)

        self.assertEqual(9, self.plan.version, 'Plan version is incorrect.')
        count = self.plan.district_set.count()
        self.assertEqual(
            17, count,
            'Number of districts in plan is incorrect. (e:17,a:%d)' % count)

    def test_purge_gt_max(self):
        self.plan.purge(after=9)

        self.assertEqual(9, self.plan.version, 'Plan version is incorrect.')
        count = self.plan.district_set.count()
        self.assertEqual(
            17, count,
            'Number of districts in plan is incorrect. (e:17,a:%d)' % count)

    def test_purge_lt_four(self):
        self.plan.purge(before=4)

        self.assertEqual(9, self.plan.version, 'Plan version is incorrect.')

        # should have 14 items, purging old versions of districts at version
        # 0, 1, 2, and 3 but keeping the most recent version of each
        # district
        # (even if the district version is less than the 'before' keyword)
        count = self.plan.district_set.count()
        self.assertEqual(
            14, count,
            'Number of districts in plan is incorrect. (e:14, a:%d)' % count)

    def test_purge_lt_nine(self):
        self.plan.purge(before=9)

        self.assertEqual(9, self.plan.version, 'Plan version is incorrect.')

        # should have 9 items, purging all old versions of districts, but
        # keeping the most recent version of each district
        # (even if the district version is less than the 'before' keyword)
        count = self.plan.district_set.count()
        self.assertEqual(
            9, count,
            'Number of districts in plan is incorrect. (e:9, a:%d)' % count)

    def test_purge_gt_five(self):
        self.plan.purge(after=5)

        self.assertEqual(9, self.plan.version, 'Plan version is incorrect.')

        # should have 9 items, since everything after version 5 was deleted
        # 2 of District 1
        # 2 of District 2
        # 2 of District 3
        # 2 of District 4
        # 1 of District 5
        count = self.plan.district_set.count()
        self.assertEqual(
            9, count,
            'Number of districts in plan is incorrect. (e:9, a:%d)' % count)

    def test_purge_many_edits(self):
        # Reset the undo mechanism
        settings.MAX_UNDOS_DURING_EDIT = 0
        settings.MAX_UNDOS_AFTER_EDIT = 0

        geolevelid = 2

        oldversion = self.plan.version

        count = self.plan.district_set.count()

        # every add_geounits call should add 2 districts to the
        # district_set, since this geounit should be removed from one
        # district, and added to another.
        for i in range(0, 8):
            item = 9 * (i + 1) + 1

            item = str(self.geounits[item].id)
            self.plan.add_geounits((i + 1), [item], geolevelid,
                                   self.plan.version)

        # net gain: 16 districts

        self.assertEqual(16,
                         self.plan.district_set.count() - count,
                         'Incorrect of districts in the plan district_set.')
        self.assertEqual(
            8, self.plan.version - oldversion,
            'Incorrect number of versions incremented after 8 edits.')

        self.plan.purge(before=oldversion)

        count = self.plan.district_set.count()
        self.assertEqual(
            25, count,
            'Number of districts in plan is incorrect. (e:25, a:%d)' % count)

    def test_version_back(self):
        version = self.plan.get_nth_previous_version(self.plan.version)

        self.assertEqual(0, version,
                         'Walking back %d versions does not land at zero.' %
                         self.plan.version)

        version = self.plan.get_nth_previous_version(self.plan.version - 1)

        self.assertEqual(1, version,
                         'Walking back %d versions does not land at one.' %
                         (self.plan.version - 1))

    def test_purge_versions(self):
        geolevelid = 2

        oldversion = self.plan.version
        for i in range(oldversion - 1, 4, -1):
            item = 9 * (i + 1) - 2
            item = str(self.geounits[item].id)
            self.plan.add_geounits((i + 1), [item], geolevelid, i)

        # added four new versions

        newversion = self.plan.version
        self.assertEqual(
            13, newversion,
            'Adding items to sequential positions in history resulted in the' +
            ' wrong number of versions. (e:17,a:%d)' % newversion)

        # the first step back in history shoulde be version 4, since the
        # last edit was off that version

        previous = self.plan.get_nth_previous_version(1)
        self.assertEqual(
            5, previous,
            'The previous version is incorrect, since edits were performed off'
            + ' of 8,7,6,5 versions, with the last edit being off of version' +
            ' 5. (e:5, a:%d)' % previous)

        previous = self.plan.get_nth_previous_version(3)
        self.assertEqual(3, previous, '(e:3, a:%d)' % previous)

        previous = self.plan.get_nth_previous_version(5)
        self.assertEqual(1, previous, '(e:1, a:%d)' % previous)
