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
from django.db.models import Sum, Min, Max
from django.test.client import Client
from django.contrib.gis.geos import *
from django.contrib.auth.models import User
from django.utils import simplejson as json
from models import *
from utils import *
from calculators import *
from django.conf import settings
from datetime import datetime
from tagging.models import Tag, TaggedItem

class BaseTestCase(TestCase):
    """
    Only contains setUp and tearDown, which are shared among all other TestCases
    """
    fixtures = ['redistricting_testdata.json',
                'redistricting_testdata_geolevel2.json',
                'redistricting_testdata_geolevel3.json',
                'redistricting_testdata_scoring.json'
                ]

    def setUp(self):
        """
        Setup the general tests. This fabricates a set of data in the 
        test database for use later.
        """
        # Get a test Plan
        self.plan = Plan.objects.get(name='testPlan')
        self.plan2 = Plan.objects.get(name='testPlan2')

        # Get the test Districts
        self.district1 = District.objects.get(name='District 1', plan=self.plan)
        self.district2 = District.objects.get(name='District 2', plan=self.plan)

        # Get a test User
        self.username = 'test_user'
        self.password = 'secret'
        self.user = User.objects.get(username=self.username)

    def tearDown(self):
        self.plan = None
        self.plan2 = None
        self.district1 = None
        self.district2 = None
        self.username = None
        self.password = None
        self.user = None

class ScoringTestCase(BaseTestCase):
    """
    Unit tests to test the logic of the scoring functionality
    """
    fixtures = ['redistricting_testdata.json',
                'redistricting_testdata_geolevel2.json',
                'redistricting_testdata_scoring.json'
                ]

    def setUp(self):
        BaseTestCase.setUp(self)

        # create a couple districts and populate with geounits
        # geounits = self.geounits[self.geolevels[1].id]
        geolevel = Geolevel.objects.get(pk=2)
        geounits = list(Geounit.objects.filter(geolevel = geolevel).order_by('id'))

        dist1units = geounits[0:3] + geounits[9:12]
        dist2units = geounits[18:21] + geounits[27:30] + geounits[36:39]

        dist1ids = map(lambda x: str(x.id), dist1units)
        dist2ids = map(lambda x: str(x.id), dist2units)

        self.plan.add_geounits(self.district1.district_id, dist1ids, geolevel.id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids, geolevel.id, self.plan.version)

        self.district1 = max(District.objects.filter(plan=self.plan,district_id=self.district1.district_id),key=lambda d: d.version)
        self.district2 = max(District.objects.filter(plan=self.plan,district_id=self.district2.district_id),key=lambda d: d.version)
        
        # create objects used for scoring
        self.legbod = LegislativeBody.objects.get(name='TestLegislativeBody')
        self.scoreDisplay1 = ScoreDisplay(title='SD1', legislative_body=self.legbod, is_page=False, owner=self.user)
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

        BaseTestCase.tearDown(self)

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
        self.assertEqual("86.83%", score, 'Schwartzberg HTML for District 1 was incorrect: ' + score)

        # JSON
        score = schwartzFunction.score(self.district1, 'json')
        self.assertEqual('{"result": 0.8683215054699209}', score, 'Schwartzberg JSON for District 1 was incorrect: ' + score)

    def testSumFunction(self):
        """
        Test the sum scoring function
        """
        # create the scoring function for summing three parameters
        sumThreeFunction = ScoreFunction(calculator='redistricting.calculators.SumValues', name='SumThreeFn')
        sumThreeFunction.save()

        # create the arguments
        ScoreArgument(function=sumThreeFunction, argument='value1', value='0', type='literal').save()
        ScoreArgument(function=sumThreeFunction, argument='value2', value='1', type='literal').save()
        ScoreArgument(function=sumThreeFunction, argument='value3', value='2', type='literal').save()

        # test raw value
        score = sumThreeFunction.score(self.district1)
        self.assertEqual(3, score, 'sumThree was incorrect: %d' % score)

        # HTML -- also make sure mixed case format works
        score = sumThreeFunction.score(self.district1, 'HtmL')
        self.assertEqual('<span>3</span>', score, 'sumThree was incorrect: %s' % score)

        # JSON -- also make sure uppercase format works
        score = sumThreeFunction.score(self.district1, 'JSON')
        self.assertEqual('{"result": 3}', score, 'sumThree was incorrect: %s' % score)

        # create the scoring function for summing a literal and a subject
        sumMixedFunction = ScoreFunction(calculator='redistricting.calculators.SumValues', name='SumMixedFn')
        sumMixedFunction.save()

        # create the arguments
        ScoreArgument(function=sumMixedFunction, argument='value1', value=self.subject1.name, type='subject').save()
        ScoreArgument(function=sumMixedFunction, argument='value2', value='5.2', type='literal').save()

        # test raw value
        score = sumMixedFunction.score(self.district1)
        self.assertEqual(Decimal('11.2'), score, 'sumMixed was incorrect: %d' % score)

    def testSumPlanFunction(self):
        """
        Test the sum scoring function on a plan level
        """
        # create the scoring function for summing the districts in a plan
        sumPlanFunction = ScoreFunction(calculator='redistricting.calculators.SumValues', name='SumPlanFn', is_planscore=True)
        sumPlanFunction.save()

        # create the arguments
        ScoreArgument(function=sumPlanFunction, argument='value1', value='1', type='literal').save()

        # test raw value
        num_districts = len(self.plan.get_districts_at_version(self.plan.version, include_geom=False)) - 1
        score = sumPlanFunction.score(self.plan)
        self.assertEqual(num_districts, score, 'sumPlanFunction was incorrect. (e:%d, a:%d)' % (num_districts, score))

        # test a list of plans
        score = sumPlanFunction.score([self.plan, self.plan])
        self.assertEqual(num_districts, score[0], 'sumPlanFunction was incorrect for first plan: %d' % score[0])
        self.assertEqual(num_districts, score[1], 'sumPlanFunction was incorrect for second plan: %d' % score[1])

    def testThresholdFunction(self):
        # create the scoring function for checking if a value passes a threshold
        thresholdFunction1 = ScoreFunction(calculator='redistricting.calculators.Threshold', name='ThresholdFn')
        thresholdFunction1.save()

        # create the arguments
        ScoreArgument(function=thresholdFunction1, argument='value', value='1', type='literal').save()
        ScoreArgument(function=thresholdFunction1, argument='threshold', value='2', type='literal').save()

        # test raw value
        score = thresholdFunction1.score(self.district1)
        self.assertEqual(False, score, '1 is not greater than 2')

        # create a new scoring function to test the inverse
        thresholdFunction2 = ScoreFunction(calculator='redistricting.calculators.Threshold', name='ThresholdFn')
        thresholdFunction2.save()

        # create the arguments
        ScoreArgument(function=thresholdFunction2, argument='value', value='2', type='literal').save()
        ScoreArgument(function=thresholdFunction2, argument='threshold', value='1', type='literal').save()

        # test raw value
        score = thresholdFunction2.score(self.district1)
        self.assertEqual(1, score, '2 is greater than 1')

        # HTML
        score = thresholdFunction2.score(self.district1, 'html')
        self.assertEqual("<span>1</span>", score, 'Threshold HTML was incorrect: ' + score)

        # JSON
        score = thresholdFunction2.score(self.district1, 'json')
        self.assertEqual('{"result": 1}', score, 'Threshold JSON was incorrect: ' + score)

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
        self.assertEqual(1, score, '2 is between 1 and 3')

        # HTML
        score = rangeFunction1.score(self.district1, 'html')
        self.assertEqual("<span>1</span>", score, 'Range HTML was incorrect: ' + score)

        # JSON
        score = rangeFunction1.score(self.district1, 'json')
        self.assertEqual('{"result": 1}', score, 'Range JSON was incorrect: ' + score)


    def testNestedSumFunction(self):
        """
        Test a sum scoring function that references a sum scoring function
        """
        # create the scoring function for summing two literals
        sumTwoLiteralsFunction = ScoreFunction(calculator='redistricting.calculators.SumValues', name='SumTwoLiteralsFn')
        sumTwoLiteralsFunction.save()
        ScoreArgument(function=sumTwoLiteralsFunction, argument='value1', value='5', type='literal').save()
        ScoreArgument(function=sumTwoLiteralsFunction, argument='value2', value='7', type='literal').save()
        
        # create the scoring function for summing a literal and a score
        sumLiteralAndScoreFunction = ScoreFunction(calculator='redistricting.calculators.SumValues', name='SumLiteralAndScoreFn')
        sumLiteralAndScoreFunction.save()

        # first argument is just a literal
        ScoreArgument(function=sumLiteralAndScoreFunction, argument='value1', value='2', type='literal').save()

        # second argument is a score function
        ScoreArgument(function=sumLiteralAndScoreFunction, argument='value2', value=sumTwoLiteralsFunction.name, type='score').save()

        # test nested sum
        score = sumLiteralAndScoreFunction.score(self.district1)
        self.assertEqual(14, score, 'sumLiteralAndScoreFunction was incorrect: %d' % score)

        # sum two of these nested sums
        sumTwoNestedSumsFunction = ScoreFunction(calculator='redistricting.calculators.SumValues', name='SumTwoNestedSumsFn')
        sumTwoNestedSumsFunction.save()
        ScoreArgument(function=sumTwoNestedSumsFunction, argument='value1', value=sumLiteralAndScoreFunction.name, type='score').save()        
        ScoreArgument(function=sumTwoNestedSumsFunction, argument='value2', value=sumLiteralAndScoreFunction.name, type='score').save()
        score = sumTwoNestedSumsFunction.score(self.district1)
        self.assertEqual(28, score, 'sumTwoNestedSumsFunction was incorrect: %d' % score)

        # test a list of districts
        score = sumTwoNestedSumsFunction.score([self.district1, self.district1])
        self.assertEqual(28, score[0], 'sumTwoNestedSumsFunction was incorrect for first district: %d' % score[0])
        self.assertEqual(28, score[1], 'sumTwoNestedSumsFunction was incorrect for second district: %d' % score[1])

    def testNestedSumPlanFunction(self):
        """
        Test the nested sum scoring function on a plan level
        """
        # create the scoring function for summing the districts in a plan
        sumPlanFunction = ScoreFunction(calculator='redistricting.calculators.SumValues', name='SumPlanFn', is_planscore=True)
        sumPlanFunction.save()
        ScoreArgument(function=sumPlanFunction, argument='value1', value='1', type='literal').save()

        # find the number of districts in the plan in an alternate fashion
        num_districts = len(self.plan.get_districts_at_version(self.plan.version, include_geom=False)) - 1

        # ensure the sumPlanFunction works correctly
        score = sumPlanFunction.score(self.plan)
        self.assertEqual(num_districts, score, 'sumPlanFunction was incorrect: %d' % score)

        # create the scoring function for summing the sum of the districts in a plan
        sumSumPlanFunction = ScoreFunction(calculator='redistricting.calculators.SumValues', name='SumSumPlanFn', is_planscore=True)
        sumSumPlanFunction.save()
        ScoreArgument(function=sumSumPlanFunction, argument='value1', value=sumPlanFunction.name, type='score').save()

        # test nested sum
        score = sumSumPlanFunction.score(self.plan)
        self.assertEqual(num_districts ** 2, score, 'sumSumPlanFunction was incorrect: %d' % score)

        # test a list of plans
        score = sumSumPlanFunction.score([self.plan, self.plan])
        self.assertEqual(num_districts ** 2, score[0], 'sumSumPlanFunction was incorrect for first plan: %d' % score[0])
        self.assertEqual(num_districts ** 2, score[1], 'sumSumPlanFunction was incorrect for second plan: %d' % score[1])

    def testPlanScoreNestedWithDistrictScore(self):
        """
        Test the case where a ScoreFunction of type 'plan' has an argument
        that is a ScoreFunction of type 'district', in which case, the argument
        ScoreFunction needs to be evaluated over all districts in the list of plans
        """
        # create the district scoring function for getting subject1
        districtSubjectFunction = ScoreFunction(calculator='redistricting.calculators.SumValues', name='GetSubjectFn')
        districtSubjectFunction.save()

        ScoreArgument(function=districtSubjectFunction, argument='value1', value=self.subject1.name, type='subject').save()

        # create the plan scoring function for summing values
        planSumFunction = ScoreFunction(calculator='redistricting.calculators.SumValues', name='PlanSumFn', is_planscore=True)
        planSumFunction.save()
        ScoreArgument(function=planSumFunction, value=districtSubjectFunction.name, type='score').save()

        # subject values are 6, 9, and 0; so the total should be 15
        score = planSumFunction.score(self.plan)
        self.assertEqual(15, score, 'planSumFunction was incorrect: (e:15, a:%d)' % score)

        # test a list of plans
        score = planSumFunction.score([self.plan, self.plan])
        self.assertEqual(15, score[0], 'planSumFunction was incorrect for first plan: %d' % score[0])
        self.assertEqual(15, score[1], 'planSumFunction was incorrect for second plan: %d' % score[1])

        # test with multiple arguments
        districtSubjectFunction2 = ScoreFunction(calculator='redistricting.calculators.SumValues', name='GetSubjectFn2')
        districtSubjectFunction2.save()
        ScoreArgument(function=districtSubjectFunction2, argument='value1', value=self.subject1.name, type='subject').save()
        ScoreArgument(function=districtSubjectFunction2, argument='value2', value=self.subject1.name, type='subject').save()
        
        planSumFunction2 = ScoreFunction(calculator='redistricting.calculators.SumValues', name='PlanSumFn2', is_planscore=True)
        planSumFunction2.save()
        ScoreArgument(function=planSumFunction2, value=districtSubjectFunction2.name, type='score').save()

        # should be twice as much
        score = planSumFunction2.score(self.plan)
        self.assertEqual(30, score, 'planSumFunction was incorrect: %d' % score)

        # test with adding another argument to the plan function, should double again
        ScoreArgument(function=planSumFunction2, value=districtSubjectFunction2.name, type='score').save()
        score = planSumFunction2.score(self.plan)
        self.assertEqual(60, score, 'planSumFunction was incorrect: %d' % score)
        

