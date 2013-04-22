"""
Define a set of tests for the redistricting app.

Test coverage is provided for the complex geographice queries and routines
in the redistricting app.

This file is part of The Public Mapping Project
https://github.com/PublicMapping/

License:
    Copyright 2010-2012 Micah Altman, Michael McDonald

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

import os, zipfile
from django.test import TestCase
from math import sin,cos
from django.contrib.gis.db.models import Union
from django.db.models import Sum, Min, Max
from django.test.client import Client
from django.contrib.gis.geos import *
from django.contrib.auth.models import User
from django.utils import simplejson as json
from lxml import etree
from models import *
from tasks import *
from calculators import *
from reportcalculators import *
from config import *
from django.conf import settings
from datetime import datetime
from tagging.models import Tag, TaggedItem
import tempfile

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

        for d in District.objects.all():
            d.simplify()

        # Get the test Districts
        self.district1 = District.objects.get(long_label='District 1', plan=self.plan)
        self.district2 = District.objects.get(long_label='District 2', plan=self.plan)

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
        geolevel = Geolevel.objects.get(name='middle level')
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
        self.assertAlmostEquals(0.86832150547, scores[0]['value'], 9, 'Schwartzberg for first district was incorrect: %f' % scores[0]['value'])
        self.assertAlmostEquals(0.88622692545, scores[1]['value'], 9, 'Schwartzberg for second district was incorrect: %f' % scores[1]['value'])

        # single district as list
        scores = schwartzFunction.score([self.district1])
        self.assertAlmostEquals(0.86832150547, scores[0]['value'], 9, 'Schwartzberg for District 1 was incorrect: %f' % scores[0]['value'])

        # single district as object
        score = schwartzFunction.score(self.district1)
        self.assertAlmostEquals(0.86832150547, score['value'], 9, 'Schwartzberg for District 1 was incorrect: %f' % score['value'])

        # HTML
        score = schwartzFunction.score(self.district1, 'html')
        self.assertEqual("86.83%", score, 'Schwartzberg HTML for District 1 was incorrect: ' + score)

        # JSON
        score = json.loads(schwartzFunction.score(self.district1, 'json'))
        self.assertAlmostEqual(0.8683215054699209, score['result'], 15, 'Schwartzberg JSON for District 1 was incorrect. (e:"%s", a:"%s")' % (0.8683215054699209,score['result'],))

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
        self.assertEqual(3, score['value'], 'sumThree was incorrect: %d' % score['value'])

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
        self.assertEqual(Decimal('11.2'), score['value'], 'sumMixed was incorrect: %d' % score['value'])

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
        num_districts = len(self.plan.get_districts_at_version(self.plan.version, include_geom=False))
        score = sumPlanFunction.score(self.plan)
        self.assertEqual(num_districts, score['value'], 'sumPlanFunction was incorrect. (e:%d, a:%d)' % (num_districts, score['value']))

        # test a list of plans
        score = sumPlanFunction.score([self.plan, self.plan])
        self.assertEqual(num_districts, score[0]['value'], 'sumPlanFunction was incorrect for first plan: %d' % score[0]['value'])
        self.assertEqual(num_districts, score[1]['value'], 'sumPlanFunction was incorrect for second plan: %d' % score[1]['value'])

    def testThresholdFunction(self):
        # create the scoring function for checking if a value passes a threshold
        thresholdFunction1 = ScoreFunction(calculator='redistricting.calculators.Threshold', name='ThresholdFn1')
        thresholdFunction1.save()

        # create the arguments
        ScoreArgument(function=thresholdFunction1, argument='value', value='1', type='literal').save()
        ScoreArgument(function=thresholdFunction1, argument='threshold', value='2', type='literal').save()

        # test raw value
        score = thresholdFunction1.score(self.district1)
        self.assertEqual(False, score['value'], '1 is not greater than 2')

        # create a new scoring function to test the inverse
        thresholdFunction2 = ScoreFunction(calculator='redistricting.calculators.Threshold', name='ThresholdFn2')
        thresholdFunction2.save()

        # create the arguments
        ScoreArgument(function=thresholdFunction2, argument='value', value='2', type='literal').save()
        ScoreArgument(function=thresholdFunction2, argument='threshold', value='1', type='literal').save()

        # test raw value
        score = thresholdFunction2.score(self.district1)
        self.assertEqual(1, score['value'], '2 is greater than 1')

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
        self.assertEqual(1, score['value'], '2 is between 1 and 3')

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
        self.assertEqual(14, score['value'], 'sumLiteralAndScoreFunction was incorrect: %d' % score['value'])

        # sum two of these nested sums
        sumTwoNestedSumsFunction = ScoreFunction(calculator='redistricting.calculators.SumValues', name='SumTwoNestedSumsFn')
        sumTwoNestedSumsFunction.save()
        ScoreArgument(function=sumTwoNestedSumsFunction, argument='value1', value=sumLiteralAndScoreFunction.name, type='score').save()        
        ScoreArgument(function=sumTwoNestedSumsFunction, argument='value2', value=sumLiteralAndScoreFunction.name, type='score').save()
        score = sumTwoNestedSumsFunction.score(self.district1)
        self.assertEqual(28, score['value'], 'sumTwoNestedSumsFunction was incorrect: %d' % score['value'])

        # test a list of districts
        score = sumTwoNestedSumsFunction.score([self.district1, self.district1])
        self.assertEqual(28, score[0]['value'], 'sumTwoNestedSumsFunction was incorrect for first district: %d' % score[0]['value'])
        self.assertEqual(28, score[1]['value'], 'sumTwoNestedSumsFunction was incorrect for second district: %d' % score[1]['value'])

    def testNestedSumPlanFunction(self):
        """
        Test the nested sum scoring function on a plan level
        """
        # create the scoring function for summing the districts in a plan
        sumPlanFunction = ScoreFunction(calculator='redistricting.calculators.SumValues', name='SumPlanFn', is_planscore=True)
        sumPlanFunction.save()
        ScoreArgument(function=sumPlanFunction, argument='value1', value='1', type='literal').save()

        # find the number of districts in the plan in an alternate fashion
        num_districts = len(self.plan.get_districts_at_version(self.plan.version, include_geom=False))

        # ensure the sumPlanFunction works correctly
        score = sumPlanFunction.score(self.plan)
        self.assertEqual(num_districts, score['value'], 'sumPlanFunction was incorrect. (e:%d, a:%d)' % (num_districts, score['value'],))

        # create the scoring function for summing the sum of the districts in a plan
        sumSumPlanFunction = ScoreFunction(calculator='redistricting.calculators.SumValues', name='SumSumPlanFn', is_planscore=True)
        sumSumPlanFunction.save()
        ScoreArgument(function=sumSumPlanFunction, argument='value1', value=sumPlanFunction.name, type='score').save()

        # test nested sum
        score = sumSumPlanFunction.score(self.plan)
        self.assertEqual(num_districts ** 2, score['value'], 'sumSumPlanFunction was incorrect: %d' % score['value'])

        # test a list of plans
        score = sumSumPlanFunction.score([self.plan, self.plan])
        self.assertEqual(num_districts ** 2, score[0]['value'], 'sumSumPlanFunction was incorrect for first plan: %d' % score[0]['value'])
        self.assertEqual(num_districts ** 2, score[1]['value'], 'sumSumPlanFunction was incorrect for second plan: %d' % score[1]['value'])

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
        self.assertEqual(9, score['value'], 'planSumFunction was incorrect: (e:9, a:%d)' % score['value'])

        # test a list of plans
        score = planSumFunction.score([self.plan, self.plan])
        self.assertEqual(9, score[0]['value'], 'planSumFunction was incorrect for first plan: %d' % score[0]['value'])
        self.assertEqual(9, score[1]['value'], 'planSumFunction was incorrect for second plan: %d' % score[1]['value'])

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
        self.assertEqual(18, score['value'], 'planSumFunction was incorrect: %d' % score['value'])

        # test with adding another argument to the plan function, should double again
        ScoreArgument(function=planSumFunction2, value=districtSubjectFunction2.name, type='score').save()
        score = planSumFunction2.score(self.plan)
        self.assertEqual(36, score['value'], 'planSumFunction was incorrect: %d' % score['value'])
        

class PlanTestCase(BaseTestCase):
    """
    Unit tests to test Plan operations
    """

    fixtures = ['redistricting_testdata.json', 'redistricting_testdata_geolevel2.json', 'redistricting_testdata_geolevel3.json']

    def setUp(self):
        BaseTestCase.setUp(self)        
        self.geolevel = Geolevel.objects.get(name='middle level')
        self.geolevels = Geolevel.objects.all().order_by('-id')

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
        d3 = District(long_label='District 3', version=0)
        d3.plan = self.plan

        p1 = Polygon( ((1, 1), (1, 1), (1, 1), (1, 1)) )
        mp1 = MultiPolygon(p1)
        d3.geom = mp1

        d3.simplify()
        latest = d3.district_id

        d4 = District(long_label = 'District 4', version=0)
        d4.plan = self.plan

        p2 = Polygon( ((0, 0), (0, 1), (1, 1), (0, 0)) )
        mp2 = MultiPolygon(p1)
        d4.geom = mp2

        d4.simplify()
        incremented = d4.district_id
        self.assertEqual(latest + 1, incremented, 'New district did not have an id greater than the previous district. (e:%d, a:%d)' % (latest+1,incremented))
        
    def test_add_to_plan(self):
        """
        Test the logic for adding geounits to a district.
        """
        district = self.district1
        districtid = district.district_id

        geounitids = [str(self.geounits[self.geolevel.id][0].id)]

        self.plan.add_geounits(districtid, geounitids, self.geolevel.id, self.plan.version)
        district = District.objects.get(plan=self.plan, district_id=districtid, version=1)

        self.assertEqual(district.geom.area, self.geounits[self.geolevel.id][0].geom.area, "Geometry area for added district doesn't match")
        self.assertEqual(district.geom.extent, self.geounits[self.geolevel.id][0].geom.extent, "Geometry area for added district doesn't match")
        self.assertEqual(district.geom.length, self.geounits[self.geolevel.id][0].geom.length, "Geometry area for added district doesn't match")

    def test_unassigned(self):
        """
        Test the logic for an unassigned district.
        """
        unassigned = District.objects.filter(long_label='Unassigned', plan = self.plan)
        self.assertEqual(1, unassigned.count(), 'No Unassigned district on plan. (e:1, a:%d)' % unassigned.count())

    def test_copyplan(self):
        """
        Test the logic for copying plans.
        """
        geounitids = [str(self.geounits[self.geolevel.id][0].id)]

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
        copyplan = Plan.objects.get(name=copyname)
        self.assertNotEqual(copyplan, None, 'Copied plan doesn\'t exist')

        # Ensure districts are the same between plans
        numdistricts = len(self.plan.get_districts_at_version(self.plan.version))
        numdistrictscopy = len(copyplan.get_districts_at_version(copyplan.version))
        self.assertEqual(numdistricts, numdistrictscopy, 'Districts between original and copy are different. (e:%d, a:%d)' % (numdistricts, numdistrictscopy))

        # Ensure geounits are the same between plans
        numunits = len(Plan.objects.get(pk=self.plan.id).get_base_geounits(0.1))
        numunitscopy = len(Plan.objects.get(pk=copyplan.id).get_base_geounits(0.1))
        self.assertEqual(numunits, numunitscopy, 'Geounits between original and copy are different')
        
    def test_district_locking(self):
        """
        Test the logic for locking/unlocking a district.
        """
        geounitids1 = [str(self.geounits[self.geolevel.id][0].id)]
        geounitids2 = [str(self.geounits[self.geolevel.id][-1].id)]

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

        self.plan.add_geounits(self.district1.district_id, geounitids1, self.geolevel.id, self.plan.version)
        self.district1 = max(District.objects.filter(plan=self.plan,district_id=self.district1.district_id),key=lambda d: d.version)
        
        # Issue lock command
        response = client.post('/districtmapping/plan/%d/district/%d/lock/' % (self.plan.id, self.district1.district_id), { 'lock':True, 'version':self.plan.version })
        self.assertEqual(200, response.status_code, 'Lock handler didn\'t return 200:' + str(response))

        # Ensure lock exists
        self.district1 = District.objects.get(pk=self.district1.id)
        self.assertTrue(self.district1.is_locked, 'District wasn\'t locked.' + str(response))

        prelock_numunits = len(self.district1.get_base_geounits(0.1))

        # Try adding geounits to the locked district (not allowed)
        self.plan.add_geounits(self.district2.district_id, geounitids1, self.geolevel.id, self.plan.version)
        self.assertRaises(District.DoesNotExist, District.objects.get, pk=self.district2.id, version=self.plan.version)

        self.district1 = max(District.objects.filter(plan=self.plan,district_id=self.district1.district_id),key=lambda d: d.version)
        numunits = len(self.district1.get_base_geounits(0.1))
        self.assertEqual(prelock_numunits, numunits, 'Geounits were added to a locked district. (e:%d, a:%d)' % (prelock_numunits, numunits,))
        
        # Issue unlock command
        response = client.post('/districtmapping/plan/%d/district/%d/lock/' % (self.plan.id, self.district1.district_id), { 'lock':False, 'version':self.plan.version })
        self.assertEqual(200, response.status_code, 'Lock handler didn\'t return 200:' + str(response))

        # Ensure lock has been removed
        self.district1 = max(District.objects.filter(plan=self.plan,district_id=self.district1.district_id),key=lambda d: d.version)
        self.assertFalse(self.district1.is_locked, 'District wasn\'t unlocked.' + str(response))

        # Add geounits to the plan
        old_geom = self.district1.geom
        self.plan.add_geounits(self.district1.district_id, geounitids2, self.geolevel.id, self.plan.version)
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

        geolevel = Geolevel.objects.get(name='biggest level')
        geounits = list(Geounit.objects.filter(geolevel=geolevel).order_by('id'))
        dist3ids = geounits[1:3] + geounits[4:6] + geounits[7:9]

        dist3ids = map(lambda x: str(x.id), dist3ids)

        self.plan.add_geounits(self.district2.district_id + 1, dist3ids, geolevel.id, self.plan.version)

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
        district.long_label = 'My Test Community'
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

    def test_reaggregation(self):
        """
        Test plan reaggregation
        """
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]
        subject = Subject.objects.get(name='TestSubject')        

        # Populate district 1
        dist1ids = geounits[0:3] + geounits[9:12] + geounits[18:21]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits(self.district1.district_id, dist1ids, geolevelid, self.plan.version)

        # Populate district 2
        dist2ids = geounits[10:13] + geounits[19:22] + geounits[28:31]
        dist2ids = map(lambda x: str(x.id), dist2ids)
        self.plan.add_geounits(self.district2.district_id, dist2ids, geolevelid, self.plan.version)

        # Helper for getting the value of a computed characteristic
        def get_cc_val(district):
            d_id = district.district_id
            district = max(District.objects.filter(plan=self.plan,district_id=d_id),key=lambda d: d.version)
            return ComputedCharacteristic.objects.get(district=district,subject=subject).number

        # Ensure starting values are correct
        self.assertEqual(3, get_cc_val(self.district1), "District1 started with wrong value")
        self.assertEqual(18, get_cc_val(self.district2), "District2 started with wrong value")

        # Modify characteristic values, and ensure the values don't change
        c = Characteristic.objects.get(geounit=geounits[0],subject=subject)
        c.number += 100
        c.save()
        d_id = self.district1.district_id
        self.district1 = max(District.objects.filter(plan=self.plan,district_id=d_id),key=lambda d: d.version)
        self.assertEqual(3, get_cc_val(self.district1), "District1 value changed unexpectedly")

        c = Characteristic.objects.get(geounit=geounits[10],subject=subject)
        c.number += 100
        c.save()
        d_id = self.district2.district_id
        self.district2 = max(District.objects.filter(plan=self.plan,district_id=d_id),key=lambda d: d.version)
        self.assertEqual(18, get_cc_val(self.district2), "District2 value changed unexpectedly")

        # Reaggregate each district, and ensure the values have been updated
        self.district1.reaggregate()
        self.assertEqual(103, get_cc_val(self.district1), "District1 not aggregated properly")

        self.district2.reaggregate()
        self.assertEqual(118, get_cc_val(self.district2), "District2 not aggregated properly")

        # Change the values back to what they were
        c = Characteristic.objects.get(geounit=geounits[0],subject=subject)
        c.number -= 100
        c.save()
        d_id = self.district1.district_id
        self.district1 = max(District.objects.filter(plan=self.plan,district_id=d_id),key=lambda d: d.version)

        c = Characteristic.objects.get(geounit=geounits[10],subject=subject)
        c.number -= 100
        c.save()
        d_id = self.district2.district_id
        self.district2 = max(District.objects.filter(plan=self.plan,district_id=d_id),key=lambda d: d.version)

        # Reaggregate entire plan, and ensure the values have been updated
        updated = self.plan.reaggregate()
        self.assertEqual(3, get_cc_val(self.district1), "Plan not aggregated properly for District1")
        self.assertEqual(18, get_cc_val(self.district2), "Plan not aggregated properly for District2")
        self.assertEqual(8, updated, "Incorrect number of districts updated")

        # Change the values back to what they were
        c = Characteristic.objects.get(geounit=geounits[0],subject=subject)
        c.number += 100
        c.save()
        d_id = self.district1.district_id
        self.district1 = max(District.objects.filter(plan=self.plan,district_id=d_id),key=lambda d: d.version)

        c = Characteristic.objects.get(geounit=geounits[10],subject=subject)
        c.number += 100
        c.save()
        d_id = self.district2.district_id
        self.district2 = max(District.objects.filter(plan=self.plan,district_id=d_id),key=lambda d: d.version)

        # Reaggregate only the first district, and ensure only the one value has been updated
        self.district1.reaggregate()
        self.assertEqual(103, get_cc_val(self.district1), "District1 not aggregated properly")
        self.assertEqual(18, get_cc_val(self.district2), "District2 aggregated when it shouldn't have been")
        
    def test_paste_districts(self):
        # Set up the test using geounits in the 2nd level
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]
        dist1ids = geounits[0:3] + geounits[9:12] + geounits[18:21]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits(self.district1.district_id, dist1ids, geolevelid, self.plan.version)

        district1 = max(District.objects.filter(plan=self.plan,district_id=self.district1.district_id),key=lambda d: d.version)
        target = Plan.create_default('Paste Plan 1', self.plan.legislative_body, owner=self.user, template=False, processing_state=ProcessingState.READY)
        target.save();

        # Paste the district and check returned number, geometry and stats
        result = target.paste_districts((district1,))
        self.assertEqual(1, len(result), "District1 wasn't pasted into the plan")
        target1 = District.objects.get(pk=result[0])
        self.assertTrue(target1.geom.equals(district1.geom), "Geometries of pasted district doesn't match original")
        # Without any language (.po) message strings, the members generated default to 'District %s'
        self.assertEqual(target1.long_label, "District 1", "Proper name wasn't assigned to pasted district. (e:'District 1', a:'%s')" % target1.long_label)

        target_stats =  ComputedCharacteristic.objects.filter(district = result[0])
        for stat in target_stats:
           district1_stat = ComputedCharacteristic.objects.get(district=district1, subject=stat.subject)
           self.assertEqual(stat.number, district1_stat.number, "Stats for pasted district (number) don't match")
           self.assertEqual(stat.percentage, district1_stat.percentage, "Stats for pasted district (percentage) don't match")

        # Add district 2 to a new plan so it doesn't overlap district 1
        new_for_2 = Plan.create_default('Paste Plan 2', self.plan.legislative_body, self.user, template=False, processing_state=ProcessingState.READY)
        dist2ids = geounits[10:13] + geounits[19:22] + geounits[28:31]
        dist2ids = map(lambda x: str(x.id), dist2ids)
        new_for_2.add_geounits(self.district2.district_id, dist2ids, geolevelid, self.plan.version)
        district2 = max(District.objects.filter(plan=new_for_2,district_id=self.district2.district_id),key=lambda d: d.version)

        # Paste district 2 into our target plan
        result = target.paste_districts((district2,))
        self.assertEqual(1, len(result), "District2 wasn't pasted into the plan")
        target2 = District.objects.get(pk=result[0])
        self.assertTrue(target2.geom.equals(district2.geom), "Geometries of pasted district doesn't match original\n")
        self.assertEqual(target2.long_label, "District 2", "Proper name wasn't assigned to pasted district")
        
        target2_stats =  ComputedCharacteristic.objects.filter(district=target2)
        for stat in target2_stats:
            # Check on District 2 stats
            district2_stat = ComputedCharacteristic.objects.get(district=district2, subject=stat.subject)

            self.assertEqual(stat.number, district2_stat.number, "Stats for pasted district (number) don't match")
            self.assertEqual(stat.percentage, district2_stat.percentage, "Stats for pasted district (percentage) don't match")
            
        # Calculate what district 1 should look like
        unassigned = max(District.objects.filter(plan=self.plan,long_label="Unassigned"),key=lambda d: d.version)
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
        # Set up the test using geounits in the 2nd level
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]
        dist1ids = geounits[0:3] + geounits[9:12] + geounits[18:21]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits(self.district1.district_id, dist1ids, geolevelid, self.plan.version)

        district1 = max(District.objects.filter(plan=self.plan,district_id=self.district1.district_id),key=lambda d: d.version)
        target = Plan.create_default('Paste Plan 1', self.plan.legislative_body, owner=self.user, template=False, processing_state=ProcessingState.READY)
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
        unassigned = max(District.objects.filter(plan=self.plan,long_label="Unassigned"),key=lambda d: d.version)
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

        self.district3 = District(plan=self.plan, long_label="TestMember 3", district_id = 3)
        self.district3.simplify()
        dist3ids = geounits[20:23] + geounits[29:32] + geounits[38:41]
        dist3ids = map(lambda x: str(x.id), dist3ids)
        self.plan.add_geounits(self.district3.district_id, dist3ids, geolevelid, self.plan.version)

        self.district1 = max(District.objects.filter(plan=self.plan,district_id=self.district1.district_id),key=lambda d: d.version)
        self.district3 = max(District.objects.filter(plan=self.plan,district_id=self.district3.district_id),key=lambda d: d.version)

        target = Plan.create_default('Paste Plan', self.plan.legislative_body, owner=self.user, template=False, processing_state=ProcessingState.READY)
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
        unassigned = District.objects.filter(plan=self.plan, long_label="Unassigned").order_by('-version')[0]
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
        all_3 = filter(lambda x : x.long_label != "Unassigned", all_4)
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
        leg_body.max_districts = 1
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
        self.assertEqual(729, num, ("District 1 doesn't contain all of the geounits", num, result))

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
        self.assertEqual(729 - 63, num, ("District 1 has the wrong number of the geounits", num, result))

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
        self.assertEqual(729 - 27, num, ("District 1 has the wrong number of the geounits", num, result))

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
        self.assertEqual(729 - 18 - 36, num, ("District 1 has the wrong number of the geounits", num, result))

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
        self.assertEqual(729 - 18 - 36 + 22, num, ("District 1 has the wrong number of the geounits", num, result))
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
        self.assertEqual(729 - 18 - 36 + 22 + 5, num, ("District 1 has the wrong number of the geounits", num, result))

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
        self.assertEqual(729 - 18 - 36 + 22 + 10, num, ("District 1 has the wrong number of the geounits", num, result))


class GeounitMixTestCase(BaseTestCase):
    """
    Unit tests to test the mixed geounit spatial queries.
    """
    
    def setUp(self):
        BaseTestCase.setUp(self)
        self.geolevels = Geolevel.objects.all().order_by('-id')
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

        units = Geounit.objects.filter(geom__within=units[0].geom,geolevel__lt=level.id)

        numunits = len(units)
        self.assertEqual(90, numunits, 'Number of geounits within a high-level geounit is incorrect. (%d)' % numunits)

    def test_get_in_gu0(self):
        """
        Test the spatial query to get geounits within a known boundary.
        """
        level = self.plan.legislative_body.get_geolevels()[0]
        units = self.geounits[level.id]

        units = Geounit.objects.filter(geom__within=units[0].geom,geolevel=level.id-1)
        numunits = len(units)
        self.assertEqual(9, numunits, 'Number of geounits within geounit 1 is incorrect. (%d)' % numunits)

    def test_get_base(self):
        """
        Test the spatial query to get all geounits at the base geolevel within a boundary.
        """
        level = self.plan.legislative_body.get_geolevels()[0]
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
        level = self.plan.legislative_body.get_geolevels()[0]
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
        self.assertEqual(3, numunits, 'Number of geounits outside boundary is incorrect. (%d)' % numunits)

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
        self.geolevel = Geolevel.objects.get(name='middle level')
        self.geounits = list(Geounit.objects.filter(geolevel=self.geolevel).order_by('id'))

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
       
            self.plan.add_geounits( (i+1), geounits, self.geolevel.id, self.plan.version)

    def tearDown(self):
        self.geounits = None
        self.geolevel = None
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
        self.geolevel = Geolevel.objects.get(name='middle level')
        self.geounits = list(self.geolevel.geounit_set.all().order_by('id'))
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
        self.assertEqual(30,sum1.result['value'])

        sum2 = SumValues()

        self.assertEqual(None,sum2.result)
        self.assertEqual(30,sum1.result['value'])

        sum2.compute(district=self.district1)

        self.assertEqual(0,sum2.result['value'])
        self.assertEqual(30,sum1.result['value'])
        
    def test_sum2a(self):
        sumcalc = SumValues()
        sumcalc.arg_dict['value1'] = ('literal','0',)
        sumcalc.arg_dict['value2'] = ('literal','1',)
        sumcalc.arg_dict['value3'] = ('literal','2',)
        sumcalc.compute(plan=self.plan)

        self.assertEqual(3, sumcalc.result['value'], 'Incorrect value during summation. (e:%d,a:%d)' % (3, sumcalc.result['value']))

    def test_sum2b(self):
        sumcalc = SumValues()
        sumcalc.arg_dict['value1'] = ('literal','0',)
        sumcalc.arg_dict['value2'] = ('literal','1',)
        sumcalc.arg_dict['value3'] = ('literal','2',)
        sumcalc.compute(district=self.district1)

        self.assertEqual(3, sumcalc.result['value'], 'Incorrect value during summation. (e:%d,a:%d)' % (3, sumcalc.result['value']))

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

        actual = float(sumcalc.result['value'])
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

        actual = float(sumcalc.result['value'])
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

        # Unassigned district has a value of -6, take that into account.
        actual = float(sumcalc.result['value']) + 6
        self.assertAlmostEquals(expected, actual, 8, 'Incorrect value during summation. (e:%d,a:%d)' % (expected, actual))


    def test_sum_negative_subject(self):
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        exqset = Characteristic.objects.filter(geounit__in=dist1ids,subject=self.subject1)
        expected = 5.0 - float(exqset.aggregate(Sum('number'))['number__sum'])

        dist1ids = map(lambda x: str(x.id), dist1ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)

        sumcalc = SumValues()
        sumcalc.arg_dict['value1'] = ('subject','-' + self.subject1.name,)
        sumcalc.arg_dict['value2'] = ('literal','5.0',)
        sumcalc.compute(district=district1)

        actual = float(sumcalc.result['value'])
        self.assertEqual(expected, actual, 'Incorrect value during summation. (e:%s-%d,a:%s-%d)' % (type(expected), expected, type(actual), actual))

    def test_sum_negative_subject2(self):
        dist1ids = self.geounits[0:3] + self.geounits[9:12]

        dist1ids = map(lambda x: str(x.id), dist1ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)

        sumcalc = SumValues()
        sumcalc.arg_dict['value1'] = ('subject','-' + self.subject1.name,)
        sumcalc.arg_dict['value2'] = ('subject', self.subject1.name)
        sumcalc.compute(district=district1)

        expected = 0
        actual = float(sumcalc.result['value'])
        self.assertEqual(expected, actual, 'Incorrect value during summation. (e:%s-%d,a:%s-%d)' % (type(expected), expected, type(actual), actual))

    def test_percent1(self):
        pctcalc = Percent()
        pctcalc.arg_dict['numerator'] = ('literal','1',)
        pctcalc.arg_dict['denominator'] = ('literal','2',)
        pctcalc.compute(district=self.district1)

        actual = float(pctcalc.result['value'])
        self.assertAlmostEquals(0.5, actual, 8, 'Incorrect value during percentage. (e:%d,a:%d)' % (0.5, actual,))

    def test_percent2(self):
        pctcalc = Percent()
        pctcalc.arg_dict['numerator'] = ('literal','2',)
        pctcalc.arg_dict['denominator'] = ('literal','4',)
        pctcalc.compute(district=self.district1)

        actual = float(pctcalc.result['value'])
        self.assertAlmostEquals(0.5, actual, 8, 'Incorrect value during percentage. (e:%d,a:%d)' % (0.5, actual,))

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

        actual = float(pctcalc.result['value'])
        self.assertAlmostEquals(expected, actual, 8, 'Incorrect value during percentage. (e:%f,a:%f)' % (expected, actual))

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

        actual = float(pctcalc.result['value'])
        self.assertAlmostEquals(expected, actual, 8, 'Incorrect value during percentage. (e:%f,a:%f)' % (expected, actual))

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

        actual = float(pctcalc.result['value'])
        self.assertAlmostEquals(1.0, actual, 8, 'Incorrect value during percentage. (e:%f,a:%f)' % (1.0, actual))


    def test_threshold1(self):
        thrcalc = Threshold()
        thrcalc.arg_dict['value'] = ('literal','1',)
        thrcalc.arg_dict['threshold'] = ('literal','2',)
        thrcalc.compute(district=self.district1)

        self.assertEqual(0, thrcalc.result['value'], 'Incorrect value during threshold. (e:%s,a:%s)' % (0, thrcalc.result['value']))

    def test_threshold2(self):
        thrcalc = Threshold()
        thrcalc.arg_dict['value'] = ('literal','2',)
        thrcalc.arg_dict['threshold'] = ('literal','1',)
        thrcalc.compute(district=self.district1)

        self.assertEqual(1, thrcalc.result['value'], 'Incorrect value during threshold. (e:%s,a:%s)' % (1, thrcalc.result['value']))

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

        actual = thrcalc.result['value']
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

        actual = thrcalc.result['value']
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

        actual = thrcalc.result['value']
        self.assertEqual(0, actual, 'Incorrect value during threshold. (e:%d,a:%d)' % (0, actual))

        thrcalc.arg_dict['threshold'] = ('literal','7.0',)
        thrcalc.compute(plan=self.plan)

        actual = thrcalc.result['value']
        self.assertEqual(1, actual, 'Incorrect value during threshold. (e:%d,a:%d)' % (1, actual))

        thrcalc.arg_dict['threshold'] = ('literal','5.0',)
        thrcalc.compute(plan=self.plan)

        actual = thrcalc.result['value']
        self.assertEqual(2, actual, 'Incorrect value during threshold. (e:%d,a:%d)' % (2, actual))


    def test_range1(self):
        rngcalc = Range()
        rngcalc.arg_dict['value'] = ('literal','2',)
        rngcalc.arg_dict['min'] = ('literal','1',)
        rngcalc.arg_dict['max'] = ('literal','3',)
        rngcalc.compute(district=self.district1)

        self.assertEqual(1, rngcalc.result['value'], 'Incorrect value during range. (e:%s,a:%s)' % (1, rngcalc.result['value']))

    def test_range2(self):
        rngcalc = Range()
        rngcalc.arg_dict['value'] = ('literal','1',)
        rngcalc.arg_dict['min'] = ('literal','2',)
        rngcalc.arg_dict['max'] = ('literal','3',)
        rngcalc.compute(district=self.district1)

        self.assertEqual(0, rngcalc.result['value'], 'Incorrect value during range. (e:%s,a:%s)' % (0, rngcalc.result['value']))

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

        actual = rngcalc.result['value']
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

        actual = rngcalc.result['value']
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

        actual = rngcalc.result['value']
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
        self.assertAlmostEquals(0.86832150547, calc.result['value'], 9, 'Schwartzberg for District 1 was incorrect: %d' % calc.result['value'])

        calc.compute(district=district2)
        self.assertAlmostEquals(0.88622692545, calc.result['value'], 9, 'Schwartzberg for District 2 was incorrect: %d' % calc.result['value'])

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
        self.assertAlmostEquals(0.87727421546, calc.result['value'], 9, 'Schwartzberg for District 1 was incorrect: %f' % calc.result['value'])

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
        self.assertAlmostEquals(expected, calc.result['value'], 6, 'Roeck for District 1 was incorrect. (e:%0.6f,a:%0.6f)' % (expected, calc.result['value']))

        calc.compute(district=district2)
        expected = 0.636620
        self.assertAlmostEquals(expected, calc.result['value'], 6, 'Roeck for District 2 was incorrect. (e:%0.6f,a:%0.6f)' % (expected, calc.result['value']))

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
        self.assertAlmostEquals(expected, calc.result['value'], 6, 'Roeck for plan was incorrect. (e:%0.6f,a:%0.6f)' % (expected, calc.result['value']))

    def test_roeck2(self):
        """
        Test the Roeck measure with a half-circle.
        """
        dist = 30
        coords = []
        for i in range(-dist,dist+1):
            coords.append( Point(cos(pi*i/dist/2.0), sin(pi*i/dist/2.0)) )

        pcoords = copy(coords)
        pcoords.append(pcoords[0])

        calc = Roeck()
        disk = calc.minidisk(coords)

        poly = Polygon(pcoords)

        parea = poly.area
        darea = pi * disk.r * disk.r

        # Testing to 3 decimal places, since this is an approximation of 
        # the circle's area -- actual ratio is 0.50014
        self.assertAlmostEquals( 0.5, parea / darea, 3, 'Roeck half-circle district was incorrect. (e:%0.6f,a:%0.6f)' % (0.5, parea / darea) )

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
        self.assertAlmostEquals(expected, calc.result['value'], 6, 'Polsby-Popper for District 1 was incorrect. (e:%0.6f,a:%0.6f)' % (expected, calc.result['value']))

        calc.compute(district=district2)
        expected = 0.785398
        self.assertAlmostEquals(expected, calc.result['value'], 6, 'Polsby-Popper for District 2 was incorrect. (e:%0.6f,a:%0.6f)' % (expected, calc.result['value']))

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
        self.assertAlmostEquals(expected, calc.result['value'], 6, 'Polsby-Popper for plan was incorrect. (e:%0.6f,a:%0.6f)' % (expected, calc.result['value']))

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
        self.assertAlmostEquals(expected, calc.result['value'], 6, 'Length/Width for District 1 was incorrect. (e:%0.6f,a:%0.6f)' % (expected, calc.result['value']))

        calc.compute(district=district2)
        expected = 1.000000
        self.assertAlmostEquals(expected, calc.result['value'], 6, 'Length/Width for District 2 was incorrect. (e:%0.6f,a:%0.6f)' % (expected, calc.result['value']))

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
        self.assertAlmostEquals(expected, calc.result['value'], 6, 'Length/Width for plan was incorrect. (e:%0.6f,a:%0.6f)' % (expected, calc.result['value']))

    def test_contiguity1(self):
        cntcalc = Contiguity()
        cntcalc.compute(district=self.district1)

        self.assertEqual(1, cntcalc.result['value'], 'District is not contiguous.')

    def test_contiguity2(self):
        dist1ids = self.geounits[0:3] + self.geounits[12:15]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)

        cntcalc = Contiguity()
        cntcalc.compute(district=district1)

        self.assertEqual(0, cntcalc.result['value'], 'District is contiguous.')

    def test_contiguity3(self):
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)

        cntcalc = Contiguity()
        cntcalc.compute(district=district1)

        self.assertEqual(1, cntcalc.result['value'], 'District is discontiguous.')

    def test_contiguity_singlepoint(self):
        dist1ids = [self.geounits[0], self.geounits[10]]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)

        # 2 geounits connected by one point -- single-point is false, should fail
        cntcalc = Contiguity()
        cntcalc.arg_dict['allow_single_point'] = ('literal','0',)
        cntcalc.compute(district=district1)
        self.assertEqual(0, cntcalc.result['value'], 'District is contiguous at 1 point, but single-point contiguity is false.')

        # 2 geounits connected by one point -- single-point is true, should pass
        cntcalc = Contiguity()
        cntcalc.arg_dict['allow_single_point'] = ('literal','1',)
        cntcalc.compute(district=district1)
        self.assertEqual(1, cntcalc.result['value'], 'District is contiguous at 1 point, and single-point contiguity is true.')

        # add another geounits so 3 geometries are connected by 2 single points (contiguous)
        dist1ids = [self.geounits[18]]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)

        cntcalc = Contiguity()
        cntcalc.arg_dict['allow_single_point'] = ('literal','1',)
        cntcalc.compute(district=district1)
        self.assertEqual(1, cntcalc.result['value'], 'District is contiguous at 1 point twice, and single-point contiguity is true.')

        # add another geounits so 4 geometries are connected by 3 single points (contiguous)
        dist1ids = [self.geounits[28]]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)

        cntcalc = Contiguity()
        cntcalc.arg_dict['allow_single_point'] = ('literal','1',)
        cntcalc.compute(district=district1)
        self.assertEqual(1, cntcalc.result['value'], 'District is contiguous at 1 point thrice, and single-point contiguity is true.')

        # add more geounits so 5 geometries are connected by 3 single points (discontiguous)
        dist1ids = [self.geounits[14]]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)

        cntcalc = Contiguity()
        cntcalc.arg_dict['allow_single_point'] = ('literal','1',)
        cntcalc.compute(district=district1)
        self.assertEqual(0, cntcalc.result['value'], 'District is contiguous at 1 point thrice, but has a disjoint geometry.')

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
        self.assertEqual(0, cntcalc.result['value'], 'District is non-contiguous, and no overrides have been defined.')

        # define a contiguity override between the two geounits, same test should now pass
        add_override(0, 11)
        cntcalc.compute(district=district1)
        self.assertEqual(1, cntcalc.result['value'], 'District is not contiguous, but an override should make it so.')

        # add a few more non-contiguous geounits without overrides, should fail
        dist1ids = [self.geounits[4], self.geounits[22], self.geounits[7]]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)
        cntcalc.compute(district=district1)
        self.assertEqual(0, cntcalc.result['value'], 'District needs 3 overrides to be considered contiguous')

        # add overrides and test one by one. the final override should make the test pass
        add_override(11, 4)
        cntcalc.compute(district=district1)
        self.assertEqual(0, cntcalc.result['value'], 'District needs 2 overrides to be considered contiguous')
        add_override(4, 22)
        cntcalc.compute(district=district1)
        self.assertEqual(0, cntcalc.result['value'], 'District needs 1 overrides to be considered contiguous')
        add_override(7, 4)
        cntcalc.compute(district=district1)
        self.assertEqual(1, cntcalc.result['value'], 'District has appropriate overrides to be considered contiguous')

        # check to make sure this works in conjunction with single-point contiguity by adding 2 more geounits
        dist1ids = [self.geounits[14], self.geounits[19]]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)
        cntcalc.arg_dict['allow_single_point'] = ('literal','0',)
        cntcalc.compute(district=district1)
        self.assertEqual(0, cntcalc.result['value'], 'Calculator needs allow_single_point on to be considered contiguous')
        cntcalc.arg_dict['allow_single_point'] = ('literal','1',)
        cntcalc.compute(district=district1)
        self.assertEqual(1, cntcalc.result['value'], 'allow_single_point is enabled, should be considered contiguous')

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

        actual = cntcalc.result['value']
        self.assertEqual(0, actual, 'Incorrect value during contiguity. (e:%d,a:%d)' % (0, actual))

        self.plan.add_geounits( self.district1.district_id, [str(self.geounits[4].id)], self.geolevel.id, self.plan.version )

        cntcalc.compute(plan=self.plan)

        actual = cntcalc.result['value']
        self.assertEqual(1, actual, 'Incorrect value during contiguity. (e:%d,a:%d)' % (1, actual))

        self.plan.add_geounits( self.district2.district_id, [str(self.geounits[13].id)], self.geolevel.id, self.plan.version )

        cntcalc.compute(plan=self.plan)

        actual = cntcalc.result['value']
        self.assertEqual(2, actual, 'Incorrect value during contiguity. (e:%d,a:%d)' % (2, actual))


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

        actual = equcalc.result['value']
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
        actual = rfcalc.result['value']
        self.assertEqual(-2, actual, 'Wrong number of districts in RepresentationalFairness (e:%d,a:%d)' % (-2, actual))

        actual = rfcalc.html()
        self.assertEqual('<span>Republican&nbsp;2</span>', actual, 'Wrong party given for RepresentationalFairness (e:%s,a:%s)' % ('<span>Republican&nbsp;2</span>', actual))

        # Swap subjects and make sure we get the right party
        rfcalc = RepresentationalFairness()
        rfcalc.arg_dict['democratic'] = ('subject',self.subject2.name,)
        rfcalc.arg_dict['republican'] = ('subject',self.subject1.name,)
        rfcalc.compute(plan=self.plan)

        actual = rfcalc.result['value']
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

        actual = ccalc.result['value']
        # by default, we have a range of .45 - .55.  Neither district is fair.
        self.assertEqual(0, actual, 'Incorrect value during competitiveness. (e:%d,a:%d)' % (0, actual))

        # Open up the range to .25 - .75. District 2 should be fair now
        ccalc = Competitiveness()
        ccalc.arg_dict['democratic'] = ('subject',self.subject1.name,)
        ccalc.arg_dict['republican'] = ('subject',self.subject2.name,)
        ccalc.arg_dict['range'] = ('literal',.25,)
        ccalc.compute(plan=self.plan)

        actual = ccalc.result['value']
        self.assertEqual(1, actual, 'Incorrect value during competitiveness. (e:%d,a:%d)' % (1, actual))

        # Open up the range to .03 - .97 (inclusive). District 1 should also be fair now. Switch subjects, too.
        ccalc = Competitiveness()
        ccalc.arg_dict['democratic'] = ('subject',self.subject2.name,)
        ccalc.arg_dict['republican'] = ('subject',self.subject1.name,)
        ccalc.arg_dict['range'] = ('literal',.47,)
        ccalc.compute(plan=self.plan)

        actual = ccalc.result['value']
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

        actual = numcalc.result['value']
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
        equicalc.arg_dict['validation'] = ('literal', 1,)
        equicalc.compute(plan=self.plan)

        actual = equicalc.result['value']
        self.assertEqual(False, actual, 'Incorrect value during plan equipop. (e:%s,a:%s)' % (False, actual))

        equicalc.arg_dict['min'] = ('literal','40',)
        equicalc.arg_dict['max'] = ('literal','45',)
        equicalc.compute(plan=self.plan)

        actual = equicalc.result['value']
        self.assertEqual(False, actual, 'Incorrect value during plan equipop. (e:%s,a:%s)' % (False, actual))

        equicalc.arg_dict['min'] = ('literal','5',)
        equicalc.arg_dict['max'] = ('literal','45',)
        equicalc.compute(plan=self.plan)

        actual = equicalc.result['value']
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
        majcalc.arg_dict['validation'] = ('literal', 1,)
        majcalc.compute(plan=self.plan)

        actual = majcalc.result['value']
        self.assertEqual(True, actual, 'Incorrect value during majority/minority. (e:%s,a:%s)' % (True, actual))

        majcalc.arg_dict['count'] = ('literal', 1,)
        majcalc.arg_dict['population'] = ('subject',self.subject2.name,)
        majcalc.arg_dict['minority1'] = ('subject',self.subject1.name,)
        majcalc.arg_dict['threshold'] = ('literal', 0.5,)
        majcalc.arg_dict['validation'] = ('literal', 1,)
        majcalc.compute(plan=self.plan)

        actual = majcalc.result['value']
        self.assertEqual(False, actual, 'Incorrect value during majority/minority. (e:%s,a:%s)' % (False, actual))

    def test_interval(self):
        interval = Interval()
        interval.arg_dict['subject'] = ('subject', self.subject2.name)
        interval.arg_dict['target'] = ('literal', 150)
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
        
        # Value of 150 for district 1.  Should be in middle class - i.e. return 2 on 0-based index
        interval.compute(district=self.district1)
        self.assertEqual(2, interval.result['index'], "Incorrect interval returned: e:%s,a:%s" % (2, interval.result['index']))
        # Value of 225 for district 1.  Should be in last class - i.e. return 4 on 0-based index
        interval.compute(district=self.district2)
        self.assertEqual(4, interval.result['index'], "Incorrect interval returned: e:%s,a:%s" % (4, interval.result['index']))

        # District 1 is in the middle class - should get a 1
        interval.compute(plan=self.plan)
        self.assertEqual(1, interval.result['value'], "Incorrect interval returned: e:%s,a:%s" % (1, interval.result['value']))

        # Adjust to get them all out of the target
        interval.arg_dict['bound1'] = ('literal', .1)
        interval.arg_dict['bound2'] = ('literal', .2)

        interval.compute(plan=self.plan)
        self.assertEqual(1, interval.result['value'], "Incorrect interval returned: e:%s,a:%s" % (1, interval.result['value']))

        # Everybody's on target 
        interval.arg_dict['bound1'] = ('literal', .6)
        del interval.arg_dict['bound2']

        interval.compute(plan=self.plan)
        self.assertEqual(2, interval.result['value'], "Incorrect interval returned: e:%s,a:%s" % (2, interval.result['value']))

        # Everybody's over - make sure we're in group 3 (0-based index 2)
        interval.arg_dict['target'] = ('literal', 0)
        interval.compute(district=self.district2)
        self.assertEqual(2, interval.result['index'], "Incorrect interval returned: e:%s,a:%s" % (2, interval.result['index']))

    def test_average1(self):
        avg = Average()
        avg.arg_dict['value1'] = ('literal','10',)
        avg.arg_dict['value2'] = ('literal','20',)

        self.assertEqual(None,avg.result)
        avg.compute(district=self.district1)
        self.assertEqual(15,avg.result['value'])

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
        self.assertEqual(78.0,avg.result['value'])

        avg = Average()
        avg.arg_dict['value1'] = ('subject', self.subject1.name)
        avg.arg_dict['value2'] = ('subject', self.subject2.name)

        self.assertEqual(None,avg.result)
        avg.compute(district=self.district2)
        self.assertEqual(117.0,avg.result['value'])

    def test_average2(self):
        avg = Average()
        avg.arg_dict['value1'] = ('literal', '10.0')
        avg.arg_dict['value2'] = ('literal', '20.0')

        self.assertEqual(None, avg.result)
        avg.compute(plan=self.plan)
        self.assertEqual(None, avg.result)

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
        self.assertEqual(97.5,avg.result['value'])

    def test_average3(self):
        avg = Average()
        avg.arg_dict['value1'] = ('literal', '10.0')
        avg.arg_dict['value2'] = ('literal', '20.0')
        avg.compute(plan=self.plan)

        # Average is 15.0, should be between 10.0 and 20.0
        self.assertEqual(None, avg.result)

        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist2ids = self.geounits[18:21] + self.geounits[27:30] + self.geounits[36:39]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        self.plan.add_geounits( self.district2.district_id, dist2ids, self.geolevel.id, self.plan.version)

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
        p1.add_geounits( d1a_id, [str(geounits[4].id)], geolevel.id, p1.version)

        d2a_id = 2
        # Create a district of geounit 8
        p1.add_geounits( d2a_id, [str(geounits[7].id)], geolevel.id, p1.version)

        # Create a plan with two districts - one crosses both 5 and 8,
        p2 = self.plan2
        d1b_id = 3
        dist1ids = self.geounits[20:23] + self.geounits[29:32] + \
            self.geounits[38:41] + self.geounits[47:50] + \
            self.geounits[56:59]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        p2.add_geounits( d1b_id, dist1ids, self.geolevel.id, p2.version)

        # the other is entirely within 5
        d2b_id = 4
        dist2ids = [self.geounits[32], self.geounits[41], self.geounits[50]]
        dist2ids = map(lambda x: str(x.id), dist2ids)
        p2.add_geounits( d2b_id, dist2ids, self.geolevel.id, p2.version)

        # Calc the first plan with second as other
        calc = SplitCounter()
        calc.arg_dict['boundary_id'] = ('literal', 'plan.%d' % p2.id)
        calc.compute(plan=p1)
        num_splits = len(calc.result['value']['splits'])
        self.assertEqual(2, num_splits, 'Did not find expected splits. e:2, a:%s' % num_splits)

        # Calc the second plan with first as other
        calc.__init__()
        calc.arg_dict['boundary_id'] = ('literal', 'plan.%d' % p1.id)
        calc.compute(plan=p2)
        num_splits = len(calc.result['value']['splits'])
        split_tuples = calc.result['value']['splits']
        self.assertEqual(3, num_splits, 'Did not find expected splits. e:3, a:%s' % num_splits)
        self.assertTrue((3,1, u'District 3', u'District 1') in calc.result['value']['splits'], 'Split not detected')
        self.assertTrue({'geo':'District 3', 'interior':'District 1', 'split':True} in calc.result['value']['named_splits'], 'Split not named correctly')

        # Calc the first plan with the smallest geolevel - no splits
        geolevel = self.plan.legislative_body.get_geolevels()[2]
        calc.__init__()
        calc.arg_dict['boundary_id'] = ('literal', 'geolevel.%d' % geolevel.id)
        calc.compute(plan=p1)
        num_splits = len(calc.result['value']['splits'])
        self.assertEqual(0, num_splits, 'Did not find expected splits. e:0, a:%s' % num_splits)

        # Calc the second plan with the middle geolevel - no splits
        calc.__init__()
        calc.arg_dict['boundary_id'] = ('literal', 'geolevel.%d' % self.geolevel.id)
        calc.compute(plan=p2)
        num_splits = len(calc.result['value']['splits'])
        self.assertEqual(0, num_splits, 'Did not find expected splits. e:0, a:%s' % num_splits)

        # Calc the second plan with biggest geolevel - d1a and d2a both split the geolevels
        geolevel = self.plan.legislative_body.get_geolevels()[0]
        calc.__init__()
        calc.arg_dict['boundary_id'] = ('literal', 'geolevel.%d' % geolevel.id)
        calc.compute(plan=p2)
        district_splits = len(set(i[0] for i in calc.result['value']['splits']))
        self.assertEqual(2, district_splits, 'Did not find expected splits. e:2, a:%s' % district_splits)
        self.assertTrue((3, u'0000004', u'District 3', u'Unit 1-4') in calc.result['value']['splits'], 'Did not find expected splits')

    def test_convexhull_l1(self):
        """
        Test the convex hull calculator for the middle geolevel
        """
        geolevel = Geolevel.objects.get(name='middle level')
        dist1ids = list(geolevel.geounit_set.all())[0:1]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        
        self.plan.add_geounits(self.district1.district_id, dist1ids, geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)

        calc = ConvexHull()
        calc.compute(district=district1)
        
        self.assertEqual(0.012345679012345678, calc.result['value'])

    def test_convexhull_l2(self):
        """
        Test the convex hull calculator for the biggest geolevel
        """
        geolevel = Geolevel.objects.get(name='biggest level')
        dist1ids = list(geolevel.geounit_set.all())[0:1]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        
        self.plan.add_geounits(self.district1.district_id, dist1ids, geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)

        calc = ConvexHull()
        calc.compute(district=district1)
        
        self.assertEqual(0.1111111111111111, calc.result['value'])

    def test_convexhull_row(self):
        """
        Test the convex hull calculator averaging a horizontal row of 9 smaller
        geounits
        """
        dist1ids = list(self.geolevel.geounit_set.all())[0:9]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        
        self.plan.add_geounits(self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)

        calc = ConvexHull()
        calc.compute(district=district1)
        
        # 9 contiguous geounits at the middle level have the same area as one
        # geounit at the biggest level
        self.assertEqual(0.1111111111111111, calc.result['value'])

    def test_convexhull_block(self):
        """
        Test the convex hull calculator averaging a block of 9 smaller geounits
        """
        dist1ids = list(self.geolevel.geounit_set.all())
        dist1ids = dist1ids[0:3] + dist1ids[9:12] + dist1ids[18:21]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        
        self.plan.add_geounits(self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)

        calc = ConvexHull()
        calc.compute(district=district1)
        
        # 9 contiguous geounits at the middle level have the same area as one
        # geounit at the biggest level
        self.assertEqual(0.1111111111111111, calc.result['value'])

    def test_convexhull_column(self):
        """
        Test the convex hull calculator averaging a column of 9 smaller geounits
        """
        dist1ids = list(self.geolevel.geounit_set.all())
        dist1ids = dist1ids[0:1] + dist1ids[9:10] + dist1ids[18:19] + \
            dist1ids[27:28] + dist1ids[36:37] + dist1ids[45:46] + \
            dist1ids[54:55] + dist1ids[63:64] + dist1ids[72:73]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        
        self.plan.add_geounits(self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)

        calc = ConvexHull()
        calc.compute(district=district1)
        
        # 9 contiguous geounits at the middle level have the same area as one
        # geounit at the biggest level
        self.assertEqual(0.1111111111111111, calc.result['value'])

    def test_convexhull_sparse(self):
        """
        Test the convex hull calculator averaging a sparse set of geounits
        """
        dist1ids = list(self.geolevel.geounit_set.all())
        dist1ids = dist1ids[0:1] + dist1ids[8:9] + dist1ids[72:73] + dist1ids[80:81]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        
        self.plan.add_geounits(self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        district1 = self.plan.district_set.get(district_id=self.district1.district_id,version=self.plan.version)

        calc = ConvexHull()
        calc.compute(district=district1)
        
        # the convex hull that covers this sparse district is bigger than the 
        # sum of the areas
        self.assertEqual(1, calc.result['value'])

    def test_convexhull_avg(self):
        """
        Test the convex hull calculator averaging a sparse set of geounits
        """
        dist1ids = list(self.geolevel.geounit_set.all())
        dist1ids = dist1ids[0:9]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        
        self.plan.add_geounits(self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)

        calc = ConvexHull()
        calc.compute(plan=self.plan)
        
        # the average convex hull that covers this plan is the same as the 
        # district convex hull
        self.assertEqual(0.1111111111111111, calc.result['value'])

    def test_convexhull_avg2(self):
        """
        Test the convex hull calculator averaging a sparse set of geounits
        """
        distids = list(self.geolevel.geounit_set.all())
        dist1ids = distids[0:9]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        
        self.plan.add_geounits(self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        
        dist2ids = distids[9:18]
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan.add_geounits(self.district2.district_id, dist2ids, self.geolevel.id, self.plan.version)

        calc = ConvexHull()
        calc.compute(plan=self.plan)
        
        # the average convex hull that covers this plan is the same as the 
        # district convex hull (both of them!)
        self.assertEqual(0.1111111111111111, calc.result['value'])



class AllBlocksTestCase(BaseTestCase):
    fixtures = ['redistricting_testdata.json',
                'redistricting_testdata_geolevel2.json',
                'redistricting_testdata_geolevel3.json',
                ]
    def setUp(self):
        BaseTestCase.setUp(self)
        self.geolevel = Geolevel.objects.get(name='middle level')
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
        actual = allblocks.result['value']
        self.assertEqual(False, actual, 'Incorrect value during plan allblocks. (e:%s,a:%s)' % (False, actual))

        remainderids = plan.get_unassigned_geounits(0.1)
        remainderids = map(lambda x: str(x[0]), remainderids)
        plan.add_geounits( self.district2.district_id, remainderids, self.geolevel.id, plan.version)

        plan = Plan.objects.get(pk=plan.id)
        allblocks.compute(plan=plan)
        actual = allblocks.result['value']
        self.assertEqual(True, actual, 'Incorrect value during plan allblocks. (e:%s,a:%s)' % (True, actual))

class ScoreRenderTestCase(BaseTestCase):
    fixtures = ['redistricting_testdata.json', 'redistricting_testdata_geolevel2.json', 'redistricting_testdata_scoring.json']

    def setUp(self):
        BaseTestCase.setUp(self)
        self.geolevel = Geolevel.objects.get(name='middle level')
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
            expected = 'testPlan:<span>9</span>' + \
                'testPlan2:<span>9</span>' + \
                'testPlan:<span>18.18%</span>' + \
                'testPlan2:<span>10.64%</span>'
                
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
            template.write('{% for dscore in districtscores %}{{dscore.district.long_label }}:{% for score in dscore.scores %}{{ score.score|safe }}{% endfor %}{% endfor %}')
            template.close()

            markup = panel.render(districts)
            expected = 'District 1:86.83%<img class="yes-contiguous" src="/static-media/images/icon-check.png">' + \
                'District 2:86.83%<img class="yes-contiguous" src="/static-media/images/icon-check.png">' + \
                'Unassigned:0.00%<img class="yes-contiguous" src="/static-media/images/icon-check.png">'
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

        expected = 'testPlan2:<span>10.64%</span>' + \
            'testPlan:<span>18.18%</span>' + \
            'testPlan:<span>9</span>' + \
            'testPlan2:<span>9</span>'
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
        template.write('{% for dscore in districtscores %}{{dscore.district.long_label }}:{% for score in dscore.scores %}{{ score.score|safe }}{% endfor %}{% endfor %}')
        template.close()

        markup = display.render(self.plan)
        expected = 'District 1:86.83%<img class="yes-contiguous" src="/static-media/images/icon-check.png">' + \
            'District 2:86.83%<img class="yes-contiguous" src="/static-media/images/icon-check.png">' + \
            'Unassigned:0.00%<img class="yes-contiguous" src="/static-media/images/icon-check.png">'
        self.assertEqual(expected, markup, 'The markup was incorrect. (e:"%s", a:"%s")' % (expected, markup))

        markup = display.render(self.plan.get_districts_at_version(self.plan.version,include_geom=False))

        expected = 'District 1:86.83%<img class="yes-contiguous" src="/static-media/images/icon-check.png">' + \
            'District 2:86.83%<img class="yes-contiguous" src="/static-media/images/icon-check.png">' + \
            'Unassigned:0.00%<img class="yes-contiguous" src="/static-media/images/icon-check.png">'
        self.assertEqual(expected, markup, 'The markup was incorrect. (e:"%s", a:"%s")' % (expected, markup))

        os.remove(tplfile)

    def test_scoredisplay_with_overrides(self):
        # Get a ScoreDisplay
        display = ScoreDisplay.objects.get(title='TestScoreDisplay')
        display.is_page = False

        # Make up a ScorePanel - don't save it
        panel = ScorePanel(title="My Fresh Panel", type="district", template="sp_template2.html")
        # Create two functions, one with an arg and one without
        function = ScoreFunction(calculator="redistricting.calculators.SumValues", name="My Fresh Calc", is_planscore=False)

        arg1 = ScoreArgument(argument="value1", value="5", type="literal")
        arg2 = ScoreArgument(argument="value2", value="TestSubject", type="subject")

        tplfile = settings.TEMPLATE_DIRS[0] + '/' + panel.template
        template = open(tplfile,'w')
        template.write('{% for dscore in districtscores %}{{dscore.district.long_label }}:{% for score in dscore.scores %}{{ score.score|safe }}{% endfor %}{% endfor %}')
        template.close()

        # Render the ScoreDisplay
        components = [(panel, [(function, arg1, arg2)])]
        district_result = display.render([self.district1], components=components)
        expected = 'District 1:<span>5</span>'
        self.assertEqual(expected, district_result, 'Didn\'t get expected result when overriding district\'s display')

        os.remove(tplfile)

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

        tplfile = settings.TEMPLATE_DIRS[0] + '/' + panel.template
        template = open(tplfile,'w')
        template.write('{% for planscore in planscores %}{{planscore.plan.name}}:{{ planscore.score|safe }}{% endfor %}')
        template.close()

        # Check the result
        plan_result = display.render(self.plan, components=components)
        expected = "testPlan:['<span>24</span>']"
        self.assertEqual(expected, plan_result, 'Didn\'t get expected result when overriding plan\'s display')

        os.remove(tplfile)

    def test_splitcounter_display(self):
        # Create a plan with two districts - one crosses both 5 and 8
        p1 = self.plan
        d1a_id = 1
        dist1ids = self.geounits[20:23] + self.geounits[29:32] + \
            self.geounits[38:41] + self.geounits[47:50] + \
            self.geounits[56:59]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        p1.add_geounits( d1a_id, dist1ids, self.geolevel.id, p1.version)

        # the other is entirely within 5
        d2a_id = 5
        dist2ids = [self.geounits[32], self.geounits[41], self.geounits[50]]
        dist2ids = map(lambda x: str(x.id), dist2ids)
        p1.add_geounits( d2a_id, dist2ids, self.geolevel.id, p1.version)

        # Get a ScoreDisplay and components to render
        display = ScoreDisplay.objects.get(title='TestScoreDisplay')
        display.is_page = False
        display.save()

        panel = ScorePanel(title="Splits Report", type="plan", template="sp_template1.html", cssclass="split_panel")
        function = ScoreFunction(calculator="redistricting.calculators.SplitCounter", name="splits_test", is_planscore=True)
        geolevel = self.plan.legislative_body.get_geolevels()[0]
        arg1 = ScoreArgument(argument="boundary_id", value="geolevel.%d" % geolevel.id, type="literal")

        components = [(panel, [(function, arg1)])]

        expected_result = '%s:[u\'<div class="split_report"><div>Total districts which split a biggest level short label: 2</div><div>Total number of splits: 7</div><div class="table_container"><table class="report"><thead><tr><th>Testplan</th><th>Biggest level short label</th></tr></thead><tbody><tr><td>District 1</td><td>Unit 1-0</td></tr><tr><td>District 1</td><td>Unit 1-1</td></tr><tr><td>District 1</td><td>Unit 1-3</td></tr><tr><td>District 1</td><td>Unit 1-4</td></tr><tr><td>District 1</td><td>Unit 1-6</td></tr><tr><td>District 1</td><td>Unit 1-7</td></tr><tr><td>District 5</td><td>Unit 1-4</td></tr></tbody></table></div></div>\']' % p1.name

        tplfile = settings.TEMPLATE_DIRS[0] + '/' + panel.template
        template = open(tplfile,'w')
        template.write('{% for planscore in planscores %}{{planscore.plan.name}}:{{ planscore.score|safe }}{% endfor %}')
        template.close()

        # Check the result
        plan_result = display.render(p1, components=components)

        self.assertEqual(expected_result, plan_result, "Didn't get expected result when rendering SplitCounter:\ne:%s\na:%s" % (expected_result, plan_result))

        os.remove(tplfile)

class ComputedScoresTestCase(BaseTestCase):
    def test_district1(self):
        geolevel = Geolevel.objects.get(name='middle level')
        geounits = list(Geounit.objects.filter(geolevel=geolevel).order_by('id'))

        dist1ids = geounits[0:3] + geounits[9:12]
        dist2ids = geounits[6:9] + geounits[15:18]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevel.id, self.plan.version)
        self.plan.add_geounits( self.district2.district_id, dist2ids, geolevel.id, self.plan.version)
        
        function = ScoreFunction.objects.get(calculator__endswith='SumValues',is_planscore=False)
        numscores = ComputedDistrictScore.objects.all().count()

        self.assertEqual(0, numscores, 'The number of computed district scores is incorrect. (e:0, a:%d)' % numscores)

        district1 = self.plan.district_set.filter(district_id=self.district1.district_id, version=self.plan.version-1)[0]
        expected = function.score(district1)

        score = ComputedDistrictScore.compute(function, district1)

        self.assertEqual(expected['value'], score['value'], 'The score computed is incorrect. (e:%0.1f, a:%0.1f)' % (expected['value'],score['value'],))

        numscores = ComputedDistrictScore.objects.all().count()

        self.assertEqual(1, numscores, 'The number of computed district scores is incorrect. (e:1, a:%d)' % numscores)

        dist1ids = geounits[3:6]
        dist1ids = map(lambda x: str(x.id), dist1ids)

        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevel.id, self.plan.version )

        district1 = self.plan.district_set.filter(district_id=self.district1.district_id, version=self.plan.version)[0]
        expected = function.score(district1)

        score = ComputedDistrictScore.compute(function, district1)

        self.assertEqual(expected['value'], score['value'], 'The score computed is incorrect. (e:%0.1f, a:%0.1f)' % (expected['value'],score['value'],))

        numscores = ComputedDistrictScore.objects.all().count()

        self.assertEqual(2, numscores, 'The number of computed district scores is incorrect. (e:2, a:%d)' % numscores)

    def test_plan1(self):
        geolevel = Geolevel.objects.get(name='middle level')
        geounits = list(Geounit.objects.filter(geolevel=geolevel).order_by('id'))

        dist1ids = geounits[0:3] + geounits[9:12]
        dist2ids = geounits[6:9] + geounits[15:18]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)
        
        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevel.id, self.plan.version)
        self.plan.add_geounits( self.district2.district_id, dist2ids, geolevel.id, self.plan.version)
        
        function = ScoreFunction.objects.get(calculator__endswith='SumValues',is_planscore=True)
        numscores = ComputedPlanScore.objects.all().count()

        self.assertEqual(0, numscores, 'The number of computed plan scores is incorrect. (e:0, a:%d)' % numscores)

        score = ComputedPlanScore.compute(function, self.plan)

        self.assertEqual(9, score['value'], 'The score computed is incorrect. (e:9.0, a:%0.1f)' % score['value'])

        numscores = ComputedPlanScore.objects.all().count()

        self.assertEqual(1, numscores, 'The number of computed plan scores is incorrect. (e:1, a:%d)' % numscores)

        dist1ids = geounits[3:6]
        dist1ids = map(lambda x: str(x.id), dist1ids)

        self.plan.add_geounits( self.district1.district_id, dist1ids, geolevel.id, self.plan.version )

        score = ComputedPlanScore.compute(function, self.plan)

        self.assertEqual(9, score['value'], 'The score computed is incorrect. (e:9.0, a:%0.1f)' % score['value'])

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
        self.geolevel = Geolevel.objects.get(name='middle level')
        self.geolevels = Geolevel.objects.all().order_by('-id')

        self.geounits = {}
        for gl in self.geolevels:
           self.geounits[gl.id] = list(Geounit.objects.filter(geolevel=gl).order_by('id'))

        # Set up new districts for testing
        self.district10 = District(long_label='District 10', version=0, district_id=10)
        self.district10.plan = self.plan
        self.district10.simplify()
        
        self.district11 = District(long_label='District 11', version=0, district_id=11)
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
        self.plan.add_geounits(self.district10.district_id, dist10ids, geolevelid, self.plan.version)
        self.plan = Plan.objects.get(pk=self.plan.id)
        
        dist11ids = [geounits[22]]
        dist11ids = map(lambda x: str(x.id), dist11ids)
        self.plan.add_geounits(self.district11.district_id, dist11ids, geolevelid, self.plan.version)
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
            BaseTestCase.tearDown(self)
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
        params = { 'version':self.plan.version, 'counts[]':5, 'districts[]':self.district_id }
        self.client.post('/districtmapping/plan/%d/districtmembers/' % self.plan.id, params)
        self.district10 = max(District.objects.filter(plan=self.plan,district_id=self.district10.district_id),key=lambda d: d.version)
        self.plan = Plan.objects.get(pk=self.plan.id)

    def test_multi_basic(self):
        """
        Test the logic for modifying the number of members in a district
        Also tests magnitudes in export process and calculators
        """
        # Issue command to assign 5 members to a district for a legislative body that doesn't support multi-members
        # Should fail
        params = { 'version':self.plan.version, 'counts[]':5, 'districts[]':self.district_id }
        response = self.client.post('/districtmapping/plan/%d/districtmembers/' % self.plan.id, params)
        
        resp_obj = json.loads(response.content)
        self.assertFalse(resp_obj['success'], 'Member assign request for disallowed legbody wasn\'t denied: ' + str(response))

        # Verify the number of members is 1
        num = self.district10.num_members
        self.assertEqual(1, num, '# members is incorrect: %d' % num)

        # Verify the version number is 2
        num = self.plan.version
        self.assertEqual(2, num, 'version number is incorrect: %d' % num)

        # Modify the legislative body, so that it does support multi-members, and reissue the request
        # Should pass
        self.plan.legislative_body.multi_members_allowed = True
        self.plan.legislative_body.save()
        params = { 'version':self.plan.version, 'counts[]':5, 'districts[]':self.district_id }
        response = self.client.post('/districtmapping/plan/%d/districtmembers/' % self.plan.id, params)
        resp_obj = json.loads(response.content)
        self.assertTrue(resp_obj['success'], 'Member assign request for allowed legbody was denied: ' + str(response))
        self.assertEqual(1, resp_obj['modified'], '# districts modified was incorrect: %d' % resp_obj['modified'])

        # Verify the number of members and version number have been updated
        self.district10 = max(District.objects.filter(plan=self.plan,district_id=self.district10.district_id),key=lambda d: d.version)
        num = self.district10.num_members
        self.assertEqual(5, num, '# members is incorrect: %d' % num)
        num = self.district10.version
        self.assertEqual(3, num, 'version number is incorrect: %d' % num)

    def test_multi_2(self):
        """
        Verify number of members is added to the exported file
        """
        self.set_multi()
        
        archive = DistrictIndexFile.plan2index(self.plan)
        zin = zipfile.ZipFile(archive.name, "r")
        strz = zin.read(self.plan.name + ".csv")
        zin.close()
        os.remove(archive.name)
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
        rngcalc.arg_dict['value'] = ('subject',self.subject1.name,)
        rngcalc.arg_dict['min'] = ('literal','1',)
        rngcalc.arg_dict['max'] = ('literal','3',)
        rngcalc.arg_dict['apply_num_members'] = ('literal','0',)
        rngcalc.compute(district=self.district10)
        actual = rngcalc.result['value']
        expected = 1
        self.assertEqual(expected, actual, 'Incorrect value during range. (e:%s,a:%s)' % (expected, actual))
        
        # Now apply multi-member magnitude
        # There are 5 members, so the range would need to be 5x smaller
        rngcalc = Range()
        rngcalc.arg_dict['value'] = ('subject',self.subject1.name,)
        rngcalc.arg_dict['min'] = ('literal','0',)
        rngcalc.arg_dict['max'] = ('literal','1',)
        rngcalc.arg_dict['apply_num_members'] = ('literal','1',)
        rngcalc.compute(district=self.district10)
        actual = rngcalc.result['value']
        expected = 1
        self.assertEqual(expected, actual, 'Incorrect value during range. (e:%s,a:%s)' % (expected, actual))

    def test_multi_equipopulation(self):
        """
        Test equipopulation calculator
        """
        self.set_multi()

        # Verify equipopulation calculator accounts for member magnitude
        # First don't apply multi-member magnitude
        # Value of subjects are 2 and 4, so we should be within the range
        equipopcalc = Equipopulation()
        equipopcalc.arg_dict['value'] = ('subject',self.subject1.name,)
        equipopcalc.arg_dict['min'] = ('literal','1',)
        equipopcalc.arg_dict['max'] = ('literal','5',)
        equipopcalc.arg_dict['apply_num_members'] = ('literal','0',)
        equipopcalc.compute(plan=self.plan)
        actual = equipopcalc.result['value']
        expected = 2
        self.assertEqual(expected, actual, 'Incorrect value during range. (e:%s,a:%s)' % (expected, actual))

        # Now apply multi-member magnitude
        # There are 5 members in one of the districts, so the range would need to be 5x smaller for that one
        equipopcalc = Equipopulation()
        equipopcalc.arg_dict['value'] = ('subject',self.subject1.name,)
        equipopcalc.arg_dict['min'] = ('literal','1',)
        equipopcalc.arg_dict['max'] = ('literal','10',)
        equipopcalc.arg_dict['apply_num_members'] = ('literal','1',)
        equipopcalc.compute(plan=self.plan)
        actual = equipopcalc.result['value']
        expected = True
        self.assertEqual(expected, actual, 'Incorrect value during range. (e:%s,a:%s)' % (expected, actual))
        
    def test_multi_equivalence(self):
        """
        Test equivalence calculator
        """
        self.set_multi()

        # Verify equivalence calculator accounts for member magnitude
        # First don't apply multi-member magnitude
        # min is 2,  max is 4. diff should be 2
        equcalc = Equivalence()
        equcalc.arg_dict['value'] = ('subject',self.subject1.name,)
        equcalc.arg_dict['apply_num_members'] = ('literal','0',)
        equcalc.compute(plan=self.plan)
        actual = equcalc.result['value']
        expected = 2.0
        self.assertEqual(expected, actual, 'Incorrect value during equivalence. (e:%f,a:%f)' % (expected, actual))
        
        # Now apply multi-member magnitude
        # min is 0.4 (2/5),  max is 4. diff should be 3.6
        equcalc = Equivalence()
        equcalc.arg_dict['value'] = ('subject',self.subject1.name,)
        equcalc.arg_dict['apply_num_members'] = ('literal','1',)
        equcalc.compute(plan=self.plan)
        actual = equcalc.result['value']
        expected = 3.6
        self.assertAlmostEquals(expected, actual, 3, 'Incorrect value during equivalence. (e:%f,a:%f)' % (expected, actual))

    def test_multi_interval(self):
        """
        Test interval calculator
        """
        self.set_multi()

        # Verify interval calculator accounts for member magnitude
        interval = Interval()
        interval.arg_dict['subject'] = ('subject', self.subject1.name)
        interval.arg_dict['apply_num_members'] = ('literal','0',)
        interval.arg_dict['target'] = ('literal', 6)
        interval.arg_dict['bound1'] = ('literal', .10)
        interval.arg_dict['bound2'] = ('literal', .20)

        # Value of 2 for district 1.  Should be in the middle
        interval.compute(district=self.district10)
        self.assertEqual(2, interval.result['value'], "Incorrect interval returned: e:%d,a:%d" % (2, interval.result['value']))
        interval.compute(plan=self.plan)
        self.assertEqual(0, interval.result['value'], "Incorrect interval returned: e:%d,a:%d" % (0, interval.result['value']))

        # Now apply multi-member magnitude
        interval = Interval()
        interval.arg_dict['subject'] = ('subject', self.subject1.name)
        interval.arg_dict['apply_num_members'] = ('literal','1',)
        interval.arg_dict['target'] = ('literal', 1.2)
        interval.arg_dict['bound1'] = ('literal', .10)
        interval.arg_dict['bound2'] = ('literal', .20)

        # Value of 0.2 for district 1.  Should be in the middle
        interval.compute(district=self.district10)
        self.assertAlmostEqual(0.4, float(interval.result['value']), 2, "Incorrect interval returned: e:%d,a:%d" % (0.4, interval.result['value']))

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
        self.assertTrue(multicalc.result['value'], "Multi-member district should have been valid")

        self.plan.legislative_body.min_multi_districts = 2
        self.plan.legislative_body.save()
        multicalc.compute(plan=self.plan)
        self.assertFalse(multicalc.result['value'], "Should be not enough multi-member districts")
        
        self.plan.legislative_body.min_multi_districts = 1
        self.plan.legislative_body.min_plan_members = 7
        self.plan.legislative_body.save()
        multicalc.compute(plan=self.plan)
        self.assertFalse(multicalc.result['value'], "Should be not enough plan members")
        
        self.plan.legislative_body.min_plan_members = 6
        self.plan.legislative_body.min_multi_district_members = 6
        self.plan.legislative_body.save()
        multicalc.compute(plan=self.plan)
        self.assertFalse(multicalc.result['value'], "Should be not enough members per multi-member district")

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

        functions = ScoreFunction.objects.filter(name__in=('Voting Age Population', 'Hispanic voting-age population', 'Total Population'))
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
        self.assertEqual("%s copy" % self.display.__unicode__(), copy.__unicode__(), 
            "ScoreDisplay title copied, allowing same name for user more than once")
        self.assertEqual(len(copy.scorepanel_set.all()), len(self.display.scorepanel_set.all()), 
            "Copied scoredisplay has wrong number of panels attached")
        self.assertNotEqual(user, copy.owner, "ScoreDisplay copied owner rather than copying owner from ScoreDisplay")

        copy = ScoreDisplay(owner=user)
        copy = copy.copy_from(display=self.display, owner=user)
        self.assertEqual(self.display.__unicode__(), copy.__unicode__(), "Title of scoredisplay not copied")
        self.assertEqual(len(copy.scorepanel_set.all()), len(self.display.scorepanel_set.all()), 
            "Copied scoredisplay has wrong number of panels attached")

        vap = ScoreFunction.objects.get(name="Voting Age Population")
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
        self.geolevel = Geolevel.objects.get(name='middle level')
        self.geolevels = self.plan.legislative_body.get_geolevels()

        self.geounits = {}
        for gl in self.geolevels:
           self.geounits[gl.id] = list(Geounit.objects.filter(geolevel=gl).order_by('id'))

        # Create 3 nested legislative bodies
        self.region = Region(name='Nesting',sort_key=2)
        self.region.save()
        self.bottom = LegislativeBody(name="bottom", max_districts=100, region=self.region)
        self.bottom.save()
        self.middle = LegislativeBody(name="middle", max_districts=20, region=self.region)
        self.middle.save()
        self.top = LegislativeBody(name="top", max_districts=4, region=self.region)
        self.top.save()

        # Create references for plans and districts
        self.plan = Plan.objects.get(name='testPlan')
        self.plan2 = Plan.objects.get(name='testPlan2')
        self.p1d1 = District.objects.get(long_label='District 1', plan=self.plan)
        self.p1d2 = District.objects.get(long_label='District 2', plan=self.plan)
        self.p2d1 = District(long_label='District 1', district_id=1, version=0, plan=self.plan2)
        self.p2d1.simplify()
        self.p2d2 = District(long_label='District 2', district_id=2, version=0, plan=self.plan2)
        self.p2d2.simplify()

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

    def test_relationships_identical_districts(self):
        gl, gs = self.geolevel, list(Geounit.objects.filter(geolevel=self.geolevel).order_by("id"))
        p1, p1d1, p1d2 = self.plan, self.p1d1, self.p1d2
        p2, p2d1, p2d2 = self.plan2, self.p2d1, self.p2d2

        dist1ids = gs[0:2] + gs[9:11]
        dist1ids = map(lambda x: str(x.id), dist1ids)

        p1.add_geounits(p1d1.district_id, dist1ids, gl.id, p1.version)
        p1d1 = max(District.objects.filter(plan=p1,district_id=p1d1.district_id),key=lambda d: d.version)

        dist2ids = gs[19:21] + gs[38:40]
        dist2ids = map(lambda x: str(x.id), dist2ids)

        p1.add_geounits(p1d2.district_id, dist2ids, gl.id, p1.version)
        p1d2 = max(District.objects.filter(plan=p1,district_id=p1d2.district_id),key=lambda d: d.version)

        # Identical
        p2.add_geounits(p2d1.district_id, dist1ids, gl.id, p2.version)
        p2d1 = max(District.objects.filter(plan=p2,district_id=p2d1.district_id),key=lambda d: d.version)
        p2.add_geounits(p2d2.district_id, dist2ids, gl.id, p2.version)
        p2d2 = max(District.objects.filter(plan=p2,district_id=p2d2.district_id),key=lambda d: d.version)

        # Test splits
        splits = p1.find_plan_splits(p2)
        self.assertEqual(len(splits), 0, "Found splits in identical plans")

        # Test contains -- two districts should each contain each other
        contains = p1.find_plan_components(p2)
        self.assertEqual(len(contains), 2, "Didn't find 2 contained districts")
        self.assertEqual(contains[0][:2], (1, 1), "Didn't find p1d1 to contain p2d1")
        self.assertEqual(contains[1][:2], (2, 2), "Didn't find p1d2 to contain p2d1")

    def test_relationships_bottom_district_smaller(self):
        gl, gs = self.geolevel, list(Geounit.objects.filter(geolevel=self.geolevel).order_by("id"))
        p1, p1d1, p1d2 = self.plan, self.p1d1, self.p1d2
        p2, p2d1, p2d2 = self.plan2, self.p2d1, self.p2d2

        dist1ids = gs[0:2] + gs[9:11]
        dist1ids = map(lambda x: str(x.id), dist1ids)

        p1.add_geounits(p1d1.district_id, dist1ids, gl.id, p1.version)
        p1d1 = max(District.objects.filter(plan=p1,district_id=p1d1.district_id),key=lambda d: d.version)

        dist2ids = gs[19:21] + gs[38:40]
        dist2ids = map(lambda x: str(x.id), dist2ids)

        p1.add_geounits(p1d2.district_id, dist2ids, gl.id, p1.version)
        p1d2 = max(District.objects.filter(plan=p1,district_id=p1d2.district_id),key=lambda d: d.version)

        # 38, 39 not included in bottom plan
        p2.add_geounits(p2d1.district_id, dist1ids, gl.id, p2.version)
        p2d1 = max(District.objects.filter(plan=p2,district_id=p2d1.district_id),key=lambda d: d.version)

        dist2ids = gs[19:21]
        dist2ids = map(lambda x: str(x.id), dist2ids)

        p2.add_geounits(p2d2.district_id, dist2ids, gl.id, p2.version)
        p2d2 = max(District.objects.filter(plan=p2,district_id=p2d2.district_id),key=lambda d: d.version)

        # Test splits
        splits = p1.find_plan_splits(p2)
        self.assertEqual(len(splits), 0, "Found splits when bottom plan had a smaller district")

        # Test contains -- top two districts should contain bottom two
        contains = p1.find_plan_components(p2)
        self.assertEqual(len(contains), 2, "Didn't find 2 contained districts")
        self.assertEqual(contains[0][:2], (1, 1), "Didn't find p1d1 to contain p2d1")
        self.assertEqual(contains[1][:2], (2, 2), "Didn't find p1d2 to contain p2d1")

    def test_relationships_top_district_smaller(self):
        gl, gs = self.geolevel, list(Geounit.objects.filter(geolevel=self.geolevel).order_by("id"))
        p1, p1d1, p1d2 = self.plan, self.p1d1, self.p1d2
        p2, p2d1, p2d2 = self.plan2, self.p2d1, self.p2d2

        # 38, 39 not included in top plan
        dist1ids = gs[0:2] + gs[9:11]
        dist1ids = map(lambda x: str(x.id), dist1ids)

        p1.add_geounits(p1d1.district_id, dist1ids, gl.id, p1.version)
        p1d1 = max(District.objects.filter(plan=p1,district_id=p1d1.district_id),key=lambda d: d.version)

        dist2ids = gs[19:21]
        dist2ids = map(lambda x: str(x.id), dist2ids)

        p1.add_geounits(p1d2.district_id, dist2ids, gl.id, p1.version)
        p1d2 = max(District.objects.filter(plan=p1,district_id=p1d2.district_id),key=lambda d: d.version)

        p2.add_geounits(p2d1.district_id, dist1ids, gl.id, p2.version)
        p2d1 = max(District.objects.filter(plan=p2,district_id=p2d1.district_id),key=lambda d: d.version)

        dist2ids = gs[19:21] + gs[28:30]
        dist2ids = map(lambda x: str(x.id), dist2ids)

        p2.add_geounits(p2d2.district_id, dist2ids, gl.id, p2.version)
        p2d2 = max(District.objects.filter(plan=p2,district_id=p2d2.district_id),key=lambda d: d.version)

        # Test splits
        splits = p1.find_plan_splits(p2)
        self.assertEqual(len(splits), 1, "Didn't find 1 split")
        self.assertEqual(splits[0][:2], (2, 2), "Didn't find p1d2 to split p2d2")

        # Test contains -- one of the bottom districts should contain the other one
        contains = p1.find_plan_components(p2)
        self.assertEqual(len(contains), 1, "Didn't find 1 contained districts")
        self.assertEqual(contains[0][:2], (1, 1), "Didn't find p1d1 to contain p2d1")

    def test_relationships_move_diagonally(self):
        gl, gs = self.geolevel, list(Geounit.objects.filter(geolevel=self.geolevel).order_by("id"))
        p1, p1d1, p1d2 = self.plan, self.p1d1, self.p1d2
        p2, p2d1, p2d2 = self.plan2, self.p2d1, self.p2d2

        # Offset plan one unit diagonally down-left
        ids = map(lambda x: str(x.id), gs[0:1])
        p1.add_geounits(p1d1.district_id, ids, gl.id, p1.version)
        p1d1 = max(District.objects.filter(plan=p1,district_id=p1d1.district_id),key=lambda d: d.version)
        ids = map(lambda x: str(x.id), gs[9:11] + gs[18:20])
        p1.add_geounits(p1d2.district_id, ids, gl.id, p1.version)
        p1d2 = max(District.objects.filter(plan=p1,district_id=p1d2.district_id),key=lambda d: d.version)
       
        ids = map(lambda x: str(x.id), gs[0:2] + gs[9:11])
        p2.add_geounits(p2d1.district_id, ids, gl.id, p2.version)
        p2d1 = max(District.objects.filter(plan=p2,district_id=p2d1.district_id),key=lambda d: d.version)
        ids = map(lambda x: str(x.id), gs[19:21] + gs[28:30])
        p2.add_geounits(p2d2.district_id, ids, gl.id, p2.version)
        p2d2 = max(District.objects.filter(plan=p2,district_id=p2d2.district_id),key=lambda d: d.version)

        # Test splits
        splits = p1.find_plan_splits(p2)
        self.assertEqual(len(splits), 3, "Didn't find 3 splits")
        self.assertEqual(splits[0][:2], (1, 1), "Didn't find p1d1 to split p2d1")
        self.assertEqual(splits[1][:2], (2, 1), "Didn't find p1d2 to split p2d1")
        self.assertEqual(splits[2][:2], (2, 2), "Didn't find p1d2 to split p2d2")

        # Test contains -- shouldn't be any districts fully contained
        contains = p1.find_plan_components(p2)
        self.assertEqual(len(contains), 0, "Found contained districts when there should be none.")
        

class CommunityTypeTestCase(BaseTestCase):
    """
    Unit tests to test detection of Community types in a district:
    """
    fixtures = ['redistricting_testdata.json', 'redistricting_testdata_geolevel2.json']

    def setUp(self):
        BaseTestCase.setUp(self)        
        self.geolevel = Geolevel.objects.get(name='middle level')
        self.geolevels = Geolevel.objects.all().order_by('-id')
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

    def test_community_union(self):
        gl, gs = self.geolevel, list(Geounit.objects.filter(geolevel=self.geolevel).order_by("id"))
        p, c = self.plan, self.community

        # Create a basic district in the plan
        ids = map(lambda x: str(x.id), gs[21:24] + gs[30:33] + gs[39:42])
        p.add_geounits(1, ids, gl.id, p.version)
        d1 = max(District.objects.filter(plan=p,district_id=1),key=lambda d: d.version)

        # Check and make sure we get 0 intersections
        intersections = d1.count_community_type_union(c.id)
        self.assertNotEquals(0, d1.geom.area, 'District 1 has no area')
        self.assertEqual(0, intersections, 'Detected community intersections when there are none a:%d' % intersections)

        # C1 intersects on the left, half-in and half-out of d1 
        ids = map(lambda x: str(x.id), gs[29:31])
        c.add_geounits(1, ids, gl.id, c.version)
        c1 = max(District.objects.filter(plan=c,district_id=1),key=lambda d: d.version)
        c1.tags = 'type=type_a'
        intersections = d1.count_community_type_union(c.id)
        self.assertEqual(1, intersections, 'detected incorrect number of community intersections. e:1;a:%d' % intersections)

        # C2 is inside of d1 and shares a border
        ids = [str(gs[32].id)]
        c.add_geounits(2, ids, gl.id, c.version)
        c2 = max(District.objects.filter(plan=c,district_id=2),key=lambda d: d.version)
        c2.tags = 'type=type_b'
        intersections = d1.count_community_type_union(c.id)
        self.assertEqual(2, intersections, 'Detected incorrect number of community intersections. e:2;a:%d' % intersections)

        #C3 is outside of d1 and shares a border
        ids = [str(gs[56].id)]
        c.add_geounits(3, ids, gl.id, c.version)
        c3 = max(District.objects.filter(plan=c,district_id=3),key=lambda d: d.version)
        c3.tags = 'type=type_c'
        intersections = d1.count_community_type_union(c.id)
        self.assertEqual(2, intersections, 'Detected incorrect number of community intersections. e:2;a:%d' % intersections)

        # C4 is entirely within d1 and shares no borders
        ids = [str(gs[31].id)]
        c.add_geounits(4, ids, gl.id, c.version)
        c4 = max(District.objects.filter(plan=c,district_id=4),key=lambda d: d.version)
        intersections = d1.count_community_type_union(c.id)
        self.assertEqual(2, intersections, 'Detected incorrect number of community intersections. e:2;a:%d' % intersections)
        c4.tags = 'type=type_a type=type_b type=type_c'
        intersections = d1.count_community_type_union(c.id)
        self.assertEqual(3, intersections, 'Detected incorrect number of community intersections. e:3;a:%d' % intersections)

    def test_community_union_calculator(self):
        calc = CommunityTypeCounter()
        gl, gs = self.geolevel, list(Geounit.objects.filter(geolevel=self.geolevel).order_by("id"))
        p, c = self.plan, self.community

        # Create a basic district in the plan
        ids = map(lambda x: str(x.id), gs[21:24] + gs[30:33] + gs[39:42])
        p.add_geounits(1, ids, gl.id, p.version)
        d1 = max(District.objects.filter(plan=p,district_id=1),key=lambda d: d.version)

        # Check and make sure we get 0 intersections
        calc.compute(district=d1, community_map_id=c.id, version=c.version)
        self.assertEqual(0, calc.result['value'], 'Detected community intersections when there are none a:%s' % calc.result['value'])

        # C1 intersects on the left, half-in and half-out of d1 
        ids = map(lambda x: str(x.id), gs[29:31])
        c.add_geounits(1, ids, gl.id, c.version)
        c1 = max(District.objects.filter(plan=c,district_id=1),key=lambda d: d.version)
        c1.tags = 'type=type_a'
        calc.compute(district=d1, community_map_id=c.id, version=c.version)
        self.assertEqual(1, calc.result['value'], 'detected incorrect number of community calc.result. e:1;a:%s' % calc.result['value'])

        calc.compute(district=d1, community_map_id=-1, version=c.version)
        self.assertEqual('n/a', calc.result['value'], 'Did\'t get "n/a" when incorrect map_id used. a:%s' % calc.result['value'])

    def test_community_intersection(self):
        calc = CommunityTypeCompatible()
        gl, gs = self.geolevel, list(Geounit.objects.filter(geolevel=self.geolevel).order_by("id"))
        p, c = self.plan, self.community

        # Create a basic district in the plan
        ids = map(lambda x: str(x.id), gs[21:24] + gs[30:33] + gs[39:42])
        p.add_geounits(1, ids, gl.id, p.version)

        ids = map(lambda x: str(x.id), gs[18:21] + gs[27:30] + gs[36:39])
        p.add_geounits(2, ids, gl.id, p.version)
        d1 = max(District.objects.filter(plan=p,district_id=1),key=lambda d: d.version)
        d2 = max(District.objects.filter(plan=p,district_id=2),key=lambda d: d.version)

        # Check and make sure we get 0 intersections
        calc.compute(plan=p, community_map_id=c.id, type='junk')
        self.assertFalse(calc.result['value'], 'Detected community type compatibility when there is none a:%s' % calc.result['value'])

        # C1 intersects on the left, half-in and half-out of d1
        ids = map(lambda x: str(x.id), gs[29:31])
        c.add_geounits(1, ids, gl.id, c.version)
        c1 = max(District.objects.filter(plan=c,district_id=1),key=lambda d: d.version)
        c1.tags = 'type=type_a'
        calc.compute(plan=p, community_map_id=c.id, type='type_a')
        self.assertTrue(calc.result['value'], 'Detected no community type compatibility. a:%s' % calc.result['value'])

        # C2 is inside of d1 and shares a border
        ids = [str(gs[32].id)]
        c.add_geounits(2, ids, gl.id, c.version)
        c2 = max(District.objects.filter(plan=c,district_id=2),key=lambda d: d.version)
        c2.tags = 'type=type_b type=type_a'
        calc.compute(plan=p, community_map_id=c.id, type='type_a')
        self.assertTrue(calc.result['value'], 'Detected no community type compatibility. a:%s' % calc.result['value'])

        # C3 is outside of d1 and shares a border
        ids = [str(gs[56].id)]
        c.add_geounits(3, ids, gl.id, c.version)
        c3 = max(District.objects.filter(plan=c,district_id=3),key=lambda d: d.version)
        c3.tags = 'type=type_c type=type_a'
        calc.compute(plan=p, community_map_id=c.id, type='type_a')
        self.assertTrue(calc.result['value'], 'Detected no community type compatibility. a:%s' % calc.result['value'])

        # C4 is entirely within d1 and shares no borders
        ids = [str(gs[31].id)]
        c.add_geounits(4, ids, gl.id, c.version)
        c4 = max(District.objects.filter(plan=c,district_id=4),key=lambda d: d.version)
        c4.tags = 'type=type_b type=type_c'
        calc.compute(plan=p, community_map_id=c.id, type='type_b')
        self.assertFalse(calc.result['value'], 'Detected community compatibility when there is none. a:%s' % calc.result['value'])


class IterativeSimplificationTest(BaseTestCase):
    """
    Unit tests for iterative simplification of complex districts
    """
    fixtures = ['redistricting_testdata.json', 'redistricting_testdata_toughtosimplify.json']

    def setUp(self):
        """
        Set up the geolevels and proper tolerances
        """
        g1 = Geolevel.objects.get(name='smallest level')
        g1.tolerance = 100.0
        g1.save()

        g2 = Geolevel.objects.get(name='middle level')
        g2.tolerance = 160.0
        g2.save()

        g3 = Geolevel.objects.get(name='biggest level')
        g3.tolerance = 250.0
        g3.save()

        self.plan = Plan.objects.get(name='testPlan')

    def test_iterative_simplification(self):
        """
        This tests the iterative simplification.  District 16 in Ohio failed to simplify at the desired
        tolerance so this feature was added.  If a district can't be simplified in a given number of
        attempts (5 by default), the full geometry is used and an error is output

        This district doesn't simplify at 250 or 180 but does at 160.  The sixth poly of the multipoly
        is the most complex so we check that one for simplification
        """
        d = District.objects.get(long_label='District 16 from Ohio')

        [geolevel2, geolevel1, geolevel0] = self.plan.legislative_body.get_geolevels()

        # geolevel2, geolevel1, and geolevel0 are offset indexes of d.simple
        # d.simple is the GEOSGeometry object that represents the geometry
        # collection of the simplified district. The indexes of d.simple
        # directly relate to the geolevel ID. However, since GEOS 0-indexes
        # this collection, and postgis 1-indexes the collection, we have to
        # -1 the value when checking the simple collection

        d.simplify(attempts_allowed=0)
        self.assertTrue(d.geom.equals(d.simple[geolevel0.id-1]), "District was simplified when it shouldn't have been")
        self.assertTrue(d.geom.equals(d.simple[geolevel1.id-1]), "District was simplified when it shouldn't have been")
        self.assertTrue(d.geom.equals(d.simple[geolevel2.id-1]), "District was simplified when it shouldn't have been")

        d.simplify(attempts_allowed=1)
        self.assertTrue(len(d.geom.coords[6][0]) > len(d.simple[geolevel0.id-1].coords[0]), "District wasn't simplified")
        self.assertTrue(len(d.geom.coords[6][0]) > len(d.simple[geolevel1.id-1].coords[0]), "District wasn't simplified")
        self.assertTrue(d.geom.equals(d.simple[geolevel2.id-1]), "District was simplified when it shouldn't have been")

        d.simplify(attempts_allowed=3)
        self.assertTrue(len(d.geom.coords[6][0]) > len(d.simple[geolevel0.id-1].coords[6][0]), "District wasn't simplified")
        self.assertTrue(len(d.geom.coords[6][0]) > len(d.simple[geolevel1.id-1].coords[6][0]), "District wasn't simplified")
        self.assertTrue(len(d.geom.coords[6][0]) > len(d.simple[geolevel2.id-1].coords[6][0]), "District wasn't simplified")

class ReportCalculatorTestCase(BaseTestCase):
    """
    Unit tests for report calculators
    """
    fixtures = ['redistricting_testdata.json', 'redistricting_testdata_geolevel2.json', 'redistricting_testdata_geolevel3.json']
    
    def setUp(self):
        BaseTestCase.setUp(self)
        self.geolevel = Geolevel.objects.get(name='middle level')
        self.geounits = list(Geounit.objects.filter(geolevel=self.geolevel).order_by('id'))
        self.subject1 = Subject.objects.get(name='TestSubject')
        self.subject2 = Subject.objects.get(name='TestSubject2')

        # add some geounits
        dist1id = self.district1.district_id
        dist1ids = self.geounits[0:3] + self.geounits[9:12]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits( self.district1.district_id, dist1ids, self.geolevel.id, self.plan.version)
        self.district1 = max(District.objects.filter(plan=self.plan,district_id=dist1id),key=lambda d: d.version)
    
    def tearDown(self):
        self.geolevel = None
        self.geounits = None
        self.subject1 = None
        self.subject2 = None
        BaseTestCase.tearDown(self)

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


from redistricting.management.commands.setup import Command
from redistricting.config import ConfigImporter
from redistricting import StoredConfig
class RegionConfigTest(BaseTestCase):
    """ 
    Test the configuration options
    """

    fixtures = []
    def setUp(self):
        self.store = StoredConfig('../../docs/config.dist.xml')
        self.store.validate()
        self.cmd = Command()

    def test_get_largest_geolevel(self):
        region1 = self.store.filter_regions()[0]
        region2 = self.store.filter_regions()[1]

        def get_largest_geolevel(region_node):
            def get_youngest_child(node):
                if len(node) == 0:
                    return node
                else:
                    return get_youngest_child(node[0])

            geolevels = self.store.get_top_regional_geolevel(region_node)
            if len(geolevels) > 0:
                return get_youngest_child(geolevels[0]).get('ref')

        bg1 = get_largest_geolevel(region1)
        bg2 = get_largest_geolevel(region2)

        self.assertEqual('county', bg1, "Didn't get correct geolevel")
        self.assertEqual('vtd', bg2, "Didn't get correct geolevel")
        
    def test_get_or_create_regional_geolevels(self):
        self.cmd.import_prereq(ConfigImporter(self.store), False)

        expected_geolevels = ['county', 'vtd', 'block', 'va_county', 'va_vtd', 'va_block',
            'dc_vtd', 'dc_block']
        all_geolevels = Geolevel.objects.all()

        self.assertEqual(len(expected_geolevels), len(all_geolevels),
            "Didn't return correct number of geolevels")
        for geolevel in expected_geolevels:
            self.assertTrue(reduce(lambda x,y: x or y.name == geolevel, all_geolevels, False),
                "Regional geolevel %s not created" % geolevel)

    def test_filter_functions(self):
        function_dict = self.cmd.create_filter_functions(self.store)
        self.assertEqual(2, len(function_dict), 'No filter functions found')

        shapefile = 'redistricting/testdata/test_data.shp'
        test_layer = DataSource(shapefile)[0]

        va = dc = 0
        for feat in test_layer:
            geolevels = []
            for key, value in function_dict.iteritems():
                for filter_function in value:
                    if filter_function(feat) == True:
                        geolevels.append(key)
                        break

            if len(geolevels) == 2:
                self.assertTrue('dc' in geolevels, "Regional feature not found in unfiltered geolevel")
                self.assertTrue('va' in geolevels, "Unfiltered feature not found in unfiltered geolevel")
                va += 1
                dc += 1
            elif len(geolevels) == 1:
                self.assertTrue('va' in geolevels, "Regional feature not found in unfiltered geolevel")
                va += 1
            else:
                self.fail("Incorrect number of geolevels returned - should never get here")
        self.assertEqual(1, dc, "Incorrect number of geolevels found for region")
        self.assertEqual(3, va, "Incorrect number of geolevels found for unfiltered region")

    def tearDown(self):
        self.region_tree = None

class ConfigTestCase(TestCase):
    good_data_filename = '../../docs/config.dist.xml'
    good_schema_filename = '../../docs/config.xsd'
    bad_data_filename = '/tmp/bad_data.xsd'
    bad_schema_filename = '/tmp/bad_schema.xsd'

    def setUp(self):
        logging.basicConfig(level=logging.ERROR)

    def make_simple_schema(self):
        test_schema = tempfile.NamedTemporaryFile(delete=False)
        test_schema.write('<?xml version="1.0" encoding="utf-8"?>\n')
        test_schema.write('<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">\n')
        test_schema.write('<xs:element name="DistrictBuilder"/>\n')
        test_schema.write('</xs:schema>')
        test_schema.close()

        return test_schema

    """
    Test the Config classes.
    """
    def test_constructor_missing_schema(self):
        try:
            x = StoredConfig(self.bad_data_filename, schema=self.bad_schema_filename)
            self.fail('Expected failure when passing nonexistant filenames to constructor.')
        except:
            pass

    def test_construct_missing_data(self):
        try:
            x = StoredConfig(self.bad_data_filename, schema=self.good_schema_filename)
            self.fail('Expected failure when passing nonexistant filenames to constructor.')
        except:
            pass

    def test_construct_okay(self):
        x = StoredConfig(self.good_data_filename, schema=self.good_schema_filename)

        self.assertEqual(x.datafile, self.good_data_filename, 'Configuration data is not correct.')
        self.assertEqual(x.schemafile, self.good_schema_filename, 'Configuration schema is not correct.')

    def test_validation_schema_xml_parser(self):
        test_schema = tempfile.NamedTemporaryFile(delete=False)
        test_schema.write('<?xml version="1.0" encoding="utf-8"?>\n')
        test_schema.write('<DistrictBuilder><junk></DistrictBuilder>\n')
        test_schema.close()

        x = StoredConfig(self.good_data_filename, schema=test_schema.name)
        is_valid = x.validate()

        os.remove(test_schema.name)

        self.assertFalse(is_valid, 'Configuration schema was not valid.')

    def test_validation_schema_xml_wellformed(self):
        test_schema = tempfile.NamedTemporaryFile(delete=False)
        test_schema.write('<?xml version="1.0" encoding="utf-8"?>\n')
        test_schema.write('<DistrictBuilder><junk/></DistrictBuilder>\n')
        test_schema.close()

        x = StoredConfig(self.good_data_filename, schema=test_schema.name)
        is_valid = x.validate()

        os.remove(test_schema.name)

        self.assertFalse(is_valid, 'Configuration schema was not valid.')

    def test_validation_schema_xml(self):
        test_schema = self.make_simple_schema()

        x = StoredConfig(self.good_data_filename, schema=test_schema.name)
        is_valid = x.validate()

        os.remove(test_schema.name)

        self.assertTrue(is_valid, 'Configuration schema should be valid.')

    def test_validation_data_xml_parser(self):
        test_schema = self.make_simple_schema()

        test_data = tempfile.NamedTemporaryFile(delete=False)
        test_data.write('<?xml version="1.0" encoding="utf-8"?>\n')
        test_data.write('<DistrictBuilder><junk></DistrictBuilder>\n')
        test_data.close()

        x = StoredConfig(test_data.name, schema=test_schema.name)
        is_valid = x.validate()

        os.remove(test_data.name)
        os.remove(test_schema.name)

        self.assertFalse(is_valid, 'Configuration data was not valid.')

    def test_validation_data_xml_wellformed(self):
        test_schema = self.make_simple_schema()
        test_data = tempfile.NamedTemporaryFile(delete=False)
        test_data.write('<?xml version="1.0" encoding="utf-8"?>\n')
        test_data.write('<DistrictBuilder><junk/></DistrictBuilder>\n')
        test_data.close()

        x = StoredConfig(test_data.name, schema=test_schema.name)
        is_valid = x.validate()

        os.remove(test_data.name)
        os.remove(test_schema.name)

        self.assertTrue(is_valid, 'Configuration data was not valid.')

    def test_validation(self):
        x = StoredConfig(self.good_data_filename, schema=self.good_schema_filename)

        is_valid = x.validate()

        self.assertTrue(is_valid, 'Configuration schema and data should be valid and should validate successfully.')
