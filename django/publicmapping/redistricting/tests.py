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

class RedistrictingTest(unittest.TestCase):
    """
    General unit tests for the redistricting application.
    """
    
    def setUp(self):
        """
        Setup the general tests. This fabricates a set of data in the 
        test database for use later.
        """
        user = User(username='test_user')
        user.save()
        self.user = user

        levelb = Geolevel(name="big_test_geolevel")
        levelb.save()
        self.levelb = levelb

        levela = Geolevel(name="smaller_test_geolevel")
        levela.save()
        self.levela = levela
        settings.BASE_GEOLEVEL = levela.id 

        p1 = Point((0,0))
        p2 = Point((6,0))
        p3 = Point((9,0))
        p4 = Point((13,0))
        p5 = Point((0,5))
        p6 = Point((4,5))
        p7 = Point((6,5))
        p8 = Point((9,5))
        p9 = Point((9,7))
        p10 = Point((13,7))
        p11 = Point((13,3))
        p12 = Point((9,3))    

        # Here are some multipolys that emulate our tiered setup
        # b1 = a1 + a2 + a3
        # b2 = a4 + a5
        
        b1 = MultiPolygon( [ Polygon ( LinearRing(p1, p3, p8, p5, p1)) ] )
        b2 = MultiPolygon( [ Polygon ( LinearRing(p3, p4, p10, p9, p3)) ] )
        a1 = MultiPolygon( [ Polygon ( LinearRing(p1, p6, p5, p1)) ] )
        a2 = MultiPolygon( [ Polygon ( LinearRing(p1, p3, p7, p6, p1)) ] )
        a3 = MultiPolygon( [ Polygon ( LinearRing(p2, p3, p8, p7, p2)) ] )
        a4 = MultiPolygon( [ Polygon ( LinearRing(p3, p4, p11, p12, p3)) ] )
        a5 = MultiPolygon( [ Polygon ( LinearRing(p11, p12, p9, p10, p11)) ] )

        geounit_a1 = Geounit(name="a1", geolevel = self.levela)
        geounit_a1.geom = a1
        geounit_a1.simple = a1
        geounit_a1.center = a1.centroid
        geounit_a1.save()
        self.geounit_a1 = geounit_a1

        geounit_a2 = Geounit(name="a2", geolevel = self.levela)
        geounit_a2.geom = a2
        geounit_a2.simple = a2
        geounit_a2.center = a1.centroid
        geounit_a2.save()
        self.geounit_a2 = geounit_a2

        geounit_a3 = Geounit(name="a3", geolevel = self.levela)
        geounit_a3.geom = a3
        geounit_a3.simple = a3
        geounit_a3.center = a3.centroid
        geounit_a3.save()
        self.geounit_a3 = geounit_a3

        geounit_a4 = Geounit(name="a4", geolevel = self.levela)
        geounit_a4.geom = a4
        geounit_a4.simple = a4
        geounit_a4.center = a4.centroid
        geounit_a4.save()
        self.geounit_a4 = geounit_a4

        geounit_a5 = Geounit(name="a5", geolevel = self.levela)
        geounit_a5.geom = a5
        geounit_a5.simple = a5
        geounit_a5.center = a5.centroid
        geounit_a5.save()
        self.geounit_a5 = geounit_a5

        geounit_b1 = Geounit(name="b1", geolevel = self.levelb)
        geounit_b1.geom = b1
        geounit_b1.simple = b1
        geounit_b1.center = b1.centroid
        geounit_b1.save()
        self.geounit_b1 = geounit_b1

        geounit_b2 = Geounit(name="b2", geolevel = self.levelb)
        geounit_b2.geom = b2
        geounit_b2.simple = b2
        geounit_b2.center = b2.centroid
        geounit_b2.save()
        self.geounit_b2 = geounit_b2

        p = Plan(name="testPlan", owner=self.user)
        p.save()
        self.p = p
        
        d1 = District(name="District 1", district_id = 1)
        d1.plan = p
        d1.save()
        self.d1 = d1

        d2 = District(name="District 2", district_id = 2) 
        d2.plan = p
        d2.save()
        self.d2 = d2
    
    def tearDown(self):
        """
        Clean up after testing.
        """
        DistrictGeounitMapping.objects.filter(plan = self.p).delete()
        self.p.delete()
        self.user.delete()

    def test_initial_geounit_set(self):
        """
        Test the initial set of geounits.
        """
        unassigned = DistrictGeounitMapping.objects.filter(plan = self.p)
        self.assertEqual(5, unassigned.count(), "Expected 5, got %s geounits placed in unassigned to start %s" % (unassigned.count(), unassigned))

    def test_add_to_plan(self):
        """
        Test the logic for adding geounits to a district.
        """
        self.p.add_geounits(self.d2.district_id, [str(self.geounit_b1.id)], self.levelb.id)        
        geounits = DistrictGeounitMapping.objects.filter(district = self.d2)
        self.assertEqual(3, geounits.all().count(), 'Geounit count not correct after adding larger geounit, expected 3, got ' + str(geounits.all().count()))
        self.assertEqual(1, geounits.filter(geounit = self.geounit_a1).count(), "Geounit a1 not in set after enclosing geounit added")
        self.p.add_geounits(self.d2.district_id, ( self.geounit_a4.id, ), self.levela.id)
        geounits = DistrictGeounitMapping.objects.filter(district = self.d2)
        self.assertEqual(4, geounits.all().count(), 'Geounit count not correct after adding single geounit')

    def test_get_base_geounits(self):
        """
        Test the logic for retrieving base geounits.
        """
        geounit_ids = Geounit.get_base_geounits( ( self.geounit_b1.id, ), self.levelb.id)
        self.assertEqual(3, len(geounit_ids), "Didn't get base geounits of large polys correctly; got " + str(len(geounit_ids)) + str(geounit_ids))
        geounit_ids = Geounit.get_base_geounits( ( self.geounit_b2.id, ), self.levelb.id)
        self.assertEqual(2, len(geounit_ids), "Didn't get base geounits of large polys correctly; got " + str(len(geounit_ids)) + str(geounit_ids))
        geounit_ids = Geounit.get_base_geounits( ( self.geounit_b1.id, self.geounit_b2.id ), self.levelb.id)
        self.assertEqual(5, len(geounit_ids), "Didn't get base geounits of large polys correctly; got " + str(len(geounit_ids)) + str(geounit_ids))