class PlanTestCase(BaseTestCase):
    """
    Unit tests to test Plan operations
    """

    fixtures = ['redistricting_testdata.json', 'redistricting_testdata_geolevel2.json', 'redistricting_testdata_geolevel3.json']

    def setUp(self):
        BaseTestCase.setUp(self)        
        self.geolevel = Geolevel.objects.get(pk=2)
        self.geolevels = Geolevel.objects.all().order_by('id')

        self.geounits = {}
        for gl in self.geolevels:
           self.geounits[gl.id] = list(Geounit.objects.filter(geolevel=gl).order_by('id'))

    def tearDown(self):
        self.geolevel = None
        self.geolevels = None
        self.geounits = None
        try:
            BaseTestCase.tearDown(self)
        except:
            import traceback
            print(traceback.format_exc())
            print('Couldn\'t tear down')

    def test_district_id_increment(self):
        """
        Test the logic for the automatically generated district_id
        """
        # Note: district_id is set to 0 here, because otherwise, the auto-increment code does not get called.
        # It may be best to revisit how district_id is used throughout the app, and to not allow for it to be set,
        # since it should be auto-generated.
        d3 = District(name='District 3', version=0)
        d3.plan = self.plan

        p1 = Polygon( ((1, 1), (1, 1), (1, 1), (1, 1)) )
        mp1 = MultiPolygon(p1)
        d3.geom = mp1

        d3.save()
        latest = d3.district_id

        d4 = District(name = 'District 4', version=0)
        d4.plan = self.plan

        p2 = Polygon( ((0, 0), (0, 1), (1, 1), (0, 0)) )
        mp2 = MultiPolygon(p1)
        d4.geom = mp2

        d4.save()
        incremented = d4.district_id
        self.assertEqual(latest + 1, incremented, 'New district did not have an id greater than the previous district. (e:%d, a:%d)' % (latest+1,incremented))
        
    def test_add_to_plan(self):
        """
        Test the logic for adding geounits to a district.
        """
        district = self.district1
        districtid = district.district_id

        geounitids = [str(self.geounits[1][0].id)]

        self.plan.add_geounits(districtid, geounitids, self.geolevel.id, self.plan.version)
        district = District.objects.get(plan=self.plan, district_id=districtid, version=1)
        
        self.assertEqual(district.geom, self.geounits[1][0].geom, "Geometry for added district doesn't match")

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
        geounitids = [str(self.geounits[1][0].id)]

        this_id = self.plan.id
        # Add geounits to plan
        self.plan.add_geounits(self.district1.district_id, geounitids, self.geolevel.id, self.plan.version)
        
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
        geounitids = [str(self.geounits[1][0].id)]

        client = Client()

        # Create a second user, and try to lock a district not belonging to that user
        username2 = 'test_user2'
        user2 = User(username=username2)
        user2.set_password(self.password)
        user2.save()
        client.login(username=username2, password=self.password)

        # Issue lock command when not logged in
        response = client.post('/districtmapping/plan/%d/district/%d/lock/' % (self.plan.id, self.district1.district_id), { 'lock':True, 'version':self.plan.version })
        self.assertEqual(403, response.status_code, 'Non-owner was able to lock district.' + str(response))
        
        # Login
        client.login(username=self.username, password=self.password)
        
        # Issue lock command
        response = client.post('/districtmapping/plan/%d/district/%d/lock/' % (self.plan.id, self.district1.district_id), { 'lock':True, 'version':self.plan.version })
        self.assertEqual(200, response.status_code, 'Lock handler didn\'t return 200:' + str(response))

        # Ensure lock exists
        self.district1 = District.objects.get(pk=self.district1.id)
        self.assertTrue(self.district1.is_locked, 'District wasn\'t locked.' + str(response))

        # Try adding geounits to the locked district (not allowed)
        self.plan.add_geounits(self.district1.district_id, geounitids, self.geolevel.id, self.plan.version)
        self.assertRaises(District.DoesNotExist, District.objects.get, pk=self.district1.id, version=self.plan.version)
        numunits = len(self.district1.get_base_geounits(0.1))
        self.assertEqual(0, numunits, 'Geounits were added to a locked district. Num geounits: %d' % numunits)
        
        # Issue unlock command
        response = client.post('/districtmapping/plan/%d/district/%d/lock/' % (self.plan.id, self.district1.district_id), { 'lock':False, 'version':self.plan.version })
        self.assertEqual(200, response.status_code, 'Lock handler didn\'t return 200:' + str(response))

        # Ensure lock has been removed
        self.district1 = max(District.objects.filter(plan=self.plan,district_id=self.district1.district_id),key=lambda d: d.version)
        self.assertFalse(self.district1.is_locked, 'District wasn\'t unlocked.' + str(response))

        # Add geounits to the plan
        old_geom = self.district1.geom
        self.plan.add_geounits(self.district1.district_id, geounitids, self.geolevel.id, self.plan.version)
        self.district1 = max(District.objects.filter(plan=self.plan,district_id=self.district1.district_id),key=lambda d: d.version)
        new_geom = self.district1.geom
        self.assertNotEqual(old_geom, new_geom, "Geounits could not be added to an unlocked district")

    def test_district_locking2(self):
        """
        Test the case where adding a partially selected geometry (due to
        locking) may add the entire geometry's aggregate value.
        """
        geounits = list(Geounit.objects.filter(geolevel=self.geolevel).order_by('id'))
        dist1ids = geounits[0:3] + geounits[9:12]
        dist2ids = geounits[18:21] + geounits[27:30] + geounits[36:39]

        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids, self.geolevel.id, self.plan.version)

        district1 = max(District.objects.filter(plan=self.plan,district_id=self.district1.district_id),key=lambda d: d.version)
        district1units = district1.get_base_geounits(0.1)

        self.assertEqual(54, len(district1units), 'Incorrect number of geounits returned in dist1: %d' % len(district1units))

        district2 = max(District.objects.filter(plan=self.plan,district_id=self.district2.district_id),key=lambda d: d.version)
        district2units = district2.get_base_geounits(0.1)

        self.assertEqual(81, len(district2units), 'Incorrect number of geounits returned in dist2: %d' % len(district2units))

        geolevel_id = 1
        geounits = list(Geounit.objects.filter(geolevel=geolevel_id).order_by('id'))
        dist3ids = geounits[1:3] + geounits[4:6] + geounits[7:9]

        dist3ids = map(lambda x: str(x.id), dist3ids)

        self.plan.add_geounits(self.district2.district_id + 1, dist3ids, geolevel_id, self.plan.version)

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

        subject = Subject.objects.get(name='TestSubject')

        districtpre_computed = ComputedCharacteristic.objects.filter(district__in=[district1,district2,district3],subject=subject
).order_by('district').values_list('number',flat=True)
        presum = 0;
        for pre in districtpre_computed:
            presum += pre

        self.plan.add_geounits(district3.district_id, [str(geounits[0].id)], self.geolevels[0].id, self.plan.version)


        district1 = max(District.objects.filter(plan=self.plan,district_id=self.district1.district_id),key=lambda d: d.version)
        district2 = max(District.objects.filter(plan=self.plan,district_id=self.district2.district_id),key=lambda d: d.version)
        district3 = max(District.objects.filter(plan=self.plan,district_id=district3.district_id),key=lambda d: d.version)

        districtpost_computed = ComputedCharacteristic.objects.filter(district__in=[district1,district2,district3],subject=subject).order_by('district').values_list('number',flat=True)
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
        self.assertEqual(1053, len(strz), 'Index file was the wrong length: %d' % len(strz))

    def test_community_plan2index(self):
        """
        Test exporting a community plan
        """
        geounits = self.geounits[self.geolevels[0].id]
        dist1ids = [str(geounits[0].id)]
        self.plan.add_geounits(self.district1.district_id, dist1ids, self.geolevels[0].id, self.plan.version)
        plan = Plan.objects.get(pk=self.plan.id)

        # extract a district to manipulate
        district = None
        for d in plan.get_districts_at_version(plan.version, include_geom=False):
            if d.district_id > 0:
                district = d
        
        # make the plan a community
        plan.legislative_body.is_community = True
        plan.legislative_body.save()

        # add label
        district.name = 'My Test Community'
        district.save()

        # add comment
        ct = ContentType.objects.get(app_label='redistricting',model='district')
        comment = Comment(object_pk=district.id, content_type=ct, site_id=1, user_name=self.username, user_email='', comment='Test comment: a, b, c || ...')
        comment.save()

        # add types
        Tag.objects.add_tag(district, 'type=%s' % 'type1')
        Tag.objects.add_tag(district, 'type=%s' % 'type2')

        # save the plan
        plan.save()

        # export
        archive = DistrictIndexFile.plan2index(plan)
        zin = zipfile.ZipFile(archive.name, "r")
        strz = zin.read(plan.name + ".csv")
        zin.close()
        os.remove(archive.name)
        self.assertEqual(5994, len(strz), 'Index file was the wrong length: %d' % len(strz))

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
        # TODO - figure out why this fails only when run with the entire test suite
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
        self.assertEqual(1, len(result), "District1 wasn't pasted into the plan")
        target1 = District.objects.get(pk=result[0])
        self.assertTrue(target1.geom.equals(district1.geom), "Geometries of pasted district doesn't match original")
        self.assertEqual(target1.name, "TestMember 1", "Proper name wasn't assigned to pasted district. (e:'TestMember 1', a:'%s')" % target1.name)

        target_stats =  ComputedCharacteristic.objects.filter(district = result[0])
        for stat in target_stats:
           district1_stat = ComputedCharacteristic.objects.get(district=district1, subject=stat.subject)
           self.assertEqual(stat.number, district1_stat.number, "Stats for pasted district (number) don't match")
           self.assertEqual(stat.percentage, district1_stat.percentage, "Stats for pasted district (percentage) don't match")

        # Add district 2 to a new plan so it doesn't overlap district 1
        new_for_2 = Plan.create_default('Paste Plan 2', self.plan.legislative_body, self.user, template=False, is_pending=False)
        dist2ids = geounits[10:13] + geounits[19:22] + geounits[28:31]
        dist2ids = map(lambda x: str(x.id), dist2ids)
        new_for_2.add_geounits(self.district2.district_id, dist2ids, geolevelid, self.plan.version)
        district2 = max(District.objects.filter(plan=new_for_2,district_id=self.district2.district_id),key=lambda d: d.version)

        # Paste district 2 into our target plan
        result = target.paste_districts((district2,))
        self.assertEqual(1, len(result), "District2 wasn't pasted into the plan")
        target2 = District.objects.get(pk=result[0])
        self.assertTrue(target2.geom.equals(district2.geom), "Geometries of pasted district doesn't match original\n")
        self.assertEqual(target2.name, "TestMember 2", "Proper name wasn't assigned to pasted district")
        
        target2_stats =  ComputedCharacteristic.objects.filter(district=target2)
        for stat in target2_stats:
            # Check on District 2 stats
            district2_stat = ComputedCharacteristic.objects.get(district=district2, subject=stat.subject)

            self.assertEqual(stat.number, district2_stat.number, "Stats for pasted district (number) don't match")
            self.assertEqual(stat.percentage, district2_stat.percentage, "Stats for pasted district (percentage) don't match")
            
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
            self.assertEqual(stat.number, district1_stat.number, "Stats for pasted district (number) don't match. (e:%f, a:%f)" % (stat.number, district1_stat.number))
            self.assertEqual(stat.percentage, district1_stat.percentage, "Stats for pasted district (percentage) don't match")
            
        # Make sure that method fails when adding too many districts
        target.legislative_body.max_districts = 2;
        target.legislative_body.save()
        self.assertRaises(Exception, target.paste_districts, (district2,), 'Allowed to merge too many districts')

    def test_paste_districts_onto_locked(self):
        # TODO - figure out why this fails only when run with the entire test suite
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
        result = target.paste_districts((self.district2,))
        district2 = District.objects.get(pk=result[0])
        # district2 = max(District.objects.filter(plan=target,district_id=self.district2.district_id),key=lambda d: d.version)
        # Create in self.plan the district we want to see in Paste Plan
        unassigned = max(District.objects.filter(plan=self.plan,name="Unassigned"),key=lambda d: d.version)
        self.plan.add_geounits(unassigned.district_id, dist1ids, geolevelid, self.plan.version)
        self.district2 = max(District.objects.filter(plan=self.plan,district_id=self.district2.district_id),key=lambda d: d.version)
        # Check stats and geometry
        self.assertTrue(self.district2.geom.equals(district2.geom), 'Geom for district pasted over locked district doesn\'t match')
        target_stats = district2.computedcharacteristic_set.all()
        for stat in target_stats:
            expected_stat = ComputedCharacteristic.objects.get(district=self.district2, subject=stat.subject)
            self.assertEqual(stat.number, expected_stat.number, "Stats for pasted district (number) don't match")
            self.assertEqual(stat.percentage, expected_stat.percentage, "Stats for pasted district (percentage) don't match")
        

    def test_paste_multiple_districts(self):
        # Set up the test using geounits in the 2nd level
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]
        dist1ids = geounits[0:3] + geounits[9:12] + geounits[18:21]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits(self.district1.district_id, dist1ids, geolevelid, self.plan.version)

        self.district3 = District(plan=self.plan, name="TestMember 3", district_id = 3)
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
            self.assertEqual(stat.number, expected_stat.number, "Stats for pasted district (number) don't match")
            self.assertEqual(stat.percentage, expected_stat.percentage, "Stats for pasted district (percentage) don't match")

        district3 = District.objects.get(pk=results[1])
        self.assertTrue(self.district3.geom.equals(district3.geom), 'Geom for pasted district doesn\'t match')
        target_stats = district3.computedcharacteristic_set.all()
        for stat in target_stats:
            expected_stat = ComputedCharacteristic.objects.get(district=self.district3, subject=stat.subject)
            self.assertEqual(stat.number, expected_stat.number, "Stats for pasted district (number) don't match")
            self.assertEqual(stat.percentage, expected_stat.percentage, "Stats for pasted district (percentage) don't match")

        # Test that already-present district is gone.
        district2 = max(District.objects.filter(plan=target,district_id=self.district2.district_id),key=lambda d: d.version)
        self.assertTrue(district2.geom.empty, 'District 2 geom wasn\'t emptied when it was pasted over')
        self.assertEqual(0, len(district2.computedcharacteristic_set.all()), 'District2 still has characteristics')

    def test_get_available_districts(self):
        # Set the max_districts setting for this test
        self.plan.legislative_body.max_districts = 1
        self.plan.legislative_body.save()

        self.assertEqual(1, self.plan.get_available_districts(), 'Wrong number of available districts returned initially. (e:1, a:%d)' % self.plan.get_available_districts())

        # Set up the test using geounits in the 2nd level
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]

        # Add a district
        dist1ids = geounits[0:3] + geounits[9:12] + geounits[18:21]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits(self.district1.district_id, dist1ids, geolevelid, self.plan.version)
        self.assertEqual(0, self.plan.get_available_districts(), 'Wrong number of available districts returned after adding a district. (e:0, a:%d)' % self.plan.get_available_districts())

        # Unassign the district
        unassigned = District.objects.filter(plan=self.plan, name="Unassigned").order_by('-version')[0]
        self.plan.add_geounits(unassigned.district_id, dist1ids, geolevelid, self.plan.version)
        self.assertEqual(1, self.plan.get_available_districts(), 'Wrong number of available districts returned after removing a district. (e:1, a:%d)' % self.plan.get_available_districts())
        
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

        all_4 = self.plan.get_districts_at_version(self.plan.version,include_geom=True)
        all_3 = filter(lambda x : x.name != "Unassigned", all_4)
        initial_state = { }
        total = 0
        for district in all_3:
            initial_state[district.district_id] = district

        totals = {}
        for subject in Subject.objects.all():
            total = ComputedCharacteristic.objects.filter(district__in=all_3, subject=subject).aggregate(Sum('number'))
            totals[subject] = total['number__sum']
        total_geom = enforce_multi(District.objects.filter(plan=self.plan,district_id__gt=0).collect(), collapse=True)

        # Paste them all together now
        district1 = initial_state[self.district1.district_id]
        district2 = initial_state[self.district2.district_id]
        district3 = initial_state[dist3_district_id]

        result = self.plan.combine_districts(district1, (district2, district3))
        self.assertTrue(result, 'Combine operation returned false')

        # Refresh our plan version
        plan = Plan.objects.get(pk=self.plan.id)
        combined = max(District.objects.filter(plan=plan,district_id=self.district1.district_id),key=lambda d: d.version)
        self.assertTrue(combined.geom.equals(total_geom), "Geometries of combined districts don't match")

        # Check our statistics
        for subject in Subject.objects.all():
            characteristic = ComputedCharacteristic.objects.get(subject=subject,district=combined)
            self.assertEqual(characteristic.number, totals[subject], 'Stats (number) don\'t match on combined district e:%d,a:%d' % (totals[subject], characteristic.number))

    def test_fix_unassigned(self):
        """
        Test the logic for fixing unassigned geounits in a plan
        """

        plan = self.plan
        geounits = list(Geounit.objects.filter(geolevel=self.geolevel).order_by('id'))

        # Ensure the min % setting is set, and then hardcode it for testing
        self.assertTrue(settings.FIX_UNASSIGNED_MIN_PERCENT > -1, 'FIX_UNASSIGNED_MIN_PERCENT is not set')
        settings.FIX_UNASSIGNED_MIN_PERCENT = 15
        self.assertEqual(15, settings.FIX_UNASSIGNED_MIN_PERCENT, 'FIX_UNASSIGNED_MIN_PERCENT did not change')

        # Ensure the comparator subject is set, and then hardcode it for testing
        self.assertTrue(settings.FIX_UNASSIGNED_COMPARATOR_SUBJECT, 'FIX_UNASSIGNED_COMPARATOR_SUBJECT is not set')
        settings.FIX_UNASSIGNED_COMPARATOR_SUBJECT = 'TestSubject2'
        self.assertEqual('TestSubject2', settings.FIX_UNASSIGNED_COMPARATOR_SUBJECT, 'FIX_UNASSIGNED_COMPARATOR_SUBJECT did not change')

        # Try fixing when not all districts exist
        result = plan.fix_unassigned(threshold=0.1)
        self.assertFalse(result[0], ('Not all districts exist', result))

        # Change the max number of districts, so we don't have to assign them all for testing
        leg_body = plan.legislative_body
        leg_body.max_districts = 2
        leg_body.save()

        # Try fixing when < min % geounits are assigned
        result = plan.fix_unassigned(threshold=0.1)
        self.assertFalse(result[0], ('Not enough % assigned blocks', result))

        # Add all geounits to District1
        plan.add_geounits(self.district1.district_id, [str(x.id) for x in geounits], self.geolevel.id, plan.version)
        district1 = max(District.objects.filter(plan=plan,district_id=self.district1.district_id),key=lambda d: d.version)

        # Ensure geounits were assigned correctly
        unassigned = plan.get_unassigned_geounits(threshold=0.1)
        self.assertEqual(0, len(unassigned), ("Unassigned has geounits", len(unassigned), result))
        num = len(district1.get_base_geounits(0.1))
        self.assertEqual(730, num, ("District 1 doesn't contain all of the geounits", num, result))

        # Fixing unassigned should fail, since there are no unassigned geounits
        result = plan.fix_unassigned(threshold=0.1)
        self.assertFalse(result[0], ('No unassigned geounits', result))

        # Create one small and one large unassigned holes in district 1
        units = geounits[10:12] + geounits[19:21] + geounits[28:30] + [geounits[47]]
        plan.add_geounits(0, [str(x.id) for x in units], self.geolevel.id, plan.version)
        district1 = max(District.objects.filter(plan=plan,district_id=self.district1.district_id),key=lambda d: d.version)
        version_with_holes = district1.version

        # Ensure geounits were unassigned correctly
        unassigned = plan.get_unassigned_geounits(threshold=0.1)
        self.assertEqual(63, len(unassigned), ("Unassigned has wrong number of geounits", len(unassigned), result))
        num = len(district1.get_base_geounits(0.1))
        self.assertEqual(730 - 63, num, ("District 1 has the wrong number of the geounits", num, result))

        # Fix the holes
        result = plan.fix_unassigned(threshold=0.1)
        self.assertTrue(result[0], ('Holes should have been closed', result))
        unassigned = plan.get_unassigned_geounits(threshold=0.1)
        self.assertEqual(0, len(unassigned), ("Unassigned should be empty", len(unassigned), result))

        # Try the same thing when the district with holes is locked
        district1 = District.objects.get(plan=plan, district_id=self.district1.district_id, version=version_with_holes)
        district1.is_locked = True
        district1.save()
        result = plan.fix_unassigned(threshold=0.1, version=version_with_holes)
        self.assertFalse(result[0], ('District locked, nothing should be fixed', result))

        # Unassign some units on the edges (not holes)
        units = geounits[0:1] + geounits[9:10] + [geounits[3]]
        plan.add_geounits(0, [str(x.id) for x in units], self.geolevel.id, plan.version)
        district1 = max(District.objects.filter(plan=plan,district_id=self.district1.district_id),key=lambda d: d.version)
        version_with_edges = district1.version

        # Ensure geounits were unassigned correctly
        unassigned = plan.get_unassigned_geounits(threshold=0.1)
        self.assertEqual(27, len(unassigned), ("Unassigned has wrong number of geounits", len(unassigned), result))
        num = len(district1.get_base_geounits(0.1))
        self.assertEqual(730 - 27, num, ("District 1 has the wrong number of the geounits", num, result))

        # Fix the edges -- this only fixes some of the base geounits
        result = plan.fix_unassigned(threshold=0.1)
        self.assertTrue(result[0], ('Edges should have been assigned', result))
        unassigned = plan.get_unassigned_geounits(threshold=0.1)
        self.assertEqual(12, len(unassigned), ("Unassigned shouldn't quite be empty", len(unassigned), result))
       
        # Fix again -- this fixes some more of the base geounits
        result = plan.fix_unassigned(threshold=0.1)
        self.assertTrue(result[0], ('Edges should have been assigned', result))
        unassigned = plan.get_unassigned_geounits(threshold=0.1)
        self.assertEqual(4, len(unassigned), ("Unassigned should still have some", len(unassigned), result))

        # Fix again -- this should complete the fix
        result = plan.fix_unassigned(threshold=0.1)
        self.assertTrue(result[0], ('Edges should have been assigned', result))
        unassigned = plan.get_unassigned_geounits(threshold=0.1)
        self.assertEqual(0, len(unassigned), ("Unassigned should be empty after 3 fixes", len(unassigned), result))

        # Create a small second district in the lower-left
        units = geounits[0:1] + geounits[9:10]
        plan.add_geounits(self.district2.district_id, [str(x.id) for x in units], self.geolevel.id, plan.version)

        # Create an area of unassigned districts between the two districts (right angle)
        units = geounits[18:20] + [geounits[2], geounits[11]]
        plan.add_geounits(0, [str(x.id) for x in units], self.geolevel.id, plan.version)

        # Ensure geounits were unassigned correctly
        district1 = max(District.objects.filter(plan=plan,district_id=self.district1.district_id),key=lambda d: d.version)
        district2 = max(District.objects.filter(plan=plan,district_id=self.district2.district_id),key=lambda d: d.version)
        unassigned = plan.get_unassigned_geounits(threshold=0.1)
        self.assertEqual(36, len(unassigned), ("Unassigned shouldn't be empty", len(unassigned), result))
        num = len(district2.get_base_geounits(0.1))
        self.assertEqual(18, num, ("District 2 has the wrong number of the geounits", num, result))
        num = len(district1.get_base_geounits(0.1))
        self.assertEqual(730 - 18 - 36, num, ("District 1 has the wrong number of the geounits", num, result))

        # Fix, and ensure the blocks are partially assigned to the one with the lower population
        result = plan.fix_unassigned(threshold=0.1)
        district1 = max(District.objects.filter(plan=plan,district_id=self.district1.district_id),key=lambda d: d.version)
        district2 = max(District.objects.filter(plan=plan,district_id=self.district2.district_id),key=lambda d: d.version)
        self.assertTrue(result[0], ('Right-angle should have been partially fixed', result))
        unassigned = plan.get_unassigned_geounits(threshold=0.1)
        self.assertEqual(10, len(unassigned), ("Unassigned shouldn't quite be empty", len(unassigned), result))
        num = len(district2.get_base_geounits(0.1))
        self.assertEqual(18 + 4, num, ("District 2 has the wrong number of the geounits", num, result))
        num = len(district1.get_base_geounits(0.1))
        self.assertEqual(730 - 18 - 36 + 22, num, ("District 1 has the wrong number of the geounits", num, result))
        version_before = plan.version

        # Fix again -- this fixes the remaining base geounits
        result = plan.fix_unassigned(threshold=0.1)
        district1 = max(District.objects.filter(plan=plan,district_id=self.district1.district_id),key=lambda d: d.version)
        district2 = max(District.objects.filter(plan=plan,district_id=self.district2.district_id),key=lambda d: d.version)
        self.assertTrue(result[0], ('Right-angle should have been fixed', result))
        unassigned = plan.get_unassigned_geounits(threshold=0.1)
        self.assertEqual(0, len(unassigned), ("Unassigned should be empty", len(unassigned), result))
        num = len(district2.get_base_geounits(0.1))
        self.assertEqual(18 + 4 + 5, num, ("District 2 has the wrong number of the geounits", num, result))
        num = len(district1.get_base_geounits(0.1))
        self.assertEqual(730 - 18 - 36 + 22 + 5, num, ("District 1 has the wrong number of the geounits", num, result))

        # Try that again with the smaller district locked
        district2 = District.objects.get(plan=plan, district_id=self.district2.district_id, version=version_before)
        district2.is_locked = True
        district2.save()
        result = plan.fix_unassigned(threshold=0.1, version=version_before)
        district1 = max(District.objects.filter(plan=plan,district_id=self.district1.district_id),key=lambda d: d.version)
        district2 = max(District.objects.filter(plan=plan,district_id=self.district2.district_id),key=lambda d: d.version)
        self.assertTrue(result[0], ('Right-angle should have been fixed', result))
        unassigned = plan.get_unassigned_geounits(threshold=0.1)
        self.assertEqual(0, len(unassigned), ("Unassigned should be empty", len(unassigned), result))
        num = len(district2.get_base_geounits(0.1))
        self.assertEqual(18 + 4, num, ("District 2 has the wrong number of the geounits", num, result))
        num = len(district1.get_base_geounits(0.1))
        self.assertEqual(730 - 18 - 36 + 22 + 10, num, ("District 1 has the wrong number of the geounits", num, result))


