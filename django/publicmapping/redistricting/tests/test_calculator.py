from base import BaseTestCase

from django.db.models import Sum
from django.contrib.gis.geos import Polygon, Point
from math import sin, cos, pi
from redistricting.models import (Geolevel, Subject, Characteristic, District,
                                  ContiguityOverride)
from redistricting.calculators import (
    SumValues, Percent, Threshold, Range, Schwartzberg, Roeck, Average,
    PolsbyPopper, ConvexHullRatio, SplitCounter, DistrictSplitCounter,
    Interval, MajorityMinority, Equipopulation, Contiguity, Competitiveness,
    LengthWidthCompactness, Equivalence, RepresentationalFairness,
    CountDistricts)
from copy import copy


class CalculatorTestCase(BaseTestCase):

    fixtures = [
        'redistricting_testdata.json', 'redistricting_testdata_geolevel2.json'
    ]

    def setUp(self):
        super(CalculatorTestCase, self).setUp()
        self.geolevel = Geolevel.objects.get(name='middle level')
        self.geounits = list(self.geolevel.geounit_set.all().order_by('id'))
        self.subject1 = Subject.objects.get(name='TestSubject')
        self.subject2 = Subject.objects.get(name='TestSubject2')

    def tearDown(self):
        self.geolevel = None
        self.geounits = None
        self.subject1 = None
        self.subject2 = None
        super(CalculatorTestCase, self).tearDown()

    def test_sum1(self):
        sum1 = SumValues()
        sum1.arg_dict['value1'] = (
            'literal',
            '10',
        )
        sum1.arg_dict['value2'] = (
            'literal',
            '20',
        )

        self.assertEqual(None, sum1.result)
        sum1.compute(district=self.district1)
        self.assertEqual(30, sum1.result['value'])

        sum2 = SumValues()

        self.assertEqual(None, sum2.result)
        self.assertEqual(30, sum1.result['value'])

        sum2.compute(district=self.district1)

        self.assertEqual(0, sum2.result['value'])
        self.assertEqual(30, sum1.result['value'])

    def test_sum2a(self):
        sumcalc = SumValues()
        sumcalc.arg_dict['value1'] = (
            'literal',
            '0',
        )
        sumcalc.arg_dict['value2'] = (
            'literal',
            '1',
        )
        sumcalc.arg_dict['value3'] = (
            'literal',
            '2',
        )
        sumcalc.compute(plan=self.plan)

        self.assertEqual(3, sumcalc.result['value'],
                         'Incorrect value during summation. (e:%d,a:%d)' %
                         (3, sumcalc.result['value']))

    def test_sum2b(self):
        sumcalc = SumValues()
        sumcalc.arg_dict['value1'] = (
            'literal',
            '0',
        )
        sumcalc.arg_dict['value2'] = (
            'literal',
            '1',
        )
        sumcalc.arg_dict['value3'] = (
            'literal',
            '2',
        )
        sumcalc.compute(district=self.district1)

        self.assertEqual(3, sumcalc.result['value'],
                         'Incorrect value during summation. (e:%d,a:%d)' %
                         (3, sumcalc.result['value']))

    def test_sum3(self):
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        exqset = Characteristic.objects.filter(
            geounit__in=dist1ids, subject=self.subject1)
        expected = float(exqset.aggregate(Sum('number'))['number__sum']) + 5.0

        dist1ids = map(lambda x: str(x.id), dist1ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(
            district_id=self.district1.district_id, version=self.plan.version)

        sumcalc = SumValues()
        sumcalc.arg_dict['value1'] = (
            'subject',
            self.subject1.name,
        )
        sumcalc.arg_dict['value2'] = (
            'literal',
            '5.0',
        )
        sumcalc.compute(district=district1)

        actual = float(sumcalc.result['value'])
        self.assertEqual(
            expected, actual,
            'Incorrect value during summation. (e:%s-%d,a:%s-%d)' %
            (type(expected), expected, type(actual), actual))

    def test_sum4(self):
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        exqset = Characteristic.objects.filter(
            geounit__in=dist1ids, subject=self.subject1)
        expected = float(exqset.aggregate(Sum('number'))['number__sum'])

        dist1ids = map(lambda x: str(x.id), dist1ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(
            district_id=self.district1.district_id, version=self.plan.version)

        sumcalc = SumValues()
        sumcalc.arg_dict['value1'] = (
            'subject',
            self.subject1.name,
        )
        sumcalc.compute(district=district1)

        actual = float(sumcalc.result['value'])
        self.assertAlmostEquals(
            expected, actual, 8,
            'Incorrect value during summation. (e:%d,a:%d)' % (expected,
                                                               actual))

    def test_sum5(self):
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[18:21] + self.geounits[27:
                                                        30] + self.geounits[36:
                                                                            39]
        exqset = Characteristic.objects.filter(
            geounit__in=dist1ids + dist2ids, subject=self.subject1)
        expected = float(exqset.aggregate(Sum('number'))['number__sum'])

        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids,
                               self.geolevel.id, self.plan.version)

        sumcalc = SumValues()
        sumcalc.arg_dict['value1'] = (
            'subject',
            self.subject1.name,
        )
        sumcalc.compute(plan=self.plan)

        # Unassigned district has a value of -6, take that into account.
        actual = float(sumcalc.result['value']) + 6
        self.assertAlmostEquals(
            expected, actual, 8,
            'Incorrect value during summation. (e:%d,a:%d)' % (expected,
                                                               actual))

    def test_sum_negative_subject(self):
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        exqset = Characteristic.objects.filter(
            geounit__in=dist1ids, subject=self.subject1)
        expected = 5.0 - float(exqset.aggregate(Sum('number'))['number__sum'])

        dist1ids = map(lambda x: str(x.id), dist1ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(
            district_id=self.district1.district_id, version=self.plan.version)

        sumcalc = SumValues()
        sumcalc.arg_dict['value1'] = (
            'subject',
            '-' + self.subject1.name,
        )
        sumcalc.arg_dict['value2'] = (
            'literal',
            '5.0',
        )
        sumcalc.compute(district=district1)

        actual = float(sumcalc.result['value'])
        self.assertEqual(
            expected, actual,
            'Incorrect value during summation. (e:%s-%d,a:%s-%d)' %
            (type(expected), expected, type(actual), actual))

    def test_sum_negative_subject2(self):
        dist1ids = self.geounits[0:3] + self.geounits[9:12]

        dist1ids = map(lambda x: str(x.id), dist1ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(
            district_id=self.district1.district_id, version=self.plan.version)

        sumcalc = SumValues()
        sumcalc.arg_dict['value1'] = (
            'subject',
            '-' + self.subject1.name,
        )
        sumcalc.arg_dict['value2'] = ('subject', self.subject1.name)
        sumcalc.compute(district=district1)

        expected = 0
        actual = float(sumcalc.result['value'])
        self.assertEqual(
            expected, actual,
            'Incorrect value during summation. (e:%s-%d,a:%s-%d)' %
            (type(expected), expected, type(actual), actual))

    def test_percent1(self):
        pctcalc = Percent()
        pctcalc.arg_dict['numerator'] = (
            'literal',
            '1',
        )
        pctcalc.arg_dict['denominator'] = (
            'literal',
            '2',
        )
        pctcalc.compute(district=self.district1)

        actual = float(pctcalc.result['value'])
        self.assertAlmostEquals(
            0.5, actual, 8,
            'Incorrect value during percentage. (e:%d,a:%d)' % (
                0.5,
                actual,
            ))

    def test_percent2(self):
        pctcalc = Percent()
        pctcalc.arg_dict['numerator'] = (
            'literal',
            '2',
        )
        pctcalc.arg_dict['denominator'] = (
            'literal',
            '4',
        )
        pctcalc.compute(district=self.district1)

        actual = float(pctcalc.result['value'])
        self.assertAlmostEquals(
            0.5, actual, 8,
            'Incorrect value during percentage. (e:%d,a:%d)' % (
                0.5,
                actual,
            ))

    def test_percent3(self):
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        exqset = Characteristic.objects.filter(
            geounit__in=dist1ids, subject=self.subject1)
        expected = float(exqset.aggregate(Sum('number'))['number__sum']) / 10.0

        dist1ids = map(lambda x: str(x.id), dist1ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(
            district_id=self.district1.district_id, version=self.plan.version)

        pctcalc = Percent()
        pctcalc.arg_dict['numerator'] = (
            'subject',
            self.subject1.name,
        )
        pctcalc.arg_dict['denominator'] = (
            'literal',
            '10.0',
        )
        pctcalc.compute(district=district1)

        actual = float(pctcalc.result['value'])
        self.assertAlmostEquals(
            expected, actual, 8,
            'Incorrect value during percentage. (e:%f,a:%f)' % (expected,
                                                                actual))

    def test_percent4(self):
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[18:21] + self.geounits[27:
                                                        30] + self.geounits[36:
                                                                            39]

        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.filter(
            district_id=self.district1.district_id,
            version=self.plan.version)[0]
        expected = float(
            district1.computedcharacteristic_set.filter(
                subject=self.subject1)[0].number)

        self.plan.add_geounits(self.district2.district_id, dist2ids,
                               self.geolevel.id, self.plan.version)
        district2 = self.plan.district_set.filter(
            district_id=self.district2.district_id,
            version=self.plan.version)[0]
        expected += float(
            district2.computedcharacteristic_set.filter(
                subject=self.subject1)[0].number)

        expected = expected / 20

        pctcalc = Percent()
        pctcalc.arg_dict['numerator'] = (
            'subject',
            self.subject1.name,
        )
        pctcalc.arg_dict['denominator'] = (
            'literal',
            '10.0',
        )
        pctcalc.compute(plan=self.plan)

        actual = float(pctcalc.result['value'])
        self.assertAlmostEquals(
            expected, actual, 8,
            'Incorrect value during percentage. (e:%f,a:%f)' % (expected,
                                                                actual))

    def test_percent5(self):
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[18:21] + self.geounits[27:
                                                        30] + self.geounits[36:
                                                                            39]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids,
                               self.geolevel.id, self.plan.version)

        pctcalc = Percent()
        pctcalc.arg_dict['numerator'] = (
            'subject',
            self.subject1.name,
        )
        pctcalc.arg_dict['denominator'] = (
            'subject',
            self.subject1.name,
        )
        pctcalc.compute(plan=self.plan)

        actual = float(pctcalc.result['value'])
        self.assertAlmostEquals(
            1.0, actual, 8,
            'Incorrect value during percentage. (e:%f,a:%f)' % (1.0, actual))

    def test_threshold1(self):
        thrcalc = Threshold()
        thrcalc.arg_dict['value'] = (
            'literal',
            '1',
        )
        thrcalc.arg_dict['threshold'] = (
            'literal',
            '2',
        )
        thrcalc.compute(district=self.district1)

        self.assertEqual(0, thrcalc.result['value'],
                         'Incorrect value during threshold. (e:%s,a:%s)' %
                         (0, thrcalc.result['value']))

    def test_threshold2(self):
        thrcalc = Threshold()
        thrcalc.arg_dict['value'] = (
            'literal',
            '2',
        )
        thrcalc.arg_dict['threshold'] = (
            'literal',
            '1',
        )
        thrcalc.compute(district=self.district1)

        self.assertEqual(1, thrcalc.result['value'],
                         'Incorrect value during threshold. (e:%s,a:%s)' %
                         (1, thrcalc.result['value']))

    def test_threshold3(self):
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        exqset = Characteristic.objects.filter(
            geounit__in=dist1ids, subject=self.subject1)
        expected = float(exqset.aggregate(Sum('number'))['number__sum']) > 10.0
        expected = 1 if expected else 0

        dist1ids = map(lambda x: str(x.id), dist1ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(
            district_id=self.district1.district_id, version=self.plan.version)

        thrcalc = Threshold()
        thrcalc.arg_dict['value'] = (
            'subject',
            self.subject1.name,
        )
        thrcalc.arg_dict['threshold'] = (
            'literal',
            '10.0',
        )
        thrcalc.compute(district=district1)

        actual = thrcalc.result['value']
        self.assertEqual(expected, actual,
                         'Incorrect value during threshold. (e:%s,a:%s)' %
                         (expected, actual))

    def test_threshold4(self):
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        exqset = Characteristic.objects.filter(
            geounit__in=dist1ids, subject=self.subject1)
        expected = float(exqset.aggregate(Sum('number'))['number__sum']) > 5.0
        expected = 1 if expected else 0

        dist1ids = map(lambda x: str(x.id), dist1ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(
            district_id=self.district1.district_id, version=self.plan.version)

        thrcalc = Threshold()
        thrcalc.arg_dict['value'] = (
            'subject',
            self.subject1.name,
        )
        thrcalc.arg_dict['threshold'] = (
            'literal',
            '5.0',
        )
        thrcalc.compute(district=district1)

        actual = thrcalc.result['value']
        self.assertEqual(expected, actual,
                         'Incorrect value during threshold. (e:%s,a:%s)' %
                         (expected, actual))

    def test_threshold_plan1(self):
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[18:21] + self.geounits[27:
                                                        30] + self.geounits[36:
                                                                            39]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids,
                               self.geolevel.id, self.plan.version)

        thrcalc = Threshold()
        thrcalc.arg_dict['value'] = (
            'subject',
            self.subject1.name,
        )
        thrcalc.arg_dict['threshold'] = (
            'literal',
            '10.0',
        )
        thrcalc.compute(plan=self.plan)

        actual = thrcalc.result['value']
        self.assertEqual(0, actual,
                         'Incorrect value during threshold. (e:%d,a:%d)' %
                         (0, actual))

        thrcalc.arg_dict['threshold'] = (
            'literal',
            '7.0',
        )
        thrcalc.compute(plan=self.plan)

        actual = thrcalc.result['value']
        self.assertEqual(1, actual,
                         'Incorrect value during threshold. (e:%d,a:%d)' %
                         (1, actual))

        thrcalc.arg_dict['threshold'] = (
            'literal',
            '5.0',
        )
        thrcalc.compute(plan=self.plan)

        actual = thrcalc.result['value']
        self.assertEqual(2, actual,
                         'Incorrect value during threshold. (e:%d,a:%d)' %
                         (2, actual))

    def test_range1(self):
        rngcalc = Range()
        rngcalc.arg_dict['value'] = (
            'literal',
            '2',
        )
        rngcalc.arg_dict['min'] = (
            'literal',
            '1',
        )
        rngcalc.arg_dict['max'] = (
            'literal',
            '3',
        )
        rngcalc.compute(district=self.district1)

        self.assertEqual(1, rngcalc.result['value'],
                         'Incorrect value during range. (e:%s,a:%s)' %
                         (1, rngcalc.result['value']))

    def test_range2(self):
        rngcalc = Range()
        rngcalc.arg_dict['value'] = (
            'literal',
            '1',
        )
        rngcalc.arg_dict['min'] = (
            'literal',
            '2',
        )
        rngcalc.arg_dict['max'] = (
            'literal',
            '3',
        )
        rngcalc.compute(district=self.district1)

        self.assertEqual(0, rngcalc.result['value'],
                         'Incorrect value during range. (e:%s,a:%s)' %
                         (0, rngcalc.result['value']))

    def test_range3(self):
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        exqset = Characteristic.objects.filter(
            geounit__in=dist1ids, subject=self.subject1)
        expected = float(exqset.aggregate(Sum('number'))['number__sum'])
        expected = 1 if 5.0 < expected and expected < 10.0 else 0

        dist1ids = map(lambda x: str(x.id), dist1ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(
            district_id=self.district1.district_id, version=self.plan.version)

        rngcalc = Range()
        rngcalc.arg_dict['value'] = (
            'subject',
            self.subject1.name,
        )
        rngcalc.arg_dict['min'] = (
            'literal',
            '5.0',
        )
        rngcalc.arg_dict['max'] = (
            'literal',
            '10.0',
        )
        rngcalc.compute(district=district1)

        actual = rngcalc.result['value']
        self.assertEqual(expected, actual,
                         'Incorrect value during range. (e:%s,a:%s)' %
                         (expected, actual))

    def test_range4(self):
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        exqset = Characteristic.objects.filter(
            geounit__in=dist1ids, subject=self.subject1)
        expected = float(exqset.aggregate(Sum('number'))['number__sum'])
        expected = 1 if 1.0 < expected and expected < 5.0 else 0

        dist1ids = map(lambda x: str(x.id), dist1ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(
            district_id=self.district1.district_id, version=self.plan.version)

        rngcalc = Range()
        rngcalc.arg_dict['value'] = (
            'subject',
            self.subject1.name,
        )
        rngcalc.arg_dict['min'] = (
            'literal',
            '1.0',
        )
        rngcalc.arg_dict['max'] = (
            'literal',
            '5.0',
        )
        rngcalc.compute(district=district1)

        actual = rngcalc.result['value']
        self.assertEqual(expected, actual,
                         'Incorrect value during range. (e:%s,a:%s)' %
                         (expected, actual))

    def test_range_plan1(self):
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[18:21] + self.geounits[27:
                                                        30] + self.geounits[36:
                                                                            39]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids,
                               self.geolevel.id, self.plan.version)

        rngcalc = Range()
        rngcalc.arg_dict['value'] = (
            'subject',
            self.subject1.name,
        )
        rngcalc.arg_dict['min'] = (
            'literal',
            '7.0',
        )
        rngcalc.arg_dict['max'] = (
            'literal',
            '11.0',
        )
        rngcalc.compute(plan=self.plan)

        actual = rngcalc.result['value']
        expected = 1

        self.assertEqual(expected, actual,
                         'Incorrect value during Plan range. (e:%d,a:%d)' %
                         (expected, actual))

    def test_schwartzberg(self):
        """
        Test the Schwartzberg measure of compactness.
        """
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[18:21] + self.geounits[27:
                                                        30] + self.geounits[36:
                                                                            39]

        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids,
                               self.geolevel.id, self.plan.version)

        district1 = max(
            District.objects.filter(
                plan=self.plan, district_id=self.district1.district_id),
            key=lambda d: d.version)
        district2 = max(
            District.objects.filter(
                plan=self.plan, district_id=self.district2.district_id),
            key=lambda d: d.version)

        calc = Schwartzberg()

        calc.compute(district=district1)
        self.assertAlmostEquals(0.86832150547, calc.result['value'], 9,
                                'Schwartzberg for District 1 was incorrect: %d'
                                % calc.result['value'])

        calc.compute(district=district2)
        self.assertAlmostEquals(0.88622692545, calc.result['value'], 9,
                                'Schwartzberg for District 2 was incorrect: %d'
                                % calc.result['value'])

    def test_schwartzberg1(self):
        """
        Test the Schwartzberg measure of compactness.
        """
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[18:21] + self.geounits[27:
                                                        30] + self.geounits[36:
                                                                            39]

        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids,
                               self.geolevel.id, self.plan.version)

        district1 = max(
            District.objects.filter(
                plan=self.plan, district_id=self.district1.district_id),
            key=lambda d: d.version)
        district2 = max(
            District.objects.filter(
                plan=self.plan, district_id=self.district2.district_id),
            key=lambda d: d.version)

        calc = Schwartzberg()

        calc.compute(plan=self.plan)
        self.assertAlmostEquals(0.87727421546, calc.result['value'], 9,
                                'Schwartzberg for District 1 was incorrect: %f'
                                % calc.result['value'])

    def test_roeck(self):
        """
        Test the Roeck measure of compactness.
        """
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[18:21] + self.geounits[27:
                                                        30] + self.geounits[36:
                                                                            39]

        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids,
                               self.geolevel.id, self.plan.version)

        district1 = max(
            District.objects.filter(
                plan=self.plan, district_id=self.district1.district_id),
            key=lambda d: d.version)
        district2 = max(
            District.objects.filter(
                plan=self.plan, district_id=self.district2.district_id),
            key=lambda d: d.version)

        calc = Roeck()

        calc.compute(district=district1)
        expected = 0.587649
        self.assertAlmostEquals(
            expected, calc.result['value'], 6,
            'Roeck for District 1 was incorrect. (e:%0.6f,a:%0.6f)' %
            (expected, calc.result['value']))

        calc.compute(district=district2)
        expected = 0.636620
        self.assertAlmostEquals(
            expected, calc.result['value'], 6,
            'Roeck for District 2 was incorrect. (e:%0.6f,a:%0.6f)' %
            (expected, calc.result['value']))

    def test_roeck1(self):
        """
        Test the Roeck measure of compactness.
        """
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[18:21] + self.geounits[27:
                                                        30] + self.geounits[36:
                                                                            39]

        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids,
                               self.geolevel.id, self.plan.version)

        district1 = max(
            District.objects.filter(
                plan=self.plan, district_id=self.district1.district_id),
            key=lambda d: d.version)
        district2 = max(
            District.objects.filter(
                plan=self.plan, district_id=self.district2.district_id),
            key=lambda d: d.version)

        calc = Roeck()

        calc.compute(plan=self.plan)
        expected = (0.636620 + 0.587649) / 2
        self.assertAlmostEquals(
            expected, calc.result['value'], 6,
            'Roeck for plan was incorrect. (e:%0.6f,a:%0.6f)' %
            (expected, calc.result['value']))

    def test_roeck2(self):
        """
        Test the Roeck measure with a half-circle.
        """
        dist = 30
        coords = []
        for i in range(-dist, dist + 1):
            coords.append(
                Point(cos(pi * i / dist / 2.0), sin(pi * i / dist / 2.0)))

        pcoords = copy(coords)
        pcoords.append(pcoords[0])

        calc = Roeck()
        disk = calc.minidisk(coords)

        poly = Polygon(pcoords)

        parea = poly.area
        darea = pi * disk.r * disk.r

        # Testing to 3 decimal places, since this is an approximation of
        # the circle's area -- actual ratio is 0.50014
        self.assertAlmostEquals(
            0.5, parea / darea, 3,
            'Roeck half-circle district was incorrect. (e:%0.6f,a:%0.6f)' %
            (0.5, parea / darea))

    def test_polsbypopper(self):
        """
        Test the Polsby-Popper measure of compactness.
        """
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[18:21] + self.geounits[27:
                                                        30] + self.geounits[36:
                                                                            39]

        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids,
                               self.geolevel.id, self.plan.version)

        district1 = max(
            District.objects.filter(
                plan=self.plan, district_id=self.district1.district_id),
            key=lambda d: d.version)
        district2 = max(
            District.objects.filter(
                plan=self.plan, district_id=self.district2.district_id),
            key=lambda d: d.version)

        calc = PolsbyPopper()

        calc.compute(district=district1)
        expected = 0.753982
        self.assertAlmostEquals(
            expected, calc.result['value'], 6,
            'Polsby-Popper for District 1 was incorrect. (e:%0.6f,a:%0.6f)' %
            (expected, calc.result['value']))

        calc.compute(district=district2)
        expected = 0.785398
        self.assertAlmostEquals(
            expected, calc.result['value'], 6,
            'Polsby-Popper for District 2 was incorrect. (e:%0.6f,a:%0.6f)' %
            (expected, calc.result['value']))

    def test_polsbypopper1(self):
        """
        Test the Polsby-Popper measure of compactness.
        """
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[18:21] + self.geounits[27:
                                                        30] + self.geounits[36:
                                                                            39]

        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids,
                               self.geolevel.id, self.plan.version)

        district1 = max(
            District.objects.filter(
                plan=self.plan, district_id=self.district1.district_id),
            key=lambda d: d.version)
        district2 = max(
            District.objects.filter(
                plan=self.plan, district_id=self.district2.district_id),
            key=lambda d: d.version)

        calc = PolsbyPopper()

        calc.compute(plan=self.plan)
        expected = (0.753982 + 0.785398) / 2
        self.assertAlmostEquals(
            expected, calc.result['value'], 6,
            'Polsby-Popper for plan was incorrect. (e:%0.6f,a:%0.6f)' %
            (expected, calc.result['value']))

    def test_lengthwidth(self):
        """
        Test the Length/Width measure of compactness.
        """
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[18:21] + self.geounits[27:
                                                        30] + self.geounits[36:
                                                                            39]

        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids,
                               self.geolevel.id, self.plan.version)

        district1 = max(
            District.objects.filter(
                plan=self.plan, district_id=self.district1.district_id),
            key=lambda d: d.version)
        district2 = max(
            District.objects.filter(
                plan=self.plan, district_id=self.district2.district_id),
            key=lambda d: d.version)

        calc = LengthWidthCompactness()

        calc.compute(district=district1)
        expected = 0.666667
        self.assertAlmostEquals(
            expected, calc.result['value'], 6,
            'Length/Width for District 1 was incorrect. (e:%0.6f,a:%0.6f)' %
            (expected, calc.result['value']))

        calc.compute(district=district2)
        expected = 1.000000
        self.assertAlmostEquals(
            expected, calc.result['value'], 6,
            'Length/Width for District 2 was incorrect. (e:%0.6f,a:%0.6f)' %
            (expected, calc.result['value']))

    def test_lengthwidth1(self):
        """
        Test the Length/Width measure of compactness.
        """
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[18:21] + self.geounits[27:
                                                        30] + self.geounits[36:
                                                                            39]

        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids,
                               self.geolevel.id, self.plan.version)

        district1 = max(
            District.objects.filter(
                plan=self.plan, district_id=self.district1.district_id),
            key=lambda d: d.version)
        district2 = max(
            District.objects.filter(
                plan=self.plan, district_id=self.district2.district_id),
            key=lambda d: d.version)

        calc = LengthWidthCompactness()

        calc.compute(plan=self.plan)
        expected = (0.666667 + 1.000000) / 2
        self.assertAlmostEquals(
            expected, calc.result['value'], 6,
            'Length/Width for plan was incorrect. (e:%0.6f,a:%0.6f)' %
            (expected, calc.result['value']))

    def test_contiguity1(self):
        cntcalc = Contiguity()
        cntcalc.compute(district=self.district1)

        self.assertEqual(1, cntcalc.result['value'],
                         'District is not contiguous.')

    def test_contiguity2(self):
        dist1ids = self.geounits[0:3] + self.geounits[12:15]
        dist1ids = map(lambda x: str(x.id), dist1ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(
            district_id=self.district1.district_id, version=self.plan.version)

        cntcalc = Contiguity()
        cntcalc.compute(district=district1)

        self.assertEqual(0, cntcalc.result['value'], 'District is contiguous.')

    def test_contiguity3(self):
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist1ids = map(lambda x: str(x.id), dist1ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(
            district_id=self.district1.district_id, version=self.plan.version)

        cntcalc = Contiguity()
        cntcalc.compute(district=district1)

        self.assertEqual(1, cntcalc.result['value'],
                         'District is discontiguous.')

    def test_contiguity_singlepoint(self):
        dist1ids = [self.geounits[0], self.geounits[10]]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(
            district_id=self.district1.district_id, version=self.plan.version)

        # 2 geounits connected by one point -- single-point is false, should
        # fail
        cntcalc = Contiguity()
        cntcalc.arg_dict['allow_single_point'] = (
            'literal',
            '0',
        )
        cntcalc.compute(district=district1)
        self.assertEqual(
            0, cntcalc.result['value'],
            'District is contiguous at 1 point, but single-point contiguity is'
            + ' false.')

        # 2 geounits connected by one point -- single-point is true, should
        # pass
        cntcalc = Contiguity()
        cntcalc.arg_dict['allow_single_point'] = (
            'literal',
            '1',
        )
        cntcalc.compute(district=district1)
        self.assertEqual(
            1, cntcalc.result['value'],
            'District is contiguous at 1 point, and single-point contiguity is'
            + ' true.')

        # add another geounits so 3 geometries are connected by 2 single points
        # (contiguous)
        dist1ids = [self.geounits[18]]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(
            district_id=self.district1.district_id, version=self.plan.version)

        cntcalc = Contiguity()
        cntcalc.arg_dict['allow_single_point'] = (
            'literal',
            '1',
        )
        cntcalc.compute(district=district1)
        self.assertEqual(
            1, cntcalc.result['value'],
            'District is contiguous at 1 point twice, and single-point ' +
            'contiguity is true.')

        # add another geounits so 4 geometries are connected by 3 single points
        # (contiguous)
        dist1ids = [self.geounits[28]]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(
            district_id=self.district1.district_id, version=self.plan.version)

        cntcalc = Contiguity()
        cntcalc.arg_dict['allow_single_point'] = (
            'literal',
            '1',
        )
        cntcalc.compute(district=district1)
        self.assertEqual(
            1, cntcalc.result['value'],
            'District is contiguous at 1 point thrice, and single-point' +
            ' contiguity is true.')

        # add more geounits so 5 geometries are connected by 3 single points
        # (discontiguous)
        dist1ids = [self.geounits[14]]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(
            district_id=self.district1.district_id, version=self.plan.version)

        cntcalc = Contiguity()
        cntcalc.arg_dict['allow_single_point'] = (
            'literal',
            '1',
        )
        cntcalc.compute(district=district1)
        self.assertEqual(
            0, cntcalc.result['value'],
            'District is contiguous at 1 point thrice, but has a disjoint' +
            ' geometry.')

    def test_contiguity_overrides(self):
        dist1ids = [self.geounits[0], self.geounits[11]]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(
            district_id=self.district1.district_id, version=self.plan.version)

        overrides = []

        def add_override(id1, id2):
            override = ContiguityOverride(
                override_geounit=self.geounits[id1],
                connect_to_geounit=self.geounits[id2])
            override.save()
            overrides.append(override)

        # add some bogus overrides for testing
        add_override(27, 28)
        add_override(28, 29)
        add_override(29, 30)
        add_override(30, 31)
        add_override(31, 32)

        # 2 disjoint geounits and no overrides defined, should fail
        cntcalc = Contiguity()
        cntcalc.compute(district=district1)
        self.assertEqual(
            0, cntcalc.result['value'],
            'District is non-contiguous, and no overrides have been defined.')

        # define a contiguity override between the two geounits, same test
        # should now pass
        add_override(0, 11)
        cntcalc.compute(district=district1)
        self.assertEqual(
            1, cntcalc.result['value'],
            'District is not contiguous, but an override should make it so.')

        # add a few more non-contiguous geounits without overrides, should fail
        dist1ids = [self.geounits[4], self.geounits[22], self.geounits[7]]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(
            district_id=self.district1.district_id, version=self.plan.version)
        cntcalc.compute(district=district1)
        self.assertEqual(
            0, cntcalc.result['value'],
            'District needs 3 overrides to be considered contiguous')

        # add overrides and test one by one. the final override should make the
        # test pass
        add_override(11, 4)
        cntcalc.compute(district=district1)
        self.assertEqual(
            0, cntcalc.result['value'],
            'District needs 2 overrides to be considered contiguous')
        add_override(4, 22)
        cntcalc.compute(district=district1)
        self.assertEqual(
            0, cntcalc.result['value'],
            'District needs 1 overrides to be considered contiguous')
        add_override(7, 4)
        cntcalc.compute(district=district1)
        self.assertEqual(
            1, cntcalc.result['value'],
            'District has appropriate overrides to be considered contiguous')

        # check to make sure this works in conjunction with single-point
        # contiguity by adding 2 more geounits
        dist1ids = [self.geounits[14], self.geounits[19]]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(
            district_id=self.district1.district_id, version=self.plan.version)
        cntcalc.arg_dict['allow_single_point'] = (
            'literal',
            '0',
        )
        cntcalc.compute(district=district1)
        self.assertEqual(
            0, cntcalc.result['value'],
            'Calculator needs allow_single_point on to be considered' +
            ' contiguous')
        cntcalc.arg_dict['allow_single_point'] = (
            'literal',
            '1',
        )
        cntcalc.compute(district=district1)
        self.assertEqual(
            1, cntcalc.result['value'],
            'allow_single_point is enabled, should be considered contiguous')

        # remove contiguity overrides
        for override in overrides:
            override.delete()

    def test_contiguity_plan1(self):
        dist1ids = self.geounits[0:4] + self.geounits[5:9]
        dist2ids = self.geounits[9:13] + self.geounits[14:18]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids,
                               self.geolevel.id, self.plan.version)

        cntcalc = Contiguity()
        cntcalc.compute(plan=self.plan)

        actual = cntcalc.result['value']
        self.assertEqual(0, actual,
                         'Incorrect value during contiguity. (e:%d,a:%d)' %
                         (0, actual))

        self.plan.add_geounits(self.district1.district_id,
                               [str(self.geounits[4].id)], self.geolevel.id,
                               self.plan.version)

        cntcalc.compute(plan=self.plan)

        actual = cntcalc.result['value']
        self.assertEqual(1, actual,
                         'Incorrect value during contiguity. (e:%d,a:%d)' %
                         (1, actual))

        self.plan.add_geounits(self.district2.district_id,
                               [str(self.geounits[13].id)], self.geolevel.id,
                               self.plan.version)

        cntcalc.compute(plan=self.plan)

        actual = cntcalc.result['value']
        self.assertEqual(2, actual,
                         'Incorrect value during contiguity. (e:%d,a:%d)' %
                         (2, actual))

    def test_equivalence1(self):
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[18:21] + self.geounits[27:
                                                        30] + self.geounits[36:
                                                                            39]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids,
                               self.geolevel.id, self.plan.version)

        equcalc = Equivalence()
        equcalc.arg_dict['value'] = (
            'subject',
            self.subject1.name,
        )
        equcalc.compute(plan=self.plan)

        actual = equcalc.result['value']
        self.assertEqual(3.0, actual,
                         'Incorrect value during equivalence. (e:%f,a:%f)' %
                         (3.0, actual))

    def test_representationalfairness(self):
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[6:9] + self.geounits[15:18]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids,
                               self.geolevel.id, self.plan.version)

        district1 = self.plan.district_set.filter(
            district_id=self.district1.district_id,
            version=self.plan.version - 1)[0]
        district2 = self.plan.district_set.filter(
            district_id=self.district2.district_id,
            version=self.plan.version)[0]

        rfcalc = RepresentationalFairness()
        rfcalc.arg_dict['democratic'] = (
            'subject',
            self.subject1.name,
        )
        rfcalc.arg_dict['republican'] = (
            'subject',
            self.subject2.name,
        )
        rfcalc.compute(plan=self.plan)

        # If you're playing along at home, the values are:
        # District 1: 6 dem, 150 rep; District 2: 42 dem, 114 rep
        actual = rfcalc.result['value']
        self.assertEqual(
            -2, actual,
            'Wrong number of districts in RepresentationalFairness (e:%d,a:%d)'
            % (-2, actual))

        actual = rfcalc.html()
        self.assertEqual(
            '<span>Republican&nbsp;2</span>', actual,
            'Wrong party given for RepresentationalFairness (e:%s,a:%s)' %
            ('<span>Republican&nbsp;2</span>', actual))

        # Swap subjects and make sure we get the right party
        rfcalc = RepresentationalFairness()
        rfcalc.arg_dict['democratic'] = (
            'subject',
            self.subject2.name,
        )
        rfcalc.arg_dict['republican'] = (
            'subject',
            self.subject1.name,
        )
        rfcalc.compute(plan=self.plan)

        actual = rfcalc.result['value']
        self.assertEqual(
            2, actual,
            'Wrong number of districts in RepresentationalFairness (e:%d,a:%d)'
            % (2, actual))

        actual = rfcalc.html()
        self.assertEqual(
            '<span>Democrat&nbsp;2</span>', actual,
            'Wrong party given for RepresentationalFairness (e:%s,a:%s)' %
            ('<span>Democrat&nbsp;2</span>', actual))

    def test_competitiveness(self):
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[6:9] + self.geounits[15:18]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids,
                               self.geolevel.id, self.plan.version)

        # If you're playing along at home, the values are:
        # District 1: 6 dem, 150 rep; District 2: 42 dem, 114 rep
        ccalc = Competitiveness()
        ccalc.arg_dict['democratic'] = (
            'subject',
            self.subject1.name,
        )
        ccalc.arg_dict['republican'] = (
            'subject',
            self.subject2.name,
        )
        ccalc.compute(plan=self.plan)

        actual = ccalc.result['value']
        # by default, we have a range of .45 - .55.  Neither district is fair.
        self.assertEqual(
            0, actual, 'Incorrect value during competitiveness. (e:%d,a:%d)' %
            (0, actual))

        # Open up the range to .25 - .75. District 2 should be fair now
        ccalc = Competitiveness()
        ccalc.arg_dict['democratic'] = (
            'subject',
            self.subject1.name,
        )
        ccalc.arg_dict['republican'] = (
            'subject',
            self.subject2.name,
        )
        ccalc.arg_dict['range'] = (
            'literal',
            .25,
        )
        ccalc.compute(plan=self.plan)

        actual = ccalc.result['value']
        self.assertEqual(
            1, actual, 'Incorrect value during competitiveness. (e:%d,a:%d)' %
            (1, actual))

        # Open up the range to .03 - .97 (inclusive). District 1 should also be
        # fair now. Switch subjects, too.
        ccalc = Competitiveness()
        ccalc.arg_dict['democratic'] = (
            'subject',
            self.subject2.name,
        )
        ccalc.arg_dict['republican'] = (
            'subject',
            self.subject1.name,
        )
        ccalc.arg_dict['range'] = (
            'literal',
            .47,
        )
        ccalc.compute(plan=self.plan)

        actual = ccalc.result['value']
        self.assertEqual(
            2, actual, 'Incorrect value during competitiveness. (e:%d,a:%d)' %
            (2, actual))

    def test_countdist(self):
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[6:9] + self.geounits[15:18]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids,
                               self.geolevel.id, self.plan.version)

        numcalc = CountDistricts()
        numcalc.arg_dict['target'] = (
            'literal',
            '2',
        )
        numcalc.compute(plan=self.plan)

        actual = numcalc.result['value']
        self.assertEqual(
            True, actual,
            'Incorrect value during district counting. (e:%s,a:%s)' % (True,
                                                                       actual))

    def test_equipop(self):
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[6:9] + self.geounits[15:18]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids,
                               self.geolevel.id, self.plan.version)

        equicalc = Equipopulation()
        equicalc.arg_dict['value'] = (
            'subject',
            self.subject1.name,
        )
        equicalc.arg_dict['min'] = (
            'literal',
            '5',
        )
        equicalc.arg_dict['max'] = (
            'literal',
            '10',
        )
        equicalc.arg_dict['validation'] = (
            'literal',
            1,
        )
        equicalc.compute(plan=self.plan)

        actual = equicalc.result['value']
        self.assertEqual(False, actual,
                         'Incorrect value during plan equipop. (e:%s,a:%s)' %
                         (False, actual))

        equicalc.arg_dict['min'] = (
            'literal',
            '40',
        )
        equicalc.arg_dict['max'] = (
            'literal',
            '45',
        )
        equicalc.compute(plan=self.plan)

        actual = equicalc.result['value']
        self.assertEqual(False, actual,
                         'Incorrect value during plan equipop. (e:%s,a:%s)' %
                         (False, actual))

        equicalc.arg_dict['min'] = (
            'literal',
            '5',
        )
        equicalc.arg_dict['max'] = (
            'literal',
            '45',
        )
        equicalc.compute(plan=self.plan)

        actual = equicalc.result['value']
        self.assertEqual(True, actual,
                         'Incorrect value during plan equipop. (e:%s,a:%s)' %
                         (True, actual))

    def test_majmin(self):
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[18:21] + self.geounits[27:
                                                        30] + self.geounits[36:
                                                                            39]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids,
                               self.geolevel.id, self.plan.version)

        majcalc = MajorityMinority()
        majcalc.arg_dict['population'] = (
            'subject',
            self.subject1.name,
        )
        majcalc.arg_dict['count'] = (
            'literal',
            1,
        )
        majcalc.arg_dict['minority1'] = (
            'subject',
            self.subject2.name,
        )
        majcalc.arg_dict['threshold'] = (
            'literal',
            0.5,
        )
        majcalc.arg_dict['validation'] = (
            'literal',
            1,
        )
        majcalc.compute(plan=self.plan)

        actual = majcalc.result['value']
        self.assertEqual(
            True, actual,
            'Incorrect value during majority/minority. (e:%s,a:%s)' % (True,
                                                                       actual))

        majcalc.arg_dict['count'] = (
            'literal',
            1,
        )
        majcalc.arg_dict['population'] = (
            'subject',
            self.subject2.name,
        )
        majcalc.arg_dict['minority1'] = (
            'subject',
            self.subject1.name,
        )
        majcalc.arg_dict['threshold'] = (
            'literal',
            0.5,
        )
        majcalc.arg_dict['validation'] = (
            'literal',
            1,
        )
        majcalc.compute(plan=self.plan)

        actual = majcalc.result['value']
        self.assertEqual(
            False, actual,
            'Incorrect value during majority/minority. (e:%s,a:%s)' % (False,
                                                                       actual))

    def test_interval(self):
        interval = Interval()
        interval.arg_dict['subject'] = ('subject', self.subject2.name)
        interval.arg_dict['target'] = ('literal', 150)
        interval.arg_dict['bound1'] = ('literal', .50)
        interval.arg_dict['bound2'] = ('literal', .25)

        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[18:21] + self.geounits[27:
                                                        30] + self.geounits[36:
                                                                            39]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids,
                               self.geolevel.id, self.plan.version)

        # Update our districts
        for d in self.plan.get_districts_at_version(
                self.plan.version, include_geom=False):
            if (d.district_id == self.district1.district_id):
                self.district1 = d
            elif (d.district_id == self.district2.district_id):
                self.district2 = d

        # Value of 150 for district 1.  Should be in middle class - i.e. return
        # 2 on 0-based index
        interval.compute(district=self.district1)
        self.assertEqual(2, interval.result['index'],
                         "Incorrect interval returned: e:%s,a:%s" %
                         (2, interval.result['index']))
        # Value of 225 for district 1.  Should be in last class - i.e. return 4
        # on 0-based index
        interval.compute(district=self.district2)
        self.assertEqual(4, interval.result['index'],
                         "Incorrect interval returned: e:%s,a:%s" %
                         (4, interval.result['index']))

        # District 1 is in the middle class - should get a 1
        interval.compute(plan=self.plan)
        self.assertEqual(1, interval.result['value'],
                         "Incorrect interval returned: e:%s,a:%s" %
                         (1, interval.result['value']))

        # Adjust to get them all out of the target
        interval.arg_dict['bound1'] = ('literal', .1)
        interval.arg_dict['bound2'] = ('literal', .2)

        interval.compute(plan=self.plan)
        self.assertEqual(1, interval.result['value'],
                         "Incorrect interval returned: e:%s,a:%s" %
                         (1, interval.result['value']))

        # Everybody's on target
        interval.arg_dict['bound1'] = ('literal', .6)
        del interval.arg_dict['bound2']

        interval.compute(plan=self.plan)
        self.assertEqual(2, interval.result['value'],
                         "Incorrect interval returned: e:%s,a:%s" %
                         (2, interval.result['value']))

        # Everybody's over - make sure we're in group 3 (0-based index 2)
        interval.arg_dict['target'] = ('literal', 0)
        interval.compute(district=self.district2)
        self.assertEqual(2, interval.result['index'],
                         "Incorrect interval returned: e:%s,a:%s" %
                         (2, interval.result['index']))

    def test_average1(self):
        avg = Average()
        avg.arg_dict['value1'] = (
            'literal',
            '10',
        )
        avg.arg_dict['value2'] = (
            'literal',
            '20',
        )

        self.assertEqual(None, avg.result)
        avg.compute(district=self.district1)
        self.assertEqual(15, avg.result['value'])

        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[18:21] + self.geounits[27:
                                                        30] + self.geounits[36:
                                                                            39]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids,
                               self.geolevel.id, self.plan.version)

        # Update our districts
        for d in self.plan.get_districts_at_version(
                self.plan.version, include_geom=False):
            if (d.district_id == self.district1.district_id):
                self.district1 = d
            elif (d.district_id == self.district2.district_id):
                self.district2 = d

        avg = Average()
        avg.arg_dict['value1'] = ('subject', self.subject1.name)
        avg.arg_dict['value2'] = ('subject', self.subject2.name)

        self.assertEqual(None, avg.result)
        avg.compute(district=self.district1)
        self.assertEqual(78.0, avg.result['value'])

        avg = Average()
        avg.arg_dict['value1'] = ('subject', self.subject1.name)
        avg.arg_dict['value2'] = ('subject', self.subject2.name)

        self.assertEqual(None, avg.result)
        avg.compute(district=self.district2)
        self.assertEqual(117.0, avg.result['value'])

    def test_average2(self):
        avg = Average()
        avg.arg_dict['value1'] = ('literal', '10.0')
        avg.arg_dict['value2'] = ('literal', '20.0')

        self.assertEqual(None, avg.result)
        avg.compute(plan=self.plan)
        self.assertEqual(None, avg.result)

        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[18:21] + self.geounits[27:
                                                        30] + self.geounits[36:
                                                                            39]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids,
                               self.geolevel.id, self.plan.version)

        avg = Average()
        avg.arg_dict['value1'] = ('subject', self.subject1.name)
        avg.arg_dict['value2'] = ('subject', self.subject2.name)

        self.assertEqual(None, avg.result)
        avg.compute(plan=self.plan)
        self.assertEqual(97.5, avg.result['value'])

    def test_average3(self):
        avg = Average()
        avg.arg_dict['value1'] = ('literal', '10.0')
        avg.arg_dict['value2'] = ('literal', '20.0')
        avg.compute(plan=self.plan)

        # Average is 15.0, should be between 10.0 and 20.0
        self.assertEqual(None, avg.result)

        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[18:21] + self.geounits[27:
                                                        30] + self.geounits[36:
                                                                            39]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids,
                               self.geolevel.id, self.plan.version)

        avg = Average()
        avg.arg_dict['value1'] = ('subject', self.subject1.name)
        avg.arg_dict['value2'] = ('subject', self.subject2.name)
        avg.compute(plan=self.plan)

        # Average is 97.5
        self.assertEqual(97.5, avg.result['value'])

        avg = Average()
        avg.arg_dict['value1'] = ('subject', self.subject1.name)
        avg.arg_dict['value2'] = ('subject', self.subject2.name)
        avg.compute(plan=self.plan)

        # Average is 97.5, should not be beween 100.0 and 105.0
        self.assertEqual(97.5, avg.result['value'])

    def test_splitcounter(self):
        # Create a plan with two large districts - geounits 5 and 8
        geolevel = Geolevel.objects.get(name='biggest level')
        geounits = list(geolevel.geounit_set.all().order_by('id'))

        p1 = self.plan
        d1a_id = 1
        # Create a district of geounit 5
        p1.add_geounits(d1a_id, [str(geounits[4].id)], geolevel.id, p1.version)

        d2a_id = 2
        # Create a district of geounit 8
        p1.add_geounits(d2a_id, [str(geounits[7].id)], geolevel.id, p1.version)

        # Create a plan with two districts - one crosses both 5 and 8,
        p2 = self.plan2
        d1b_id = 3
        dist1ids = self.geounits[20:23] + self.geounits[29:32] + \
            self.geounits[38:41] + self.geounits[47:50] + \
            self.geounits[56:59]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        p2.add_geounits(d1b_id, dist1ids, self.geolevel.id, p2.version)

        # the other is entirely within 5
        d2b_id = 4
        dist2ids = [self.geounits[32], self.geounits[41], self.geounits[50]]
        dist2ids = map(lambda x: str(x.id), dist2ids)
        p2.add_geounits(d2b_id, dist2ids, self.geolevel.id, p2.version)

        # Calc the first plan with second as other
        calc = SplitCounter()
        calc.arg_dict['boundary_id'] = ('literal', 'plan.%d' % p2.id)
        calc.compute(plan=p1)
        num_splits = len(calc.result['value']['splits'])
        self.assertEqual(
            2, num_splits,
            'Did not find expected splits. e:2, a:%s' % num_splits)

        # Calc the second plan with first as other
        calc.__init__()
        calc.arg_dict['boundary_id'] = ('literal', 'plan.%d' % p1.id)
        calc.compute(plan=p2)
        num_splits = len(calc.result['value']['splits'])
        split_tuples = calc.result['value']['splits']
        self.assertEqual(
            3, num_splits,
            'Did not find expected splits. e:3, a:%s' % num_splits)
        self.assertTrue((3, 1, u'District 3',
                         u'District 1') in calc.result['value']['splits'],
                        'Split not detected')
        self.assertTrue({
            'geo': 'District 3',
            'interior': 'District 1',
            'split': True
        } in calc.result['value']['named_splits'], 'Split not named correctly')

        # Calc the first plan with the smallest geolevel - no splits
        geolevel = self.plan.legislative_body.get_geolevels()[2]
        calc.__init__()
        calc.arg_dict['boundary_id'] = ('literal', 'geolevel.%d' % geolevel.id)
        calc.compute(plan=p1)
        num_splits = len(calc.result['value']['splits'])
        self.assertEqual(
            0, num_splits,
            'Did not find expected splits. e:0, a:%s' % num_splits)

        # Calc the second plan with the middle geolevel - no splits
        calc.__init__()
        calc.arg_dict['boundary_id'] = ('literal',
                                        'geolevel.%d' % self.geolevel.id)
        calc.compute(plan=p2)
        num_splits = len(calc.result['value']['splits'])
        self.assertEqual(
            0, num_splits,
            'Did not find expected splits. e:0, a:%s' % num_splits)

        # Calc the second plan with biggest geolevel - d1a and d2a both split
        # the geolevels
        geolevel = self.plan.legislative_body.get_geolevels()[0]
        calc.__init__()
        calc.arg_dict['boundary_id'] = ('literal', 'geolevel.%d' % geolevel.id)
        calc.compute(plan=p2)
        district_splits = len(
            set(i[0] for i in calc.result['value']['splits']))
        self.assertEqual(
            2, district_splits,
            'Did not find expected splits. e:2, a:%s' % district_splits)
        self.assertTrue((3, u'0000004', u'District 3',
                         u'Unit 1-4') in calc.result['value']['splits'],
                        'Did not find expected splits')

        # Ensure the district split counter matches up to the plan split
        # counter
        districts = p2.get_districts_at_version(p2.version)
        dist_calc = DistrictSplitCounter()
        dist_calc.arg_dict['geolevel_id'] = ('literal', geolevel.id)
        dist_calc.compute(district=districts[0])
        result1 = dist_calc.result['value']
        dist_calc.compute(district=districts[1])
        result2 = dist_calc.result['value']
        num_dist_splits = result1 + result2
        num_plan_splits = len(calc.result['value']['splits'])
        self.assertEqual(num_plan_splits, num_dist_splits,
                         'Did not find expected district splits. e:%d, a:%d' %
                         (num_plan_splits, num_dist_splits))

    def test_convexhull_l1(self):
        """
        Test the convex hull calculator for the middle geolevel
        """
        geolevel = Geolevel.objects.get(name='middle level')
        dist1ids = list(geolevel.geounit_set.all())[0:1]
        dist1ids = map(lambda x: str(x.id), dist1ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(
            district_id=self.district1.district_id, version=self.plan.version)

        calc = ConvexHullRatio()
        calc.compute(district=district1)

        self.assertAlmostEqual(
            district1.geom.area / 0.012345679012345678,
            calc.result['value'],
            places=9)

    def test_convexhull_l2(self):
        """
        Test the convex hull calculator for the biggest geolevel
        """
        geolevel = Geolevel.objects.get(name='biggest level')
        dist1ids = list(geolevel.geounit_set.all())[0:1]
        dist1ids = map(lambda x: str(x.id), dist1ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(
            district_id=self.district1.district_id, version=self.plan.version)

        calc = ConvexHullRatio()
        calc.compute(district=district1)

        self.assertAlmostEqual(
            district1.geom.area / 0.1111111111111111,
            calc.result['value'],
            places=9)

    def test_convexhull_row(self):
        """
        Test the convex hull calculator averaging a horizontal row of 9 smaller
        geounits
        """
        dist1ids = list(self.geolevel.geounit_set.all())[0:9]
        dist1ids = map(lambda x: str(x.id), dist1ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(
            district_id=self.district1.district_id, version=self.plan.version)

        calc = ConvexHullRatio()
        calc.compute(district=district1)

        # 9 contiguous geounits at the middle level have the same area as one
        # geounit at the biggest level
        self.assertAlmostEqual(
            district1.geom.area / 0.1111111111111111,
            calc.result['value'],
            places=9)

    def test_convexhull_block(self):
        """
        Test the convex hull calculator averaging a block of 9 smaller geounits
        """
        dist1ids = list(self.geolevel.geounit_set.all())
        dist1ids = dist1ids[0:3] + dist1ids[9:12] + dist1ids[18:21]
        dist1ids = map(lambda x: str(x.id), dist1ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(
            district_id=self.district1.district_id, version=self.plan.version)

        calc = ConvexHullRatio()
        calc.compute(district=district1)

        # 9 contiguous geounits at the middle level have the same area as one
        # geounit at the biggest level
        self.assertAlmostEqual(
            district1.geom.area / 0.1111111111111111,
            calc.result['value'],
            places=9)

    def test_convexhull_column(self):
        """
        Test the convex hull calculator averaging a column of 9 smaller
        geounits
        """
        dist1ids = list(self.geolevel.geounit_set.all())
        dist1ids = dist1ids[0:1] + dist1ids[9:10] + dist1ids[18:19] + \
            dist1ids[27:28] + dist1ids[36:37] + dist1ids[45:46] + \
            dist1ids[54:55] + dist1ids[63:64] + dist1ids[72:73]
        dist1ids = map(lambda x: str(x.id), dist1ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(
            district_id=self.district1.district_id, version=self.plan.version)

        calc = ConvexHullRatio()
        calc.compute(district=district1)

        # 9 contiguous geounits at the middle level have the same area as one
        # geounit at the biggest level
        self.assertAlmostEqual(
            district1.geom.area / 0.1111111111111111,
            calc.result['value'],
            places=9)

    def test_convexhull_sparse(self):
        """
        Test the convex hull calculator averaging a sparse set of geounits
        """
        dist1ids = list(self.geolevel.geounit_set.all())
        dist1ids = dist1ids[0:1] + dist1ids[8:9] + dist1ids[72:
                                                            73] + dist1ids[80:
                                                                           81]
        dist1ids = map(lambda x: str(x.id), dist1ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(
            district_id=self.district1.district_id, version=self.plan.version)

        calc = ConvexHullRatio()
        calc.compute(district=district1)

        # the convex hull that covers this sparse district is bigger than the
        # sum of the areas
        self.assertEqual(district1.geom.area / 1, calc.result['value'])

    def test_convexhull_avg(self):
        """
        Test the convex hull calculator averaging a sparse set of geounits
        """
        dist1ids = list(self.geolevel.geounit_set.all())
        dist1ids = dist1ids[0:9]
        dist1ids = map(lambda x: str(x.id), dist1ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(
            district_id=self.district1.district_id, version=self.plan.version)

        calc = ConvexHullRatio()
        calc.compute(plan=self.plan)

        # the average convex hull that covers this plan is the same as the
        # district convex hull
        self.assertAlmostEqual(
            district1.geom.area / 0.1111111111111111,
            calc.result['value'],
            places=9)

    def test_convexhull_avg2(self):
        """
        Test the convex hull calculator averaging a sparse set of geounits
        """
        distids = list(self.geolevel.geounit_set.all())
        dist1ids = distids[0:9]
        dist1ids = map(lambda x: str(x.id), dist1ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(
            district_id=self.district1.district_id, version=self.plan.version)

        dist2ids = distids[9:18]
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district2.district_id, dist2ids,
                               self.geolevel.id, self.plan.version)

        calc = ConvexHullRatio()
        calc.compute(plan=self.plan)

        # the average convex hull that covers this plan is the same as the
        # district convex hull (both of them!)
        self.assertAlmostEqual(
            district1.geom.area / 0.1111111111111111,
            calc.result['value'],
            places=9)
