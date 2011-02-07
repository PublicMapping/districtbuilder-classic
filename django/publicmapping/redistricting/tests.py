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
    Andrew Jennings, David Zwarg
"""

import unittest
from django.test.client import Client
from django.contrib.gis.geos import *
from django.contrib.auth.models import User
from publicmapping.redistricting.models import *
from django.conf import settings
from datetime import datetime

class BaseTestCase(unittest.TestCase):
    """
    Only contains setUp and tearDown, which are shared among all other TestCases
    """

    def setUp(self):
        """
        Setup the general tests. This fabricates a set of data in the 
        test database for use later.
        """
        self.longMessage = True

        # need geounits for ids & geometries
        self.geolevels = Geolevel.objects.filter( 
            Q(name='first level') |
            Q(name='second level') |
            Q(name='third level')
        ).order_by('id')
        if len(self.geolevels) == 0:
            self.geolevels = [
                Geolevel(name='first level'),
                Geolevel(name='second level'),
                Geolevel(name='third level')
            ]
        else:
            self.geolevels = list(self.geolevels)

        self.geounits = {}

        # create a three-tiered 27x27 square grid of geounits with coords from (0,0) to (1,1)
        dim = 3.0
        lastgl = None
        supp_id = 0
        for gl in self.geolevels:
            if not gl.id:
                gl.save()

            self.geounits[gl.id] = list(Geounit.objects.filter(geolevel=gl).order_by('id'))
            if len(self.geounits[gl.id]) > 0:
                continue

            for y in range(0,int(dim)):
                for x in range(0,int(dim)):
                    geom = MultiPolygon(Polygon(LinearRing( 
                        Point(((x/dim),(y/dim))), 
                        Point((((x+1)/dim),(y/dim))), 
                        Point((((x+1)/dim),((y+1)/dim))), 
                        Point(((x/dim),((y+1)/dim))), 
                        Point(((x/dim),(y/dim))) )))
                    geom.srid = 3785
                    try:
                        child = Geounit.objects.get(geolevel=lastgl,geom__contains=geom.centroid)
                    except:
                        child = None
                    gu = Geounit(
                        name=('Unit %d-%d' % (gl.id,(y * int(dim) + x))),
                        geolevel=gl,
                        geom=geom,
                        simple=geom,
                        center=geom.centroid,
                        child=child,
                        portable_id="%07d" % supp_id,
                        tree_code="%07d" % supp_id
                    )
                    gu.save()
                    self.geounits[gl.id].append(gu)
                    supp_id += 1
            lastgl = gl
            dim *= 3.0

        # create a User
        self.username = 'test_user'
        self.password = 'secret'
        self.user = User(username=self.username)
        self.user.set_password(self.password)
        self.user.save()

        # create a LegislativeBody
        self.legbod = LegislativeBody(name='TestLegislativeBody', member='TestMember', max_districts=20)
        self.legbod.save()

        # create a Subject
        self.subject = Subject(name='TestSubject')
        self.subject.save()
        
        # create a Target
        self.target = Target(subject=self.subject, range1=1, range2=5, value=3)
        self.target.save()

        # create a LegislativeDefault
        self.legdef = LegislativeDefault(legislative_body=self.legbod, target=self.target)
        self.legdef.save()

        # create LegislativeLevel hierarchy
        self.leglev3 = LegislativeLevel(geolevel=self.geolevels[2], legislative_body=self.legbod, target=self.target)
        self.leglev3.save()
        self.leglev2 = LegislativeLevel(geolevel=self.geolevels[1], legislative_body=self.legbod, target=self.target, parent=self.leglev3)
        self.leglev2.save()
        self.leglev1 = LegislativeLevel(geolevel=self.geolevels[0], legislative_body=self.legbod, target=self.target, parent=self.leglev2)
        self.leglev1.save()
        
        # create a Plan
        self.plan = Plan(name='testPlan', owner=self.user, legislative_body=self.legbod)
        self.plan.save()

        # create Districts
        self.district1 = District(name='District 1', district_id = 0)
        self.district1.plan = self.plan
        self.district1.save()
        self.district2 = District(name='District 2', district_id = 0) 
        self.district2.plan = self.plan
        self.district2.save()
    
    def tearDown(self):
        """
        Clean up after testing.
        """
        self.plan.delete()
        self.user.delete()
        self.legbod.delete()
        self.subject.delete()
        self.target.delete()
        self.legdef.delete()
        self.leglev3.delete()
        self.leglev2.delete()
        self.leglev1.delete()
        self.district1.delete()
        self.district2.delete()
        # Keep the geolevels/units around. They are too expensive to create and delete each time.
            
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
        d3 = District(name='District 3',district_id=0)
        d3.plan = self.plan
        d3.save()
        latest = d3.district_id
        d4 = District(name = 'District 4',district_id=0)
        d4.plan = self.plan
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
        cursor = self.plan.district_mapping_cursor()
        numunits = len(cursor.fetchall())
        cursor.close()
        self.assertEqual(81, numunits, 'Geounits not added to plan correctly')

    def test_unassigned(self):
        """
        Test the logic for an unassigned district.
        """
        unassigned = District.objects.filter(name='Unassigned', plan = self.plan)
        self.assertEqual(1, unassigned.count(), 'No Unassigned district on plan')

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
        self.assertEqual(numdistricts, numdistrictscopy, 'Districts between original and copy are different')

        # Ensure geounits are the same between plans
        cursor = self.plan.district_mapping_cursor()
        numunits = len(cursor.fetchall())
        cursor.close()
        cursor = copy.district_mapping_cursor()
        numunitscopy = len(cursor.fetchall())
        cursor.close()
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
        cursor = self.plan.district_mapping_cursor()
        numunits = len(cursor.fetchall())
        cursor.close()
        self.assertEqual(0, numunits, 'Geounits were added to a locked district. Num geounits: %d' % numunits)
        
        # Issue unlock command
        response = client.post('/districtmapping/plan/%d/district/%d/lock/' % (self.plan.id, district_id), { 'lock':False, 'version':self.plan.version })
        self.assertEqual(200, response.status_code, 'Lock handler didn\'t return 200:' + str(response))

        # Ensure lock has been removed
        district = District.objects.get(pk=districtid)
        self.assertFalse(district.is_locked, 'District wasn\'t unlocked.' + str(response))

        # Add geounits to the plan
        self.plan.add_geounits(district_id, geounitids, levelid, self.plan.version)
        cursor = self.plan.district_mapping_cursor()
        numunits = len(cursor.fetchall())
        cursor.close()
        self.assertEqual(81, numunits, 'Geounits could not be added to an unlocked district. Num geounits: %d' % numunits)


# This test is commented out, because get_base_geounits has also been commented out.
# If get_base_geounits becomes uncommented, and starts being used, this test should be reactivated.        
#    def test_get_base_geounits(self):
#        """
#        Test the logic for retrieving base geounits.
#        """
#        geounit_ids = Geounit.get_base_geounits( ( self.geounit_b1.id, ), self.levelb.id)
#        self.assertEqual(3, len(geounit_ids), "Didn't get base geounits of large polys correctly; got " + str(len(geounit_ids)) + str(geounit_ids))
#        geounit_ids = Geounit.get_base_geounits( ( self.geounit_b2.id, ), self.levelb.id)
#        self.assertEqual(2, len(geounit_ids), "Didn't get base geounits of large polys correctly; got " + str(len(geounit_ids)) + str(geounit_ids))
#        geounit_ids = Geounit.get_base_geounits( ( self.geounit_b1.id, self.geounit_b2.id ), self.levelb.id)
#        self.assertEqual(5, len(geounit_ids), "Didn't get base geounits of large polys correctly; got " + str(len(geounit_ids)) + str(geounit_ids))


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