class GeounitMixTestCase(BaseTestCase):
    """
    Unit tests to test the mixed geounit spatial queries.
    """
    
    def setUp(self):
        BaseTestCase.setUp(self)
        self.geolevels = Geolevel.objects.all().order_by('id')
        self.geounits = {}
        for gl in self.geolevels:
            self.geounits[gl.id] = list(Geounit.objects.filter(geolevel=gl).order_by('id'))
        self.legbod = LegislativeBody.objects.get(name='TestLegislativeBody')

    def tearDown(self):
        self.geolevels = None
        self.geounits = None
        self.legbod = None
        BaseTestCase.tearDown(self)

    def test_numgeolevels(self):
        """
        Test the number of geolevels created.
        """
        self.assertEqual(3, len(self.geolevels), 'Number of geolevels for mixed geounits is incorrect.')

    def test_numgeounits1(self):
        """
        Test the number of geounits in the first tier of geounits.
        """
        self.assertEqual(9, len(self.geounits[self.geolevels[0].id]), 'Number of geounits at geolevel "%s" is incorrect.' % self.geolevels[0].name)

    def test_numgeounits2(self):
        """
        Test the number of geounits in the second tier of geounits.
        """
        self.assertEqual(81, len(self.geounits[self.geolevels[1].id]), 'Number of geounits at geolevel "%s" is incorrect.' % self.geolevels[1].name)

    def test_numgeounits3(self):
        """
        Test the number of geounits in the third tier of geounits.
        """
        self.assertEqual(729, len(self.geounits[self.geolevels[2].id]), 'Number of geounits at geolevel "%s" is incorrect.' % self.geolevels[2].name)

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
        self.assertEqual(90, numunits, 'Number of geounits within a high-level geounit is incorrect. (%d)' % numunits)

    def test_get_in_gu0(self):
        """
        Test the spatial query to get geounits within a known boundary.
        """
        level = self.geolevels[0]
        units = self.geounits[level.id]

        units = Geounit.objects.filter(geom__within=units[0].geom,geolevel=level.id+1)
        numunits = len(units)
        self.assertEqual(9, numunits, 'Number of geounits within geounit 1 is incorrect. (%d)' % numunits)

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
        self.assertEqual(81, numunits, 'Number of geounits within a high-level geounit is incorrect. (%d)' % numunits)

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
        self.assertEqual(8, numunits, 'Number of geounits inside boundary is incorrect. (%d)' % numunits)

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
        self.assertEqual(1, numunits, 'Number of geounits outside boundary is incorrect. (%d)' % numunits)

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
        self.assertEqual(8, numunits, 'Number of geounits inside boundary is incorrect. (%d)' % numunits)

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
        self.assertEqual(1, numunits, 'Number of geounits outside boundary is incorrect. (%d)' % numunits)

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
        self.assertEqual(3, numunits, 'Number of geounits inside boundary is incorrect. (%d)' % numunits)

        units = Geounit.get_mixed_geounits([str(bigunits[0].id),str(bigunits[4].id),str(bigunits[8].id)], self.legbod, level.id, boundary, True)
        numunits = len(units)
        self.assertEqual(63, numunits, 'Number of geounits inside boundary is incorrect. (%d)' % numunits)

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
        self.assertEqual(19, numunits, 'Number of geounits outside boundary is incorrect. (%d)' % numunits)

        units = Geounit.get_mixed_geounits([str(bigunits[0].id),str(bigunits[4].id),str(bigunits[8].id)], self.legbod, level.id, boundary, False)
        numunits = len(units)
        self.assertEqual(63, numunits, 'Number of geounits outside boundary is incorrect. (%d)' % numunits)


class PurgeTestCase(BaseTestCase):
    """
    Unit tests to test the methods for purging extra districts off a plan.
    """
    fixtures = ['redistricting_testdata.json', 'redistricting_testdata_geolevel2.json']

    def setUp(self):
        BaseTestCase.setUp(self)

        # create a new buch of districts for this test case
        self.plan.district_set.all().delete()
        self.geounits = list(Geounit.objects.filter(geolevel=2).order_by('id'))

        geolevelid = 2

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

            geounits = self.geounits
            geounits = map(lambda x: str(x.id), geounits)
       
            self.plan.add_geounits( (i+1), geounits, geolevelid, self.plan.version)

    def tearDown(self):
        self.geounits = None
        self.plan = None
        BaseTestCase.tearDown(self)

    def test_purge_lt_zero(self):
        self.plan.purge(before=-1)

        self.assertEqual(9, self.plan.version, 'Plan version is incorrect.')
        count = self.plan.district_set.count()
        self.assertEqual(17, count, 'Number of districts in plan is incorrect. (e:17,a:%d)' % count)
        
    def test_purge_gt_max(self):
        self.plan.purge(after=9)

        self.assertEqual(9, self.plan.version, 'Plan version is incorrect.')
        count = self.plan.district_set.count()
        self.assertEqual(17, count, 'Number of districts in plan is incorrect. (e:17,a:%d)' % count)

    def test_purge_lt_four(self):
        self.plan.purge(before=4)

        self.assertEqual(9, self.plan.version, 'Plan version is incorrect.')

        # should have 14 items, purging old versions of districts at version
        # 0, 1, 2, and 3 but keeping the most recent version of each 
        # district 
        # (even if the district version is less than the 'before' keyword)
        count = self.plan.district_set.count()
        self.assertEqual(14, count, 'Number of districts in plan is incorrect. (e:14, a:%d)' % count)

    def test_purge_lt_nine(self):
        self.plan.purge(before=9)

        self.assertEqual(9, self.plan.version, 'Plan version is incorrect.')

        # should have 9 items, purging all old versions of districts, but 
        # keeping the most recent version of each district 
        # (even if the district version is less than the 'before' keyword)
        count = self.plan.district_set.count()
        self.assertEqual(9, count, 'Number of districts in plan is incorrect. (e:9, a:%d)' % count)

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
        self.assertEqual(9, count, 'Number of districts in plan is incorrect. (e:9, a:%d)' % count)

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
        for i in range(0,8):
            item = 9 * (i + 1) + 1

            item = str(self.geounits[item].id)
            self.plan.add_geounits( (i+1), [item], geolevelid, self.plan.version)

        # net gain: 16 districts

        self.assertEqual(16, self.plan.district_set.count() - count, 'Incorrect of districts in the plan district_set.')
        self.assertEqual(8, self.plan.version-oldversion, 'Incorrect number of versions incremented after 8 edits.')

        self.plan.purge(before=oldversion)

        count = self.plan.district_set.count()
        self.assertEqual(25, count, 'Number of districts in plan is incorrect. (e:25, a:%d)' % count)

    def test_version_back(self):
        version = self.plan.get_nth_previous_version(self.plan.version)

        self.assertEqual(0, version, 'Walking back %d versions does not land at zero.' % self.plan.version)

        version = self.plan.get_nth_previous_version(self.plan.version-1)

        self.assertEqual(1, version, 'Walking back %d versions does not land at one.' % (self.plan.version - 1))

    def test_purge_versions(self):
        geolevelid = 2

        oldversion = self.plan.version
        for i in range(oldversion - 1, 4, -1):
            item = 9 * (i + 1) - 2;
            item = str(self.geounits[item].id)
            self.plan.add_geounits( (i+1), [item], geolevelid, i)

        # added four new versions

        newversion = self.plan.version
        self.assertEqual(13, newversion, 'Adding items to sequential positions in history resulted in the wrong number of versions. (e:17,a:%d)' % newversion)

        # the first step back in history shoulde be version 4, since the
        # last edit was off that version

        previous = self.plan.get_nth_previous_version(1)
        self.assertEqual(5, previous, 'The previous version is incorrect, since edits were performed off of 8,7,6,5 versions, with the last edit being off of version 5. (e:5, a:%d)' % previous)

        previous = self.plan.get_nth_previous_version(3)
        self.assertEqual(3, previous, '(e:3, a:%d)' % previous)

        previous = self.plan.get_nth_previous_version(5)
        self.assertEqual(1, previous, '(e:1, a:%d)' % previous)

