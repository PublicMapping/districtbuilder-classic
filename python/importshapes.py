#!/usr/bin/python

# You need to run this from withing the django shell; it'll import the settings so that
# the database is writable

from decimal import Decimal
from django.contrib.gis.gdal import *
from django.contrib.gis.geos import *
from django.core.management import setup_environ
from publicmapping import settings
from publicmapping.redistricting.models import *

setup_environ(settings)

county = {
    'shapepath' : '/projects/publicmapping/local/data/OH_39_census_county_web_mercator.shp',
    'geolevel' : 'county',
    'name_field' : 'NAMELSAD00',
    'subject_fields' : {'POPTOT':'Total Population','PRES_DEM':'Democrats','PRES_REP':'Republicans'},
}
block = {
    'shapepath' : '/projects/publicmapping/local/data/OH_39_census_block_web_mercator.shp',
    'geolevel' : 'block',
    'name_field' : 'NAME00',
    'subject_fields' : {'POPTOT':'Total Population','PRES_DEM':'Democrats','PRES_REP':'Republicans'},
}
tract = {
    'shapepath' : '/projects/publicmapping/local/data/OH_39_census_tract_web_mercator.shp',
    'geolevel' : 'tract',
    'name_field' : 'NAMELSAD00',
    'subject_fields' : {'POPTOT':'Total Population','PRES_DEM':'Democrats','PRES_REP':'Republicans'},
}

configs = { 'county' : county, 'block': block, 'tract' : tract }

def import_shape(config):
    ds = DataSource(config['shapepath'])

    print 'Importing from ', ds

    lyr = ds[0]
    print len(lyr), ' objects in shapefile'
    # print 'Data is in srs: ', lyr.srs, lyr.srs.name
    print 'Fields contained in layer: ', lyr.fields

    # Create a level
    level = Geolevel(name=config['geolevel'])
    level.save()

    # Create the subjects we need
    subject_objects = {}
    for attr, name in config['subject_fields'].iteritems():
        # don't recreate any subjects that already exist
        # (in another geolevel, for instance)
        sub = Subject.objects.filter(name=attr, display=name)
        if len(sub) == 0:
            sub = Subject(name=attr, display=name, short_display=name, is_displayed=True)
        else:
            sub = sub[0]
        sub.save()
        subject_objects[attr] = sub

    for feat in lyr:
        try :
            if feat.geom_type == 'MultiPolygon' :
                my_geom = GEOSGeometry(feat.geom.wkt)
            elif feat.geom_type == 'Polygon' :
                my_geom = MultiPolygon([GEOSGeometry(feat.geom.wkt)])
            g = Geounit(geom = my_geom, name = feat.get(config['name_field']), geolevel = level)
            g.save()
        except Exception as ex:
            print 'Failed to import geometry for feature ', feat.fid, type(ex), ex
            continue
            # print feat.get(name_field), feat.geom.num_points
        for attr, obj in subject_objects.iteritems():
            value = Decimal(str(feat.get(attr))).quantize(Decimal('000000.0000', 'ROUND_DOWN'))
            try:
                c = Characteristic(subject=obj, number=value, geounit = g)
                c.save()
                # print 'Value for ', feat.get(name_field), ' is ', value
            except:
                c = Characteristic(subject=obj, number='0.0', geounit = g)
                c.save()
                print 'Failed to set value ', attr, ' to ', feat.get(attr), ' in feature ', feat.get(config['name_field'])
            # print 'Value  for ', obj.name, ' is ', c.number
        g.save()

# for config in configs: 
import_shape(county)
import_shape(tract)
import_shape(block)
