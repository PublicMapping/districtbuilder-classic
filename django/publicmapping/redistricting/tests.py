import unittest
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
        geounit_a1.save()
        self.geounit_a1 = geounit_a1

        geounit_a2 = Geounit(name="a2", geolevel = self.levela)
        geounit_a2.geom = a2
        geounit_a2.save()
        self.geounit_a2 = geounit_a2

        geounit_a3 = Geounit(name="a3", geolevel = self.levela)
        geounit_a3.geom = a3
        geounit_a3.save()
        self.geounit_a3 = geounit_a3

        geounit_a4 = Geounit(name="a4", geolevel = self.levela)
        geounit_a4.geom = a4
        geounit_a4.save()
        self.geounit_a4 = geounit_a4

        geounit_a5 = Geounit(name="a5", geolevel = self.levela)
        geounit_a5.geom = a5
        geounit_a5.save()
        self.geounit_a5 = geounit_a5

        geounit_b1 = Geounit(name="b1", geolevel = self.levelb)
        geounit_b1.geom = b1
        geounit_b1.save()
        self.geounit_b1 = geounit_b1

        geounit_b2 = Geounit(name="b2", geolevel = self.levelb)
        geounit_b2.geom = b2
        geounit_b2.save()
        self.geounit_b2 = geounit_b2

        p = Plan(name="testPlan", owner=self.user)
        p.save()
        self.p = p
        
        d1 = District(name="District 1")
        d1.plan = p
        d1.save()
        self.d1 = d1

        d2 = District(name="District 2") 
        d2.plan = p
        d2.save()
        self.d2 = d2
    
    def tearDown(self):
        self.p.delete()
        self.user.delete()

    def test_add_to_plan(self):
        self.p.add_geounits(self.d2.id, [ self.geounit_b1.id ], self.levelb)        
        self.p.save()
        self.assertEqual(3, self.d2.geounits.all().count(), 'Geounit count not correct after adding larger geounit')
        self.assertEqual(1, self.d2.geounits.filter(id__exact=self.geounit_a1.id).count(), 'Geounit a1 not in set after enclosing geounit added; contains ' + str(self.d2.geounits.all()))
        self.p.add_geounits(self.d2.id, [ self.geounit_a4.id], self.levela)
        self.assertEqual(4, self.d2.geounits.all().count(), 'Geounit count not correct after adding single geounit')

    def test_get_base_geounits(self):
        geounit_ids = Geounit.get_base_geounits( [ self.geounit_b1.id ], self.levelb)
        self.assertEqual(3, len(geounit_ids), "Didn't get base geounits of large polys correctly; got " + str(len(geounit_ids)) + str(geounit_ids))
        geounit_ids = Geounit.get_base_geounits( [ self.geounit_b2.id ], self.levelb)
        self.assertEqual(2, len(geounit_ids), "Didn't get base geounits of large polys correctly; got " + str(len(geounit_ids)) + str(geounit_ids))
        geounit_ids = Geounit.get_base_geounits( [ self.geounit_b1.id, self.geounit_b2.id ], self.levelb)
        self.assertEqual(5, len(geounit_ids), "Didn't get base geounits of large polys correctly; got " + str(len(geounit_ids)) + str(geounit_ids))