class CalculatorTestCase(BaseTestCase):

    fixtures = ['redistricting_testdata.json', 'redistricting_testdata_geolevel2.json']

    def setUp(self):
        BaseTestCase.setUp(self)
        self.geolevel = Geolevel.objects.get(pk=2)
        self.geounits = list(Geounit.objects.filter(geolevel=self.geolevel).order_by('id'))
        self.subject1 = Subject.objects.get(name='TestSubject')
        self.subject2 = Subject.objects.get(name='TestSubject2')
    
    def tearDown(self):
        self.geolevel = None
        self.geounits = None
        self.subject1 = None
        self.subject2 = None
        BaseTestCase.tearDown(self)

    def test_sum1(self):
        sum1 = SumValues()
        sum1.arg_dict['value1'] = ('literal','10',)
        sum1.arg_dict['value2'] = ('literal','20',)

        self.assertEqual(None,sum1.result)
        sum1.compute(district=self.district1)
        self.assertEqual(30,sum1.result)

        sum2 = SumValues()

        self.assertEqual(None,sum2.result)
        self.assertEqual(30,sum1.result)

        sum2.compute(district=self.district1)

        self.assertEqual(0,sum2.result)
        self.assertEqual(30,sum1.result)
        
    def test_sum2a(self):
        sumcalc = SumValues()
        sumcalc.arg_dict['value1'] = ('literal','0',)
        sumcalc.arg_dict['value2'] = ('literal','1',)
        sumcalc.arg_dict['value3'] = ('literal','2',)
        sumcalc.compute(plan=self.plan)

        # The sum of a plan w/2 districts and w/3 literals is the sum
        # of literals * the number of plans

        self.assertEqual(6, sumcalc.result, 'Incorrect value during summation. (e:%d,a:%d)' % (6, sumcalc.result))

    def test_sum2b(self):
        sumcalc = SumValues()
        sumcalc.arg_dict['value1'] = ('literal','0',)
        sumcalc.arg_dict['value2'] = ('literal','1',)
        sumcalc.arg_dict['value3'] = ('literal','2',)
        sumcalc.compute(district=self.district1)

        self.assertEqual(3, sumcalc.result, 'Incorrect value during summation. (e:%d,a:%d)' % (3, sumcalc.result))

    def test_sum3(self):
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        exqset = Characteristic.objects.filter(geounit__in=dist1ids,subject=self.subject1)
        expected = float(exqset.aggregate(Sum('number'))['number__sum']) + 5.0

        dist1ids = map(lambda x: str(x.id), dist1ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)

        sumcalc = SumValues()
        sumcalc.arg_dict['value1'] = ('subject',self.subject1.name,)
        sumcalc.arg_dict['value2'] = ('literal','5.0',)
        sumcalc.compute(district=district1)

        actual = sumcalc.result

        self.assertEqual(expected, actual, 'Incorrect value during summation. (e:%s-%d,a:%s-%d)' % (type(expected), expected, type(actual), actual))

    def test_sum4(self):
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        exqset = Characteristic.objects.filter(geounit__in=dist1ids,subject=self.subject1)
        expected = float(exqset.aggregate(Sum('number'))['number__sum'])

        dist1ids = map(lambda x: str(x.id), dist1ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)

        sumcalc = SumValues()
        sumcalc.arg_dict['value1'] = ('subject',self.subject1.name,)
        sumcalc.compute(district=district1)

        actual = sumcalc.result

        self.assertAlmostEquals(expected, actual, 8, 'Incorrect value during summation. (e:%d,a:%d)' % (expected, actual))

    def test_sum5(self):
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[18:21] + self.geounits[27:30] + self.geounits[36:39]
        exqset = Characteristic.objects.filter(geounit__in=dist1ids+dist2ids,subject=self.subject1)
        expected = float(exqset.aggregate(Sum('number'))['number__sum'])

        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        self.plan.add_geounits( self.district2.district_id, dist2ids, self.geolevel.id, self.plan.version)

        sumcalc = SumValues()
        sumcalc.arg_dict['value1'] = ('subject',self.subject1.name,)
        sumcalc.compute(plan=self.plan)

        actual = sumcalc.result

        self.assertAlmostEquals(expected, actual, 8, 'Incorrect value during summation. (e:%d,a:%d)' % (expected, actual))


    def test_percent1(self):
        pctcalc = Percent()
        pctcalc.arg_dict['numerator'] = ('literal','1',)
        pctcalc.arg_dict['denominator'] = ('literal','2',)
        pctcalc.compute(district=self.district1)

        self.assertEqual(0.5, pctcalc.result, 'Incorrect value during percentage. (e:%d,a:%d)' % (0.5, pctcalc.result))

    def test_percent2(self):
        pctcalc = Percent()
        pctcalc.arg_dict['numerator'] = ('literal','2',)
        pctcalc.arg_dict['denominator'] = ('literal','4',)
        pctcalc.compute(district=self.district1)

        self.assertEqual(0.5, pctcalc.result, 'Incorrect value during percentage. (e:%d,a:%d)' % (0.5, pctcalc.result))

    def test_percent3(self):
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        exqset = Characteristic.objects.filter(geounit__in=dist1ids,subject=self.subject1)
        expected = float(exqset.aggregate(Sum('number'))['number__sum']) / 10.0

        dist1ids = map(lambda x: str(x.id), dist1ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)

        pctcalc = Percent()
        pctcalc.arg_dict['numerator'] = ('subject',self.subject1.name,)
        pctcalc.arg_dict['denominator'] = ('literal','10.0',)
        pctcalc.compute(district=district1)

        actual = pctcalc.result

        self.assertEqual(expected, actual, 'Incorrect value during percentage. (e:%f,a:%f)' % (expected, actual))

    def test_percent4(self):
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[18:21] + self.geounits[27:30] + self.geounits[36:39]

        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.filter(district_id=self.district1.district_id,version=self.plan.version)[0]
        expected = float(district1.computedcharacteristic_set.filter(subject=self.subject1)[0].number)

        self.plan.add_geounits( self.district2.district_id, dist2ids, self.geolevel.id, self.plan.version)
        district2 = self.plan.district_set.filter(district_id=self.district2.district_id,version=self.plan.version)[0]
        expected += float(district2.computedcharacteristic_set.filter(subject=self.subject1)[0].number)

        expected = expected / 20

        pctcalc = Percent()
        pctcalc.arg_dict['numerator'] = ('subject',self.subject1.name,)
        pctcalc.arg_dict['denominator'] = ('literal','10.0',)
        pctcalc.compute(plan=self.plan)

        actual = pctcalc.result

        self.assertEqual(expected, actual, 'Incorrect value during percentage. (e:%f,a:%f)' % (expected, actual))

    def test_percent5(self):
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[18:21] + self.geounits[27:30] + self.geounits[36:39]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        self.plan.add_geounits( self.district2.district_id, dist2ids, self.geolevel.id, self.plan.version)

        pctcalc = Percent()
        pctcalc.arg_dict['numerator'] = ('subject',self.subject1.name,)
        pctcalc.arg_dict['denominator'] = ('subject',self.subject1.name,)
        pctcalc.compute(plan=self.plan)

        actual = pctcalc.result

        self.assertEqual(1.0, actual, 'Incorrect value during percentage. (e:%f,a:%f)' % (1.0, actual))


    def test_threshold1(self):
        thrcalc = Threshold()
        thrcalc.arg_dict['value'] = ('literal','1',)
        thrcalc.arg_dict['threshold'] = ('literal','2',)
        thrcalc.compute(district=self.district1)

        self.assertEqual(0, thrcalc.result, 'Incorrect value during threshold. (e:%s,a:%s)' % (0, thrcalc.result))

    def test_threshold2(self):
        thrcalc = Threshold()
        thrcalc.arg_dict['value'] = ('literal','2',)
        thrcalc.arg_dict['threshold'] = ('literal','1',)
        thrcalc.compute(district=self.district1)

        self.assertEqual(1, thrcalc.result, 'Incorrect value during threshold. (e:%s,a:%s)' % (1, thrcalc.result))

    def test_threshold3(self):
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        exqset = Characteristic.objects.filter(geounit__in=dist1ids,subject=self.subject1)
        expected = float(exqset.aggregate(Sum('number'))['number__sum']) > 10.0
        expected = 1 if expected else 0

        dist1ids = map(lambda x: str(x.id), dist1ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)

        thrcalc = Threshold()
        thrcalc.arg_dict['value'] = ('subject',self.subject1.name,)
        thrcalc.arg_dict['threshold'] = ('literal','10.0',)
        thrcalc.compute(district=district1)

        actual = thrcalc.result

        self.assertEqual(expected, actual, 'Incorrect value during threshold. (e:%s,a:%s)' % (expected, actual))

    def test_threshold4(self):
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        exqset = Characteristic.objects.filter(geounit__in=dist1ids,subject=self.subject1)
        expected = float(exqset.aggregate(Sum('number'))['number__sum']) > 5.0
        expected = 1 if expected else 0

        dist1ids = map(lambda x: str(x.id), dist1ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)

        thrcalc = Threshold()
        thrcalc.arg_dict['value'] = ('subject',self.subject1.name,)
        thrcalc.arg_dict['threshold'] = ('literal','5.0',)
        thrcalc.compute(district=district1)

        actual = thrcalc.result

        self.assertEqual(expected, actual, 'Incorrect value during threshold. (e:%s,a:%s)' % (expected, actual))

    def test_threshold_plan1(self):
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[18:21] + self.geounits[27:30] + self.geounits[36:39]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        self.plan.add_geounits( self.district2.district_id, dist2ids, self.geolevel.id, self.plan.version)

        thrcalc = Threshold()
        thrcalc.arg_dict['value'] = ('subject',self.subject1.name,)
        thrcalc.arg_dict['threshold'] = ('literal','10.0',)
        thrcalc.compute(plan=self.plan)

        actual = thrcalc.result

        self.assertEqual(0, actual, 'Incorrect value during threshold. (e:%d,a:%d)' % (0, actual))

        thrcalc.arg_dict['threshold'] = ('literal','7.0',)
        thrcalc.compute(plan=self.plan)

        actual = thrcalc.result

        self.assertEqual(1, actual, 'Incorrect value during threshold. (e:%d,a:%d)' % (1, actual))

        thrcalc.arg_dict['threshold'] = ('literal','5.0',)
        thrcalc.compute(plan=self.plan)

        actual = thrcalc.result

        self.assertEqual(2, actual, 'Incorrect value during threshold. (e:%d,a:%d)' % (2, actual))


    def test_range1(self):
        rngcalc = Range()
        rngcalc.arg_dict['value'] = ('literal','2',)
        rngcalc.arg_dict['min'] = ('literal','1',)
        rngcalc.arg_dict['max'] = ('literal','3',)
        rngcalc.compute(district=self.district1)

        self.assertEqual(1, rngcalc.result, 'Incorrect value during range. (e:%s,a:%s)' % (1, rngcalc.result))

    def test_range2(self):
        rngcalc = Range()
        rngcalc.arg_dict['value'] = ('literal','1',)
        rngcalc.arg_dict['min'] = ('literal','2',)
        rngcalc.arg_dict['max'] = ('literal','3',)
        rngcalc.compute(district=self.district1)

        self.assertEqual(0, rngcalc.result, 'Incorrect value during range. (e:%s,a:%s)' % (0, rngcalc.result))

    def test_range3(self):
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        exqset = Characteristic.objects.filter(geounit__in=dist1ids,subject=self.subject1)
        expected = float(exqset.aggregate(Sum('number'))['number__sum'])
        expected = 1 if 5.0 < expected and expected < 10.0 else 0

        dist1ids = map(lambda x: str(x.id), dist1ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)

        rngcalc = Range()
        rngcalc.arg_dict['value'] = ('subject',self.subject1.name,)
        rngcalc.arg_dict['min'] = ('literal','5.0',)
        rngcalc.arg_dict['max'] = ('literal','10.0',)
        rngcalc.compute(district=district1)

        actual = rngcalc.result

        self.assertEqual(expected, actual, 'Incorrect value during range. (e:%s,a:%s)' % (expected, actual))

    def test_range4(self):
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        exqset = Characteristic.objects.filter(geounit__in=dist1ids,subject=self.subject1)
        expected = float(exqset.aggregate(Sum('number'))['number__sum'])
        expected = 1 if 1.0 < expected and expected < 5.0 else 0

        dist1ids = map(lambda x: str(x.id), dist1ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)

        rngcalc = Range()
        rngcalc.arg_dict['value'] = ('subject',self.subject1.name,)
        rngcalc.arg_dict['min'] = ('literal','1.0',)
        rngcalc.arg_dict['max'] = ('literal','5.0',)
        rngcalc.compute(district=district1)

        actual = rngcalc.result

        self.assertEqual(expected, actual, 'Incorrect value during range. (e:%s,a:%s)' % (expected, actual))


    def test_range_plan1(self):
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[18:21] + self.geounits[27:30] + self.geounits[36:39]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        self.plan.add_geounits( self.district2.district_id, dist2ids, self.geolevel.id, self.plan.version)

        rngcalc = Range()
        rngcalc.arg_dict['value'] = ('subject',self.subject1.name,)
        rngcalc.arg_dict['min'] = ('literal','7.0',)
        rngcalc.arg_dict['max'] = ('literal','11.0',)
        rngcalc.compute(plan=self.plan)

        actual = rngcalc.result
        expected = 1

        self.assertEqual(expected, actual, 'Incorrect value during Plan range. (e:%d,a:%d)' % (expected, actual))


    def test_schwartzberg(self):
        """
        Test the Schwartzberg measure of compactness.
        """
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[18:21] + self.geounits[27:30] + self.geounits[36:39]

        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids, self.geolevel.id, self.plan.version)

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
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[18:21] + self.geounits[27:30] + self.geounits[36:39]

        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids, self.geolevel.id, self.plan.version)

        district1 = max(District.objects.filter(plan=self.plan,district_id=self.district1.district_id),key=lambda d: d.version)
        district2 = max(District.objects.filter(plan=self.plan,district_id=self.district2.district_id),key=lambda d: d.version)

        calc = Schwartzberg()

        calc.compute(plan=self.plan)
        self.assertAlmostEquals(0.87727421546, calc.result, 9, 'Schwartzberg for District 1 was incorrect: %f' % calc.result)

    def test_roeck(self):
        """
        Test the Roeck measure of compactness.
        """
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[18:21] + self.geounits[27:30] + self.geounits[36:39]

        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids, self.geolevel.id, self.plan.version)

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
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[18:21] + self.geounits[27:30] + self.geounits[36:39]

        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids, self.geolevel.id, self.plan.version)

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
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[18:21] + self.geounits[27:30] + self.geounits[36:39]

        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids, self.geolevel.id, self.plan.version)

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
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[18:21] + self.geounits[27:30] + self.geounits[36:39]

        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids, self.geolevel.id, self.plan.version)

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
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[18:21] + self.geounits[27:30] + self.geounits[36:39]

        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids, self.geolevel.id, self.plan.version)

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
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[18:21] + self.geounits[27:30] + self.geounits[36:39]

        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids, self.geolevel.id, self.plan.version)

        district1 = max(District.objects.filter(plan=self.plan,district_id=self.district1.district_id),key=lambda d: d.version)
        district2 = max(District.objects.filter(plan=self.plan,district_id=self.district2.district_id),key=lambda d: d.version)

        calc = LengthWidthCompactness()

        calc.compute(plan=self.plan)
        expected = (0.666667 + 1.000000) / 2
        self.assertAlmostEquals(expected, calc.result, 6, 'Length/Width for plan was incorrect. (e:%0.6f,a:%0.6f)' % (expected, calc.result))

    def test_contiguity1(self):
        cntcalc = Contiguity()
        cntcalc.compute(district=self.district1)

        self.assertEqual(0, cntcalc.result, 'District is contiguous.')

    def test_contiguity2(self):
        dist1ids = self.geounits[0:3] + self.geounits[12:15]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)

        cntcalc = Contiguity()
        cntcalc.compute(district=district1)

        self.assertEqual(0, cntcalc.result, 'District is contiguous.')

    def test_contiguity3(self):
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)

        cntcalc = Contiguity()
        cntcalc.compute(district=district1)

        self.assertEqual(1, cntcalc.result, 'District is discontiguous.')

    def test_contiguity_singlepoint(self):
        dist1ids = [self.geounits[0], self.geounits[10]]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)

        # 2 geounits connected by one point -- single-point is false, should fail
        cntcalc = Contiguity()
        cntcalc.arg_dict['allow_single_point'] = ('literal','0',)
        cntcalc.compute(district=district1)
        self.assertEqual(0, cntcalc.result, 'District is contiguous at 1 point, but single-point contiguity is false.')

        # 2 geounits connected by one point -- single-point is true, should pass
        cntcalc = Contiguity()
        cntcalc.arg_dict['allow_single_point'] = ('literal','1',)
        cntcalc.compute(district=district1)
        self.assertEqual(1, cntcalc.result, 'District is contiguous at 1 point, and single-point contiguity is true.')

        # add another geounits so 3 geometries are connected by 2 single points (contiguous)
        dist1ids = [self.geounits[18]]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)

        cntcalc = Contiguity()
        cntcalc.arg_dict['allow_single_point'] = ('literal','1',)
        cntcalc.compute(district=district1)
        self.assertEqual(1, cntcalc.result, 'District is contiguous at 1 point twice, and single-point contiguity is true.')

        # add another geounits so 4 geometries are connected by 3 single points (contiguous)
        dist1ids = [self.geounits[28]]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)

        cntcalc = Contiguity()
        cntcalc.arg_dict['allow_single_point'] = ('literal','1',)
        cntcalc.compute(district=district1)
        self.assertEqual(1, cntcalc.result, 'District is contiguous at 1 point thrice, and single-point contiguity is true.')

        # add more geounits so 5 geometries are connected by 3 single points (discontiguous)
        dist1ids = [self.geounits[14]]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)

        cntcalc = Contiguity()
        cntcalc.arg_dict['allow_single_point'] = ('literal','1',)
        cntcalc.compute(district=district1)
        self.assertEqual(0, cntcalc.result, 'District is contiguous at 1 point thrice, but has a disjoint geometry.')

    def test_contiguity_overrides(self):
        dist1ids = [self.geounits[0], self.geounits[11]]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)

        overrides = []
        def add_override(id1, id2):
            override = ContiguityOverride(override_geounit=self.geounits[id1], connect_to_geounit=self.geounits[id2])
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
        self.assertEqual(0, cntcalc.result, 'District is non-contiguous, and no overrides have been defined.')

        # define a contiguity override between the two geounits, same test should now pass
        add_override(0, 11)
        cntcalc.compute(district=district1)
        self.assertEqual(1, cntcalc.result, 'District is not contiguous, but an override should make it so.')

        # add a few more non-contiguous geounits without overrides, should fail
        dist1ids = [self.geounits[4], self.geounits[22], self.geounits[7]]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)
        cntcalc.compute(district=district1)
        self.assertEqual(0, cntcalc.result, 'District needs 3 overrides to be considered contiguous')

        # add overrides and test one by one. the final override should make the test pass
        add_override(11, 4)
        cntcalc.compute(district=district1)
        self.assertEqual(0, cntcalc.result, 'District needs 2 overrides to be considered contiguous')
        add_override(4, 22)
        cntcalc.compute(district=district1)
        self.assertEqual(0, cntcalc.result, 'District needs 1 overrides to be considered contiguous')
        add_override(7, 4)
        cntcalc.compute(district=district1)
        self.assertEqual(1, cntcalc.result, 'District has appropriate overrides to be considered contiguous')

        # check to make sure this works in conjunction with single-point contiguity by adding 2 more geounits
        dist1ids = [self.geounits[14], self.geounits[19]]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)
        cntcalc.arg_dict['allow_single_point'] = ('literal','0',)
        cntcalc.compute(district=district1)
        self.assertEqual(0, cntcalc.result, 'Calculator needs allow_single_point on to be considered contiguous')
        cntcalc.arg_dict['allow_single_point'] = ('literal','1',)
        cntcalc.compute(district=district1)
        self.assertEqual(1, cntcalc.result, 'allow_single_point is enabled, should be considered contiguous')

        # remove contiguity overrides
        for override in overrides:
            override.delete()

    def test_contiguity_plan1(self):
        dist1ids = self.geounits[0:4] + self.geounits[5:9]
        dist2ids = self.geounits[9:13] + self.geounits[14:18]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        self.plan.add_geounits( self.district2.district_id, dist2ids, self.geolevel.id, self.plan.version)

        cntcalc = Contiguity()
        cntcalc.compute(plan=self.plan)

        actual = cntcalc.result

        self.assertEqual(1, actual, 'Incorrect value during contiguity. (e:%d,a:%d)' % (1, actual))

        self.plan.add_geounits( self.district1.district_id, [str(self.geounits[4].id)], self.geolevel.id, self.plan.version )

        cntcalc.compute(plan=self.plan)

        actual = cntcalc.result

        self.assertEqual(2, actual, 'Incorrect value during contiguity. (e:%d,a:%d)' % (2, actual))

        self.plan.add_geounits( self.district2.district_id, [str(self.geounits[13].id)], self.geolevel.id, self.plan.version )

        cntcalc.compute(plan=self.plan)

        actual = cntcalc.result

        self.assertEqual(3, actual, 'Incorrect value during contiguity. (e:%d,a:%d)' % (3, actual))


    def test_equivalence1(self):
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[18:21] + self.geounits[27:30] + self.geounits[36:39]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        self.plan.add_geounits( self.district2.district_id, dist2ids, self.geolevel.id, self.plan.version)

        equcalc = Equivalence()
        equcalc.arg_dict['value'] = ('subject',self.subject1.name,)
        equcalc.compute(plan=self.plan)

        actual = equcalc.result

        self.assertEqual(3.0, actual, 'Incorrect value during equivalence. (e:%f,a:%f)' % (3.0, actual))


    def test_representationalfairness(self):
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[6:9] + self.geounits[15:18]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        self.plan.add_geounits( self.district2.district_id, dist2ids, self.geolevel.id, self.plan.version)

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
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[6:9] + self.geounits[15:18]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        self.plan.add_geounits( self.district2.district_id, dist2ids, self.geolevel.id, self.plan.version)

        # If you're playing along at home, the values are:
        # District 1: 6 dem, 150 rep; District 2: 42 dem, 114 rep
        ccalc = Competitiveness()
        ccalc.arg_dict['democratic'] = ('subject',self.subject1.name,)
        ccalc.arg_dict['republican'] = ('subject',self.subject2.name,)
        ccalc.compute(plan=self.plan)

        actual = ccalc.result

        # by default, we have a range of .45 - .55.  Neither district is fair.
        self.assertEqual(0, actual, 'Incorrect value during competitiveness. (e:%d,a:%d)' % (0, actual))

        # Open up the range to .25 - .75. District 2 should be fair now
        ccalc = Competitiveness()
        ccalc.arg_dict['democratic'] = ('subject',self.subject1.name,)
        ccalc.arg_dict['republican'] = ('subject',self.subject2.name,)
        ccalc.arg_dict['range'] = ('literal',.25,)
        ccalc.compute(plan=self.plan)

        actual = ccalc.result
        self.assertEqual(1, actual, 'Incorrect value during competitiveness. (e:%d,a:%d)' % (1, actual))

        # Open up the range to .03 - .97 (inclusive). District 1 should also be fair now. Switch subjects, too.
        ccalc = Competitiveness()
        ccalc.arg_dict['democratic'] = ('subject',self.subject2.name,)
        ccalc.arg_dict['republican'] = ('subject',self.subject1.name,)
        ccalc.arg_dict['range'] = ('literal',.47,)
        ccalc.compute(plan=self.plan)

        actual = ccalc.result
        self.assertEqual(2, actual, 'Incorrect value during competitiveness. (e:%d,a:%d)' % (2, actual))

    def test_countdist(self):
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[6:9] + self.geounits[15:18]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        self.plan.add_geounits( self.district2.district_id, dist2ids, self.geolevel.id, self.plan.version)

        numcalc = CountDistricts()
        numcalc.arg_dict['target'] = ('literal','2',)
        numcalc.compute(plan=self.plan)

        actual = numcalc.result

        self.assertEqual(True, actual, 'Incorrect value during district counting. (e:%s,a:%s)' % (True, actual))

    def test_equipop(self):
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[6:9] + self.geounits[15:18]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        self.plan.add_geounits( self.district2.district_id, dist2ids, self.geolevel.id, self.plan.version)

        equicalc = Equipopulation()
        equicalc.arg_dict['value'] = ('subject',self.subject1.name,)
        equicalc.arg_dict['min'] = ('literal','5',)
        equicalc.arg_dict['max'] = ('literal','10',)
        equicalc.compute(plan=self.plan)

        actual = equicalc.result

        self.assertEqual(False, actual, 'Incorrect value during plan equipop. (e:%s,a:%s)' % (False, actual))

        equicalc.arg_dict['min'] = ('literal','40',)
        equicalc.arg_dict['max'] = ('literal','45',)
        equicalc.compute(plan=self.plan)

        actual = equicalc.result

        self.assertEqual(False, actual, 'Incorrect value during plan equipop. (e:%s,a:%s)' % (False, actual))

        equicalc.arg_dict['min'] = ('literal','5',)
        equicalc.arg_dict['max'] = ('literal','45',)
        equicalc.compute(plan=self.plan)

        actual = equicalc.result

        self.assertEqual(True, actual, 'Incorrect value during plan equipop. (e:%s,a:%s)' % (True, actual))



    def test_majmin(self):
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[18:21] + self.geounits[27:30] + self.geounits[36:39]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        self.plan.add_geounits( self.district2.district_id, dist2ids, self.geolevel.id, self.plan.version)

        majcalc = MajorityMinority()
        majcalc.arg_dict['population'] = ('subject',self.subject1.name,)
        majcalc.arg_dict['count'] = ('literal', 1,)
        majcalc.arg_dict['minority1'] = ('subject',self.subject2.name,)
        majcalc.arg_dict['threshold'] = ('literal', 0.5,)
        majcalc.compute(plan=self.plan)

        actual = majcalc.result

        self.assertEqual(True, actual, 'Incorrect value during majority/minority. (e:%f,a:%f)' % (True, actual))

        majcalc.arg_dict['count'] = ('literal', 1,)
        majcalc.arg_dict['population'] = ('subject',self.subject2.name,)
        majcalc.arg_dict['minority1'] = ('subject',self.subject1.name,)
        majcalc.arg_dict['threshold'] = ('literal', 0.5,)
        majcalc.compute(plan=self.plan)

        actual = majcalc.result

        self.assertEqual(False, actual, 'Incorrect value during majority/minority. (e:%f,a:%f)' % (False, actual))

    def test_interval(self):
        interval = Interval()
        interval.arg_dict['subject'] = ('subject', self.subject2.name)
        interval.arg_dict['target'] = ('literal', 301)
        interval.arg_dict['bound1'] = ('literal', .50)
        interval.arg_dict['bound2'] = ('literal', .25)

        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[18:21] + self.geounits[27:30] + self.geounits[36:39]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        self.plan.add_geounits( self.district2.district_id, dist2ids, self.geolevel.id, self.plan.version)

        # Update our districts
        for d in self.plan.get_districts_at_version(self.plan.version, include_geom = False):
            if (d.district_id == self.district1.district_id):
                self.district1 = d
            elif (d.district_id == self.district2.district_id):
                self.district2 = d
        
        # Value of 375 for district 1.  Should be in middle class - i.e. return 2 on 0-based index
        interval.compute(district=self.district1)
        self.assertEqual(2, interval.result, "Incorrect interval returned: e:%s,a:%s" % (2, interval.result))
        # Value of 225 for district 1.  Should be in 2nd class - i.e. return 1 on 0-based index
        interval.compute(district=self.district2)
        self.assertEqual(1, interval.result, "Incorrect interval returned: e:%s,a:%s" % (1, interval.result))

        # District 1 is in the middle class - should get a 1
        interval.compute(plan=self.plan)
        self.assertEqual(1, interval.result, "Incorrect interval returned: e:%s,a:%s" % (1, interval.result))

        # Adjust to get them all out of the target
        interval.arg_dict['bound1'] = ('literal', .1)
        interval.arg_dict['bound2'] = ('literal', .2)

        interval.compute(plan=self.plan)
        self.assertEqual(0, interval.result, "Incorrect interval returned: e:%s,a:%s" % (0, interval.result))

        # Everybody's on target 
        interval.arg_dict['bound1'] = ('literal', .5)
        del interval.arg_dict['bound2']

        interval.compute(plan=self.plan)
        self.assertEqual(2, interval.result, "Incorrect interval returned: e:%s,a:%s" % (2, interval.result))

        # Everybody's over - make sure we're in group 3 (0-based index 2)
        interval.arg_dict['target'] = ('literal', 0)
        interval.compute(district=self.district2)
        self.assertEqual(2, interval.result, "Incorrect interval returned: e:%s,a:%s" % (2, interval.result))

    def test_average1(self):
        avg = Average()
        avg.arg_dict['value1'] = ('literal','10',)
        avg.arg_dict['value2'] = ('literal','20',)

        self.assertEqual(None,avg.result)
        avg.compute(district=self.district1)
        self.assertEqual(15,avg.result)

        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[18:21] + self.geounits[27:30] + self.geounits[36:39]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        self.plan.add_geounits( self.district2.district_id, dist2ids, self.geolevel.id, self.plan.version)

        # Update our districts
        for d in self.plan.get_districts_at_version(self.plan.version, include_geom = False):
            if (d.district_id == self.district1.district_id):
                self.district1 = d
            elif (d.district_id == self.district2.district_id):
                self.district2 = d

        avg = Average()
        avg.arg_dict['value1'] = ('subject', self.subject1.name)
        avg.arg_dict['value2'] = ('subject', self.subject2.name)

        self.assertEqual(None,avg.result)
        avg.compute(district=self.district1)
        self.assertEqual(195.0,avg.result)

        avg = Average()
        avg.arg_dict['value1'] = ('subject', self.subject1.name)
        avg.arg_dict['value2'] = ('subject', self.subject2.name)

        self.assertEqual(None,avg.result)
        avg.compute(district=self.district2)
        self.assertEqual(117.0,avg.result)

    def test_average2(self):
        avg = Average()
        avg.arg_dict['value1'] = ('literal', '10.0')
        avg.arg_dict['value2'] = ('literal', '20.0')

        self.assertEqual(None, avg.result)
        avg.compute(plan=self.plan)
        self.assertEqual(15.0,avg.result)

        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[18:21] + self.geounits[27:30] + self.geounits[36:39]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        self.plan.add_geounits( self.district2.district_id, dist2ids, self.geolevel.id, self.plan.version)

        avg = Average()
        avg.arg_dict['value1'] = ('subject', self.subject1.name)
        avg.arg_dict['value2'] = ('subject', self.subject2.name)

        self.assertEqual(None,avg.result)
        avg.compute(plan=self.plan)
        self.assertEqual(97.5,avg.result)

    def test_average3(self):
        avg = Average()
        avg.arg_dict['value1'] = ('literal', '10.0')
        avg.arg_dict['value2'] = ('literal', '20.0')
        avg.arg_dict['min'] = ('literal', '10.0')
        avg.arg_dict['max'] = ('literal', '20.0')
        avg.compute(plan=self.plan)

        # Average is 15.0, should be between 10.0 and 20.0
        self.assertEqual(True,avg.result)

        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[18:21] + self.geounits[27:30] + self.geounits[36:39]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        self.plan.add_geounits( self.district2.district_id, dist2ids, self.geolevel.id, self.plan.version)

        avg = Average()
        avg.arg_dict['value1'] = ('subject', self.subject1.name)
        avg.arg_dict['value2'] = ('subject', self.subject2.name)
        avg.arg_dict['min'] = ('literal', '90.0')
        avg.arg_dict['max'] = ('literal', '95.0')
        avg.compute(plan=self.plan)

        # Average is 97.5, should not be beween 90.0 and 95.0
        self.assertEqual(False,avg.result)

        avg = Average()
        avg.arg_dict['value1'] = ('subject', self.subject1.name)
        avg.arg_dict['value2'] = ('subject', self.subject2.name)
        avg.arg_dict['min'] = ('literal', '100.0')
        avg.arg_dict['max'] = ('literal', '105.0')
        avg.compute(plan=self.plan)

        # Average is 97.5, should not be beween 100.0 and 105.0
        self.assertEqual(False,avg.result)

    def test_splitcounter(self):
        # Create a plan with two large districts - geounits 5 and 8

        p1 = self.plan
        d1a_id = 1
        # Create a district of geounit 5
        p1.add_geounits( d1a_id, ['5'], 1, p1.version)

        d2a_id = 2
        # Create a district of geounit 8
        p1.add_geounits( d2a_id, ['8'], 1, p1.version)

        # Create a plan with two districts - one crosses both 5 and 8,
        p2 = self.plan2
        d1b_id = 3
        geounits = [str(i) for i in range(30,69) if i % 9 in (3,4,5)]
        p2.add_geounits( d1b_id, geounits, 2, p2.version)

        # the other is entirely within 5
        d2b_id = 4
        geounits = [str(i) for i in range(42, 61) if i % 9 == 6]
        p2.add_geounits( d2b_id, geounits, 2, p2.version)

        # Calc the first plan with second as other
        calc = SplitCounter()
        calc.arg_dict['boundary_id'] = ('literal', 'plan.%d' % p2.id)
        calc.compute(plan=p1)
        num_splits = calc.result['total_splits']
        self.assertEqual(2, num_splits, 'Did not find expected splits. e:2, a:%s' % num_splits)

        # Calc the second plan with first as other
        calc.__init__()
        calc.arg_dict['boundary_id'] = ('literal', 'plan.%d' % p1.id)
        calc.compute(plan=p2)
        num_splits = calc.result['total_splits']
        split_tuples = calc.result['splits']
        self.assertEqual(3, num_splits, 'Did not find expected splits. e:3, a:%s' % num_splits)
        self.assertTrue((3,1) in calc.result['splits'], 'Split not detected')
        self.assertTrue(('TestMember 3', 'TestMember 1') in calc.result['named_splits'], 'Split not named correctly')

        # Calc the first plan with geolevel 1 - no splits
        calc.__init__()
        calc.arg_dict['boundary_id'] = ('literal', 'geolevel.1')
        calc.compute(plan=p1)
        num_splits = calc.result['total_splits']
        self.assertEqual(0, num_splits, 'Did not find expected splits. e:0, a:%s' % num_splits)

        # Calc the second plan with geolevel 2 - no splits
        calc.__init__()
        calc.arg_dict['boundary_id'] = ('literal', 'geolevel.2')
        calc.compute(plan=p2)
        num_splits = calc.result['total_splits']
        self.assertEqual(0, num_splits, 'Did not find expected splits. e:0, a:%s' % num_splits)

        # Calc the second plan with geolevel 1 - d1a and d2a both split the geolevels
        calc.__init__()
        calc.arg_dict['boundary_id'] = ('literal', 'geolevel.1')
        calc.compute(plan=p2)
        district_splits = calc.result['total_split_districts']
        self.assertEqual(2, district_splits, 'Did not find expected splits. e:2, a:%s' % district_splits)
        self.assertTrue((4, u'0000004') in calc.result['splits'], 'Did not find expected splits')
    
