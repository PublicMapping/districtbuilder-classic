"""
Define a set of tests for the redistricting app.

Test coverage is provided for the complex geographice queries and routines
in the redistricting app.

This file is part of The Public Mapping Project
http://sourceforge.net/projects/publicmapping/

License:
    Copyright 2010 Micah Altman, Michael McDonald

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

Author: 
    Andrew Jennings, David Zwarg, Kenny Shepard
"""

import os
from django.test import TestCase
import zipfile
from django.contrib.gis.db.models import Union
from django.db.models import Sum as SumAgg, Min, Max
from django.test.client import Client
from django.contrib.gis.geos import *
from django.contrib.auth.models import User
from publicmapping.redistricting.models import *
from publicmapping.redistricting.utils import *
from publicmapping.redistricting.calculators import *
from django.conf import settings
from datetime import datetime

class BaseTestCase(TestCase):
    """
    Only contains setUp and tearDown, which are shared among all other TestCases
    """
    fixtures = ['redistricting_testdata.json']

    def setUp(self):
        """
        Setup the general tests. This fabricates a set of data in the 
        test database for use later.
        """
        # Get the test Geolevels
        self.geolevels = Geolevel.objects.all().order_by('id')

        # Get test Subjects
        self.subject1 = Subject.objects.get(name='TestSubject')
        self.subject2 = Subject.objects.get(name='TestSubject2')

        # Get the test Geounits
        self.geounits = {}
        for gl in self.geolevels:
            self.geounits[gl.id] = list(Geounit.objects.filter(geolevel=gl).order_by('id'))

        # Get a test User
        self.username = 'test_user'
        self.password = 'secret'
        self.user = User.objects.get(username=self.username)

        # Get a test LegislativeBody
        self.legbod = LegislativeBody.objects.get(name='TestLegislativeBody')

        # Get a test Target
        self.target = Target.objects.get(subject=self.subject1)

        # Get a test LegislativeDefault
        self.legdef = LegislativeDefault.objects.get(legislative_body=self.legbod, target=self.target)

        # Get a test LegislativeLevel hierarchy
        self.leglev3 = LegislativeLevel.objects.get(geolevel=self.geolevels[2])
        self.leglev2 = LegislativeLevel.objects.get(geolevel=self.geolevels[1])
        self.leglev1 = LegislativeLevel.objects.get(geolevel=self.geolevels[0])
        
        # Get a test Plan
        self.plan = Plan.objects.get(name='testPlan')
        self.plan2 = Plan.objects.get(name='testPlan2')

        # Get the test Districts
        self.district1 = District.objects.get(name='District 1', plan=self.plan)
        self.district2 = District.objects.get(name='District 2', plan=self.plan)



class ScoringTestCase(BaseTestCase):
    """
    Unit tests to test the logic of the scoring functionality
    """
    def setUp(self):
        BaseTestCase.setUp(self)

        # create a couple districts and populate with geounits
        geounits = self.geounits[self.geolevels[1].id]

        self.dist1units = geounits[0:3] + geounits[9:12]
        self.dist2units = geounits[18:21] + geounits[27:30] + geounits[36:39]

        dist1ids = map(lambda x: str(x.id), self.dist1units)
        dist2ids = map(lambda x: str(x.id), self.dist2units)

        self.plan.add_geounits(self.district1.district_id, dist1ids, self.geolevels[1].id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids, self.geolevels[1].id, self.plan.version)

        self.district1 = max(District.objects.filter(plan=self.plan,district_id=self.district1.district_id),key=lambda d: d.version)
        self.district2 = max(District.objects.filter(plan=self.plan,district_id=self.district2.district_id),key=lambda d: d.version)
        
        # create objects used for scoring
        self.scoreDisplay1 = ScoreDisplay(title='SD1', legislative_body=self.legbod, is_page=False)
        self.scoreDisplay1.save()

        self.scorePanel1 = ScorePanel(type='district', display=self.scoreDisplay1, position=0, title='SP1')
        self.scorePanel1.save()

    def tearDown(self):
        """
        Clean up after testing.
        """
        BaseTestCase.tearDown(self)
        self.scorePanel1.delete()
        self.scoreDisplay1.delete()

    def testSetup(self):
        """
        Make sure we have the districts created during setUp
        """
        district1units = self.district1.get_base_geounits()
        self.assertEqual(54, len(district1units), 'Incorrect number of geounits returned in dist1: %d' % len(district1units))

        district2units = self.district2.get_base_geounits()
        self.assertEqual(81, len(district2units), 'Incorrect number of geounits returned in dist1: %d' % len(district2units))

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
        schwartzFunction = ScoreFunction(calculator='redistricting.calculators.Schwartzberg', name='SchwartzbergFn')

        # multiple districts
        scores = schwartzFunction.score([self.district1, self.district2])
        self.assertAlmostEquals(0.86832150547, scores[0], 9, 'Schwartzberg for first district was incorrect: %f' % scores[0])
        self.assertAlmostEquals(0.88622692545, scores[1], 9, 'Schwartzberg for second district was incorrect: %f' % scores[1])

        # single district as list
        scores = schwartzFunction.score([self.district1])
        self.assertAlmostEquals(0.86832150547, scores[0], 9, 'Schwartzberg for District 1 was incorrect: %f' % scores[0])

        # single district as object
        score = schwartzFunction.score(self.district1)
        self.assertAlmostEquals(0.86832150547, score, 9, 'Schwartzberg for District 1 was incorrect: %f' % score)

        # HTML
        score = schwartzFunction.score(self.district1, 'html')
        self.assertEquals("86.83%", score, 'Schwartzberg HTML for District 1 was incorrect: ' + score)

        # JSON
        score = schwartzFunction.score(self.district1, 'json')
        self.assertEquals('{"result": 0.86832150546992093}', score, 'Schwartzberg JSON for District 1 was incorrect: ' + score)

    def testSumFunction(self):
        """
        Test the sum scoring function
        """
        # create the scoring function for summing three parameters
        sumThreeFunction = ScoreFunction(calculator='redistricting.calculators.Sum', name='SumThreeFn')
        sumThreeFunction.save()

        # create the arguments
        ScoreArgument(function=sumThreeFunction, argument='value1', value='0', type='literal').save()
        ScoreArgument(function=sumThreeFunction, argument='value2', value='1', type='literal').save()
        ScoreArgument(function=sumThreeFunction, argument='value3', value='2', type='literal').save()

        # test raw value
        score = sumThreeFunction.score(self.district1)
        self.assertEquals(3, score, 'sumThree was incorrect: %d' % score)

        # HTML -- also make sure mixed case format works
        score = sumThreeFunction.score(self.district1, 'HtmL')
        self.assertEquals('<span>3.0</span>', score, 'sumThree was incorrect: %s' % score)

        # JSON -- also make sure uppercase format works
        score = sumThreeFunction.score(self.district1, 'JSON')
        self.assertEquals('{"result": 3.0}', score, 'sumThree was incorrect: %s' % score)

        # create the scoring function for summing a literal and a subject
        sumMixedFunction = ScoreFunction(calculator='redistricting.calculators.Sum', name='SumMixedFn')
        sumMixedFunction.save()

        # create the arguments
        ScoreArgument(function=sumMixedFunction, argument='value1', value=self.subject1.name, type='subject').save()
        ScoreArgument(function=sumMixedFunction, argument='value2', value='5.0', type='literal').save()

        # test raw value
        score = sumMixedFunction.score(self.district1)
        self.assertEquals(11, score, 'sumMixed was incorrect: %d' % score)

    def testSumPlanFunction(self):
        """
        Test the sum scoring function on a plan level
        """
        # create the scoring function for summing the districts in a plan
        sumPlanFunction = ScoreFunction(calculator='redistricting.calculators.Sum', name='SumPlanFn', is_planscore=True)
        sumPlanFunction.save()

        # create the arguments
        ScoreArgument(function=sumPlanFunction, argument='value1', value='1', type='literal').save()

        # test raw value
        num_districts = len(self.plan.get_districts_at_version(self.plan.version, include_geom=False))
        score = sumPlanFunction.score(self.plan)
        self.assertEquals(num_districts, score, 'sumPlanFunction was incorrect: %d' % score)

        # test a list of plans
        score = sumPlanFunction.score([self.plan, self.plan])
        self.assertEquals(num_districts, score[0], 'sumPlanFunction was incorrect for first plan: %d' % score[0])
        self.assertEquals(num_districts, score[1], 'sumPlanFunction was incorrect for second plan: %d' % score[1])

    def testThresholdFunction(self):
        # create the scoring function for checking if a value passes a threshold
        thresholdFunction1 = ScoreFunction(calculator='redistricting.calculators.Threshold', name='ThresholdFn')
        thresholdFunction1.save()

        # create the arguments
        ScoreArgument(function=thresholdFunction1, argument='value', value='1', type='literal').save()
        ScoreArgument(function=thresholdFunction1, argument='threshold', value='2', type='literal').save()

        # test raw value
        score = thresholdFunction1.score(self.district1)
        self.assertEquals(False, score, '1 is not greater than 2')

        # create a new scoring function to test the inverse
        thresholdFunction2 = ScoreFunction(calculator='redistricting.calculators.Threshold', name='ThresholdFn')
        thresholdFunction2.save()

        # create the arguments
        ScoreArgument(function=thresholdFunction2, argument='value', value='2', type='literal').save()
        ScoreArgument(function=thresholdFunction2, argument='threshold', value='1', type='literal').save()

        # test raw value
        score = thresholdFunction2.score(self.district1)
        self.assertEquals(1, score, '2 is greater than 1')

        # HTML
        score = thresholdFunction2.score(self.district1, 'html')
        self.assertEquals("<span>1</span>", score, 'Threshold HTML was incorrect: ' + score)

        # JSON
        score = thresholdFunction2.score(self.district1, 'json')
        self.assertEquals('{"result": 1}', score, 'Threshold JSON was incorrect: ' + score)

    def testRangeFunction(self):
        # create the scoring function for checking if a value passes a range
        rangeFunction1 = ScoreFunction(calculator='redistricting.calculators.Range', name='RangeFn')
        rangeFunction1.save()

        # create the arguments
        ScoreArgument(function=rangeFunction1, argument='value', value='2', type='literal').save()
        ScoreArgument(function=rangeFunction1, argument='min', value='1', type='literal').save()
        ScoreArgument(function=rangeFunction1, argument='max', value='3', type='literal').save()

        # test raw value
        score = rangeFunction1.score(self.district1)
        self.assertEquals(1, score, '2 is between 1 and 3')

        # HTML
        score = rangeFunction1.score(self.district1, 'html')
        self.assertEquals("<span>1</span>", score, 'Range HTML was incorrect: ' + score)

        # JSON
        score = rangeFunction1.score(self.district1, 'json')
        self.assertEquals('{"result": 1}', score, 'Range JSON was incorrect: ' + score)


    def testNestedSumFunction(self):
        """
        Test a sum scoring function that references a sum scoring function
        """
        # create the scoring function for summing two literals
        sumTwoLiteralsFunction = ScoreFunction(calculator='redistricting.calculators.Sum', name='SumTwoLiteralsFn')
        sumTwoLiteralsFunction.save()
        ScoreArgument(function=sumTwoLiteralsFunction, argument='value1', value='5', type='literal').save()
        ScoreArgument(function=sumTwoLiteralsFunction, argument='value2', value='7', type='literal').save()
        
        # create the scoring function for summing a literal and a score
        sumLiteralAndScoreFunction = ScoreFunction(calculator='redistricting.calculators.Sum', name='SumLiteralAndScoreFn')
        sumLiteralAndScoreFunction.save()

        # first argument is just a literal
        ScoreArgument(function=sumLiteralAndScoreFunction, argument='value1', value='2', type='literal').save()

        # second argument is a score function
        ScoreArgument(function=sumLiteralAndScoreFunction, argument='value2', value=sumTwoLiteralsFunction.name, type='score').save()

        # test nested sum
        score = sumLiteralAndScoreFunction.score(self.district1)
        self.assertEquals(14, score, 'sumLiteralAndScoreFunction was incorrect: %d' % score)

        # sum two of these nested sums
        sumTwoNestedSumsFunction = ScoreFunction(calculator='redistricting.calculators.Sum', name='SumTwoNestedSumsFn')
        sumTwoNestedSumsFunction.save()
        ScoreArgument(function=sumTwoNestedSumsFunction, argument='value1', value=sumLiteralAndScoreFunction.name, type='score').save()        
        ScoreArgument(function=sumTwoNestedSumsFunction, argument='value2', value=sumLiteralAndScoreFunction.name, type='score').save()
        score = sumTwoNestedSumsFunction.score(self.district1)
        self.assertEquals(28, score, 'sumTwoNestedSumsFunction was incorrect: %d' % score)

        # test a list of districts
        score = sumTwoNestedSumsFunction.score([self.district1, self.district1])
        self.assertEquals(28, score[0], 'sumTwoNestedSumsFunction was incorrect for first district: %d' % score[0])
        self.assertEquals(28, score[1], 'sumTwoNestedSumsFunction was incorrect for second district: %d' % score[1])

    def testNestedSumPlanFunction(self):
        """
        Test the nested sum scoring function on a plan level
        """
        # create the scoring function for summing the districts in a plan
        sumPlanFunction = ScoreFunction(calculator='redistricting.calculators.Sum', name='SumPlanFn', is_planscore=True)
        sumPlanFunction.save()
        ScoreArgument(function=sumPlanFunction, argument='value1', value='1', type='literal').save()

        # find the number of districts in the plan in an alternate fashion
        num_districts = len(self.plan.get_districts_at_version(self.plan.version, include_geom=False))

        # ensure the sumPlanFunction works correctly
        score = sumPlanFunction.score(self.plan)
        self.assertEquals(num_districts, score, 'sumPlanFunction was incorrect: %d' % score)

        # create the scoring function for summing the sum of the districts in a plan
        sumSumPlanFunction = ScoreFunction(calculator='redistricting.calculators.Sum', name='SumSumPlanFn', is_planscore=True)
        sumSumPlanFunction.save()
        ScoreArgument(function=sumSumPlanFunction, argument='value1', value=sumPlanFunction.name, type='score').save()

        # test nested sum
        score = sumSumPlanFunction.score(self.plan)
        self.assertEquals(num_districts ** 2, score, 'sumSumPlanFunction was incorrect: %d' % score)

        # test a list of plans
        score = sumSumPlanFunction.score([self.plan, self.plan])
        self.assertEquals(num_districts ** 2, score[0], 'sumSumPlanFunction was incorrect for first plan: %d' % score[0])
        self.assertEquals(num_districts ** 2, score[1], 'sumSumPlanFunction was incorrect for second plan: %d' % score[1])

    def testPlanScoreNestedWithDistrictScore(self):
        """
        Test the case where a ScoreFunction of type 'plan' has an argument
        that is a ScoreFunction of type 'district', in which case, the argument
        ScoreFunction needs to be evaluated over all districts in the list of plans
        """
        # create the district scoring function for getting subject1
        districtSubjectFunction = ScoreFunction(calculator='redistricting.calculators.Sum', name='GetSubjectFn')
        districtSubjectFunction.save()
        ScoreArgument(function=districtSubjectFunction, argument='value1', value=self.subject1.name, type='subject').save()

        # create the plan scoring function for summing values
        planSumFunction = ScoreFunction(calculator='redistricting.calculators.Sum', name='PlanSumFn', is_planscore=True)
        planSumFunction.save()
        ScoreArgument(function=planSumFunction, value=districtSubjectFunction.name, type='score').save()

        # subject values are 6, 9, and 0; so the total should be 15
        score = planSumFunction.score(self.plan)
        self.assertEquals(15, score, 'planSumFunction was incorrect: %d' % score)

        # test a list of plans
        score = planSumFunction.score([self.plan, self.plan])
        self.assertEquals(15, score[0], 'planSumFunction was incorrect for first plan: %d' % score[0])
        self.assertEquals(15, score[1], 'planSumFunction was incorrect for second plan: %d' % score[1])

        # test with multiple arguments
        districtSubjectFunction2 = ScoreFunction(calculator='redistricting.calculators.Sum', name='GetSubjectFn2')
        districtSubjectFunction2.save()
        ScoreArgument(function=districtSubjectFunction2, argument='value1', value=self.subject1.name, type='subject').save()
        ScoreArgument(function=districtSubjectFunction2, argument='value2', value=self.subject1.name, type='subject').save()
        
        planSumFunction2 = ScoreFunction(calculator='redistricting.calculators.Sum', name='PlanSumFn2', is_planscore=True)
        planSumFunction2.save()
        ScoreArgument(function=planSumFunction2, value=districtSubjectFunction2.name, type='score').save()

        # should be twice as much
        score = planSumFunction2.score(self.plan)
        self.assertEquals(30, score, 'planSumFunction was incorrect: %d' % score)

        # test with adding another argument to the plan function, should double again
        ScoreArgument(function=planSumFunction2, value=districtSubjectFunction2.name, type='score').save()
        score = planSumFunction2.score(self.plan)
        self.assertEquals(60, score, 'planSumFunction was incorrect: %d' % score)
        

