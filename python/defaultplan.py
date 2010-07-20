#!/usr/bin/python

from django.contrib.gis.gdal import *
from django.contrib.gis.geos import *
from redistricting.models import *

shapepath = '/projects/publicmapping/local/data/OH_congressional_web_mercator.shp'
name_field = 'C_DIST_ID'

datasource = DataSource(shapepath)
layer = datasource[0]

# whoever user #1 is, they get this template
owner = User.objects.get(username='admin')

plan = Plan( name='Congressional', is_template=True, version=0, owner=owner )
plan.save()

district = District(
    district_id=0,
    name='Unassigned',
    plan=plan,
    version=0,
    geom=None,
    simple=None)
district.save()

for feature in layer:
    geom = feature.geom.geos
    if geom.geom_type != 'MultiPolygon':
        geom = MultiPolygon(geom)
    simple = geom.simplify(tolerance=100.0,preserve_topology=True)
    if simple.geom_type != 'MultiPolygon':
        simple = MultiPolygon(simple)

    district = District(
        district_id=feature.get(name_field),
        name='District %s' % feature.get(name_field),
        plan=plan,
        version=0,
        geom=geom,
        simple=simple)
    district.save()