class AllBlocksTestCase(BaseTestCase):
    fixtures = ['redistricting_testdata.json',
                'redistricting_testdata_geolevel2.json',
                'redistricting_testdata_geolevel3.json',
                ]
    def setUp(self):
        BaseTestCase.setUp(self)
        self.geolevel = Geolevel.objects.get(pk=2)
        self.geounits = list(Geounit.objects.filter(geolevel=self.geolevel).order_by('id'))
    
    def tearDown(self):
        self.geolevel = None
        self.geounits = None
        BaseTestCase.tearDown(self)

    def test_allblocks(self):
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[6:9] + self.geounits[15:18]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        self.plan.add_geounits( self.district2.district_id, dist2ids, self.geolevel.id, self.plan.version)

        allblocks = AllBlocksAssigned()
        allblocks.arg_dict['threshold'] = ('literal', 0.1)

        plan = Plan.objects.get(pk=self.plan.id)
        allblocks.compute(plan=plan)
        actual = allblocks.result
        self.assertEqual(False, actual, 'Incorrect value during plan allblocks. (e:%s,a:%s)' % (False, actual))

        remainderids = plan.get_unassigned_geounits(0.1)
        remainderids = map(lambda x: str(x[0]), remainderids)
        plan.add_geounits( self.district2.district_id, remainderids, self.geolevel.id, plan.version)

        plan = Plan.objects.get(pk=plan.id)
        allblocks.compute(plan=plan)
        actual = allblocks.result
        self.assertEqual(True, actual, 'Incorrect value during plan allblocks. (e:%s,a:%s)' % (True, actual))