class PlanTestCase(BaseTestCase):
    """
    Unit tests to test Plan operations
    """
    def test_district_id_increment(self):
        """
        Test the logic for the automatically generated district_id
        """
        # Note: district_id is set to 0 here, because otherwise, the auto-increment code does not get called.
        # It may be best to revisit how district_id is used throughout the app, and to not allow for it to be set,
        # since it should be auto-generated.
        d3 = District(name='District 3',district_id=0,version=0)
        d3.plan = self.plan

        p1 = Polygon( ((1, 1), (1, 1), (1, 1), (1, 1)) )
        mp1 = MultiPolygon(p1)
        d3.geom = mp1

        d3.save()
        latest = d3.district_id

        d4 = District(name = 'District 4',district_id=0,version=0)
        d4.plan = self.plan

        p2 = Polygon( ((0, 0), (0, 1), (1, 1), (0, 0)) )
        mp2 = MultiPolygon(p1)
        d4.geom = mp2

        d4.save()
        incremented = d4.district_id
        self.assertTrue(latest + 1 == incremented, 'New district did not have an id greater than the previous district')
        
    def test_add_to_plan(self):
        """
        Test the logic for adding geounits to a district.
        """
        district = self.district1
        districtid = district.district_id

        level = self.geolevels[0]
        levelid = level.id
        
        geounits = self.geounits[level.id]
        geounitids = [str(geounits[0].id)]

        self.plan.add_geounits(districtid, geounitids, levelid, self.plan.version)

        # Check for new geounits
        numunits = len(Plan.objects.get(pk=self.plan.id).get_base_geounits(0.1))
        self.assertEqual(81, numunits, 'Geounits not added to plan correctly')

    def test_unassigned(self):
        """
        Test the logic for an unassigned district.
        """
        unassigned = District.objects.filter(name='Unassigned', plan = self.plan)
        self.assertEqual(1, unassigned.count(), 'No Unassigned district on plan. (e:1, a:%d)' % unassigned.count())

    def test_copyplan(self):
        """
        Test the logic for copying plans.
        """
        district = self.district1
        districtid = district.district_id

        level = self.geolevels[0]
        levelid = level.id
        
        geounits = self.geounits[level.id]
        geounitids = [str(geounits[0].id)]

        # Add geounits to plan
        self.plan.add_geounits(districtid, geounitids, levelid, self.plan.version)
        
        # Login
        client = Client()
        client.login(username=self.username, password=self.password)

        # Issue copy command
        copyname = 'MyTestCopy'
        response = client.post('/districtmapping/plan/%d/copy/' % self.plan.id, { 'name':copyname })
        self.assertEqual(200, response.status_code, 'Copy handler didn\'t return 200:' + str(response))

        # Ensure copy exists
        copy = Plan.objects.get(name=copyname)
        self.assertNotEqual(copy, None, 'Copied plan doesn\'t exist')

        # Ensure districts are the same between plans
        numdistricts = len(self.plan.get_districts_at_version(self.plan.version))
        numdistrictscopy = len(copy.get_districts_at_version(copy.version))
        self.assertEqual(numdistricts, numdistrictscopy, 'Districts between original and copy are different. (e:%d, a:%d)' % (numdistricts, numdistrictscopy))

        # Ensure geounits are the same between plans
        numunits = len(Plan.objects.get(pk=self.plan.id).get_base_geounits(0.1))
        numunitscopy = len(Plan.objects.get(pk=copy.id).get_base_geounits(0.1))
        self.assertEqual(numunits, numunitscopy, 'Geounits between original and copy are different')

    def test_district_locking(self):
        """
        Test the logic for locking/unlocking a district.
        """
        district = self.district1
        districtid = district.id
        district_id = district.district_id
        
        level = self.geolevels[0]
        levelid = level.id
        
        geounits = self.geounits[level.id]
        geounitids = [str(geounits[0].id)]

        client = Client()

        # Create a second user, and try to lock a district not belonging to that user
        username2 = 'test_user2'
        user2 = User(username=username2)
        user2.set_password(self.password)
        user2.save()
        client.login(username=username2, password=self.password)

        # Issue lock command when not logged in
        response = client.post('/districtmapping/plan/%d/district/%d/lock/' % (self.plan.id, district_id), { 'lock':True, 'version':self.plan.version })
        self.assertEqual(403, response.status_code, 'Non-owner was able to lock district.' + str(response))
        
        # Login
        client.login(username=self.username, password=self.password)
        
        # Issue lock command
        response = client.post('/districtmapping/plan/%d/district/%d/lock/' % (self.plan.id, district_id), { 'lock':True, 'version':self.plan.version })
        self.assertEqual(200, response.status_code, 'Lock handler didn\'t return 200:' + str(response))

        # Ensure lock exists
        district = District.objects.get(pk=districtid)
        self.assertTrue(district.is_locked, 'District wasn\'t locked.' + str(response))

        # Try adding geounits to the locked district (not allowed)
        self.plan.add_geounits(district_id, geounitids, levelid, self.plan.version)
        numunits = len(Plan.objects.get(pk=self.plan.id).get_base_geounits(0.1))
        self.assertEqual(0, numunits, 'Geounits were added to a locked district. Num geounits: %d' % numunits)
        
        # Issue unlock command
        response = client.post('/districtmapping/plan/%d/district/%d/lock/' % (self.plan.id, district_id), { 'lock':False, 'version':self.plan.version })
        self.assertEqual(200, response.status_code, 'Lock handler didn\'t return 200:' + str(response))

        # Ensure lock has been removed
        district = District.objects.get(pk=districtid)
        self.assertFalse(district.is_locked, 'District wasn\'t unlocked.' + str(response))

        # Add geounits to the plan
        self.plan.add_geounits(district_id, geounitids, levelid, self.plan.version)
        numunits = len(Plan.objects.get(pk=self.plan.id).get_base_geounits(0.1))
        self.assertEqual(81, numunits, 'Geounits could not be added to an unlocked district. Num geounits: %d' % numunits)

    def test_district_locking2(self):
        """
        Test the case where adding a partially selected geometry (due to
        locking) may add the entire geometry's aggregate value.
        """
        geounits = self.geounits[self.geolevels[1].id]

        dist1ids = geounits[0:3] + geounits[9:12]
        dist2ids = geounits[18:21] + geounits[27:30] + geounits[36:39]

        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids, self.geolevels[1].id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids, self.geolevels[1].id, self.plan.version)

        district1 = max(District.objects.filter(plan=self.plan,district_id=self.district1.district_id),key=lambda d: d.version)
        district1units = district1.get_base_geounits(0.1)

        self.assertEqual(54, len(district1units), 'Incorrect number of geounits returned in dist1: %d' % len(district1units))

        district2 = max(District.objects.filter(plan=self.plan,district_id=self.district2.district_id),key=lambda d: d.version)
        district2units = district2.get_base_geounits(0.1)

        self.assertEqual(81, len(district2units), 'Incorrect number of geounits returned in dist2: %d' % len(district2units))

        geounits = self.geounits[self.geolevels[0].id] 
        dist3ids = geounits[1:3] + geounits[4:6] + geounits[7:9]

        dist3ids = map(lambda x: str(x.id), dist3ids)

        self.plan.add_geounits(self.district2.district_id + 1, dist3ids, self.geolevels[0].id, self.plan.version)

        district3 = max(District.objects.filter(plan=self.plan,district_id=self.district2.district_id+1),key=lambda d: d.version)
        district3units = district3.get_base_geounits(0.1)

        self.assertEqual(486, len(district3units), 'Incorrect number of geounits returned in dist3: %d' % len(district3units))

        # Plan looks like this now:
        #
        #  *-----------*-----------*-----------*
        #  |           |                       |
        #  |           |                       |
        #  |           |                       |
        #  |           |                       | 
        #  |           |                       |
        #  *           *           *           *
        #  |           |                       |
        #  |           |                       |
        #  +-----------+      District 3       |
        #  |           |                       |
        #  | District 2|                       |
        #  *           *           *           *
        #  |           |                       |
        #  +-----------+                       |
        #  |           |                       |
        #  | District 1|                       |
        #  |           |                       |
        #  *-----------*-----------*-----------*

        # Try locking District 2, selecting the large block that totally
        # contains District 1, and add it to District 3
        district2.is_locked = True
        district2.save()

        districtpre_computed = ComputedCharacteristic.objects.filter(district__in=[district1,district2,district3],subject=self.subject1).order_by('district').values_list('number',flat=True)
        presum = 0;
        for pre in districtpre_computed:
            presum += pre

        self.plan.add_geounits(district3.district_id, [str(geounits[0].id)], self.geolevels[0].id, self.plan.version)


        district1 = max(District.objects.filter(plan=self.plan,district_id=self.district1.district_id),key=lambda d: d.version)
        district2 = max(District.objects.filter(plan=self.plan,district_id=self.district2.district_id),key=lambda d: d.version)
        district3 = max(District.objects.filter(plan=self.plan,district_id=district3.district_id),key=lambda d: d.version)

        districtpost_computed = ComputedCharacteristic.objects.filter(district__in=[district1,district2,district3],subject=self.subject1).order_by('district').values_list('number',flat=True)
        postsum = 0;
        for post in districtpost_computed:
            postsum += post

        self.assertEqual(presum, postsum, 'The computed districts of the new plan do not match the computed districts of the old plan, when only reassigning geography. (e:%0.2f,a:%0.2f)' % (presum, postsum))

    def test_get_base_geounits(self):
        """
        Test getting base geounits
        """
        geounits = self.geounits[self.geolevels[0].id]

        dist1ids = [str(geounits[0].id)]
        dist2ids = [str(geounits[1].id)]

        self.plan.add_geounits(self.district1.district_id, dist1ids, self.geolevels[0].id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids, self.geolevels[0].id, self.plan.version)

        # Test getting the base geounits for a district
        district1 = max(District.objects.filter(plan=self.plan,district_id=self.district1.district_id),key=lambda d: d.version)
        district1units = district1.get_base_geounits(0.1)
        self.assertEqual(81, len(district1units), 'Incorrect number of geounits returned in dist1: %d' % len(district1units))

        district2 = max(District.objects.filter(plan=self.plan,district_id=self.district2.district_id),key=lambda d: d.version)
        district2units = district2.get_base_geounits(0.1)
        self.assertEqual(81, len(district2units), 'Incorrect number of geounits returned in dist2: %d' % len(district2units))

        # Test getting the base geounits for a plan
        plan = Plan.objects.get(pk=self.plan.id)
        planunits = plan.get_base_geounits(0.1)
        self.assertEqual(162, len(planunits), 'Incorrect number of geounits returned in plan: %d' % len(planunits))

        # Test sorting the units by geounit id
        planunits.sort(key=lambda unit: unit[0])
        lastid = 0
        for unit in planunits:
            self.assertTrue(unit[0] >= lastid, 'Not in order: %d < %d' % (unit[0], lastid))
            lastid = unit[0]

        # Test getting assigned geounits
        assigned = plan.get_assigned_geounits(0.1)
        self.assertEqual(162, len(assigned), 'Incorrect number of assigned geounits returned: %d' % len(assigned))

        # Test getting unassigned geounits
        unassigned = plan.get_unassigned_geounits(0.1)
        self.assertEqual(729 - 162, len(unassigned), 'Incorrect number of unassigned geounits returned: %d' % len(unassigned))

    def test_plan2index(self):
        """
        Test exporting a plan
        """
        geounits = self.geounits[self.geolevels[0].id]
        dist1ids = [str(geounits[0].id)]
        self.plan.add_geounits(self.district1.district_id, dist1ids, self.geolevels[0].id, self.plan.version)

        plan = Plan.objects.get(pk=self.plan.id)
        archive = DistrictIndexFile.plan2index(plan)
        zin = zipfile.ZipFile(archive.name, "r")
        strz = zin.read(plan.name + ".csv")
        zin.close()
        os.remove(archive.name)
        self.assertEqual(891, len(strz), 'Index file was the wrong length: %d' % len(strz))

    def test_sorted_district_list(self):
        """
        Test the sorted district list for reporting
        """
        geounits = self.geounits[self.geolevels[0].id]
        dist1ids = [str(geounits[0].id)]
        self.plan.add_geounits(self.district1.district_id, dist1ids, self.geolevels[0].id, self.plan.version)
        plan = Plan.objects.get(pk=self.plan.id)

        mapping = plan.get_base_geounits()
        mapping.sort(key=lambda unit: unit[0])

        geolevel = plan.legislative_body.get_base_geolevel()
        geounits = Geounit.objects.filter(geolevel=geolevel)
        max_and_min = geounits.aggregate(Min('id'), Max('id'))
        min_id = int(max_and_min['id__min'])
        max_id = int(max_and_min['id__max'])

        sorted_district_list = list()
        row = None
        if len(mapping) > 0:
             row = mapping.pop(0)
        for i in range(min_id, max_id + 1):
            if row and row[0] == i:
                district_id = row[2]
                row = None
                if len(mapping) > 0:
                    row = mapping.pop(0)
            else:
                district_id = 'NA'
            sorted_district_list.append(district_id)

        self.assertEqual(729, len(sorted_district_list), 'Sorted district list was the wrong length: %d' % len(sorted_district_list))

    def test_paste_districts(self):
        
        # Set up the test using geounits in the 2nd level
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]
        dist1ids = geounits[0:3] + geounits[9:12] + geounits[18:21]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits(self.district1.district_id, dist1ids, geolevelid, self.plan.version)

        district1 = max(District.objects.filter(plan=self.plan,district_id=self.district1.district_id),key=lambda d: d.version)
        target = Plan.create_default('Paste Plan 1', self.plan.legislative_body, owner=self.user, template=False, is_pending=False)
        target.save();

        # Paste the district and check returned number, geometry and stats
        result = target.paste_districts((district1,))
        self.assertEquals(1, len(result), "District1 wasn't pasted into the plan")
        target1 = District.objects.get(pk=result[0])
        self.assertTrue(target1.geom.equals(district1.geom), "Geometries of pasted district doesn't match original")
        self.assertEquals(target1.name, "TestMember 1", "Proper name wasn't assigned to pasted district")

        target_stats =  ComputedCharacteristic.objects.filter(district = result[0])
        for stat in target_stats:
           district1_stat = ComputedCharacteristic.objects.get(district=district1, subject=stat.subject)
           self.assertEquals(stat.number, district1_stat.number, "Stats for pasted district (number) don't match")
           self.assertEquals(stat.percentage, district1_stat.percentage, "Stats for pasted district (percentage) don't match")

        # Add district 2 to a new plan so it doesn't overlap district 1
        new_for_2 = Plan.create_default('Paste Plan 2', self.plan.legislative_body, self.user, template=False, is_pending=False)
        dist2ids = geounits[10:13] + geounits[19:22] + geounits[28:31]
        dist2ids = map(lambda x: str(x.id), dist2ids)
        new_for_2.add_geounits(self.district2.district_id, dist2ids, geolevelid, self.plan.version)
        district2 = max(District.objects.filter(plan=new_for_2,district_id=self.district2.district_id),key=lambda d: d.version)

        # Paste district 2 into our target plan
        result = target.paste_districts((district2,))
        self.assertEquals(1, len(result), "District2 wasn't pasted into the plan")
        target2 = District.objects.get(pk=result[0])
        self.assertTrue(target2.geom.equals(district2.geom), "Geometries of pasted district doesn't match original\n")
        self.assertEquals(target2.name, "TestMember 2", "Proper name wasn't assigned to pasted district")
        
        target2_stats =  ComputedCharacteristic.objects.filter(district=target2)
        for stat in target2_stats:
            # Check on District 2 stats
            district2_stat = ComputedCharacteristic.objects.get(district=district2, subject=stat.subject)

            self.assertEquals(stat.number, district2_stat.number, "Stats for pasted district (number) don't match")
            self.assertEquals(stat.percentage, district2_stat.percentage, "Stats for pasted district (percentage) don't match")
            
        # Calculate what district 1 should look like
        unassigned = max(District.objects.filter(plan=self.plan,name="Unassigned"),key=lambda d: d.version)
        self.plan.add_geounits(unassigned.district_id, dist2ids, geolevelid, self.plan.version)
        self.district1 = max(District.objects.filter(plan=self.plan,district_id=self.district1.district_id),key=lambda d: d.version)

        # Get the statistics for the district 1 in the target
        target1 = max(District.objects.filter(plan=target,district_id=target1.district_id),key=lambda d: d.version)
        self.assertTrue(target1.geom.equals(self.district1.geom), 'Geometry of pasted geometry is not correct')
        target_stats = target1.computedcharacteristic_set.all()
        
        for stat in target_stats:
            district1_stat = ComputedCharacteristic.objects.get(district=self.district1, subject=stat.subject)
            self.assertEquals(stat.number, district1_stat.number, "Stats for pasted district (number) don't match")
            self.assertEquals(stat.percentage, district1_stat.percentage, "Stats for pasted district (percentage) don't match")
            
        # Make sure that method fails when adding too many districts
        target.legislative_body.max_districts = 2;
        target.legislative_body.save()
        self.assertRaises(Exception, target.paste_districts, (district2,), 'Allowed to merge too many districts')

    def test_paste_districts_onto_locked(self):
        
        # Set up the test using geounits in the 2nd level
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]
        dist1ids = geounits[0:3] + geounits[9:12] + geounits[18:21]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits(self.district1.district_id, dist1ids, geolevelid, self.plan.version)

        district1 = max(District.objects.filter(plan=self.plan,district_id=self.district1.district_id),key=lambda d: d.version)
        target = Plan.create_default('Paste Plan 1', self.plan.legislative_body, owner=self.user, template=False, is_pending=False)
        target.save();

        # Add a district to the Paste Plan
        target.add_geounits(self.district1.district_id, dist1ids, geolevelid, self.plan.version)
        # Lock that district
        district1 = max(District.objects.filter(plan=target,district_id=self.district1.district_id),key=lambda d: d.version)
        district1.is_locked = True;
        district1.save()
        # Add a district that would overlap district1 to self.plan
        dist2ids = geounits[10:13] + geounits[19:22] + geounits[28:31]
        dist2ids = map(lambda x: str(x.id), dist2ids)
        self.plan.add_geounits(self.district2.district_id, dist2ids, geolevelid, self.plan.version)
        self.district2 = max(District.objects.filter(plan=self.plan,district_id=self.district2.district_id),key=lambda d: d.version)

        # Paste district2 into our Paste Plan, on top of the locked district1
        target.paste_districts((self.district2,))
        district2 = max(District.objects.filter(plan=target,district_id=self.district2.district_id),key=lambda d: d.version)
        # Create in self.plan the district we want to see if Paste Plan
        unassigned = max(District.objects.filter(plan=self.plan,name="Unassigned"),key=lambda d: d.version)
        self.plan.add_geounits(unassigned.district_id, dist1ids, geolevelid, self.plan.version)
        self.district2 = max(District.objects.filter(plan=self.plan,district_id=self.district2.district_id),key=lambda d: d.version)
        # Check stats and geometry
        self.assertTrue(self.district2.geom.equals(district2.geom), 'Geom for district pasted over locked district doesn\'t match')
        target_stats = district2.computedcharacteristic_set.all()
        for stat in target_stats:
            expected_stat = ComputedCharacteristic.objects.get(district=self.district2, subject=stat.subject)
            self.assertEquals(stat.number, expected_stat.number, "Stats for pasted district (number) don't match")
            self.assertEquals(stat.percentage, expected_stat.percentage, "Stats for pasted district (percentage) don't match")
        

    def test_paste_multiple_districts(self):
        # Set up the test using geounits in the 2nd level
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]
        dist1ids = geounits[0:3] + geounits[9:12] + geounits[18:21]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits(self.district1.district_id, dist1ids, geolevelid, self.plan.version)

        self.district3 = District(plan=self.plan, name="TestMember 3", district_id = 4)
        self.district3.save()
        dist3ids = geounits[20:23] + geounits[29:32] + geounits[38:41]
        dist3ids = map(lambda x: str(x.id), dist3ids)
        self.plan.add_geounits(self.district3.district_id, dist3ids, geolevelid, self.plan.version)

        self.district1 = max(District.objects.filter(plan=self.plan,district_id=self.district1.district_id),key=lambda d: d.version)
        self.district3 = max(District.objects.filter(plan=self.plan,district_id=self.district3.district_id),key=lambda d: d.version)

        target = Plan.create_default('Paste Plan', self.plan.legislative_body, owner=self.user, template=False, is_pending=False)
        target.save();

        # Add a district to the Paste Plan
        dist2ids = geounits[10:12] + geounits[19:22] + geounits[29:31]
        dist2ids = map(lambda x: str(x.id), dist2ids)
        target.add_geounits(self.district2.district_id, dist2ids, geolevelid, target.version)

        # Paste over top of it with two districts, both intersecting the present district
        old_version = target.version
        results = target.paste_districts((self.district1, self.district3))
        new_version = target.version
        # Check that we've only moved up one version
        self.assertTrue(new_version == old_version + 1, 'Adding multiple districts increased plan version by %d rather than 1' % (new_version - old_version))
        # Check stats and geometry for all districts in Paste Plan
        self.assertEqual(2, len(results), 'Didn\'t get 2 pasted district IDs')
        district1 = District.objects.get(pk=results[0])
        self.assertTrue(self.district1.geom.equals(district1.geom), 'Geom for pasted district doesn\'t match')
        target_stats = district1.computedcharacteristic_set.all()
        for stat in target_stats:
            expected_stat = ComputedCharacteristic.objects.get(district=self.district1, subject=stat.subject)
            self.assertEquals(stat.number, expected_stat.number, "Stats for pasted district (number) don't match")
            self.assertEquals(stat.percentage, expected_stat.percentage, "Stats for pasted district (percentage) don't match")

        district3 = District.objects.get(pk=results[1])
        self.assertTrue(self.district3.geom.equals(district3.geom), 'Geom for pasted district doesn\'t match')
        target_stats = district3.computedcharacteristic_set.all()
        for stat in target_stats:
            expected_stat = ComputedCharacteristic.objects.get(district=self.district3, subject=stat.subject)
            self.assertEquals(stat.number, expected_stat.number, "Stats for pasted district (number) don't match")
            self.assertEquals(stat.percentage, expected_stat.percentage, "Stats for pasted district (percentage) don't match")

        # Test that already-present district is gone.
        district2 = max(District.objects.filter(plan=target,district_id=self.district2.district_id),key=lambda d: d.version)
        self.assertTrue(district2.geom == None, 'District 2 geom wasn\'t emptied when it was pasted over')
        self.assertEqual(0, len(district2.computedcharacteristic_set.all()), 'District2 still has characteristics')

    def test_get_available_districts(self):
        # Set the max_districts setting for this test
        self.plan.legislative_body.max_districts = 1
        self.plan.legislative_body.save()

        self.assertEqual(1, self.plan.get_available_districts(), 'Wrong number of available districts returned initially: %d')

        # Set up the test using geounits in the 2nd level
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]

        # Add a district
        dist1ids = geounits[0:3] + geounits[9:12] + geounits[18:21]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits(self.district1.district_id, dist1ids, geolevelid, self.plan.version)
        self.assertEqual(0, self.plan.get_available_districts(), 'Wrong number of available districts returned after adding a district')

        # Unassign the district
        unassigned = District.objects.get(plan=self.plan, name="Unassigned")
        self.plan.add_geounits(unassigned.district_id, dist1ids, geolevelid, self.plan.version)
        self.assertEqual(1, self.plan.get_available_districts(), 'Wrong number of available districts returned after removing a district')
        
    def test_combine_districts(self):
        # Set up three districst using geounits in the 2nd level
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]

        # District 1 in the corner
        dist1ids = geounits[0:3] + geounits[9:12] + geounits[18:21]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits(self.district1.district_id, dist1ids, geolevelid, self.plan.version)

        # District 2 right of that
        dist2ids = geounits[3:6] + geounits[12:15] + geounits[21:24]
        dist2ids = map(lambda x: str(x.id), dist2ids)
        self.plan.add_geounits(self.district2.district_id, dist2ids, geolevelid, self.plan.version)

        # District 3 above district 1
        dist3ids = geounits[27:30] + geounits[36:39] + geounits[45:48]
        dist3ids = map(lambda x: str(x.id), dist3ids)
        dist3_district_id = 4
        self.plan.add_geounits(dist3_district_id, dist3ids, geolevelid, self.plan.version)

        all_3 = self.plan.get_districts_at_version(self.plan.version,include_geom=True)
        initial_state = { }
        total = 0
        for district in all_3:
            initial_state[district.district_id] = district

        totals = {}
        for subject in Subject.objects.all():
            total = ComputedCharacteristic.objects.filter(district__plan=self.plan, subject=subject).aggregate(SumAgg('number'))
            totals[subject] = total['number__sum']

        total_geom = District.objects.filter(plan = self.plan).unionagg()

        # Paste them all together now
        self.district1 = initial_state[self.district1.district_id]
        self.district2 = initial_state[self.district2.district_id]
        self.district3 = initial_state[dist3_district_id]

        result = self.plan.combine_districts(self.district1, (self.district2, self.district3))
        self.assertTrue(result, 'Combine operation returned false')

        # Refresh our plan version
        self.plan = Plan.objects.get(pk=self.plan.id)
        combined = District.objects.get(district_id=self.district1.district_id, plan=self.plan, version=self.plan.version)
        self.assertTrue(combined.geom.equals(total_geom), "Geometries of combined districts don't match")