class GeounitBaseTestCase(BaseTestCase):
    def get_max_extent(self,level):
        """
        A helper method to get the maximum extents of all geographic
        units.

        Parameters:
            None

        Returns:
            The maximum extent as a MultiPolygon with an SRID of 3785.
        """
        geolevel = self.legbod.get_geolevels()[level]
        ext = Geounit.objects.filter(geolevel=geolevel).extent()
        boundary = MultiPolygon(Polygon(LinearRing(
            Point((ext[0],ext[1])),
            Point((ext[2],ext[1])),
            Point((ext[2],ext[3])),
            Point((ext[0],ext[3])),
            Point((ext[0],ext[1]))
        )))
        boundary.srid = 3785
        return boundary

    def get_base_within(self, level):
        """
        A helper test method to get the base geounits within a geometry.
        This method starts at the given geographic level, and drills its
        way down.

        This method asserts that all the base geounits were found, no matter
        which geolevel is passed.

        Parameters:
            level - The geographic level to start searching.
        """
        boundary = self.get_max_extent(level)
        units = Geounit.get_base_geounits_within(boundary, self.legbod)
        numunits = len(units)
        self.assertEquals(729, numunits, "Number of geounits is incorrect. (%d)" % numunits)

    def test_get_base_within0(self):
        self.get_base_within(0)

    def test_get_base_within1(self):
        self.get_base_within(1)

    def test_get_base_within2(self):
        self.get_base_within(2)

    def get_base_from_child(self, units, expected):
        baseunits = Geounit.get_base_geounits(units,self.legbod)
        numunits = len(baseunits)

        self.assertEquals(expected, numunits, 'Number of base geounits is incorrect. (%d)' % numunits)

    def test_get_base_from_child0(self):
        geolevel = self.legbod.get_geolevels()[0]
        units = self.geounits[geolevel.id][0:1]

        self.get_base_from_child(units, 81)
       
    def test_get_base_from_child1(self):
        geolevel = self.legbod.get_geolevels()[1]
        units = self.geounits[geolevel.id][0:1]

        self.get_base_from_child(units, 9)

    def test_get_base_from_child2(self):
        geolevel = self.legbod.get_geolevels()[2]
        units = self.geounits[geolevel.id][0:1]

        self.get_base_from_child(units, 1)

    def test_get_base_from_child_dupes(self):
        geolevels = self.legbod.get_geolevels()
        units = self.geounits[geolevels[0].id][0:1] + \
            self.geounits[geolevels[1].id][0:1] + \
            self.geounits[geolevels[2].id][0:1]

        self.get_base_from_child(units, 81)

    def test_get_base_from_child_eachlevel(self):
        geolevels = self.legbod.get_geolevels()
        units = self.geounits[geolevels[0].id][0:1] + \
            self.geounits[geolevels[1].id][3:4] + \
            self.geounits[geolevels[2].id][12:13]

        self.get_base_from_child(units, 91)

    def test_time_within_vs_child(self):
        level = self.geolevels[0]
        bigunits = self.geounits[level.id]
        ltlunits = self.geounits[self.geolevels[2].id]
        ltlunits = ltlunits[0:len(ltlunits)/2]
        ltlunits = map(lambda x: str(x.id), ltlunits)

        boundary = Geounit.objects.filter(id__in=ltlunits).unionagg()

        t1 = datetime.now()
        units1 = list(Geounit.get_base_geounits_within(boundary, self.legbod))
        t2 = datetime.now()

        bigunits = map(lambda x: str(x.id), bigunits)

        t1 = datetime.now()
        units2 = Geounit.get_mixed_geounits(bigunits, self.legbod, level.id, boundary, True)
        t2 = datetime.now()
        units2 = list(Geounit.get_base_geounits(units2, self.legbod))
        t3 = datetime.now()

        self.assertEquals( len(units1), len(units2), 'Number of units for two methods is incorrect.')