class ScoreRenderTestCase(BaseTestCase):
    fixtures = ['redistricting_testdata.json', 'redistricting_testdata_geolevel2.json', 'redistricting_testdata_scoring.json']

    def setUp(self):
        BaseTestCase.setUp(self)
        self.geolevel = Geolevel.objects.get(pk=2)
        self.geounits = list(Geounit.objects.filter(geolevel=self.geolevel).order_by('id'))

    def tearDown(self):
        self.geolevel = None
        self.geounits = None
        BaseTestCase.tearDown(self)

    def test_panelrender_plan(self):
        geolevelid = self.geolevel.id
        geounits = self.geounits

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
                
            self.assertEqual(expected, markup, 'The markup was incorrect. (e:"%s", a:"%s")' % (expected, markup))

            os.remove(tplfile)

    def test_panelrender_district(self):
        geolevelid = self.geolevel.id
        geounits = self.geounits

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
            self.assertEqual(expected, markup, 'The markup for districts was incorrect. (e:"%s", a:"%s")' % (expected,markup))

            os.remove(tplfile)

    def test_display_render_page(self):
        geolevelid = self.geolevel.id
        geounits = self.geounits

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
        self.assertEqual(expected, markup, 'The markup was incorrect. (e:"%s", a:"%s")' % (expected, markup))

        os.remove(tplfile)

    def test_display_render_div(self):
        geolevelid = self.geolevel.id
        geounits = self.geounits

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
        self.assertEqual('', markup, 'The markup was incorrect. (e:"", a:"%s")' % markup)

        markup = display.render(self.plan.get_districts_at_version(self.plan.version,include_geom=False))

        expected = 'District 1:86.83%<span>1</span>' + \
            'District 2:86.83%<span>1</span>' + \
            'Unassigned:n/a<span>0</span>'
        self.assertEqual(expected, markup, 'The markup was incorrect. (e:"%s", a:"%s")' % (expected, markup))

        os.remove(tplfile)

    def test_scoredisplay_with_overrides(self):
        # Get a ScoreDisplay
        display = ScoreDisplay.objects.get(pk=1)
        display.is_page = False

        # Make up a ScorePanel - don't save it
        panel = ScorePanel(title="My Fresh Panel", type="district", template="sp_template2.html")
        # Create two functions, one with an arg and one without
        function = ScoreFunction(calculator="redistricting.calculators.SumValues", name="My Fresh Calc", label="Hot Sums",is_planscore=False)

        arg1 = ScoreArgument(argument="value1", value="5", type="literal")
        arg2 = ScoreArgument(argument="value2", value="TestSubject", type="subject")

        # Render the ScoreDisplay
        components = [(panel, [(function, arg1, arg2)])]
        district_result = display.render([self.district1], components=components)
        self.assertEqual("District 1:<span>14.0000</span>", district_result, 'Didn\'t get expected result when overriding district\'s display')

        # Add some districts to our plan
        geolevelid = self.geolevel.id
        geounits = self.geounits

        dist1ids = geounits[0:3] + geounits[9:12]
        dist2ids = geounits[6:9] + geounits[15:18]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevelid, self.plan.version)
        self.plan.add_geounits( self.district2.district_id, dist2ids, geolevelid, self.plan.version)

        # Set up the elements to work for a plan
        panel.type = 'plan'
        panel.template = 'sp_template1.html'
        function.is_planscore = True
        components = [(panel, [(function, arg1, arg2)])]

        # Check the result
        plan_result = display.render(self.plan, components=components)
        self.assertEqual("testPlan:['<span>58.0000</span>']", plan_result, 'Didn\'t get expected result when overriding plan\'s display')

    def test_splitcounter_display(self):
        # Create a plan with two districts - one crosses both 5 and 8
        p1 = self.plan
        d1a_id = 1
        geounits = [str(i) for i in range(30,69) if i % 9 in (3,4,5)]
        p1.add_geounits( d1a_id, geounits, 2, p1.version)

        # the other is entirely within 5
        d2a_id = 5
        geounits = [str(i) for i in range(42, 61) if i % 9 == 6]
        p1.add_geounits( d2a_id, geounits, 2, p1.version)

        # Get a ScoreDisplay and components to render
        display = ScoreDisplay.objects.get(pk=1)
        display.is_page = False
        display.save()

        panel = ScorePanel(title="Splits Report", type="plan", template="sp_template1.html", cssclass="split_panel")
        function = ScoreFunction(calculator="redistricting.calculators.SplitCounter", name="splits_test", label="Geolevel Splits", is_planscore=True)
        arg1 = ScoreArgument(argument="boundary_id", value="geolevel.1", type="literal")

        components = [(panel, [(function, arg1)])]

        expected_result = "%s:[u'<div class=\"split_report\"><div>Total districts split by first level: 2</div><div>Total number of splits: 7</div><div class=\"table_container\"><table class=\"report\"><thead><tr><th>testPlan district</th><th>first level district</th></tr></thead><tbody><tr><td>TestMember 1</td><td>0000000</td></tr><tr><td>TestMember 1</td><td>0000001</td></tr><tr><td>TestMember 1</td><td>0000003</td></tr><tr><td>TestMember 1</td><td>0000004</td></tr><tr><td>TestMember 1</td><td>0000006</td></tr><tr><td>TestMember 1</td><td>0000007</td></tr><tr><td>TestMember 5</td><td>0000004</td></tr></tbody></table></div></div>']" % p1.name

        # Check the result
        plan_result = display.render(p1, components=components)

        self.assertEqual(expected_result, plan_result, "Didn't get expected result when rendering SplitCounter:\ne:%s\na:%s" % (expected_result, plan_result))

class ComputedScoresTestCase(BaseTestCase):
    def test_district1(self):
        geolevelid = 2
        geounits = list(Geounit.objects.filter(geolevel=geolevelid).order_by('id'))

        dist1ids = geounits[0:3] + geounits[9:12]
        dist2ids = geounits[6:9] + geounits[15:18]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevelid, self.plan.version)
        self.plan.add_geounits( self.district2.district_id, dist2ids, geolevelid, self.plan.version)
        
        function = ScoreFunction.objects.get(calculator__endswith='SumValues',is_planscore=False)
        numscores = ComputedDistrictScore.objects.all().count()

        self.assertEqual(0, numscores, 'The number of computed district scores is incorrect. (e:0, a:%d)' % numscores)

        district1 = self.plan.district_set.filter(district_id=self.district1.district_id, version=self.plan.version-1)[0]
        expected = function.score(district1)

        score = ComputedDistrictScore.compute(function, district1)

        self.assertEqual(expected, score, 'The score computed is incorrect. (e:%0.1f, a:%0.1f)' % (expected,score,))

        numscores = ComputedDistrictScore.objects.all().count()

        self.assertEqual(1, numscores, 'The number of computed district scores is incorrect. (e:1, a:%d)' % numscores)

        dist1ids = geounits[3:6]
        dist1ids = map(lambda x: str(x.id), dist1ids)

        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevelid, self.plan.version )

        district1 = self.plan.district_set.filter(district_id=self.district1.district_id, version=self.plan.version)[0]
        expected = function.score(district1)

        score = ComputedDistrictScore.compute(function, district1)

        self.assertEqual(expected, score, 'The score computed is incorrect. (e:%0.1f, a:%0.1f)' % (expected,score,))

        numscores = ComputedDistrictScore.objects.all().count()

        self.assertEqual(2, numscores, 'The number of computed district scores is incorrect. (e:2, a:%d)' % numscores)

    def test_plan1(self):
        geolevelid = 2
        geounits = list(Geounit.objects.filter(geolevel=geolevelid).order_by('id'))

        dist1ids = geounits[0:3] + geounits[9:12]
        dist2ids = geounits[6:9] + geounits[15:18]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevelid, self.plan.version)
        self.plan.add_geounits( self.district2.district_id, dist2ids, geolevelid, self.plan.version)
        
        function = ScoreFunction.objects.get(calculator__endswith='SumValues',is_planscore=True)
        numscores = ComputedPlanScore.objects.all().count()

        self.assertEqual(0, numscores, 'The number of computed plan scores is incorrect. (e:0, a:%d)' % numscores)

        score = ComputedPlanScore.compute(function, self.plan)

        self.assertEqual(48, score, 'The score computed is incorrect. (e:48.0, a:%0.1f)' % score)

        numscores = ComputedPlanScore.objects.all().count()

        self.assertEqual(1, numscores, 'The number of computed plan scores is incorrect. (e:1, a:%d)' % numscores)

        dist1ids = geounits[3:6]
        dist1ids = map(lambda x: str(x.id), dist1ids)

        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevelid, self.plan.version )

        score = ComputedPlanScore.compute(function, self.plan)

        self.assertEqual(147, score, 'The score computed is incorrect. (e:147.0, a:%0.1f)' % score)

        numscores = ComputedPlanScore.objects.all().count()

        self.assertEqual(2, numscores, 'The number of computed plan scores is incorrect. (e:2, a:%d)' % numscores)