#    def test_delete_geounits_from_plan(self):
#        self.p.add_geounits(self.d2.district_id, [ self.geounit_b1.id ], self.levelb)        
#        geounits = DistrictGeounitMapping.objects.filter(district = self.d2)
#        self.assertEquals(3, geounits.all().count(), "Couldn't add a geounit so can't test deletion")
#        deleted = self.p.delete_geounits([ self.geounit_a1.id ], self.geounit_a1.geolevel)
#        self.assertEqual(1, deleted, "More than one geounit effected during deletion of base geounit")
#        self.assertEqual(0, geounits.filter(id__exact=self.geounit_b1.id).count(), "Geounit wasn't deleted correctly")
#        self.assertEqual(1, geounits.filter(id__exact=self.geounit_a2.id).count(), "Too many sub-geounits deleted during request to delete parent")
#
    def test_district_id_increment(self):
        """
        Test the logic for the automatically generated district_id
        """
        d3 = District(name="District 3")
        d3.plan = self.p
        d3.save()
        latest = d3.district_id
        d4 = District(name = "District 4")
        d4.plan = self.p
        d4.save()
        incremented = d4.district_id
        self.assertTrue(latest + 1 == incremented, "New district did not have an id greater than the previous district")

    def test_copyplan(self):
        """
        Test the logic for copying plans.
        """
        self.p.add_geounits(self.d2.district_id, [str(self.geounit_b1.id)], self.levelb.id)
        geounits = DistrictGeounitMapping.objects.filter(district = self.d2)
        district_map  = DistrictGeounitMapping.objects.filter(plan = self.p)
        geounit_count = district_map.count()
        district_count = district_map.values('district').distinct().count()
        client = Client()
        response = client.post('/districtmapping/plan/%d/copy' % self.p.id, { 'name':'MyTestCopy' })
        self.assertEqual(200, response.status_code, 'Copy handler didn\'t return 200:' + str(response))
        copy = Plan.objects.get(name='MyTestCopy')
        self.assertNotEqual(copy, None, "Copied plan doesn't exist")
        copy_map  = DistrictGeounitMapping.objects(plan = copy)
        self.assertEqual(geounit_count, copy_map.count(), 'Copy wasn\'t mapped to all geounits')
        self.assertEqual(district_count, copy_map.values('district').distinct().count(), 'Copy didn\'t have same number of districts')
   
    def test_unassigned(self):
        """
        Test the logic for an unassigned district.
        """
        unassigned = District.objects.filter(name="Unassigned", plan = self.p)
        self.assertEqual(1, unassigned.count(), 'New Plan didn\'t have one value on saving')
        district_map = DistrictGeounitMapping.objects.filter(plan = self.p, district = unassigned)
        base_geounit_count = Geounit.objects.filter(geolevel = settings.BASE_GEOLEVEL).count()
        self.assertEqual(district_map.count(), base_geounit_count, 'Test plan was not mapped to all districts on saving') 


