from base import BaseTestCase

from redistricting.models import Geolevel, Geounit, Subject, District
from redistricting.reportcalculators import (Population, Compactness, Majority,
                                             Unassigned)


class ReportCalculatorTestCase(BaseTestCase):
    """
    Unit tests for report calculators
    """
    fixtures = [
        'redistricting_testdata.json', 'redistricting_testdata_geolevel2.json',
        'redistricting_testdata_geolevel3.json'
    ]

    def setUp(self):
        super(ReportCalculatorTestCase, self).setUp()
        self.geolevel = Geolevel.objects.get(name='middle level')
        self.geounits = list(
            Geounit.objects.filter(geolevel=self.geolevel).order_by('id'))
        self.subject1 = Subject.objects.get(name='TestSubject')
        self.subject2 = Subject.objects.get(name='TestSubject2')

        # add some geounits
        dist1id = self.district1.district_id
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        self.district1 = max(
            District.objects.filter(plan=self.plan, district_id=dist1id),
            key=lambda d: d.version)

    def tearDown(self):
        self.geolevel = None
        self.geounits = None
        self.subject1 = None
        self.subject2 = None
        super(ReportCalculatorTestCase, self).tearDown()

    def test_population(self):
        """
        Test the Population report calculator
        """
        # no range provided
        calc = Population()
        calc.arg_dict['value'] = ('subject', 'TestSubject')
        calc.compute(district=self.district1)

        self.assertEqual(2, len(calc.result['raw']))

        col1 = calc.result['raw'][0]
        self.assertEqual('string', col1['type'])
        self.assertEqual(self.district1.long_label, col1['value'])
        self.assertEqual('DistrictID', col1['label'])
        self.assertFalse('avg_key' in col1)

        col2 = calc.result['raw'][1]
        self.assertEqual('integer', col2['type'])
        self.assertEqual(6, col2['value'])
        self.assertEqual('Population', col2['label'])
        self.assertEqual('population_TestSubject', col2['avg_key'])

        # range that's within
        calc.arg_dict['min'] = ('literal', 5)
        calc.arg_dict['max'] = ('literal', 7)
        calc.compute(district=self.district1)

        self.assertEqual(3, len(calc.result['raw']))

        col3 = calc.result['raw'][2]
        self.assertEqual('boolean', col3['type'])
        self.assertEqual(True, col3['value'])
        self.assertEqual('Within Target Range', col3['label'])
        self.assertFalse('avg_key' in col3)

        # range that's not within
        calc.arg_dict['min'] = ('literal', 7)
        calc.arg_dict['max'] = ('literal', 8)
        calc.compute(district=self.district1)
        col3 = calc.result['raw'][2]
        self.assertEqual(False, col3['value'])

    def test_compactness(self):
        """
        Test the Compactness report calculator
        """
        calc = Compactness()

        # LengthWidth
        calc.arg_dict['comptype'] = ('literal', 'LengthWidth')
        calc.compute(district=self.district1)

        self.assertEqual(2, len(calc.result['raw']))

        col1 = calc.result['raw'][0]
        self.assertEqual('string', col1['type'])
        self.assertEqual(self.district1.long_label, col1['value'])
        self.assertEqual('DistrictID', col1['label'])
        self.assertFalse('avg_key' in col1)

        col2 = calc.result['raw'][1]
        self.assertEqual('percent', col2['type'])
        self.assertAlmostEquals(0.666666, col2['value'], 3)
        self.assertEqual('Compactness', col2['label'])
        self.assertEqual('LengthWidth', col2['avg_key'])

        # Roeck
        calc.arg_dict['comptype'] = ('literal', 'Roeck')
        calc.compute(district=self.district1)

        self.assertEqual(2, len(calc.result['raw']))

        col1 = calc.result['raw'][0]
        self.assertEqual('string', col1['type'])
        self.assertEqual(self.district1.long_label, col1['value'])
        self.assertEqual('DistrictID', col1['label'])
        self.assertFalse('avg_key' in col1)

        col2 = calc.result['raw'][1]
        self.assertEqual('percent', col2['type'])
        self.assertAlmostEquals(0.587649, col2['value'], 3)
        self.assertEqual('Compactness', col2['label'])
        self.assertEqual('Roeck', col2['avg_key'])

        # Schwartzberg
        calc.arg_dict['comptype'] = ('literal', 'Schwartzberg')
        calc.compute(district=self.district1)

        self.assertEqual(2, len(calc.result['raw']))

        col1 = calc.result['raw'][0]
        self.assertEqual('string', col1['type'])
        self.assertEqual(self.district1.long_label, col1['value'])
        self.assertEqual('DistrictID', col1['label'])
        self.assertFalse('avg_key' in col1)

        col2 = calc.result['raw'][1]
        self.assertEqual('percent', col2['type'])
        self.assertAlmostEquals(0.868321, col2['value'], 3)
        self.assertEqual('Compactness', col2['label'])
        self.assertEqual('Schwartzberg', col2['avg_key'])

    def test_majority(self):
        """
        Test the Majority report calculator
        """
        calc = Majority()

        # not a majority
        calc.arg_dict['value'] = ('subject', 'TestSubject')
        calc.arg_dict['total'] = ('subject', 'TestSubject2')
        calc.compute(district=self.district1)

        self.assertEqual(4, len(calc.result['raw']))

        col1 = calc.result['raw'][0]
        self.assertEqual('string', col1['type'])
        self.assertEqual(self.district1.long_label, col1['value'])
        self.assertEqual('DistrictID', col1['label'])
        self.assertFalse('avg_key' in col1)

        col2 = calc.result['raw'][1]
        self.assertEqual('integer', col2['type'])
        self.assertEquals(6, col2['value'])
        self.assertEqual('Population', col2['label'])
        self.assertEqual('majminpop_TestSubject', col2['avg_key'])

        col3 = calc.result['raw'][2]
        self.assertEqual('percent', col3['type'])
        self.assertAlmostEquals(0.04, col3['value'], 3)
        self.assertEqual('Proportion', col3['label'])
        self.assertEqual('majminpop_TestSubject_proportion', col3['avg_key'])

        col4 = calc.result['raw'][3]
        self.assertEqual('boolean', col4['type'])
        self.assertAlmostEquals(False, col4['value'])
        self.assertEqual('>= 50%', col4['label'])
        self.assertFalse('avg_key' in col4)

        # is a majority
        calc.arg_dict['value'] = ('subject', 'TestSubject2')
        calc.arg_dict['total'] = ('subject', 'TestSubject')
        calc.compute(district=self.district1)

        self.assertEqual(4, len(calc.result['raw']))

        col1 = calc.result['raw'][0]
        self.assertEqual('string', col1['type'])
        self.assertEqual(self.district1.long_label, col1['value'])
        self.assertEqual('DistrictID', col1['label'])
        self.assertFalse('avg_key' in col1)

        col2 = calc.result['raw'][1]
        self.assertEqual('integer', col2['type'])
        self.assertEquals(150, col2['value'])
        self.assertEqual('Population', col2['label'])
        self.assertEqual('majminpop_TestSubject2', col2['avg_key'])

        col3 = calc.result['raw'][2]
        self.assertEqual('percent', col3['type'])
        self.assertAlmostEquals(25, col3['value'], 3)
        self.assertEqual('Proportion', col3['label'])
        self.assertEqual('majminpop_TestSubject2_proportion', col3['avg_key'])

        col4 = calc.result['raw'][3]
        self.assertEqual('boolean', col4['type'])
        self.assertAlmostEquals(True, col4['value'])
        self.assertEqual('>= 50%', col4['label'])
        self.assertFalse('avg_key' in col4)

    def test_unassigned(self):
        """
        Test the Unassigned report calculator
        """
        calc = Unassigned()
        calc.arg_dict['threshold'] = ('literal', 0.1)
        calc.compute(plan=self.plan)

        self.assertEqual(1, len(calc.result['raw']))

        col1 = calc.result['raw'][0]
        self.assertEqual('list', col1['type'])
        self.assertEqual(675, len(col1['value']))