class MultiMemberTestCase(BaseTestCase):
    """
    Unit tests to multi-member districts
    
    Note: this test is separated out, and in a single method, because
    of hard-to-track down segfault problems most likely related to
    fixtures and performing posts with the Client component. When these
    problems are worked out, the tests should be broken out into more
    methods.
    """

    fixtures = ['redistricting_testdata.json', 'redistricting_testdata_geolevel2.json', 'redistricting_testdata_geolevel3.json']

    def setUp(self):
        BaseTestCase.setUp(self)        
        self.geolevel = Geolevel.objects.get(pk=2)
        self.geolevels = Geolevel.objects.all().order_by('id')

        self.geounits = {}
        for gl in self.geolevels:
           self.geounits[gl.id] = list(Geounit.objects.filter(geolevel=gl).order_by('id'))

    def tearDown(self):
        self.plan = None
        self.district1 = None
        self.district2 = None
        self.subject1 = None
        self.geolevel = None
        self.geolevels = None
        self.geounits = None
        try:
            BaseTestCase.tearDown(self)
        except:
            import traceback
            print(traceback.format_exc())
            print('Couldn\'t tear down')

    def test_multi_member(self):
        """
        Test the logic for modifying the number of members in a district
        Also tests magnitudes in export process and calculators
        """
        district10 = District(name='District 10', version=0)
        district10.plan = self.plan
        district10.save()
        
        district11 = District(name='District 11', version=0)
        district11.plan = self.plan
        district11.save()
        
        district = district10
        districtid = district.id
        district_id = district.district_id
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]

        self.subject1 = Subject.objects.get(name='TestSubject')
        
        # Login
        client = Client()
        client.login(username=self.username, password=self.password)

        # Add some geounits
        dist10ids = [geounits[11]]
        dist10ids = map(lambda x: str(x.id), dist10ids)
        self.plan.add_geounits(district10.district_id, dist10ids, geolevelid, self.plan.version)
        self.plan = Plan.objects.get(pk=self.plan.id)
        
        dist11ids = [geounits[22]]
        dist11ids = map(lambda x: str(x.id), dist11ids)
        self.plan.add_geounits(district11.district_id, dist11ids, geolevelid, self.plan.version)
        self.plan = Plan.objects.get(pk=self.plan.id)
        
        # Issue command to assign 5 members to a district for a legislative body that doesn't support multi-members
        # Should fail
        params = { 'version':self.plan.version, 'counts[]':5, 'districts[]':district_id }
        response = client.post('/districtmapping/plan/%d/districtmembers/' % self.plan.id, params)
        
        resp_obj = json.loads(response.content)
        self.assertFalse(resp_obj['success'], 'Member assign request for disallowed legbody wasn\'t denied: ' + str(response))

        # Verify the number of members is 1
        num = district10.num_members
        self.assertEqual(1, num, '# members is incorrect: %d' % num)

        # Verify the version number is 2
        num = self.plan.version
        self.assertEqual(2, num, 'version number is incorrect: %d' % num)

        # Modify the legislative body, so that it does support multi-members, and reissue the request
        # Should pass
        self.plan.legislative_body.multi_members_allowed = True
        self.plan.legislative_body.save()
        params = { 'version':self.plan.version, 'counts[]':5, 'districts[]':district_id }
        response = client.post('/districtmapping/plan/%d/districtmembers/' % self.plan.id, params)
        resp_obj = json.loads(response.content)
        self.assertTrue(resp_obj['success'], 'Member assign request for allowed legbody was denied: ' + str(response))
        self.assertEqual(1, resp_obj['modified'], '# districts modified was incorrect: %d' % resp_obj['modified'])

        # Verify the number of members and version number have been updated
        district10 = max(District.objects.filter(plan=self.plan,district_id=district10.district_id),key=lambda d: d.version)
        num = district10.num_members
        self.assertEqual(5, num, '# members is incorrect: %d' % num)
        num = district10.version
        self.assertEqual(3, num, 'version number is incorrect: %d' % num)

        # Verify number of members is added to the exported file
        plan = Plan.objects.get(pk=self.plan.id)
        archive = DistrictIndexFile.plan2index(plan)
        zin = zipfile.ZipFile(archive.name, "r")
        strz = zin.read(plan.name + ".csv")
        zin.close()
        os.remove(archive.name)
        self.assertTrue(strz.startswith('0000232,2,5'), 'Index file does not have num_members set: %s' % strz)

        # Verify range calculator accounts for member magnitude
        # First don't apply multi-member magnitude
        # Value of subject is 6, so we should be within the range
        rngcalc = Range()
        rngcalc.arg_dict['value'] = ('subject',self.subject1.name,)
        rngcalc.arg_dict['min'] = ('literal','5',)
        rngcalc.arg_dict['max'] = ('literal','7',)
        rngcalc.arg_dict['apply_num_members'] = ('literal','0',)
        rngcalc.compute(district=district10)
        actual = rngcalc.result
        expected = 1
        self.assertEqual(expected, actual, 'Incorrect value during range. (e:%s,a:%s)' % (expected, actual))
        
        # Now apply multi-member magnitude
        # There are 5 members, so the range would need to be 5x smaller
        rngcalc = Range()
        rngcalc.arg_dict['value'] = ('subject',self.subject1.name,)
        rngcalc.arg_dict['min'] = ('literal','1',)
        rngcalc.arg_dict['max'] = ('literal','2',)
        rngcalc.arg_dict['apply_num_members'] = ('literal','1',)
        rngcalc.compute(district=district10)
        actual = rngcalc.result
        expected = 1
        self.assertEqual(expected, actual, 'Incorrect value during range. (e:%s,a:%s)' % (expected, actual))

        # Remove district2 from the plan, since it seems to cause
        # problems with states between tests
        District.objects.filter(plan=plan, district_id=2).delete()
        
        # Verify equipopulation calculator accounts for member magnitude
        # First don't apply multi-member magnitude
        # Value of subjects are 9 and 6, so we should be within the range
        equipopcalc = Equipopulation()
        equipopcalc.arg_dict['value'] = ('subject',self.subject1.name,)
        equipopcalc.arg_dict['min'] = ('literal','5',)
        equipopcalc.arg_dict['max'] = ('literal','10',)
        equipopcalc.arg_dict['apply_num_members'] = ('literal','0',)
        equipopcalc.compute(plan=plan)
        actual = equipopcalc.result
        expected = True
        self.assertEqual(expected, actual, 'Incorrect value during range. (e:%s,a:%s)' % (expected, actual))

        # Now apply multi-member magnitude
        # There are 5 members in one of the districts, so the range would need to be 5x smaller for that one
        equipopcalc = Equipopulation()
        equipopcalc.arg_dict['value'] = ('subject',self.subject1.name,)
        equipopcalc.arg_dict['min'] = ('literal','1',)
        equipopcalc.arg_dict['max'] = ('literal','10',)
        equipopcalc.arg_dict['apply_num_members'] = ('literal','1',)
        equipopcalc.compute(plan=plan)
        actual = equipopcalc.result
        expected = True
        self.assertEqual(expected, actual, 'Incorrect value during range. (e:%s,a:%s)' % (expected, actual))
        
        # Verify equivalence calculator accounts for member magnitude
        # First don't apply multi-member magnitude
        # min is 6,  max is 9. diff should be 3
        equcalc = Equivalence()
        equcalc.arg_dict['value'] = ('subject',self.subject1.name,)
        equipopcalc.arg_dict['apply_num_members'] = ('literal','0',)
        equcalc.compute(plan=plan)
        actual = equcalc.result
        expected = 3.0
        self.assertEqual(expected, actual, 'Incorrect value during equivalence. (e:%f,a:%f)' % (expected, actual))
        
        # Now apply multi-member magnitude
        # min is 1.2 (6/5),  max is 9. diff should be 7.8
        equcalc = Equivalence()
        equcalc.arg_dict['value'] = ('subject',self.subject1.name,)
        equcalc.arg_dict['apply_num_members'] = ('literal','1',)
        equcalc.compute(plan=plan)
        actual = equcalc.result
        expected = 7.8
        self.assertAlmostEquals(expected, actual, 3, 'Incorrect value during equivalence. (e:%f,a:%f)' % (expected, actual))

        # Verify interval calculator accounts for member magnitude
        interval = Interval()
        interval.arg_dict['subject'] = ('subject', self.subject1.name)
        interval.arg_dict['apply_num_members'] = ('literal','0',)
        interval.arg_dict['target'] = ('literal', 6)
        interval.arg_dict['bound1'] = ('literal', .10)
        interval.arg_dict['bound2'] = ('literal', .20)

        # Value of 6 for district 1.  Should be in the middle (2)
        interval.compute(district=district10)
        self.assertEqual(2, interval.result, "Incorrect interval returned: e:%d,a:%d" % (2, interval.result))
        interval.compute(plan=plan)
        self.assertEqual(1, interval.result, "Incorrect interval returned: e:%d,a:%d" % (1, interval.result))

        # Now apply multi-member magnitude
        interval = Interval()
        interval.arg_dict['subject'] = ('subject', self.subject1.name)
        interval.arg_dict['apply_num_members'] = ('literal','1',)
        interval.arg_dict['target'] = ('literal', 1.2)
        interval.arg_dict['bound1'] = ('literal', .10)
        interval.arg_dict['bound2'] = ('literal', .20)

        # Value of 1.2 for district 1.  Should be in the middle (2)
        interval.compute(district=district10)
        self.assertEqual(2, interval.result, "Incorrect interval returned: e:%d,a:%d" % (2, interval.result))
        interval.compute(plan=plan)
        self.assertEqual(1, interval.result, "Incorrect interval returned: e:%d,a:%d" % (1, interval.result))

        # Perform MultiMember validation
        plan.legislative_body.min_multi_district_members = 3
        plan.legislative_body.max_multi_district_members = 6
        plan.legislative_body.min_multi_districts = 1
        plan.legislative_body.max_multi_districts = 2
        plan.legislative_body.min_plan_members = 6
        plan.legislative_body.max_plan_members = 8
        plan.legislative_body.save()
        
        multicalc = MultiMember()
        multicalc.compute(plan=plan)
        self.assertTrue(multicalc.result, "Multi-member district should have been valid")

        plan.legislative_body.min_multi_districts = 2
        plan.legislative_body.save()
        multicalc.compute(plan=plan)
        self.assertFalse(multicalc.result, "Should be not enough multi-member districts")
        
        plan.legislative_body.min_multi_districts = 1
        plan.legislative_body.min_plan_members = 7
        plan.legislative_body.save()
        multicalc.compute(plan=plan)
        self.assertFalse(multicalc.result, "Should be not enough plan members")
        
        plan.legislative_body.min_plan_members = 6
        plan.legislative_body.min_multi_district_members = 6
        plan.legislative_body.save()
        multicalc.compute(plan=plan)
        self.assertFalse(multicalc.result, "Should be not enough members per multi-member district")

class StatisticsSetTestCase(BaseTestCase):
    fixtures = ['redistricting_testdata.json',
                'redistricting_testdata_geolevel2.json',
                'redistricting_statisticssets.json',
                ]

    def setUp(self):
        BaseTestCase.setUp(self)

        display = ScoreDisplay.objects.get(title='Demographics')
        summary = ScorePanel.objects.get(title='Plan Summary')
        demographics = ScorePanel.objects.get(title='Demographics')
        
        display.scorepanel_set.add(summary)
        display.scorepanel_set.add(demographics)

        functions = ScoreFunction.objects.filter(label__in=('Black VAP', 'His. VAP', 'Tot Pop'))
        demographics.score_functions = functions.all()
        demographics.save()

        self.functions = functions.all()
        self.demographics = demographics
        self.summary = summary
        self.display = display
        

        
    def tearDown(self):
        self.display.delete()
        BaseTestCase.tearDown(self)
        
    def test_copy_scoredisplay(self):
        user = User(username="Stats User")
        user.save()
        # We'll set the owner but it's overwritten
        copy = ScoreDisplay(owner=user)
        copy = copy.copy_from(display=self.display)
        self.assertEqual("%s copy" % self.display.title, copy.title, 
            "ScoreDisplay title copied, allowing same name for user more than once")
        self.assertEqual(len(copy.scorepanel_set.all()), len(self.display.scorepanel_set.all()), 
            "Copied scoredisplay has wrong number of panels attached")
        self.assertNotEqual(user, copy.owner, "ScoreDisplay copied owner rather than copying owner from ScoreDisplay")

        copy = ScoreDisplay(owner=user)
        copy = copy.copy_from(display=self.display, owner=user)
        self.assertEqual(self.display.title, copy.title, "Title of scoredisplay not copied")
        self.assertEqual(len(copy.scorepanel_set.all()), len(self.display.scorepanel_set.all()), 
            "Copied scoredisplay has wrong number of panels attached")

        vap = ScoreFunction.objects.get(label="VAP")
        copy = copy.copy_from(display=self.display, functions=[unicode(str(vap.id))], title="Copied from")
        self.assertEqual(len(copy.scorepanel_set.all()), len(self.display.scorepanel_set.all()), 
            "Copied scoredisplay has wrong number of panels attached")

        
        new_demo = ScoreDisplay.objects.get(title="Copied from")
        panels_tested = 0
        for panel in new_demo.scorepanel_set.all():
            if panel.title == "Plan Summary":
                self.assertEqual(len(self.summary.score_functions.all()), len(panel.score_functions.all()), 
                    "Copied plan summary panel didn't have correct number of functions")
                panels_tested += 1
            elif panel.title == "Demographics":
                self.assertEqual(1, len(panel.score_functions.all()),
                    "Copied demographics panel didn't have correct number of functions")
                panels_tested += 1
        self.assertEqual(2, panels_tested, "Copied scoredisplay didn't have both panels needed")

        # Let's try just updating those score functions
        new_copy = ScoreDisplay(owner=user)
        new_copy = copy.copy_from(display=copy, functions = self.functions)
        self.assertEqual(copy.title, new_copy.title, "Title of scoredisplay not copied")
        self.assertEqual(copy.id, new_copy.id, "Scorefunctions not added to current display")
        self.assertEqual(len(copy.scorepanel_set.all()), len(new_copy.scorepanel_set.all()), 
            "Copied scoredisplay has wrong number of panels attached")

        panels_tested = 0
        for panel in new_copy.scorepanel_set.all():
            if panel.title == "Plan Summary":
                self.assertEqual(len(self.summary.score_functions.all()), len(panel.score_functions.all()), 
                    "Copied plan summary panel didn't have correct number of functions")
                panels_tested += 1
            elif panel.title == "Demographics":
                self.assertEqual(len(self.functions), len(panel.score_functions.all()),
                    "Copied demographics panel didn't have correct number of functions; e:%d,a:%d" % (3, len(panel.score_functions.all())))
                panels_tested += 1
        self.assertEqual(2, panels_tested, "Copied scoredisplay didn't have both panels needed")

class TaggingTestCase(BaseTestCase):
    fixtures = ['redistricting_testdata.json']

    def test_tagging1(self):
        # Set all tags at once
        self.district1.tags = 'type=Neighborhood'
        alltags = Tag.objects.all().count()
        self.assertEqual(1, alltags, 'Total number of tags is incorrect.')

        # Change all the tags
        self.district1.tags = "type='hood"
        alltags = Tag.objects.all().count()
        self.assertEqual(2, alltags, 'Total number of tags is incorrect.')

        # Even though there are two tags, only one is used by this model
        tags = Tag.objects.usage_for_model(self.district1)
        self.assertEqual(1, len(tags), 'Total number of used tags is incorrect.')

        # Append a tag to a model
        Tag.objects.add_tag(self.district1, 'type=Neighborhood')
        alltags = Tag.objects.all().count()
        self.assertEqual(2, alltags, 'Total number of tags is incorrect.')

        # Now the model is using both tags
        tags = Tag.objects.usage_for_model(self.district1)
        self.assertEqual(2, len(tags), 'Total number of used tags is incorrect.')

    def test_tagging2(self):
        # Add tags to property, which parses them out
        self.district1.tags = 'type=typeval name=nameval extra=extraval'
        alltags = Tag.objects.all().count()
        self.assertEqual(3, alltags, 'Total number of tags is incorrect.')

        # Three different tags parsed and assigned to the model
        tags = Tag.objects.usage_for_model(self.district1)
        self.assertEqual(3, len(tags), 'Total number of used tags is incorrect.')

        # Filter the types of tags off the object
        tset = Tag.objects.get_for_object(self.district1)
        types = tset.filter(name__startswith='type')
        names = tset.filter(name__startswith='name')
        extras = tset.filter(name__startswith='extra')

        # This object has one type of tag for each key
        self.assertEqual(1, types.count())
        self.assertEqual(1, names.count())
        self.assertEqual(1, extras.count())

    def test_tagging3(self):
        # Add tags separately
        Tag.objects.add_tag(self.district1, 'type=typeval')
        Tag.objects.add_tag(self.district1, 'name=nameval')
        Tag.objects.add_tag(self.district1, 'extra=extraval')

        # Three different tags parsed and assigned to the model
        alltags = Tag.objects.get_for_object(self.district1).count()
        self.assertEqual(3, alltags)

        # Filter the types of tags off the object
        tset = Tag.objects.get_for_object(self.district1)
        types = tset.filter(name__startswith='type')
        names = tset.filter(name__startswith='name')
        extras = tset.filter(name__startswith='extra')

        # This object has one type of tag for each key
        self.assertEqual(1, types.count())
        self.assertEqual(1, names.count())
        self.assertEqual(1, extras.count())

    def test_tagging4(self):
        self.district1.tags = 'type=t1 name=n1 extra=e1'
        self.district2.tags = 'type=t2 name=n2 extra=e2'

        # Get the tags of a specific type
        tags = Tag.objects.filter(name__startswith='type=')
        # Get the union, where any model in the District Qset matches
        # any tag in the list of tags
        intersection = TaggedItem.objects.get_union_by_model(District.objects.all(), tags)

        self.assertEqual(2, intersection.count(), 'Number of models with type= tags are not correct.')


