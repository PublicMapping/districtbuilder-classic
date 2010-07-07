from django.test import TestCase
from django.contrib.gis.geos import GEOSGeometry
from publicmapping.redistricting.models import *

class RedistrictingTest(TestCase):

    def setUp(self):
        g = Geounit(name="testGeo")
        g.geom = GEOSGeometry("MULTIPOLYGON(((1 1,5 1,5 5,1 5,1 1),(2 2,2 3,3 2,2 2)))")
        g.save()
        p = Plan(name="testPlan")
        d1 = District(name="District 1")
        d2 = District(name="District 2") 
        p.save()
        d1.plan = p
        d1.geounits.add(g)
        d1.save()
        d2.plan = p
        d2.save()


    def test_add_to_plan(self):
        p.add_geounit(g)        