# TODO: Figure out a way to get this test right - computedcharacteristics and versioning aren't working correctly
#        for subject in Subject.objects.all():
#            characteristic = ComputedCharacteristic.objects.get(subject=subject,district=combined)
#            sys.stdout.write('Characteristic for %s : %d, %d' % (characteristic.subject, characteristic.number, characteristic.percentage))
#            self.assertEqual(characteristic.number, totals[subject], 'Stats (number) don\'t match on combined district')
#            self.assertEqual(characteristic.number, total, 'Stats (number) don\'t match on combined district')
#            self.assertEqual(characteristic.percentage, totals[subject], 'Stats (percentage) don\'t match on combined district')

class GeounitMixTestCase(BaseTestCase):
    """
    Unit tests to test the mixed geounit spatial queries.
    """
    
    def test_numgeolevels(self):
        """
        Test the number of geolevels created.
        """
        self.assertEquals(3, len(self.geolevels), 'Number of geolevels for mixed geounits is incorrect.')

    def test_numgeounits1(self):
        """
        Test the number of geounits in the first tier of geounits.
        """
        self.assertEquals(9, len(self.geounits[self.geolevels[0].id]), 'Number of geounits at geolevel "%s" is incorrect.' % self.geolevels[0].name)

    def test_numgeounits2(self):
        """
        Test the number of geounits in the second tier of geounits.
        """
        self.assertEquals(81, len(self.geounits[self.geolevels[1].id]), 'Number of geounits at geolevel "%s" is incorrect.' % self.geolevels[1].name)

    def test_numgeounits3(self):
        """
        Test the number of geounits in the third tier of geounits.
        """
        self.assertEquals(729, len(self.geounits[self.geolevels[2].id]), 'Number of geounits at geolevel "%s" is incorrect.' % self.geolevels[2].name)

    def test_allunitscount(self):
        """
        Test that known geounits are spatially contained within other geounits.
        """
        unit1 = self.geounits[self.geolevels[0].id][0]

        unit2 = self.geounits[self.geolevels[1].id][0]

        self.assertTrue(unit1.geom.contains(unit2.geom), 'First unit does not contain secont unit.')

        unit3 = self.geounits[self.geolevels[2].id][0]

        self.assertTrue(unit1.geom.contains(unit3.geom), 'First unit does not contain second unit.')
        self.assertTrue(unit2.geom.contains(unit3.geom), 'Second unit does not contain third unit.')

    def test_get_all_in(self):
        """
        Test the spatial query to get geounits within a known boundary.
        """
        level = self.geolevels[0]
        units = self.geounits[level.id]

        units = Geounit.objects.filter(geom__within=units[0].geom,geolevel__gt=level.id)

        numunits = len(units)
        self.assertEquals(90, numunits, 'Number of geounits within a high-level geounit is incorrect. (%d)' % numunits)

    def test_get_in_gu0(self):
        """
        Test the spatial query to get geounits within a known boundary.
        """
        level = self.geolevels[0]
        units = self.geounits[level.id]

        units = Geounit.objects.filter(geom__within=units[0].geom,geolevel=level.id+1)
        numunits = len(units)
        self.assertEquals(9, numunits, 'Number of geounits within geounit 1 is incorrect. (%d)' % numunits)

    def test_get_base(self):
        """
        Test the spatial query to get all geounits at the base geolevel within a boundary.
        """
        level = self.legbod.get_geolevels()[0]
        units = self.geounits[level.id]
        geounit_ids = tuple([units[0].id, units[1].id])
        base_level = self.legbod.get_base_geolevel()


        units = Geounit.objects.filter(geom__within=units[0].geom,geolevel=base_level)

        numunits = len(units)
        self.assertEquals(81, numunits, 'Number of geounits within a high-level geounit is incorrect. (%d)' % numunits)

    def test_get_mixed1(self):
        """
        Test the logic for getting mixed geounits inside a boundary at the
        highest geolevel.
        """
        level = self.geolevels[0]
        bigunits = self.geounits[level.id]
        ltlunits = self.geounits[self.geolevels[1].id]
        boundary = bigunits[0].geom.difference(ltlunits[9].geom)

        units = Geounit.get_mixed_geounits([str(bigunits[0].id)], self.legbod, level.id, boundary, True)
        numunits = len(units)
        self.assertEquals(8, numunits, 'Number of geounits inside boundary is incorrect. (%d)' % numunits)

    def test_get_imixed1(self):
        """
        Test the logic for getting mixed geounits outside a boundary at the
        highest geolevel.
        """
        level = self.geolevels[0]
        bigunits = self.geounits[level.id]
        ltlunits = self.geounits[self.geolevels[1].id]
        boundary = bigunits[0].geom.difference(ltlunits[9].geom)

        units = Geounit.get_mixed_geounits([str(bigunits[0].id)], self.legbod, level.id, boundary, False)
        numunits = len(units)
        self.assertEquals(1, numunits, 'Number of geounits outside boundary is incorrect. (%d)' % numunits)

    def test_get_mixed2(self):
        """
        Test the logic for getting mixed geounits inside a boundary at the
        middle geolevel.
        """
        level = self.geolevels[1]
        bigunits = self.geounits[level.id]
        ltlunits = self.geounits[self.geolevels[2].id]
        boundary = bigunits[0].geom.difference(ltlunits[27].geom)

        units = Geounit.get_mixed_geounits([str(bigunits[0].id)], self.legbod, level.id, boundary, True)
        numunits = len(units)
        self.assertEquals(8, numunits, 'Number of geounits inside boundary is incorrect. (%d)' % numunits)

    def test_get_imixed2(self):
        """
        Test the logic for getting mixed geounits outside a boundary at the
        middle geolevel.
        """
        level = self.geolevels[1]
        bigunits = self.geounits[level.id]
        ltlunits = self.geounits[self.geolevels[2].id]
        boundary = bigunits[0].geom.difference(ltlunits[27].geom)

        units = Geounit.get_mixed_geounits([str(bigunits[0].id)], self.legbod, level.id, boundary, False)
        numunits = len(units)
        self.assertEquals(1, numunits, 'Number of geounits outside boundary is incorrect. (%d)' % numunits)

    def test_get_mixed3(self):
        """
        Test the logic for getting mixed geounits inside a boundary at the
        lowest geolevel.
        """
        level = self.geolevels[0]
        bigunits = self.geounits[level.id]
        boundary = MultiPolygon(Polygon(LinearRing(
            Point((0,0)),
            Point((1,0)),
            Point((1,1)),
            Point((0,0))
        )))
        boundary.srid = 3785
        
        units = Geounit.get_mixed_geounits([str(bigunits[1].id), str(bigunits[2].id), str(bigunits[5].id)], self.legbod, level.id, boundary, True)
        numunits = len(units)
        self.assertEquals(3, numunits, 'Number of geounits inside boundary is incorrect. (%d)' % numunits)

        units = Geounit.get_mixed_geounits([str(bigunits[0].id),str(bigunits[4].id),str(bigunits[8].id)], self.legbod, level.id, boundary, True)
        numunits = len(units)
        self.assertEquals(63, numunits, 'Number of geounits inside boundary is incorrect. (%d)' % numunits)

    def test_get_imixed3(self):
        """
        Test the logic for getting mixed geounits outside a boundary at the
        lowest geolevel.
        """
        level = self.geolevels[0]
        bigunits = self.geounits[level.id]
        boundary = MultiPolygon(Polygon(LinearRing(
            Point((0,0)),
            Point((1,0)),
            Point((1,1)),
            Point((0,0))
        )))
        boundary.srid = 3785
        
        units = Geounit.get_mixed_geounits([str(bigunits[3].id),str(bigunits[6].id),str(bigunits[7].id)], self.legbod, level.id, boundary, False)
        numunits = len(units)
        # this test should return 3, for the large geounits are completely
        # without yet intersect at the corner. the net geometry from this
        # set of mixed geounits is correct, though
        self.assertEquals(19, numunits, 'Number of geounits outside boundary is incorrect. (%d)' % numunits)

        units = Geounit.get_mixed_geounits([str(bigunits[0].id),str(bigunits[4].id),str(bigunits[8].id)], self.legbod, level.id, boundary, False)
        numunits = len(units)
        self.assertEquals(63, numunits, 'Number of geounits outside boundary is incorrect. (%d)' % numunits)


