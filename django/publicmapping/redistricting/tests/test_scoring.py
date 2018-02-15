from base import BaseTestCase

from redistricting.models import (Geolevel, Geounit, District, LegislativeBody,
                                  ScoreDisplay, ScorePanel, Subject,
                                  ScoreFunction, ScoreArgument)
from decimal import Decimal

import json


class ScoringTestCase(BaseTestCase):
    """
    Unit tests to test the logic of the scoring functionality
    """
    fixtures = [
        'redistricting_testdata.json', 'redistricting_testdata_geolevel2.json',
        'redistricting_testdata_scoring.json'
    ]

    def setUp(self):
        super(ScoringTestCase, self).setUp()

        # create a couple districts and populate with geounits
        # geounits = self.geounits[self.geolevels[1].id]
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

        # create objects used for scoring
        self.legbod = LegislativeBody.objects.get(name='TestLegislativeBody')
        self.scoreDisplay1 = ScoreDisplay(
            title='SD1',
            legislative_body=self.legbod,
            is_page=False,
            owner=self.user)
        self.scoreDisplay1.save()

        self.scorePanel1 = ScorePanel(type='district', position=0, title='SP1')
        self.scorePanel1.save()
        self.scorePanel1.displays.add(self.scoreDisplay1)

        self.subject1 = Subject.objects.get(name='TestSubject')

    def tearDown(self):
        """
        Clean up after testing.
        """
        self.scorePanel1.delete()
        self.scoreDisplay1.delete()

        self.district1 = None
        self.district2 = None
        self.legbod = None
        self.subject1 = None

        super(ScoringTestCase, self).tearDown()

    def testInvalidScenarios(self):
        """
        Test what happens when a calculator module doesn't exist,
        or bad parameters are passed in
        """
        badFunction = ScoreFunction(calculator='does.not.Exist', name='bad')
        self.assertRaises(ImportError, badFunction.score, [self.district1])

    def testSchwarzbergScoringFunction(self):
        """
        Test the schwarzberg scoring function
        """
        # create the ScoreFunction
        schwartzFunction = ScoreFunction(
            calculator='redistricting.calculators.Schwartzberg',
            name='SchwartzbergFn')

        # multiple districts
        scores = schwartzFunction.score([self.district1, self.district2])
        self.assertAlmostEquals(
            0.86832150547, scores[0]['value'], 9,
            'Schwartzberg for first district was incorrect: %f' %
            scores[0]['value'])
        self.assertAlmostEquals(
            0.88622692545, scores[1]['value'], 9,
            'Schwartzberg for second district was incorrect: %f' %
            scores[1]['value'])

        # single district as list
        scores = schwartzFunction.score([self.district1])
        self.assertAlmostEquals(0.86832150547, scores[0]['value'], 9,
                                'Schwartzberg for District 1 was incorrect: %f'
                                % scores[0]['value'])

        # single district as object
        score = schwartzFunction.score(self.district1)
        self.assertAlmostEquals(
            0.86832150547, score['value'], 9,
            'Schwartzberg for District 1 was incorrect: %f' % score['value'])

        # HTML
        score = schwartzFunction.score(self.district1, 'html')
        self.assertEqual(
            "86.83%", score,
            'Schwartzberg HTML for District 1 was incorrect: ' + score)

        # JSON
        score = json.loads(schwartzFunction.score(self.district1, 'json'))
        self.assertAlmostEqual(
            0.8683215054699209, score['result'], 15,
            'Schwartzberg JSON for District 1 was incorrect. (e:"%s", a:"%s")'
            % (
                0.8683215054699209,
                score['result'],
            ))

    def testSumFunction(self):
        """
        Test the sum scoring function
        """
        # create the scoring function for summing three parameters
        sumThreeFunction = ScoreFunction(
            calculator='redistricting.calculators.SumValues',
            name='SumThreeFn')
        sumThreeFunction.save()

        # create the arguments
        ScoreArgument(
            function=sumThreeFunction,
            argument='value1',
            value='0',
            type='literal').save()
        ScoreArgument(
            function=sumThreeFunction,
            argument='value2',
            value='1',
            type='literal').save()
        ScoreArgument(
            function=sumThreeFunction,
            argument='value3',
            value='2',
            type='literal').save()

        # test raw value
        score = sumThreeFunction.score(self.district1)
        self.assertEqual(3, score['value'],
                         'sumThree was incorrect: %d' % score['value'])

        # HTML -- also make sure mixed case format works
        score = sumThreeFunction.score(self.district1, 'HtmL')
        self.assertEqual('<span>3</span>', score,
                         'sumThree was incorrect: %s' % score)

        # JSON -- also make sure uppercase format works
        score = sumThreeFunction.score(self.district1, 'JSON')
        self.assertEqual('{"result": 3.0}', score,
                         'sumThree was incorrect: %s' % score)

        # create the scoring function for summing a literal and a subject
        sumMixedFunction = ScoreFunction(
            calculator='redistricting.calculators.SumValues',
            name='SumMixedFn')
        sumMixedFunction.save()

        # create the arguments
        ScoreArgument(
            function=sumMixedFunction,
            argument='value1',
            value=self.subject1.name,
            type='subject').save()
        ScoreArgument(
            function=sumMixedFunction,
            argument='value2',
            value='5.2',
            type='literal').save()

        # test raw value
        score = sumMixedFunction.score(self.district1)
        self.assertEqual(
            Decimal('11.2'), score['value'],
            'sumMixed was incorrect: %d' % score['value'])

    def testSumPlanFunction(self):
        """
        Test the sum scoring function on a plan level
        """
        # create the scoring function for summing the districts in a plan
        sumPlanFunction = ScoreFunction(
            calculator='redistricting.calculators.SumValues',
            name='SumPlanFn',
            is_planscore=True)
        sumPlanFunction.save()

        # create the arguments
        ScoreArgument(
            function=sumPlanFunction,
            argument='value1',
            value='1',
            type='literal').save()

        # test raw value
        num_districts = len(
            self.plan.get_districts_at_version(
                self.plan.version, include_geom=False))
        score = sumPlanFunction.score(self.plan)
        self.assertEqual(num_districts, score['value'],
                         'sumPlanFunction was incorrect. (e:%d, a:%d)' %
                         (num_districts, score['value']))

        # test a list of plans
        score = sumPlanFunction.score([self.plan, self.plan])
        self.assertEqual(num_districts, score[0]['value'],
                         'sumPlanFunction was incorrect for first plan: %d' %
                         score[0]['value'])
        self.assertEqual(num_districts, score[1]['value'],
                         'sumPlanFunction was incorrect for second plan: %d' %
                         score[1]['value'])

    def testThresholdFunction(self):
        # create the scoring function for checking if a value passes a
        # threshold
        thresholdFunction1 = ScoreFunction(
            calculator='redistricting.calculators.Threshold',
            name='ThresholdFn1')
        thresholdFunction1.save()

        # create the arguments
        ScoreArgument(
            function=thresholdFunction1,
            argument='value',
            value='1',
            type='literal').save()
        ScoreArgument(
            function=thresholdFunction1,
            argument='threshold',
            value='2',
            type='literal').save()

        # test raw value
        score = thresholdFunction1.score(self.district1)
        self.assertEqual(False, score['value'], '1 is not greater than 2')

        # create a new scoring function to test the inverse
        thresholdFunction2 = ScoreFunction(
            calculator='redistricting.calculators.Threshold',
            name='ThresholdFn2')
        thresholdFunction2.save()

        # create the arguments
        ScoreArgument(
            function=thresholdFunction2,
            argument='value',
            value='2',
            type='literal').save()
        ScoreArgument(
            function=thresholdFunction2,
            argument='threshold',
            value='1',
            type='literal').save()

        # test raw value
        score = thresholdFunction2.score(self.district1)
        self.assertEqual(1, score['value'], '2 is greater than 1')

        # HTML
        score = thresholdFunction2.score(self.district1, 'html')
        self.assertEqual("<span>1</span>", score,
                         'Threshold HTML was incorrect: ' + score)

        # JSON
        score = thresholdFunction2.score(self.district1, 'json')
        self.assertEqual('{"result": 1}', score,
                         'Threshold JSON was incorrect: ' + score)

    def testRangeFunction(self):
        # create the scoring function for checking if a value passes a range
        rangeFunction1 = ScoreFunction(
            calculator='redistricting.calculators.Range', name='RangeFn')
        rangeFunction1.save()

        # create the arguments
        ScoreArgument(
            function=rangeFunction1,
            argument='value',
            value='2',
            type='literal').save()
        ScoreArgument(
            function=rangeFunction1, argument='min', value='1',
            type='literal').save()
        ScoreArgument(
            function=rangeFunction1, argument='max', value='3',
            type='literal').save()

        # test raw value
        score = rangeFunction1.score(self.district1)
        self.assertEqual(1, score['value'], '2 is between 1 and 3')

        # HTML
        score = rangeFunction1.score(self.district1, 'html')
        self.assertEqual("<span>1</span>", score,
                         'Range HTML was incorrect: ' + score)

        # JSON
        score = rangeFunction1.score(self.district1, 'json')
        self.assertEqual('{"result": 1}', score,
                         'Range JSON was incorrect: ' + score)

    def testNestedSumFunction(self):
        """
        Test a sum scoring function that references a sum scoring function
        """
        # create the scoring function for summing two literals
        sumTwoLiteralsFunction = ScoreFunction(
            calculator='redistricting.calculators.SumValues',
            name='SumTwoLiteralsFn')
        sumTwoLiteralsFunction.save()
        ScoreArgument(
            function=sumTwoLiteralsFunction,
            argument='value1',
            value='5',
            type='literal').save()
        ScoreArgument(
            function=sumTwoLiteralsFunction,
            argument='value2',
            value='7',
            type='literal').save()

        # create the scoring function for summing a literal and a score
        sumLiteralAndScoreFunction = ScoreFunction(
            calculator='redistricting.calculators.SumValues',
            name='SumLiteralAndScoreFn')
        sumLiteralAndScoreFunction.save()

        # first argument is just a literal
        ScoreArgument(
            function=sumLiteralAndScoreFunction,
            argument='value1',
            value='2',
            type='literal').save()

        # second argument is a score function
        ScoreArgument(
            function=sumLiteralAndScoreFunction,
            argument='value2',
            value=sumTwoLiteralsFunction.name,
            type='score').save()

        # test nested sum
        score = sumLiteralAndScoreFunction.score(self.district1)
        self.assertEqual(
            14, score['value'],
            'sumLiteralAndScoreFunction was incorrect: %d' % score['value'])

        # sum two of these nested sums
        sumTwoNestedSumsFunction = ScoreFunction(
            calculator='redistricting.calculators.SumValues',
            name='SumTwoNestedSumsFn')
        sumTwoNestedSumsFunction.save()
        ScoreArgument(
            function=sumTwoNestedSumsFunction,
            argument='value1',
            value=sumLiteralAndScoreFunction.name,
            type='score').save()
        ScoreArgument(
            function=sumTwoNestedSumsFunction,
            argument='value2',
            value=sumLiteralAndScoreFunction.name,
            type='score').save()
        score = sumTwoNestedSumsFunction.score(self.district1)
        self.assertEqual(
            28, score['value'],
            'sumTwoNestedSumsFunction was incorrect: %d' % score['value'])

        # test a list of districts
        score = sumTwoNestedSumsFunction.score(
            [self.district1, self.district1])
        self.assertEqual(
            28, score[0]['value'],
            'sumTwoNestedSumsFunction was incorrect for first district: %d' %
            score[0]['value'])
        self.assertEqual(
            28, score[1]['value'],
            'sumTwoNestedSumsFunction was incorrect for second district: %d' %
            score[1]['value'])

    def testNestedSumPlanFunction(self):
        """
        Test the nested sum scoring function on a plan level
        """
        # create the scoring function for summing the districts in a plan
        sumPlanFunction = ScoreFunction(
            calculator='redistricting.calculators.SumValues',
            name='SumPlanFn',
            is_planscore=True)
        sumPlanFunction.save()
        ScoreArgument(
            function=sumPlanFunction,
            argument='value1',
            value='1',
            type='literal').save()

        # find the number of districts in the plan in an alternate fashion
        num_districts = len(
            self.plan.get_districts_at_version(
                self.plan.version, include_geom=False))

        # ensure the sumPlanFunction works correctly
        score = sumPlanFunction.score(self.plan)
        self.assertEqual(num_districts, score['value'],
                         'sumPlanFunction was incorrect. (e:%d, a:%d)' % (
                             num_districts,
                             score['value'],
                         ))

        # create the scoring function for summing the sum of the districts in a
        # plan
        sumSumPlanFunction = ScoreFunction(
            calculator='redistricting.calculators.SumValues',
            name='SumSumPlanFn',
            is_planscore=True)
        sumSumPlanFunction.save()
        ScoreArgument(
            function=sumSumPlanFunction,
            argument='value1',
            value=sumPlanFunction.name,
            type='score').save()

        # test nested sum
        score = sumSumPlanFunction.score(self.plan)
        self.assertEqual(
            num_districts**2, score['value'],
            'sumSumPlanFunction was incorrect: %d' % score['value'])

        # test a list of plans
        score = sumSumPlanFunction.score([self.plan, self.plan])
        self.assertEqual(num_districts**2, score[0]['value'],
                         'sumSumPlanFunction was incorrect for first plan: %d'
                         % score[0]['value'])
        self.assertEqual(num_districts**2, score[1]['value'],
                         'sumSumPlanFunction was incorrect for second plan: %d'
                         % score[1]['value'])

    def testPlanScoreNestedWithDistrictScore(self):
        """
        Test the case where a ScoreFunction of type 'plan' has an argument
        that is a ScoreFunction of type 'district', in which case, the argument
        ScoreFunction needs to be evaluated over all districts in the list of
        plans
        """
        # create the district scoring function for getting subject1
        districtSubjectFunction = ScoreFunction(
            calculator='redistricting.calculators.SumValues',
            name='GetSubjectFn')
        districtSubjectFunction.save()

        ScoreArgument(
            function=districtSubjectFunction,
            argument='value1',
            value=self.subject1.name,
            type='subject').save()

        # create the plan scoring function for summing values
        planSumFunction = ScoreFunction(
            calculator='redistricting.calculators.SumValues',
            name='PlanSumFn',
            is_planscore=True)
        planSumFunction.save()
        ScoreArgument(
            function=planSumFunction,
            value=districtSubjectFunction.name,
            type='score').save()

        # subject values are 6, 9, and 0; so the total should be 15
        score = planSumFunction.score(self.plan)
        self.assertEqual(
            9, score['value'],
            'planSumFunction was incorrect: (e:9, a:%d)' % score['value'])

        # test a list of plans
        score = planSumFunction.score([self.plan, self.plan])
        self.assertEqual(9, score[0]['value'],
                         'planSumFunction was incorrect for first plan: %d' %
                         score[0]['value'])
        self.assertEqual(9, score[1]['value'],
                         'planSumFunction was incorrect for second plan: %d' %
                         score[1]['value'])

        # test with multiple arguments
        districtSubjectFunction2 = ScoreFunction(
            calculator='redistricting.calculators.SumValues',
            name='GetSubjectFn2')
        districtSubjectFunction2.save()
        ScoreArgument(
            function=districtSubjectFunction2,
            argument='value1',
            value=self.subject1.name,
            type='subject').save()
        ScoreArgument(
            function=districtSubjectFunction2,
            argument='value2',
            value=self.subject1.name,
            type='subject').save()

        planSumFunction2 = ScoreFunction(
            calculator='redistricting.calculators.SumValues',
            name='PlanSumFn2',
            is_planscore=True)
        planSumFunction2.save()
        ScoreArgument(
            function=planSumFunction2,
            value=districtSubjectFunction2.name,
            type='score').save()

        # should be twice as much
        score = planSumFunction2.score(self.plan)
        self.assertEqual(18, score['value'],
                         'planSumFunction was incorrect: %d' % score['value'])

        # test with adding another argument to the plan function, should
        # double again
        ScoreArgument(
            function=planSumFunction2,
            value=districtSubjectFunction2.name,
            type='score').save()
        score = planSumFunction2.score(self.plan)
        self.assertEqual(36, score['value'],
                         'planSumFunction was incorrect: %d' % score['value'])
