#!/usr/bin/python

# You need to run this from withing the django shell; it'll import the settings so that
# the database is writable

from decimal import Decimal
from django.contrib.gis.gdal import *
from django.contrib.gis.geos import *
from django.core.management import setup_environ
from django.contrib.gis.db.models import Union 
from django.contrib.auth.models import User
import settings

setup_environ(settings)

from redistricting.models import *

county = {
    'shapepath' : '/projects/publicmapping/local/data/OH_counties_dtl_web_mercator.shp',
    'geolevel' : 'county',
    'name_field' : 'NAME',
    'subject_fields' : { 'POP2005' : 'Total Population' , 'BLACK' : 'Black Persons' , 'HISPANIC' : 'Hispanic or Latino' },
}
block = {
    'shapepath' : '/projects/publicmapping/local/data/OH_39_census_block_web_mercator.shp',
    'geolevel' : 'block',
    'name_field' : 'NAME00',
    'subject_fields' : { 'POPTOT' : 'Total Population' , 'POPBLK' : 'Black Persons' , 'POPHISP' : 'Hispanic or Latino' },
}
tract = {
    'shapepath' : '/projects/publicmapping/local/data/OH_tracts_2000_web_mercator.shp',
    'geolevel' : 'tract',
    'name_field' : 'NAMELSAD00',
    'subject_fields' : { 'POPTOT' : 'Total Population' , 'POPBLK' : 'Black Persons' , 'POPHISP' : 'Hispanic or Latino' },
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
        sub = Subject.objects.filter(display=name)
        if len(sub) == 0:
            sub = Subject(name=attr, display=name, short_display=name, is_displayed=True)
        else:
            sub = sub[0]
        sub.save()
        subject_objects[attr] = sub

    for feat in lyr:
        try :
            if feat.geom_type == 'MultiPolygon' :
                my_geom = feat.geom.geos
            elif feat.geom_type == 'Polygon' :
                my_geom = MultiPolygon(feat.geom.geos)
            simple = my_geom.simplify(tolerance=10.0,preserve_topology=True)
            if simple.geom_type != 'MultiPolygon':
                simple = MultiPolygon(simple)
            g = Geounit(geom = my_geom, name = feat.get(config['name_field']), geolevel = level, simple = simple)
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

def create_basic_template():
    """If the MAX_DISTRICTS settings is set, create a default plan with that number of districts created already
    """
    if settings.MAX_DISTRICTS and settings.PLAN_TEMPLATE:
        admin = User.objects.get(pk = 1)
        p = Plan(name=settings.PLAN_TEMPLATE, owner=admin, is_template=True)
        p.save()
        for district_num in range(1, settings.MAX_DISTRICTS + 1):
            district = District(name="District " + str(district_num) , district_id = district_num, plan = p) 
            district.save()

def add_unassigned_to_template():
        p = Plan.objects.get(pk=1)
        geom = Geounit.objects.filter(geolevel = 1).aggregate(Union('geom'))
        geom = MultiPolygon(geom["geom__union"])
        simple = geom.simplify(tolerance=10.0,preserve_topology=True)
        simple = MultiPolygon(simple)
        district = District(name="Unassigned", district_id = settings.MAX_DISTRICTS + 1, plan = p, geom = geom, simple = simple)
        district.save()

        blocks = Geounit.objects.filter(geolevel=3).all()
        for block in blocks:
            mapping = DistrictGeounitMapping(plan = p, district = district, geounit = block)
            mapping.save()
        subjects = Subject.objects.all()
        for subject in subjects:
            agg = Characteristic.objects.filter(geolevel = 1, subject = subject.id).aggregate(Sum('value'))
            characteristic = ComputedCharacteristic(subject = subject, district = district, number = agg['value__sum'], percentage = 100)
            characteristic.save()
        

# for config in configs: 
 # create_basic_template()

# import_shape(county)
# import_shape(tract)
# import_shape(block)

add_unassigned_to_template()