class PurgeTestCase(BaseTestCase):
    """
    Unit tests to test the methods for purging extra districts off a plan.
    """
    def setUp(self):
        BaseTestCase.setUp(self)

        # create a new buch of districts for this test case
        self.plan.district_set.all().delete()

        geolevelid = self.geolevels[1].id

        # create Districts
        for i in range(0,9):
            start = 9 * i
            end = 9 * (i + 1)

            # overlap the previous assignment to create multiple versions
            # of districts
            if i > 0:
                start -= 1
            if i < 8:
                end += 1

            geounits = self.geounits[geolevelid][start:end]
            geounits = map(lambda x: str(x.id), geounits)
       
            self.plan.add_geounits( (i+1), geounits, geolevelid, self.plan.version)

    def test_purge_lt_zero(self):
        self.plan.purge(before=-1)

        self.assertEquals(9, self.plan.version, 'Plan version is incorrect.')
        count = self.plan.district_set.count()
        self.assertEquals(17, count, 'Number of districts in plan is incorrect. (e:17,a:%d)' % count)
        
    def test_purge_gt_max(self):
        self.plan.purge(after=9)

        self.assertEquals(9, self.plan.version, 'Plan version is incorrect.')
        count = self.plan.district_set.count()
        self.assertEquals(17, count, 'Number of districts in plan is incorrect. (e:17,a:%d)' % count)

    def test_purge_lt_four(self):
        self.plan.purge(before=4)

        self.assertEquals(9, self.plan.version, 'Plan version is incorrect.')

        # should have 14 items, purging old versions of districts at version
        # 0, 1, 2, and 3 but keeping the most recent version of each 
        # district 
        # (even if the district version is less than the 'before' keyword)
        count = self.plan.district_set.count()
        self.assertEquals(14, count, 'Number of districts in plan is incorrect. (e:14, a:%d)' % count)

    def test_purge_lt_nine(self):
        self.plan.purge(before=9)

        self.assertEquals(9, self.plan.version, 'Plan version is incorrect.')

        # should have 9 items, purging all old versions of districts, but 
        # keeping the most recent version of each district 
        # (even if the district version is less than the 'before' keyword)
        count = self.plan.district_set.count()
        self.assertEquals(9, count, 'Number of districts in plan is incorrect. (e:9, a:%d)' % count)

    def test_purge_gt_five(self):
        self.plan.purge(after=5)

        self.assertEquals(9, self.plan.version, 'Plan version is incorrect.')

        # should have 9 items, since everything after version 5 was deleted
        # 2 of District 1
        # 2 of District 2
        # 2 of District 3
        # 2 of District 4
        # 1 of District 5
        count = self.plan.district_set.count()
        self.assertEquals(9, count, 'Number of districts in plan is incorrect. (e:9, a:%d)' % count)

    def test_purge_many_edits(self):
        # Reset the undo mechanism
        settings.MAX_UNDOS_DURING_EDIT = 0
        settings.MAX_UNDOS_AFTER_EDIT = 0

        geolevelid = self.geolevels[1].id

        oldversion = self.plan.version

        count = self.plan.district_set.count()

        # every add_geounits call should add 2 districts to the 
        # district_set, since this geounit should be removed from one
        # district, and added to another.
        for i in range(0,8):
            item = 9 * (i + 1) + 1

            item = str(self.geounits[geolevelid][item].id)
            self.plan.add_geounits( (i+1), [item], geolevelid, self.plan.version)

        # net gain: 16 districts

        self.assertEquals(16, self.plan.district_set.count() - count, 'Incorrect of districts in the plan district_set.')
        self.assertEquals(8, self.plan.version-oldversion, 'Incorrect number of versions incremented after 8 edits.')

        self.plan.purge(before=oldversion)

        count = self.plan.district_set.count()
        self.assertEquals(25, count, 'Number of districts in plan is incorrect. (e:25, a:%d)' % count)

    def test_version_back(self):
        version = self.plan.get_nth_previous_version(self.plan.version)

        self.assertEquals(0, version, 'Walking back %d versions does not land at zero.' % self.plan.version)

        version = self.plan.get_nth_previous_version(self.plan.version-1)

        self.assertEquals(1, version, 'Walking back %d versions does not land at one.' % (self.plan.version - 1))

    def test_purge_versions(self):
        geolevelid = self.geolevels[1].id

        oldversion = self.plan.version
        for i in range(oldversion - 1, 4, -1):
            item = 9 * (i + 1) - 2;
            item = str(self.geounits[geolevelid][item].id)
            self.plan.add_geounits( (i+1), [item], geolevelid, i)

        # added four new versions

        newversion = self.plan.version
        self.assertEquals(13, newversion, 'Adding items to sequential positions in history resulted in the wrong number of versions. (e:17,a:%d)' % newversion)

        # the first step back in history shoulde be version 4, since the
        # last edit was off that version

        previous = self.plan.get_nth_previous_version(1)
        self.assertEquals(5, previous, 'The previous version is incorrect, since edits were performed off of 8,7,6,5 versions, with the last edit being off of version 5. (e:5, a:%d)' % previous)

        previous = self.plan.get_nth_previous_version(3)
        self.assertEquals(3, previous, '(e:3, a:%d)' % previous)

        previous = self.plan.get_nth_previous_version(5)
        self.assertEquals(1, previous, '(e:1, a:%d)' % previous)