class NestingTestCase(BaseTestCase):
    """
    Unit tests to test Legislative chamber nesting 
    """
    fixtures = ['redistricting_testdata.json', 'redistricting_testdata_geolevel2.json', 'redistricting_testdata_geolevel3.json']

    def setUp(self):
        BaseTestCase.setUp(self)        
        self.geolevel = Geolevel.objects.get(pk=2)
        self.geolevels = Geolevel.objects.all().order_by('id')

        self.geounits = {}
        for gl in self.geolevels:
           self.geounits[gl.id] = list(Geounit.objects.filter(geolevel=gl).order_by('id'))

        # Create 3 nested legislative bodies
        self.bottom = LegislativeBody(name="bottom", max_districts=100)
        self.bottom.save()
        self.middle = LegislativeBody(name="middle", max_districts=20)
        self.middle.save()
        self.top = LegislativeBody(name="top", max_districts=4)
        self.top.save()

        # Create references for plans and districts
        self.plan = Plan.objects.get(name='testPlan')
        self.plan2 = Plan.objects.get(name='testPlan2')
        self.p1d1 = District.objects.get(name='District 1', plan=self.plan)
        self.p1d2 = District.objects.get(name='District 2', plan=self.plan)
        self.p2d1 = District(name='District 1', district_id=1, version=0, plan=self.plan2)
        self.p2d1.save()
        self.p2d2 = District(name='District 2', district_id=2, version=0, plan=self.plan2)
        self.p2d2.save()

    def tearDown(self):
        self.geolevel = None
        self.geolevels = None
        self.geounits = None
        try:
            BaseTestCase.tearDown(self)
        except:
            import traceback
            print(traceback.format_exc())
            print('Couldn\'t tear down')

    def test_child_parent(self):
        # Try out each permutation of nested districts
        self.assertFalse(self.bottom.is_below(self.bottom), "Bottom was below Bottom")
        self.assertTrue(self.bottom.is_below(self.middle), "Bottom wasn't below Middle")
        self.assertTrue(self.bottom.is_below(self.top), "Bottom wasn't below Top")
        self.assertFalse(self.middle.is_below(self.bottom), "Middle was below Bottom")
        self.assertFalse(self.middle.is_below(self.middle), "Middle was below Middle")
        self.assertTrue(self.middle.is_below(self.top), "Middle wasn't below Top")
        self.assertFalse(self.top.is_below(self.bottom), "Top was below Bottom")
        self.assertFalse(self.top.is_below(self.middle), "Top was below Middle")
        self.assertFalse(self.top.is_below(self.top), "Top was below Top")

    def test_split_identical_districts(self):
        gl, gs = self.geolevel, list(Geounit.objects.filter(geolevel=self.geolevel).order_by("id"))
        p1, p1d1, p1d2 = self.plan, self.p1d1, self.p1d2
        p2, p2d1, p2d2 = self.plan2, self.p2d1, self.p2d2

        p1.add_geounits(p1d1.district_id, [str(x.id) for x in gs if x.id in [10, 11, 19, 20]], gl.id, p1.version)
        p1d1 = max(District.objects.filter(plan=p1,district_id=p1d1.district_id),key=lambda d: d.version)
        p1.add_geounits(p1d2.district_id, [str(x.id) for x in gs if x.id in [29, 30, 38, 39]], gl.id, p1.version)
        p1d2 = max(District.objects.filter(plan=p1,district_id=p1d2.district_id),key=lambda d: d.version)

        # Identical
        p2.add_geounits(p2d1.district_id, [str(x.id) for x in gs if x.id in [10, 11, 19, 20]], gl.id, p2.version)
        p2d1 = max(District.objects.filter(plan=p2,district_id=p2d1.district_id),key=lambda d: d.version)
        p2.add_geounits(p2d2.district_id, [str(x.id) for x in gs if x.id in [29, 30, 38, 39]], gl.id, p2.version)
        p2d2 = max(District.objects.filter(plan=p2,district_id=p2d2.district_id),key=lambda d: d.version)

        # Test splits
        splits = p1.find_plan_splits(p2)
        self.assertEqual(len(splits), 0, "Found splits in identical plans")

    def test_split_bottom_district_smaller(self):
        gl, gs = self.geolevel, list(Geounit.objects.filter(geolevel=self.geolevel).order_by("id"))
        p1, p1d1, p1d2 = self.plan, self.p1d1, self.p1d2
        p2, p2d1, p2d2 = self.plan2, self.p2d1, self.p2d2

        p1.add_geounits(p1d1.district_id, [str(x.id) for x in gs if x.id in [10, 11, 19, 20]], gl.id, p1.version)
        p1d1 = max(District.objects.filter(plan=p1,district_id=p1d1.district_id),key=lambda d: d.version)
        p1.add_geounits(p1d2.district_id, [str(x.id) for x in gs if x.id in [29, 30, 38, 39]], gl.id, p1.version)
        p1d2 = max(District.objects.filter(plan=p1,district_id=p1d2.district_id),key=lambda d: d.version)

        # 38, 39 not included in bottom plan
        p2.add_geounits(p2d1.district_id, [str(x.id) for x in gs if x.id in [10, 11, 19, 20]], gl.id, p2.version)
        p2d1 = max(District.objects.filter(plan=p2,district_id=p2d1.district_id),key=lambda d: d.version)
        p2.add_geounits(p2d2.district_id, [str(x.id) for x in gs if x.id in [29, 30]], gl.id, p2.version)
        p2d2 = max(District.objects.filter(plan=p2,district_id=p2d2.district_id),key=lambda d: d.version)

        # Test splits
        splits = p1.find_plan_splits(p2)
        self.assertEqual(len(splits), 0, "Found splits when bottom plan had a smaller district")

    def test_split_top_district_smaller(self):
        gl, gs = self.geolevel, list(Geounit.objects.filter(geolevel=self.geolevel).order_by("id"))
        p1, p1d1, p1d2 = self.plan, self.p1d1, self.p1d2
        p2, p2d1, p2d2 = self.plan2, self.p2d1, self.p2d2

        # 38, 39 not included in top plan
        p1.add_geounits(p1d1.district_id, [str(x.id) for x in gs if x.id in [10, 11, 19, 20]], gl.id, p1.version)
        p1d1 = max(District.objects.filter(plan=p1,district_id=p1d1.district_id),key=lambda d: d.version)
        p1.add_geounits(p1d2.district_id, [str(x.id) for x in gs if x.id in [29, 30]], gl.id, p1.version)
        p1d2 = max(District.objects.filter(plan=p1,district_id=p1d2.district_id),key=lambda d: d.version)

        p2.add_geounits(p2d1.district_id, [str(x.id) for x in gs if x.id in [10, 11, 19, 20]], gl.id, p2.version)
        p2d1 = max(District.objects.filter(plan=p2,district_id=p2d1.district_id),key=lambda d: d.version)
        p2.add_geounits(p2d2.district_id, [str(x.id) for x in gs if x.id in [29, 30, 38, 39]], gl.id, p2.version)
        p2d2 = max(District.objects.filter(plan=p2,district_id=p2d2.district_id),key=lambda d: d.version)

        # Test splits
        splits = p1.find_plan_splits(p2)
        self.assertEqual(len(splits), 1, "Didn't find 1 split")
        self.assertEqual(splits[0], (2, 2), "Didn't find p1d2 to split p2d2")

    def test_split_move_diagonally(self):
        gl, gs = self.geolevel, list(Geounit.objects.filter(geolevel=self.geolevel).order_by("id"))
        p1, p1d1, p1d2 = self.plan, self.p1d1, self.p1d2
        p2, p2d1, p2d2 = self.plan2, self.p2d1, self.p2d2

        # Offset plan one unit diagonally down-left
        p1.add_geounits(p1d1.district_id, [str(x.id) for x in gs if x.id in [0, 1, 9, 10]], gl.id, p1.version)
        p1d1 = max(District.objects.filter(plan=p1,district_id=p1d1.district_id),key=lambda d: d.version)
        p1.add_geounits(p1d2.district_id, [str(x.id) for x in gs if x.id in [19, 20, 28, 29]], gl.id, p1.version)
        p1d2 = max(District.objects.filter(plan=p1,district_id=p1d2.district_id),key=lambda d: d.version)
        
        p2.add_geounits(p2d1.district_id, [str(x.id) for x in gs if x.id in [10, 11, 19, 20]], gl.id, p2.version)
        p2d1 = max(District.objects.filter(plan=p2,district_id=p2d1.district_id),key=lambda d: d.version)
        p2.add_geounits(p2d2.district_id, [str(x.id) for x in gs if x.id in [29, 30, 38, 39]], gl.id, p2.version)
        p2d2 = max(District.objects.filter(plan=p2,district_id=p2d2.district_id),key=lambda d: d.version)

        # Test splits
        splits = p1.find_plan_splits(p2)
        self.assertEqual(len(splits), 3, "Didn't find 3 splits")
        self.assertEqual(splits[0], (1, 1), "Didn't find p1d1 to split p2d1")
        self.assertEqual(splits[1], (2, 1), "Didn't find p1d2 to split p2d1")
        self.assertEqual(splits[2], (2, 2), "Didn't find p1d2 to split p2d2")

class CommunityTypeTestCase(BaseTestCase):
    """
    Unit tests to test detection of Community types in a district:
    """
    fixtures = ['redistricting_testdata.json', 'redistricting_testdata_geolevel2.json']

    def setUp(self):
        BaseTestCase.setUp(self)        
        self.geolevel = Geolevel.objects.get(pk=2)
        self.geolevels = Geolevel.objects.all().order_by('id')
        self.legbod = LegislativeBody.objects.get(name='TestLegislativeBody')

        self.geounits = {}
        for gl in self.geolevels:
           self.geounits[gl.id] = list(Geounit.objects.filter(geolevel=gl).order_by('id'))

        # Create a standard district
        self.plan = Plan(name='political', owner=self.user, legislative_body=self.legbod)
        self.plan.save()

        # Create a community map with districts of varying types
        self.community = Plan(name='community', owner=self.user, legislative_body=self.legbod)
        self.community.save()

    def tearDown(self):
        self.geolevel = None
        self.geolevels = None
        self.legbod = None
        self.geounits = None
        self.plan.delete()
        self.community.delete()

        try:
            BaseTestCase.tearDown(self)
        except:
            import traceback
            print(traceback.format_exc())
            print('Couldn\'t tear down')

    def test_community_intersections(self):
        gl, gs = self.geolevel, list(Geounit.objects.filter(geolevel=self.geolevel).order_by("id"))
        p, c = self.plan, self.community

        # Create a basic district in the plan
        p.add_geounits(1, [str(x.id) for x in gs if x.id > 28 and x.id < 73 and x.id % 9 in [4, 5, 6]], gl.id, p.version)
        d1 = max(District.objects.filter(plan=p,district_id=1),key=lambda d: d.version)

        # Check and make sure we get 0 intersections
        intersections = d1.count_community_type_intersections(c.id)
        self.assertNotEquals(0, d1.geom.area, 'District 1 has no area')
        self.assertEqual(0, intersections, 'Detected community intersections when there are none a:%d' % intersections)

        # C1 intersects on the left, half-in and half-out of d1 
        c.add_geounits(1, ['57', '58'] , gl.id, c.version)
        c1 = max(District.objects.filter(plan=c,district_id=1),key=lambda d: d.version)
        c1.tags = 'type=type_a'
        intersections = d1.count_community_type_intersections(c.id)
        self.assertEqual(1, intersections, 'detected incorrect number of community intersections. e:1;a:%d' % intersections)

        # C2 is inside of d1 and shares a border
        c.add_geounits(2, ['42'], gl.id, c.version)
        c2 = max(District.objects.filter(plan=c,district_id=2),key=lambda d: d.version)
        c2.tags = 'type=type_b'
        intersections = d1.count_community_type_intersections(c.id)
        self.assertEqual(2, intersections, 'Detected incorrect number of community intersections. e:2;a:%d' % intersections)

        #C3 is outside of d1 and shares a border
        c.add_geounits(3, ['66'], gl.id, c.version)
        c3 = max(District.objects.filter(plan=c,district_id=3),key=lambda d: d.version)
        c3.tags = 'type=type_c'
        intersections = d1.count_community_type_intersections(c.id)
        self.assertEqual(2, intersections, 'Detected incorrect number of community intersections. e:2;a:%d' % intersections)

        # C4 is entirely within d1 and shares no borders
        c.add_geounits(4, ['59'], gl.id, c.version)
        c4 = max(District.objects.filter(plan=c,district_id=4),key=lambda d: d.version)
        intersections = d1.count_community_type_intersections(c.id)
        self.assertEqual(2, intersections, 'Detected incorrect number of community intersections. e:2;a:%d' % intersections)
        c4.tags = 'type=type_a type=type_b type=type_c'
        intersections = d1.count_community_type_intersections(c.id)
        self.assertEqual(3, intersections, 'Detected incorrect number of community intersections. e:3;a:%d' % intersections)

    def test_community_intersection_calculator(self):
        calc = CommunityTypeCounter()
        gl, gs = self.geolevel, list(Geounit.objects.filter(geolevel=self.geolevel).order_by("id"))
        p, c = self.plan, self.community

        # Create a basic district in the plan
        p.add_geounits(1, [str(x.id) for x in gs if x.id > 28 and x.id < 73 and x.id % 9 in [4, 5, 6]], gl.id, p.version)
        d1 = max(District.objects.filter(plan=p,district_id=1),key=lambda d: d.version)

        # Check and make sure we get 0 intersections
        calc.compute(district=d1, community_map_id=c.id, version=c.version)
        self.assertEqual(0, calc.result, 'Detected community intersections when there are none a:%s' % calc.result)

        # C1 intersects on the left, half-in and half-out of d1 
        c.add_geounits(1, ['57', '58'] , gl.id, c.version)
        c1 = max(District.objects.filter(plan=c,district_id=1),key=lambda d: d.version)
        c1.tags = 'type=type_a'
        calc.compute(district=d1, community_map_id=c.id, version=c.version)
        self.assertEqual(1, calc.result, 'detected incorrect number of community calc.result. e:1;a:%s' % calc.result)

        calc.compute(district=d1, community_map_id=-1, version=c.version)
        self.assertEqual('n/a', calc.result, 'Did\'t get "n/a" when incorrect map_id used. a:%s' % calc.result)
