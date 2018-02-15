from base import BaseTestCase

import os
import zipfile
from django.test.client import Client
from redistricting.models import Geolevel, Geounit, District, Plan, Subject
from redistricting.tasks import DistrictIndexFile
from redistricting.calculators import (Range, Equipopulation, Equivalence,
                                       Interval, MultiMember)
import json


class MultiMemberTestCase(BaseTestCase):
    """
    Unit tests to multi-member districts

    Note: this test is separated out, and in a single method, because
    of hard-to-track down segfault problems most likely related to
    fixtures and performing posts with the Client component. When these
    problems are worked out, the tests should be broken out into more
    methods.
    """

    fixtures = [
        'redistricting_testdata.json', 'redistricting_testdata_geolevel2.json',
        'redistricting_testdata_geolevel3.json'
    ]

    def setUp(self):
        super(MultiMemberTestCase, self).setUp()
        self.geolevel = Geolevel.objects.get(name='middle level')
        self.geolevels = Geolevel.objects.all().order_by('-id')

        self.geounits = {}
        for gl in self.geolevels:
            self.geounits[gl.id] = list(
                Geounit.objects.filter(geolevel=gl).order_by('id'))

        # Set up new districts for testing
        self.district10 = District(
            long_label='District 10', version=0, district_id=10)
        self.district10.plan = self.plan
        self.district10.simplify()

        self.district11 = District(
            long_label='District 11', version=0, district_id=11)
        self.district11.plan = self.plan
        self.district11.simplify()

        district = self.district10
        districtid = district.id
        self.district_id = district.district_id
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]

        # Login
        self.client = Client()
        self.client.login(username=self.username, password=self.password)

        # Add some geounits
        dist10ids = [geounits[11]]
        dist10ids = map(lambda x: str(x.id), dist10ids)
        self.plan.add_geounits(self.district10.district_id, dist10ids,
                               geolevelid, self.plan.version)
        self.plan = Plan.objects.get(pk=self.plan.id)

        dist11ids = [geounits[22]]
        dist11ids = map(lambda x: str(x.id), dist11ids)
        self.plan.add_geounits(self.district11.district_id, dist11ids,
                               geolevelid, self.plan.version)
        self.plan = Plan.objects.get(pk=self.plan.id)
        self.subject1 = Subject.objects.get(name='TestSubject')

    def tearDown(self):
        self.plan = None
        self.district1 = None
        self.district2 = None
        self.subject1 = None
        self.geolevel = None
        self.geolevels = None
        self.geounits = None
        try:
            super(MultiMemberTestCase, self).tearDown()
        except:
            import traceback
            print(traceback.format_exc())
            print('Couldn\'t tear down')

    def set_multi(self):
        """
        Helper to turn a district into a multi-member district
        """
        self.plan.legislative_body.multi_members_allowed = True
        self.plan.legislative_body.save()
        params = {
            'version': self.plan.version,
            'counts[]': 5,
            'districts[]': self.district_id
        }
        self.client.post(
            '/districtmapping/plan/%d/districtmembers/' % self.plan.id, params)
        self.district10 = max(
            District.objects.filter(
                plan=self.plan, district_id=self.district10.district_id),
            key=lambda d: d.version)
        self.plan = Plan.objects.get(pk=self.plan.id)

    def test_multi_basic(self):
        """
        Test the logic for modifying the number of members in a district
        Also tests magnitudes in export process and calculators
        """
        # Issue command to assign 5 members to a district for a legislative
        # body that doesn't support multi-members
        # Should fail
        params = {
            'version': self.plan.version,
            'counts[]': 5,
            'districts[]': self.district_id
        }
        response = self.client.post(
            '/districtmapping/plan/%d/districtmembers/' % self.plan.id, params)

        resp_obj = json.loads(response.content)
        self.assertFalse(
            resp_obj['success'],
            'Member assign request for disallowed legbody wasn\'t denied: ' +
            str(response))

        # Verify the number of members is 1
        num = self.district10.num_members
        self.assertEqual(1, num, '# members is incorrect: %d' % num)

        # Verify the version number is 2
        num = self.plan.version
        self.assertEqual(2, num, 'version number is incorrect: %d' % num)

        # Modify the legislative body, so that it does support multi-members,
        # and reissue the request
        # Should pass
        self.plan.legislative_body.multi_members_allowed = True
        self.plan.legislative_body.save()
        params = {
            'version': self.plan.version,
            'counts[]': 5,
            'districts[]': self.district_id
        }
        response = self.client.post(
            '/districtmapping/plan/%d/districtmembers/' % self.plan.id, params)
        resp_obj = json.loads(response.content)
        self.assertTrue(
            resp_obj['success'],
            'Member assign request for allowed legbody was denied: ' +
            str(response))
        self.assertEqual(
            1, resp_obj['modified'],
            '# districts modified was incorrect: %d' % resp_obj['modified'])

        # Verify the number of members and version number have been updated
        self.district10 = max(
            District.objects.filter(
                plan=self.plan, district_id=self.district10.district_id),
            key=lambda d: d.version)
        num = self.district10.num_members
        self.assertEqual(5, num, '# members is incorrect: %d' % num)
        num = self.district10.version
        self.assertEqual(3, num, 'version number is incorrect: %d' % num)

    def test_multi_2(self):
        """
        Verify number of members is added to the exported file
        """
        self.set_multi()

        archive = DistrictIndexFile.plan2index(self.plan.pk)
        zin = zipfile.ZipFile(archive, "r")
        strz = zin.read(self.plan.name + ".csv")
        zin.close()
        os.remove(archive)
        self.assertTrue(strz.count(','), 36)

    def test_multi_range(self):
        """
        Test range calculator
        """
        self.set_multi()

        # Verify range calculator accounts for member magnitude
        # First don't apply multi-member magnitude
        # Value of subject is 2, so we should be within the range
        rngcalc = Range()
        rngcalc.arg_dict['value'] = (
            'subject',
            self.subject1.name,
        )
        rngcalc.arg_dict['min'] = (
            'literal',
            '1',
        )
        rngcalc.arg_dict['max'] = (
            'literal',
            '3',
        )
        rngcalc.arg_dict['apply_num_members'] = (
            'literal',
            '0',
        )
        rngcalc.compute(district=self.district10)
        actual = rngcalc.result['value']
        expected = 1
        self.assertEqual(expected, actual,
                         'Incorrect value during range. (e:%s,a:%s)' %
                         (expected, actual))

        # Now apply multi-member magnitude
        # There are 5 members, so the range would need to be 5x smaller
        rngcalc = Range()
        rngcalc.arg_dict['value'] = (
            'subject',
            self.subject1.name,
        )
        rngcalc.arg_dict['min'] = (
            'literal',
            '0',
        )
        rngcalc.arg_dict['max'] = (
            'literal',
            '1',
        )
        rngcalc.arg_dict['apply_num_members'] = (
            'literal',
            '1',
        )
        rngcalc.compute(district=self.district10)
        actual = rngcalc.result['value']
        expected = 1
        self.assertEqual(expected, actual,
                         'Incorrect value during range. (e:%s,a:%s)' %
                         (expected, actual))

    def test_multi_equipopulation(self):
        """
        Test equipopulation calculator
        """
        self.set_multi()

        # Verify equipopulation calculator accounts for member magnitude
        # First don't apply multi-member magnitude
        # Value of subjects are 2 and 4, so we should be within the range
        equipopcalc = Equipopulation()
        equipopcalc.arg_dict['value'] = (
            'subject',
            self.subject1.name,
        )
        equipopcalc.arg_dict['min'] = (
            'literal',
            '1',
        )
        equipopcalc.arg_dict['max'] = (
            'literal',
            '5',
        )
        equipopcalc.arg_dict['apply_num_members'] = (
            'literal',
            '0',
        )
        equipopcalc.compute(plan=self.plan)
        actual = equipopcalc.result['value']
        expected = 2
        self.assertEqual(expected, actual,
                         'Incorrect value during range. (e:%s,a:%s)' %
                         (expected, actual))

        # Now apply multi-member magnitude
        # There are 5 members in one of the districts, so the range would need
        # to be 5x smaller for that one
        equipopcalc = Equipopulation()
        equipopcalc.arg_dict['value'] = (
            'subject',
            self.subject1.name,
        )
        equipopcalc.arg_dict['min'] = (
            'literal',
            '1',
        )
        equipopcalc.arg_dict['max'] = (
            'literal',
            '10',
        )
        equipopcalc.arg_dict['apply_num_members'] = (
            'literal',
            '1',
        )
        equipopcalc.compute(plan=self.plan)
        actual = equipopcalc.result['value']
        expected = True
        self.assertEqual(expected, actual,
                         'Incorrect value during range. (e:%s,a:%s)' %
                         (expected, actual))

    def test_multi_equivalence(self):
        """
        Test equivalence calculator
        """
        self.set_multi()

        # Verify equivalence calculator accounts for member magnitude
        # First don't apply multi-member magnitude
        # min is 2,  max is 4. diff should be 2
        equcalc = Equivalence()
        equcalc.arg_dict['value'] = (
            'subject',
            self.subject1.name,
        )
        equcalc.arg_dict['apply_num_members'] = (
            'literal',
            '0',
        )
        equcalc.compute(plan=self.plan)
        actual = equcalc.result['value']
        expected = 2.0
        self.assertEqual(expected, actual,
                         'Incorrect value during equivalence. (e:%f,a:%f)' %
                         (expected, actual))

        # Now apply multi-member magnitude
        # min is 0.4 (2/5),  max is 4. diff should be 3.6
        equcalc = Equivalence()
        equcalc.arg_dict['value'] = (
            'subject',
            self.subject1.name,
        )
        equcalc.arg_dict['apply_num_members'] = (
            'literal',
            '1',
        )
        equcalc.compute(plan=self.plan)
        actual = equcalc.result['value']
        expected = 3.6
        self.assertAlmostEquals(
            expected, actual, 3,
            'Incorrect value during equivalence. (e:%f,a:%f)' % (expected,
                                                                 actual))

    def test_multi_interval(self):
        """
        Test interval calculator
        """
        self.set_multi()

        # Verify interval calculator accounts for member magnitude
        interval = Interval()
        interval.arg_dict['subject'] = ('subject', self.subject1.name)
        interval.arg_dict['apply_num_members'] = (
            'literal',
            '0',
        )
        interval.arg_dict['target'] = ('literal', 6)
        interval.arg_dict['bound1'] = ('literal', .10)
        interval.arg_dict['bound2'] = ('literal', .20)

        # Value of 2 for district 1.  Should be in the middle
        interval.compute(district=self.district10)
        self.assertEqual(2, interval.result['value'],
                         "Incorrect interval returned: e:%d,a:%d" %
                         (2, interval.result['value']))
        interval.compute(plan=self.plan)
        self.assertEqual(0, interval.result['value'],
                         "Incorrect interval returned: e:%d,a:%d" %
                         (0, interval.result['value']))

        # Now apply multi-member magnitude
        interval = Interval()
        interval.arg_dict['subject'] = ('subject', self.subject1.name)
        interval.arg_dict['apply_num_members'] = (
            'literal',
            '1',
        )
        interval.arg_dict['target'] = ('literal', 1.2)
        interval.arg_dict['bound1'] = ('literal', .10)
        interval.arg_dict['bound2'] = ('literal', .20)

        # Value of 0.2 for district 1.  Should be in the middle
        interval.compute(district=self.district10)
        self.assertAlmostEqual(0.4, float(interval.result['value']), 2,
                               "Incorrect interval returned: e:%d,a:%d" %
                               (0.4, interval.result['value']))

    def test_multi_validation(self):
        """
        Perform MultiMember validation
        """
        self.set_multi()

        self.plan.legislative_body.min_multi_district_members = 3
        self.plan.legislative_body.max_multi_district_members = 6
        self.plan.legislative_body.min_multi_districts = 1
        self.plan.legislative_body.max_multi_districts = 2
        self.plan.legislative_body.min_plan_members = 6
        self.plan.legislative_body.max_plan_members = 8
        self.plan.legislative_body.save()

        multicalc = MultiMember()
        multicalc.compute(plan=self.plan)
        self.assertTrue(multicalc.result['value'],
                        "Multi-member district should have been valid")

        self.plan.legislative_body.min_multi_districts = 2
        self.plan.legislative_body.save()
        multicalc.compute(plan=self.plan)
        self.assertFalse(multicalc.result['value'],
                         "Should be not enough multi-member districts")

        self.plan.legislative_body.min_multi_districts = 1
        self.plan.legislative_body.min_plan_members = 7
        self.plan.legislative_body.save()
        multicalc.compute(plan=self.plan)
        self.assertFalse(multicalc.result['value'],
                         "Should be not enough plan members")

        self.plan.legislative_body.min_plan_members = 6
        self.plan.legislative_body.min_multi_district_members = 6
        self.plan.legislative_body.save()
        multicalc.compute(plan=self.plan)
        self.assertFalse(
            multicalc.result['value'],
            "Should be not enough members per multi-member district")