class CalculatorCase(BaseTestCase):
    def test_sum1(self):
        sum1 = Sum()
        sum1.arg_dict['value1'] = ('literal','10',)
        sum1.arg_dict['value2'] = ('literal','20',)

        self.assertEquals(None,sum1.result)
        sum1.compute(district=self.district1)
        self.assertEquals(30,sum1.result)

        sum2 = Sum()

        self.assertEquals(None,sum2.result)
        self.assertEquals(30,sum1.result)

        sum2.compute(district=self.district1)

        self.assertEquals(0,sum2.result)
        self.assertEquals(30,sum1.result)
        
    def test_sum2a(self):
        sumcalc = Sum()
        sumcalc.arg_dict['value1'] = ('literal','0',)
        sumcalc.arg_dict['value2'] = ('literal','1',)
        sumcalc.arg_dict['value3'] = ('literal','2',)
        sumcalc.compute(plan=self.plan)

        # The sum of a plan w/3 districts and w/3 literals is the sum
        # of literals * the number of plans

        self.assertEquals(9, sumcalc.result, 'Incorrect value during summation. (e:%d,a:%d)' % (9, sumcalc.result))

    def test_sum2b(self):
        sumcalc = Sum()
        sumcalc.arg_dict['value1'] = ('literal','0',)
        sumcalc.arg_dict['value2'] = ('literal','1',)
        sumcalc.arg_dict['value3'] = ('literal','2',)
        sumcalc.compute(district=self.district1)

        self.assertEquals(3, sumcalc.result, 'Incorrect value during summation. (e:%d,a:%d)' % (3, sumcalc.result))

    def test_sum3(self):
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]

        dist1ids = geounits[0:3] + geounits[9:12]
        exqset = Characteristic.objects.filter(geounit__in=dist1ids,subject=self.subject1)
        expected = float(exqset.aggregate(SumAgg('number'))['number__sum']) + 5.0

        dist1ids = map(lambda x: str(x.id), dist1ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevelid, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)

        sumcalc = Sum()
        sumcalc.arg_dict['value1'] = ('subject',self.subject1.name,)
        sumcalc.arg_dict['value2'] = ('literal','5.0',)
        sumcalc.compute(district=district1)

        actual = sumcalc.result

        self.assertEquals(expected, actual, 'Incorrect value during summation. (e:%d,a:%d)' % (expected, actual))

    def test_sum4(self):
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]

        dist1ids = geounits[0:3] + geounits[9:12]
        exqset = Characteristic.objects.filter(geounit__in=dist1ids,subject=self.subject1)
        expected = float(exqset.aggregate(SumAgg('number'))['number__sum'])

        dist1ids = map(lambda x: str(x.id), dist1ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevelid, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)

        sumcalc = Sum()
        sumcalc.arg_dict['value1'] = ('subject',self.subject1.name,)
        sumcalc.compute(district=district1)

        actual = sumcalc.result

        self.assertEquals(expected, actual, 'Incorrect value during summation. (e:%d,a:%d)' % (expected, actual))

    def test_sum5(self):
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]

        dist1ids = geounits[0:3] + geounits[9:12]
        dist2ids = geounits[18:21] + geounits[27:30] + geounits[36:39]
        exqset = Characteristic.objects.filter(geounit__in=dist1ids+dist2ids,subject=self.subject1)
        expected = float(exqset.aggregate(SumAgg('number'))['number__sum'])

        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevelid, self.plan.version)
        self.plan.add_geounits( self.district2.district_id, dist2ids, geolevelid, self.plan.version)

        sumcalc = Sum()
        sumcalc.arg_dict['value1'] = ('subject',self.subject1.name,)
        sumcalc.compute(plan=self.plan)

        actual = sumcalc.result

        self.assertEquals(expected, actual, 'Incorrect value during summation. (e:%d,a:%d)' % (expected, actual))


    def test_percent1(self):
        pctcalc = Percent()
        pctcalc.arg_dict['numerator'] = ('literal','1',)
        pctcalc.arg_dict['denominator'] = ('literal','2',)
        pctcalc.compute(district=self.district1)

        self.assertEquals(0.5, pctcalc.result, 'Incorrect value during percentage. (e:%d,a:%d)' % (0.5, pctcalc.result))

    def test_percent2(self):
        pctcalc = Percent()
        pctcalc.arg_dict['numerator'] = ('literal','2',)
        pctcalc.arg_dict['denominator'] = ('literal','4',)
        pctcalc.compute(district=self.district1)

        self.assertEquals(0.5, pctcalc.result, 'Incorrect value during percentage. (e:%d,a:%d)' % (0.5, pctcalc.result))

    def test_percent3(self):
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]

        dist1ids = geounits[0:3] + geounits[9:12]
        exqset = Characteristic.objects.filter(geounit__in=dist1ids,subject=self.subject1)
        expected = float(exqset.aggregate(SumAgg('number'))['number__sum']) / 10.0

        dist1ids = map(lambda x: str(x.id), dist1ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevelid, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)

        pctcalc = Percent()
        pctcalc.arg_dict['numerator'] = ('subject',self.subject1.name,)
        pctcalc.arg_dict['denominator'] = ('literal','10.0',)
        pctcalc.compute(district=district1)

        actual = pctcalc.result

        self.assertEquals(expected, actual, 'Incorrect value during percentage. (e:%f,a:%f)' % (expected, actual))

    def test_percent4(self):
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]

        dist1ids = geounits[0:3] + geounits[9:12]
        dist2ids = geounits[18:21] + geounits[27:30] + geounits[36:39]
        exqset = Characteristic.objects.filter(geounit__in=dist1ids+dist2ids,subject=self.subject1)
        expected = float(exqset.aggregate(SumAgg('number'))['number__sum']) / 20.0

        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevelid, self.plan.version)
        self.plan.add_geounits( self.district2.district_id, dist2ids, geolevelid, self.plan.version)

        pctcalc = Percent()
        pctcalc.arg_dict['numerator'] = ('subject',self.subject1.name,)
        pctcalc.arg_dict['denominator'] = ('literal','10.0',)
        pctcalc.compute(plan=self.plan)

        actual = pctcalc.result

        self.assertEquals(expected, actual, 'Incorrect value during percentage. (e:%f,a:%f)' % (expected, actual))

    def test_percent5(self):
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]

        dist1ids = geounits[0:3] + geounits[9:12]
        dist2ids = geounits[18:21] + geounits[27:30] + geounits[36:39]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevelid, self.plan.version)
        self.plan.add_geounits( self.district2.district_id, dist2ids, geolevelid, self.plan.version)

        pctcalc = Percent()
        pctcalc.arg_dict['numerator'] = ('subject',self.subject1.name,)
        pctcalc.arg_dict['denominator'] = ('subject',self.subject1.name,)
        pctcalc.compute(plan=self.plan)

        actual = pctcalc.result

        self.assertEquals(1.0, actual, 'Incorrect value during percentage. (e:%f,a:%f)' % (1.0, actual))


    def test_threshold1(self):
        thrcalc = Threshold()
        thrcalc.arg_dict['value'] = ('literal','1',)
        thrcalc.arg_dict['threshold'] = ('literal','2',)
        thrcalc.compute(district=self.district1)

        self.assertEquals(0, thrcalc.result, 'Incorrect value during threshold. (e:%s,a:%s)' % (0, thrcalc.result))

    def test_threshold2(self):
        thrcalc = Threshold()
        thrcalc.arg_dict['value'] = ('literal','2',)
        thrcalc.arg_dict['threshold'] = ('literal','1',)
        thrcalc.compute(district=self.district1)

        self.assertEquals(1, thrcalc.result, 'Incorrect value during threshold. (e:%s,a:%s)' % (1, thrcalc.result))

    def test_threshold3(self):
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]

        dist1ids = geounits[0:3] + geounits[9:12]
        exqset = Characteristic.objects.filter(geounit__in=dist1ids,subject=self.subject1)
        expected = float(exqset.aggregate(SumAgg('number'))['number__sum']) > 10.0
        expected = 1 if expected else 0

        dist1ids = map(lambda x: str(x.id), dist1ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevelid, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)

        thrcalc = Threshold()
        thrcalc.arg_dict['value'] = ('subject',self.subject1.name,)
        thrcalc.arg_dict['threshold'] = ('literal','10.0',)
        thrcalc.compute(district=district1)

        actual = thrcalc.result

        self.assertEquals(expected, actual, 'Incorrect value during threshold. (e:%s,a:%s)' % (expected, actual))

    def test_threshold4(self):
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]

        dist1ids = geounits[0:3] + geounits[9:12]
        exqset = Characteristic.objects.filter(geounit__in=dist1ids,subject=self.subject1)
        expected = float(exqset.aggregate(SumAgg('number'))['number__sum']) > 5.0
        expected = 1 if expected else 0

        dist1ids = map(lambda x: str(x.id), dist1ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevelid, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)

        thrcalc = Threshold()
        thrcalc.arg_dict['value'] = ('subject',self.subject1.name,)
        thrcalc.arg_dict['threshold'] = ('literal','5.0',)
        thrcalc.compute(district=district1)

        actual = thrcalc.result

        self.assertEquals(expected, actual, 'Incorrect value during threshold. (e:%s,a:%s)' % (expected, actual))

    def test_threshold_plan1(self):
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]

        dist1ids = geounits[0:3] + geounits[9:12]
        dist2ids = geounits[18:21] + geounits[27:30] + geounits[36:39]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevelid, self.plan.version)
        self.plan.add_geounits( self.district2.district_id, dist2ids, geolevelid, self.plan.version)

        thrcalc = Threshold()
        thrcalc.arg_dict['value'] = ('subject',self.subject1.name,)
        thrcalc.arg_dict['threshold'] = ('literal','10.0',)
        thrcalc.compute(plan=self.plan)

        actual = thrcalc.result

        self.assertEquals(0, actual, 'Incorrect value during threshold. (e:%d,a:%d)' % (0, actual))

        thrcalc.arg_dict['threshold'] = ('literal','7.0',)
        thrcalc.compute(plan=self.plan)

        actual = thrcalc.result

        self.assertEquals(1, actual, 'Incorrect value during threshold. (e:%d,a:%d)' % (1, actual))

        thrcalc.arg_dict['threshold'] = ('literal','5.0',)
        thrcalc.compute(plan=self.plan)

        actual = thrcalc.result

        self.assertEquals(2, actual, 'Incorrect value during threshold. (e:%d,a:%d)' % (2, actual))


    def test_range1(self):
        rngcalc = Range()
        rngcalc.arg_dict['value'] = ('literal','2',)
        rngcalc.arg_dict['min'] = ('literal','1',)
        rngcalc.arg_dict['max'] = ('literal','3',)
        rngcalc.compute(district=self.district1)

        self.assertEquals(1, rngcalc.result, 'Incorrect value during range. (e:%s,a:%s)' % (1, rngcalc.result))

    def test_range2(self):
        rngcalc = Range()
        rngcalc.arg_dict['value'] = ('literal','1',)
        rngcalc.arg_dict['min'] = ('literal','2',)
        rngcalc.arg_dict['max'] = ('literal','3',)
        rngcalc.compute(district=self.district1)

        self.assertEquals(0, rngcalc.result, 'Incorrect value during range. (e:%s,a:%s)' % (0, rngcalc.result))

    def test_range3(self):
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]

        dist1ids = geounits[0:3] + geounits[9:12]
        exqset = Characteristic.objects.filter(geounit__in=dist1ids,subject=self.subject1)
        expected = float(exqset.aggregate(SumAgg('number'))['number__sum'])
        expected = 1 if 5.0 < expected and expected < 10.0 else 0

        dist1ids = map(lambda x: str(x.id), dist1ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevelid, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)

        rngcalc = Range()
        rngcalc.arg_dict['value'] = ('subject',self.subject1.name,)
        rngcalc.arg_dict['min'] = ('literal','5.0',)
        rngcalc.arg_dict['max'] = ('literal','10.0',)
        rngcalc.compute(district=district1)

        actual = rngcalc.result

        self.assertEquals(expected, actual, 'Incorrect value during range. (e:%s,a:%s)' % (expected, actual))

    def test_range4(self):
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]

        dist1ids = geounits[0:3] + geounits[9:12]
        exqset = Characteristic.objects.filter(geounit__in=dist1ids,subject=self.subject1)
        expected = float(exqset.aggregate(SumAgg('number'))['number__sum'])
        expected = 1 if 1.0 < expected and expected < 5.0 else 0

        dist1ids = map(lambda x: str(x.id), dist1ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevelid, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)

        rngcalc = Range()
        rngcalc.arg_dict['value'] = ('subject',self.subject1.name,)
        rngcalc.arg_dict['min'] = ('literal','1.0',)
        rngcalc.arg_dict['max'] = ('literal','5.0',)
        rngcalc.compute(district=district1)

        actual = rngcalc.result

        self.assertEquals(expected, actual, 'Incorrect value during range. (e:%s,a:%s)' % (expected, actual))


    def test_range_plan1(self):
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]

        dist1ids = geounits[0:3] + geounits[9:12]
        dist2ids = geounits[18:21] + geounits[27:30] + geounits[36:39]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevelid, self.plan.version)
        self.plan.add_geounits( self.district2.district_id, dist2ids, geolevelid, self.plan.version)

        rngcalc = Range()
        rngcalc.arg_dict['value'] = ('subject',self.subject1.name,)
        rngcalc.arg_dict['min'] = ('literal','7.0',)
        rngcalc.arg_dict['max'] = ('literal','11.0',)
        rngcalc.compute(plan=self.plan)

        actual = rngcalc.result
        expected = 1

        self.assertEquals(expected, actual, 'Incorrect value during Plan range. (e:%d,a:%d)' % (expected, actual))


    def test_schwartzberg(self):
        """
        Test the Schwartzberg measure of compactness.
        """
        geounits = self.geounits[self.geolevels[1].id]

        dist1ids = geounits[0:3] + geounits[9:12]
        dist2ids = geounits[18:21] + geounits[27:30] + geounits[36:39]

        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids, self.geolevels[1].id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids, self.geolevels[1].id, self.plan.version)

        district1 = max(District.objects.filter(plan=self.plan,district_id=self.district1.district_id),key=lambda d: d.version)
        district2 = max(District.objects.filter(plan=self.plan,district_id=self.district2.district_id),key=lambda d: d.version)

        calc = Schwartzberg()

        calc.compute(district=district1)
        self.assertAlmostEquals(0.86832150547, calc.result, 9, 'Schwartzberg for District 1 was incorrect: %d' % calc.result)

        calc.compute(district=district2)
        self.assertAlmostEquals(0.88622692545, calc.result, 9, 'Schwartzberg for District 2 was incorrect: %d' % calc.result)

    def test_schwartzberg1(self):
        """
        Test the Schwartzberg measure of compactness.
        """
        geounits = self.geounits[self.geolevels[1].id]

        dist1ids = geounits[0:3] + geounits[9:12]
        dist2ids = geounits[18:21] + geounits[27:30] + geounits[36:39]

        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids, self.geolevels[1].id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids, self.geolevels[1].id, self.plan.version)

        district1 = max(District.objects.filter(plan=self.plan,district_id=self.district1.district_id),key=lambda d: d.version)
        district2 = max(District.objects.filter(plan=self.plan,district_id=self.district2.district_id),key=lambda d: d.version)

        calc = Schwartzberg()

        calc.compute(plan=self.plan)
        self.assertAlmostEquals(0.87727421546, calc.result, 9, 'Schwartzberg for District 1 was incorrect: %f' % calc.result)

    def test_roeck(self):
        """
        Test the Roeck measure of compactness.
        """
        geounits = self.geounits[self.geolevels[1].id]

        dist1ids = geounits[0:3] + geounits[9:12]
        dist2ids = geounits[18:21] + geounits[27:30] + geounits[36:39]

        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids, self.geolevels[1].id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids, self.geolevels[1].id, self.plan.version)

        district1 = max(District.objects.filter(plan=self.plan,district_id=self.district1.district_id),key=lambda d: d.version)
        district2 = max(District.objects.filter(plan=self.plan,district_id=self.district2.district_id),key=lambda d: d.version)

        calc = Roeck()

        calc.compute(district=district1)
        expected = 0.587649
        self.assertAlmostEquals(expected, calc.result, 6, 'Roeck for District 1 was incorrect. (e:%0.6f,a:%0.6f)' % (expected, calc.result))

        calc.compute(district=district2)
        expected = 0.636620
        self.assertAlmostEquals(expected, calc.result, 6, 'Roeck for District 2 was incorrect. (e:%0.6f,a:%0.6f)' % (expected, calc.result))

    def test_roeck1(self):
        """
        Test the Roeck measure of compactness.
        """
        geounits = self.geounits[self.geolevels[1].id]

        dist1ids = geounits[0:3] + geounits[9:12]
        dist2ids = geounits[18:21] + geounits[27:30] + geounits[36:39]

        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids, self.geolevels[1].id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids, self.geolevels[1].id, self.plan.version)

        district1 = max(District.objects.filter(plan=self.plan,district_id=self.district1.district_id),key=lambda d: d.version)
        district2 = max(District.objects.filter(plan=self.plan,district_id=self.district2.district_id),key=lambda d: d.version)

        calc = Roeck()

        calc.compute(plan=self.plan)
        expected = (0.636620 + 0.587649) / 2
        self.assertAlmostEquals(expected, calc.result, 6, 'Roeck for plan was incorrect. (e:%0.6f,a:%0.6f)' % (expected, calc.result))

    def test_polsbypopper(self):
        """
        Test the Polsby-Popper measure of compactness.
        """
        geounits = self.geounits[self.geolevels[1].id]

        dist1ids = geounits[0:3] + geounits[9:12]
        dist2ids = geounits[18:21] + geounits[27:30] + geounits[36:39]

        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids, self.geolevels[1].id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids, self.geolevels[1].id, self.plan.version)

        district1 = max(District.objects.filter(plan=self.plan,district_id=self.district1.district_id),key=lambda d: d.version)
        district2 = max(District.objects.filter(plan=self.plan,district_id=self.district2.district_id),key=lambda d: d.version)

        calc = PolsbyPopper()

        calc.compute(district=district1)
        expected = 0.753982
        self.assertAlmostEquals(expected, calc.result, 6, 'Polsby-Popper for District 1 was incorrect. (e:%0.6f,a:%0.6f)' % (expected, calc.result))

        calc.compute(district=district2)
        expected = 0.785398
        self.assertAlmostEquals(expected, calc.result, 6, 'Polsby-Popper for District 2 was incorrect. (e:%0.6f,a:%0.6f)' % (expected, calc.result))

    def test_polsbypopper1(self):
        """
        Test the Polsby-Popper measure of compactness.
        """
        geounits = self.geounits[self.geolevels[1].id]

        dist1ids = geounits[0:3] + geounits[9:12]
        dist2ids = geounits[18:21] + geounits[27:30] + geounits[36:39]

        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids, self.geolevels[1].id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids, self.geolevels[1].id, self.plan.version)

        district1 = max(District.objects.filter(plan=self.plan,district_id=self.district1.district_id),key=lambda d: d.version)
        district2 = max(District.objects.filter(plan=self.plan,district_id=self.district2.district_id),key=lambda d: d.version)

        calc = PolsbyPopper()

        calc.compute(plan=self.plan)
        expected = (0.753982 + 0.785398) / 2
        self.assertAlmostEquals(expected, calc.result, 6, 'Polsby-Popper for plan was incorrect. (e:%0.6f,a:%0.6f)' % (expected, calc.result))

    def test_lengthwidth(self):
        """
        Test the Length/Width measure of compactness.
        """
        geounits = self.geounits[self.geolevels[1].id]

        dist1ids = geounits[0:3] + geounits[9:12]
        dist2ids = geounits[18:21] + geounits[27:30] + geounits[36:39]

        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids, self.geolevels[1].id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids, self.geolevels[1].id, self.plan.version)

        district1 = max(District.objects.filter(plan=self.plan,district_id=self.district1.district_id),key=lambda d: d.version)
        district2 = max(District.objects.filter(plan=self.plan,district_id=self.district2.district_id),key=lambda d: d.version)

        calc = LengthWidthCompactness()

        calc.compute(district=district1)
        expected = 0.666667
        self.assertAlmostEquals(expected, calc.result, 6, 'Length/Width for District 1 was incorrect. (e:%0.6f,a:%0.6f)' % (expected, calc.result))

        calc.compute(district=district2)
        expected = 1.000000
        self.assertAlmostEquals(expected, calc.result, 6, 'Length/Width for District 2 was incorrect. (e:%0.6f,a:%0.6f)' % (expected, calc.result))

    def test_lengthwidth1(self):
        """
        Test the Length/Width measure of compactness.
        """
        geounits = self.geounits[self.geolevels[1].id]

        dist1ids = geounits[0:3] + geounits[9:12]
        dist2ids = geounits[18:21] + geounits[27:30] + geounits[36:39]

        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids, self.geolevels[1].id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids, self.geolevels[1].id, self.plan.version)

        district1 = max(District.objects.filter(plan=self.plan,district_id=self.district1.district_id),key=lambda d: d.version)
        district2 = max(District.objects.filter(plan=self.plan,district_id=self.district2.district_id),key=lambda d: d.version)

        calc = LengthWidthCompactness()

        calc.compute(plan=self.plan)
        expected = (0.666667 + 1.000000) / 2
        self.assertAlmostEquals(expected, calc.result, 6, 'Length/Width for plan was incorrect. (e:%0.6f,a:%0.6f)' % (expected, calc.result))

    def test_contiguity1(self):
        cntcalc = Contiguity()
        cntcalc.compute(district=self.district1)

        self.assertEquals(0, cntcalc.result, 'District is contiguous.')

    def test_contiguity2(self):
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]

        dist1ids = geounits[0:3] + geounits[12:15]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevelid, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)

        cntcalc = Contiguity()
        cntcalc.compute(district=district1)

        self.assertEquals(0, cntcalc.result, 'District is contiguous.')

    def test_contiguity3(self):
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]

        dist1ids = geounits[0:3] + geounits[9:12]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevelid, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)

        cntcalc = Contiguity()
        cntcalc.compute(district=district1)

        self.assertEquals(1, cntcalc.result, 'District is discontiguous.')

    def test_contiguity_singlepoint(self):
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]

        dist1ids = [geounits[0], geounits[10]]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevelid, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)

        # 2 geounits connected by one point -- single-point is false, should fail
        cntcalc = Contiguity()
        cntcalc.arg_dict['allow_single_point'] = ('literal','0',)
        cntcalc.compute(district=district1)
        self.assertEquals(0, cntcalc.result, 'District is contiguous at 1 point, but single-point contiguity is false.')

        # 2 geounits connected by one point -- single-point is true, should pass
        cntcalc = Contiguity()
        cntcalc.arg_dict['allow_single_point'] = ('literal','1',)
        cntcalc.compute(district=district1)
        self.assertEquals(1, cntcalc.result, 'District is contiguous at 1 point, and single-point contiguity is true.')

        # add another geounits so 3 geometries are connected by 2 single points (contiguous)
        dist1ids = [geounits[18]]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevelid, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)

        cntcalc = Contiguity()
        cntcalc.arg_dict['allow_single_point'] = ('literal','1',)
        cntcalc.compute(district=district1)
        self.assertEquals(1, cntcalc.result, 'District is contiguous at 1 point twice, and single-point contiguity is true.')

        # add another geounits so 4 geometries are connected by 3 single points (contiguous)
        dist1ids = [geounits[28]]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevelid, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)

        cntcalc = Contiguity()
        cntcalc.arg_dict['allow_single_point'] = ('literal','1',)
        cntcalc.compute(district=district1)
        self.assertEquals(1, cntcalc.result, 'District is contiguous at 1 point thrice, and single-point contiguity is true.')

        # add more geounits so 5 geometries are connected by 3 single points (discontiguous)
        dist1ids = [geounits[14]]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevelid, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)

        cntcalc = Contiguity()
        cntcalc.arg_dict['allow_single_point'] = ('literal','1',)
        cntcalc.compute(district=district1)
        self.assertEquals(0, cntcalc.result, 'District is contiguous at 1 point thrice, but has a disjoint geometry.')

    def test_contiguity_overrides(self):
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]

        dist1ids = [geounits[0], geounits[11]]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevelid, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)

        overrides = []
        def add_override(id1, id2):
            override = ContiguityOverride(override_geounit=geounits[id1], connect_to_geounit=geounits[id2])
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
        self.assertEquals(0, cntcalc.result, 'District is non-contiguous, and no overrides have been defined.')

        # define a contiguity override between the two geounits, same test should now pass
        add_override(0, 11)
        cntcalc.compute(district=district1)
        self.assertEquals(1, cntcalc.result, 'District is not contiguous, but an override should make it so.')

        # add a few more non-contiguous geounits without overrides, should fail
        dist1ids = [geounits[4], geounits[22], geounits[7]]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevelid, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)
        cntcalc.compute(district=district1)
        self.assertEquals(0, cntcalc.result, 'District needs 3 overrides to be considered contiguous')

        # add overrides and test one by one. the final override should make the test pass
        add_override(11, 4)
        cntcalc.compute(district=district1)
        self.assertEquals(0, cntcalc.result, 'District needs 2 overrides to be considered contiguous')
        add_override(4, 22)
        cntcalc.compute(district=district1)
        self.assertEquals(0, cntcalc.result, 'District needs 1 overrides to be considered contiguous')
        add_override(7, 4)
        cntcalc.compute(district=district1)
        self.assertEquals(1, cntcalc.result, 'District has appropriate overrides to be considered contiguous')

        # check to make sure this works in conjunction with single-point contiguity by adding 2 more geounits
        dist1ids = [geounits[14], geounits[19]]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevelid, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)
        cntcalc.arg_dict['allow_single_point'] = ('literal','0',)
        cntcalc.compute(district=district1)
        self.assertEquals(0, cntcalc.result, 'Calculator needs allow_single_point on to be considered contiguous')
        cntcalc.arg_dict['allow_single_point'] = ('literal','1',)
        cntcalc.compute(district=district1)
        self.assertEquals(1, cntcalc.result, 'allow_single_point is enabled, should be considered contiguous')

        # remove contiguity overrides
        for override in overrides:
            override.delete()

    def test_contiguity_plan1(self):
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]

        dist1ids = geounits[0:4] + geounits[5:9]
        dist2ids = geounits[9:13] + geounits[14:18]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevelid, self.plan.version)
        self.plan.add_geounits( self.district2.district_id, dist2ids, geolevelid, self.plan.version)

        cntcalc = Contiguity()
        cntcalc.compute(plan=self.plan)

        actual = cntcalc.result

        self.assertEquals(0, actual, 'Incorrect value during contiguity. (e:%d,a:%d)' % (0, actual))

        self.plan.add_geounits( self.district1.district_id, [str(geounits[4].id)], geolevelid, self.plan.version )

        cntcalc.compute(plan=self.plan)

        actual = cntcalc.result

        self.assertEquals(1, actual, 'Incorrect value during contiguity. (e:%d,a:%d)' % (1, actual))

        self.plan.add_geounits( self.district2.district_id, [str(geounits[13].id)], geolevelid, self.plan.version )

        cntcalc.compute(plan=self.plan)

        actual = cntcalc.result

        self.assertEquals(2, actual, 'Incorrect value during contiguity. (e:%d,a:%d)' % (2, actual))


    def test_equivalence1(self):
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]

        dist1ids = geounits[0:3] + geounits[9:12]
        dist2ids = geounits[18:21] + geounits[27:30] + geounits[36:39]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevelid, self.plan.version)
        self.plan.add_geounits( self.district2.district_id, dist2ids, geolevelid, self.plan.version)

        equcalc = Equivalence()
        equcalc.arg_dict['value'] = ('subject',self.subject1.name,)
        equcalc.compute(plan=self.plan)

        actual = equcalc.result

        self.assertEquals(3.0, actual, 'Incorrect value during equivalence. (e:%f,a:%f)' % (3.0, actual))


    def test_representationalfairness(self):
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]

        dist1ids = geounits[0:3] + geounits[9:12]
        dist2ids = geounits[6:9] + geounits[15:18]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevelid, self.plan.version)
        self.plan.add_geounits( self.district2.district_id, dist2ids, geolevelid, self.plan.version)

        district1 = self.plan.district_set.filter(district_id=self.district1.district_id, version=self.plan.version-1)[0]
        district2 = self.plan.district_set.filter(district_id=self.district2.district_id, version=self.plan.version)[0]

        rfcalc = RepresentationalFairness()
        rfcalc.arg_dict['democratic'] = ('subject',self.subject1.name,)
        rfcalc.arg_dict['republican'] = ('subject',self.subject2.name,)
        rfcalc.compute(plan=self.plan)

        # If you're playing along at home, the values are:
        # District 1: 6 dem, 150 rep; District 2: 42 dem, 114 rep
        actual = rfcalc.result
        self.assertEqual(-2, actual, 'Wrong number of districts in RepresentationalFairness (e:%d,a:%d)' % (-2, actual))

        actual = rfcalc.html()
        self.assertEqual('<span>Republican&nbsp;2</span>', actual, 'Wrong party given for RepresentationalFairness (e:%s,a:%s)' % ('<span>Republican&nbsp;2</span>', actual))

        # Swap subjects and make sure we get the right party
        rfcalc = RepresentationalFairness()
        rfcalc.arg_dict['democratic'] = ('subject',self.subject2.name,)
        rfcalc.arg_dict['republican'] = ('subject',self.subject1.name,)
        rfcalc.compute(plan=self.plan)

        actual = rfcalc.result
        self.assertEqual(2, actual, 'Wrong number of districts in RepresentationalFairness (e:%d,a:%d)' % (2, actual))

        actual = rfcalc.html()
        self.assertEqual('<span>Democrat&nbsp;2</span>', actual, 'Wrong party given for RepresentationalFairness (e:%s,a:%s)' % ('<span>Democrat&nbsp;2</span>', actual))

    def test_competitiveness(self):
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]

        dist1ids = geounits[0:3] + geounits[9:12]
        dist2ids = geounits[6:9] + geounits[15:18]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevelid, self.plan.version)
        self.plan.add_geounits( self.district2.district_id, dist2ids, geolevelid, self.plan.version)

        # If you're playing along at home, the values are:
        # District 1: 6 dem, 150 rep; District 2: 42 dem, 114 rep
        ccalc = Competitiveness()
        ccalc.arg_dict['democratic'] = ('subject',self.subject1.name,)
        ccalc.arg_dict['republican'] = ('subject',self.subject2.name,)
        ccalc.compute(plan=self.plan)

        actual = ccalc.result

        # by default, we have a range of .45 - .55.  Neither district is fair.
        self.assertEquals(0, actual, 'Incorrect value during competitiveness. (e:%d,a:%d)' % (0, actual))

        # Open up the range to .25 - .75. District 2 should be fair now
        ccalc = Competitiveness()
        ccalc.arg_dict['democratic'] = ('subject',self.subject1.name,)
        ccalc.arg_dict['republican'] = ('subject',self.subject2.name,)
        ccalc.arg_dict['range'] = ('literal',.25,)
        ccalc.compute(plan=self.plan)

        actual = ccalc.result
        self.assertEquals(1, actual, 'Incorrect value during competitiveness. (e:%d,a:%d)' % (1, actual))

        # Open up the range to .03 - .97 (inclusive). District 1 should also be fair now. Switch subjects, too.
        ccalc = Competitiveness()
        ccalc.arg_dict['democratic'] = ('subject',self.subject2.name,)
        ccalc.arg_dict['republican'] = ('subject',self.subject1.name,)
        ccalc.arg_dict['range'] = ('literal',.47,)
        ccalc.compute(plan=self.plan)

        actual = ccalc.result
        self.assertEquals(2, actual, 'Incorrect value during competitiveness. (e:%d,a:%d)' % (2, actual))

    def test_countdist(self):
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]

        dist1ids = geounits[0:3] + geounits[9:12]
        dist2ids = geounits[6:9] + geounits[15:18]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevelid, self.plan.version)
        self.plan.add_geounits( self.district2.district_id, dist2ids, geolevelid, self.plan.version)

        numcalc = CountDistricts()
        numcalc.arg_dict['target'] = ('literal','2',)
        numcalc.compute(plan=self.plan)

        actual = numcalc.result

        self.assertEquals(True, actual, 'Incorrect value during district counting. (e:%s,a:%s)' % (True, actual))

    def test_allblocks(self):
        self.fail('Incomplete test')

    def test_equipop(self):
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]

        dist1ids = geounits[0:3] + geounits[9:12]
        dist2ids = geounits[6:9] + geounits[15:18]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevelid, self.plan.version)
        self.plan.add_geounits( self.district2.district_id, dist2ids, geolevelid, self.plan.version)

        equicalc = Equipopulation()
        equicalc.arg_dict['value'] = ('subject',self.subject1.name,)
        equicalc.arg_dict['min'] = ('literal','5',)
        equicalc.arg_dict['max'] = ('literal','10',)
        equicalc.compute(plan=self.plan)

        actual = equicalc.result

        self.assertEquals(False, actual, 'Incorrect value during plan equipop. (e:%s,a:%s)' % (False, actual))

        equicalc.arg_dict['min'] = ('literal','40',)
        equicalc.arg_dict['max'] = ('literal','45',)
        equicalc.compute(plan=self.plan)

        actual = equicalc.result

        self.assertEquals(False, actual, 'Incorrect value during plan equipop. (e:%s,a:%s)' % (False, actual))

        equicalc.arg_dict['min'] = ('literal','5',)
        equicalc.arg_dict['max'] = ('literal','45',)
        equicalc.compute(plan=self.plan)

        actual = equicalc.result

        self.assertEquals(True, actual, 'Incorrect value during plan equipop. (e:%s,a:%s)' % (True, actual))


    def test_allblocks(self):
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]

        dist1ids = geounits[0:3] + geounits[9:12]
        dist2ids = geounits[6:9] + geounits[15:18]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevelid, self.plan.version)
        self.plan.add_geounits( self.district2.district_id, dist2ids, geolevelid, self.plan.version)

        allblocks = AllBlocksAssigned()
        allblocks.arg_dict['threshold'] = ('literal', 0.1)

        plan = Plan.objects.get(pk=self.plan.id)
        allblocks.compute(plan=plan)
        actual = allblocks.result
        self.assertEquals(False, actual, 'Incorrect value during plan allblocks. (e:%s,a:%s)' % (False, actual))

        remainderids = plan.get_unassigned_geounits(0.1)
        remainderids = map(lambda x: str(x[0]), remainderids)
        plan.add_geounits( self.district2.district_id, remainderids, geolevelid, plan.version)

        plan = Plan.objects.get(pk=plan.id)
        allblocks.compute(plan=plan)
        actual = allblocks.result
        self.assertEquals(True, actual, 'Incorrect value during plan allblocks. (e:%s,a:%s)' % (True, actual))


    def test_majmin(self):
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]

        dist1ids = geounits[0:3] + geounits[9:12]
        dist2ids = geounits[18:21] + geounits[27:30] + geounits[36:39]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevelid, self.plan.version)
        self.plan.add_geounits( self.district2.district_id, dist2ids, geolevelid, self.plan.version)

        majcalc = MajorityMinority()
        majcalc.arg_dict['population'] = ('subject',self.subject1.name,)
        majcalc.arg_dict['count'] = ('literal', 1,)
        majcalc.arg_dict['minority1'] = ('subject',self.subject2.name,)
        majcalc.arg_dict['threshold'] = ('literal', 0.5,)
        majcalc.compute(plan=self.plan)

        actual = majcalc.result

        self.assertEquals(True, actual, 'Incorrect value during percentage. (e:%f,a:%f)' % (True, actual))

        majcalc.arg_dict['count'] = ('literal', 1,)
        majcalc.arg_dict['population'] = ('subject',self.subject2.name,)
        majcalc.arg_dict['minority1'] = ('subject',self.subject1.name,)
        majcalc.arg_dict['threshold'] = ('literal', 0.5,)
        majcalc.compute(plan=self.plan)

        actual = majcalc.result

        self.assertEquals(False, actual, 'Incorrect value during percentage. (e:%f,a:%f)' % (False, actual))