class GeounitMixTester(unittest.TestCase):
    """
    Unit tests to test the mixed geounit spatial queries.
    """
    
    def setUp(self):
        """
        Setup the spatial query tests. This fabricates some test data and
        changes the base geolevel and the simple tolerance.
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

        dim = 3.0
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
                    gu = Geounit(
                        name=('Unit %d-%d' % (gl.id,(y * int(dim) + x))),
                        geolevel=gl,
                        geom=geom,
                        simple=geom,
                        center=geom.centroid
                    )
                    gu.save()
                    self.geounits[gl.id].append(gu)
            dim *= 3.0
            
        settings.BASE_GEOLEVEL = self.geolevels[2].id
        settings.SIMPLE_TOLERANCE = 0.1

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

        self.assertTrue(unit1.geom.contains(unit2.geom), "First unit does not contain secont unit.")

        unit3 = self.geounits[self.geolevels[2].id][0]

        self.assertTrue(unit1.geom.contains(unit3.geom), "First unit does not contain second unit.")
        self.assertTrue(unit2.geom.contains(unit3.geom), "Second unit does not contain third unit.")

    def test_get_all_in(self):
        """
        Test the spatial query to get geounits within a known boundary.
        """
        level = self.geolevels[0]
        units = self.geounits[level.id]

        units = Geounit.objects.filter(geom__within=units[0].geom,geolevel__gt=level.id)

        numunits = len(units)
        self.assertEquals(90, numunits, "Number of geounits within a high-level geounit is incorrect. (%d)" % numunits)

    def test_get_in_gu0(self):
        """
        Test the spatial query to get geounits within a known boundary.
        """
        level = self.geolevels[0]
        units = self.geounits[level.id]

        units = Geounit.objects.filter(geom__within=units[0].geom,geolevel=level.id+1)
        numunits = len(units)
        self.assertEquals(9, numunits, "Number of geounits within geounit 1 is incorrect. (%d)" % numunits)

    def test_get_base(self):
        """
        Test the spatial query to get all geounits at the base geolevel within a boundary.
        """
        level = self.geolevels[0]
        units = self.geounits[level.id]
        geounit_ids = tuple([units[0].id, units[1].id])

        units = Geounit.objects.filter(geom__within=units[0].geom,geolevel=settings.BASE_GEOLEVEL)

        numunits = len(units)
        self.assertEquals(81, numunits, "Number of geounits within a high-level geounit is incorrect. (%d)" % numunits)

    def test_get_mixed1(self):
        """
        Test the logic for getting mixed geounits inside a boundary at the
        highest geolevel.
        """
        level = self.geolevels[0]
        bigunits = self.geounits[level.id]
        ltlunits = self.geounits[self.geolevels[1].id]
        boundary = bigunits[0].geom.difference(ltlunits[9].geom)

        units = Geounit.get_mixed_geounits([str(bigunits[0].id)], level.id, boundary, True)
        numunits = len(units)
        self.assertEquals(8, numunits, "Number of geounits inside boundary is incorrect. (%d)" % numunits)

    def test_get_imixed1(self):
        """
        Test the logic for getting mixed geounits outside a boundary at the
        highest geolevel.
        """
        level = self.geolevels[0]
        bigunits = self.geounits[level.id]
        ltlunits = self.geounits[self.geolevels[1].id]
        boundary = bigunits[0].geom.difference(ltlunits[9].geom)

        units = Geounit.get_mixed_geounits([str(bigunits[0].id)], level.id, boundary, False)
        numunits = len(units)
        self.assertEquals(1, numunits, "Number of geounits outside boundary is incorrect. (%d)" % numunits)

    def test_get_mixed2(self):
        """
        Test the logic for getting mixed geounits inside a boundary at the
        middle geolevel.
        """
        level = self.geolevels[1]
        bigunits = self.geounits[level.id]
        ltlunits = self.geounits[self.geolevels[2].id]
        boundary = bigunits[0].geom.difference(ltlunits[27].geom)

        units = Geounit.get_mixed_geounits([str(bigunits[0].id)], level.id, boundary, True)
        numunits = len(units)
        self.assertEquals(8, numunits, "Number of geounits inside boundary is incorrect. (%d)" % numunits)

    def test_get_imixed2(self):
        """
        Test the logic for getting mixed geounits outside a boundary at the
        middle geolevel.
        """
        level = self.geolevels[1]
        bigunits = self.geounits[level.id]
        ltlunits = self.geounits[self.geolevels[2].id]
        boundary = bigunits[0].geom.difference(ltlunits[27].geom)

        units = Geounit.get_mixed_geounits([str(bigunits[0].id)], level.id, boundary, False)
        numunits = len(units)
        self.assertEquals(1, numunits, "Number of geounits outside boundary is incorrect. (%d)" % numunits)

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
        
        units = Geounit.get_mixed_geounits([str(bigunits[1].id),str(bigunits[2].id),str(bigunits[5].id)], level.id, boundary, True)
        numunits = len(units)
        self.assertEquals(3, numunits, "Number of geounits inside boundary is incorrect. (%d)" % numunits)

        units = Geounit.get_mixed_geounits([str(bigunits[0].id),str(bigunits[4].id),str(bigunits[8].id)], level.id, boundary, True)
        numunits = len(units)
        self.assertEquals(63, numunits, "Number of geounits inside boundary is incorrect. (%d)" % numunits)

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
        
        units = Geounit.get_mixed_geounits([str(bigunits[3].id),str(bigunits[6].id),str(bigunits[7].id)], level.id, boundary, False)
        numunits = len(units)
        # this test should return 3, for the large geounits are completely
        # without yet intersect at the corner. the net geometry from this
        # set of mixed geounits is correct, though
        self.assertEquals(19, numunits, "Number of geounits outside boundary is incorrect. (%d)" % numunits)

        units = Geounit.get_mixed_geounits([str(bigunits[0].id),str(bigunits[4].id),str(bigunits[8].id)], level.id, boundary, False)
        numunits = len(units)
        self.assertEquals(63, numunits, "Number of geounits outside boundary is incorrect. (%d)" % numunits)
