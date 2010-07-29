import unittest
from django.test.client import Client
from django.contrib.gis.geos import *
from django.contrib.auth.models import User
from publicmapping.redistricting.models import *
from django.conf import settings

class RedistrictingTest(unittest.TestCase):

    def setUp(self):
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

        """ Here are some multipolys that emulate our tiered setup
        b1 = a1 + a2 + a3
        b2 = a4 + a5
        """
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
        geounit_a1.save()
        self.geounit_a1 = geounit_a1

        geounit_a2 = Geounit(name="a2", geolevel = self.levela)
        geounit_a2.geom = a2
        geounit_a2.simple = a2
        geounit_a2.save()
        self.geounit_a2 = geounit_a2

        geounit_a3 = Geounit(name="a3", geolevel = self.levela)
        geounit_a3.geom = a3
        geounit_a3.simple = a3
        geounit_a3.save()
        self.geounit_a3 = geounit_a3

        geounit_a4 = Geounit(name="a4", geolevel = self.levela)
        geounit_a4.geom = a4
        geounit_a4.simple = a4
        geounit_a4.save()
        self.geounit_a4 = geounit_a4

        geounit_a5 = Geounit(name="a5", geolevel = self.levela)
        geounit_a5.geom = a5
        geounit_a5.simple = a5
        geounit_a5.save()
        self.geounit_a5 = geounit_a5

        geounit_b1 = Geounit(name="b1", geolevel = self.levelb)
        geounit_b1.geom = b1
        geounit_b1.simple = b1
        geounit_b1.save()
        self.geounit_b1 = geounit_b1

        geounit_b2 = Geounit(name="b2", geolevel = self.levelb)
        geounit_b2.geom = b2
        geounit_b2.simple = b2
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
        DistrictGeounitMapping.objects.filter(plan = self.p).delete()
        self.p.delete()
        self.user.delete()

    def test_initial_geounit_set(self):
        unassigned = DistrictGeounitMapping.objects.filter(plan = self.p)
        self.assertEqual(5, unassigned.count(), "Expected 5, got %s geounits placed in unassigned to start %s" % (unassigned.count(), unassigned))

    def test_add_to_plan(self):
        self.p.add_geounits(self.d2.district_id, ( self.geounit_b1.id, ), self.levelb.id)        
        geounits = DistrictGeounitMapping.objects.filter(district = self.d2)
        self.assertEqual(3, geounits.all().count(), 'Geounit count not correct after adding larger geounit, expected 3, got ' + str(geounits.all().count()))
        self.assertEqual(1, geounits.filter(geounit = self.geounit_a1).count(), "Geounit a1 not in set after enclosing geounit added")
        self.p.add_geounits(self.d2.district_id, ( self.geounit_a4.id, ), self.levela.id)
        geounits = DistrictGeounitMapping.objects.filter(district = self.d2)
        self.assertEqual(4, geounits.all().count(), 'Geounit count not correct after adding single geounit')

    def test_get_base_geounits(self):
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
        self.p.add_geounits(self.d2.district_id, ( self.geounit_b1.id, ), self.levelb.id)        
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
        unassigned = District.objects.filter(name="Unassigned", plan = self.p)
        self.assertEqual(1, unassigned.count(), 'New Plan didn\'t have one value on saving')
        district_map = DistrictGeounitMapping.objects.filter(plan = self.p, district = unassigned)
        base_geounit_count = Geounit.objects.filter(geolevel = settings.BASE_GEOLEVEL).count()
        self.assertEqual(district_map.count(), base_geounit_count, 'Test plan was not mapped to all districts on saving') 