class ScoreRenderCase(BaseTestCase):
    def test_panelrender_plan(self):
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]

        dist1ids = geounits[0:3] + geounits[9:12]
        dist2ids = geounits[6:9] + geounits[15:18]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevelid, self.plan.version)
        self.plan.add_geounits( self.district2.district_id, dist2ids, geolevelid, self.plan.version)

        dist1ids = geounits[3:6] + geounits[12:15]
        dist2ids = geounits[9:12] + geounits[18:21]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan2.add_geounits( 1, dist1ids, geolevelid, self.plan2.version)
        self.plan2.add_geounits( 1, dist2ids, geolevelid, self.plan2.version)

        panels = ScorePanel.objects.filter(type='plan')

        for panel in panels:
            tplfile = settings.TEMPLATE_DIRS[0] + '/' + panel.template
            template = open(tplfile,'w')
            template.write('{% for planscore in planscores %}{{planscore.plan.name}}:{{ planscore.score|safe }}{% endfor %}')
            template.close()

            panel.is_ascending = False
            markup = panel.render([self.plan,self.plan2])
            expected = 'testPlan2:<span>152.0</span>' + \
                'testPlan:<span>48.0</span>' + \
                'testPlan2:<span>0.263888888889</span>' + \
                'testPlan:<span>0.181818181818</span>'
                
            self.assertEquals(expected, markup, 'The markup was incorrect. (e:"%s", a:"%s")' % (expected, markup))

            os.remove(tplfile)

    def test_panelrender_district(self):
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]

        dist1ids = geounits[0:3] + geounits[9:12]
        dist2ids = geounits[6:9] + geounits[15:18]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevelid, self.plan.version)
        self.plan.add_geounits( self.district2.district_id, dist2ids, geolevelid, self.plan.version)

        panels = ScorePanel.objects.filter(type='district')

        for panel in panels:
            districts = self.plan.get_districts_at_version(self.plan.version,include_geom=False)

            tplfile = settings.TEMPLATE_DIRS[0] + '/' + panel.template
            template = open(tplfile,'w')
            template.write('{% for dscore in districtscores %}{{dscore.district.name }}:{% for score in dscore.scores %}{{ score.score|safe }}{% endfor %}{% endfor %}')
            template.close()

            markup = panel.render(districts)
            expected = 'District 1:86.83%<span>1</span>' + \
                'District 2:86.83%<span>1</span>' + \
                'Unassigned:n/a<span>0</span>'
            self.assertEquals(expected, markup, 'The markup for districts was incorrect. (e:"%s", a:"%s")' % (expected,markup))

            os.remove(tplfile)

    def test_display_render_page(self):
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]

        dist1ids = geounits[0:3] + geounits[9:12]
        dist2ids = geounits[6:9] + geounits[15:18]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevelid, self.plan.version)
        self.plan.add_geounits( self.district2.district_id, dist2ids, geolevelid, self.plan.version)
        self.plan.is_valid = True
        self.plan.save()

        dist1ids = geounits[3:6] + geounits[12:15]
        dist2ids = geounits[9:12] + geounits[18:21]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan2.add_geounits( 1, dist1ids, geolevelid, self.plan2.version)
        self.plan2.add_geounits( 1, dist2ids, geolevelid, self.plan2.version)
        self.plan2.is_valid = True
        self.plan2.save()

        display = ScoreDisplay.objects.filter(is_page=True)[0]
        plans = list(Plan.objects.filter(is_valid=True))

        panel = display.scorepanel_set.all()[0]
        tplfile = settings.TEMPLATE_DIRS[0] + '/' + panel.template
        template = open(tplfile,'w')
        template.write('{% for planscore in planscores %}{{planscore.plan.name}}:{{ planscore.score|safe }}{% endfor %}')
        template.close()

        markup = display.render(plans)

        expected = 'testPlan:<span>0.181818181818</span>' + \
            'testPlan2:<span>0.263888888889</span>' + \
            'testPlan:<span>48.0</span>' + \
            'testPlan2:<span>152.0</span>'
        self.assertEquals(expected, markup, 'The markup was incorrect. (e:"%s", a:"%s")' % (expected, markup))

        os.remove(tplfile)

    def test_display_render_div(self):
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]

        dist1ids = geounits[0:3] + geounits[9:12]
        dist2ids = geounits[6:9] + geounits[15:18]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevelid, self.plan.version)
        self.plan.add_geounits( self.district2.district_id, dist2ids, geolevelid, self.plan.version)

        display = ScoreDisplay.objects.filter(is_page=False)[0]

        panel = display.scorepanel_set.all()[0]
        tplfile = settings.TEMPLATE_DIRS[0] + '/' + panel.template
        template = open(tplfile,'w')
        template.write('{% for dscore in districtscores %}{{dscore.district.name }}:{% for score in dscore.scores %}{{ score.score|safe }}{% endfor %}{% endfor %}')
        template.close()

        markup = display.render(self.plan)
        self.assertEquals('', markup, 'The markup was incorrect. (e:"", a:"%s")' % markup)

        markup = display.render(self.plan.get_districts_at_version(self.plan.version,include_geom=False))

        expected = 'District 1:86.83%<span>1</span>' + \
            'District 2:86.83%<span>1</span>' + \
            'Unassigned:n/a<span>0</span>'
        self.assertEquals(expected, markup, 'The markup was incorrect. (e:"%s", a:"%s")' % (expected, markup))

        os.remove(tplfile)

class ComputedScoresTestCase(BaseTestCase):
    def test_district1(self):
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]

        dist1ids = geounits[0:3] + geounits[9:12]
        dist2ids = geounits[6:9] + geounits[15:18]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevelid, self.plan.version)
        self.plan.add_geounits( self.district2.district_id, dist2ids, geolevelid, self.plan.version)
        
        function = ScoreFunction.objects.get(calculator__endswith='Sum',is_planscore=False)
        numscores = ComputedDistrictScore.objects.all().count()

        self.assertEquals(0, numscores, 'The number of computed district scores is incorrect. (e:0, a:%d)' % numscores)

        district1 = self.plan.district_set.filter(district_id=self.district1.district_id, version=self.plan.version-1)[0]

        score = ComputedDistrictScore.compute(function, district1)

        self.assertEquals(156, score, 'The score computed is incorrect. (e:156.0, a:%0.1f)' % score)

        numscores = ComputedDistrictScore.objects.all().count()

        self.assertEquals(1, numscores, 'The number of computed district scores is incorrect. (e:1, a:%d)' % numscores)

        dist1ids = geounits[3:6]
        dist1ids = map(lambda x: str(x.id), dist1ids)

        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevelid, self.plan.version )

        district1 = self.plan.district_set.filter(district_id=self.district1.district_id, version=self.plan.version)[0]

        score = ComputedDistrictScore.compute(function, district1)

        self.assertEquals(442, score, 'The score computed is incorrect. (e:442.0, a:%0.1f)' % score)

        numscores = ComputedDistrictScore.objects.all().count()

        self.assertEquals(2, numscores, 'The number of computed district scores is incorrect. (e:2, a:%d)' % numscores)

    def test_plan1(self):
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]

        dist1ids = geounits[0:3] + geounits[9:12]
        dist2ids = geounits[6:9] + geounits[15:18]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevelid, self.plan.version)
        self.plan.add_geounits( self.district2.district_id, dist2ids, geolevelid, self.plan.version)
        
        function = ScoreFunction.objects.get(calculator__endswith='Sum',is_planscore=True)
        numscores = ComputedPlanScore.objects.all().count()

        self.assertEquals(0, numscores, 'The number of computed plan scores is incorrect. (e:0, a:%d)' % numscores)

        score = ComputedPlanScore.compute(function, self.plan)

        self.assertEquals(48, score, 'The score computed is incorrect. (e:48.0, a:%0.1f)' % score)

        numscores = ComputedPlanScore.objects.all().count()

        self.assertEquals(1, numscores, 'The number of computed plan scores is incorrect. (e:1, a:%d)' % numscores)

        dist1ids = geounits[3:6]
        dist1ids = map(lambda x: str(x.id), dist1ids)

        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevelid, self.plan.version )

        score = ComputedPlanScore.compute(function, self.plan)

        self.assertEquals(147, score, 'The score computed is incorrect. (e:147.0, a:%0.1f)' % score)

        numscores = ComputedPlanScore.objects.all().count()

        self.assertEquals(2, numscores, 'The number of computed plan scores is incorrect. (e:2, a:%d)' % numscores)

