"""
Import the geography from shapefiles into The Public Mapping Project.

The geographic units (Geounits) in The Public Mapping Project are based
on geographies pulled from shapefiles. Use this import management command
to import geographic data for each geographic level (Geolevel) into the
application.

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

from decimal import Decimal
from django.contrib.gis.gdal import *
from django.contrib.gis.geos import *
from django.contrib.gis.db.models import Union 
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.conf import settings
from optparse import make_option
from redistricting.models import *
import traceback

class Command(BaseCommand):
    """
    A command that imports spatial data into the configured database.
    """
    args = '<layer ...>'
    help = 'Imports specific layers into the redistricting django app.'
    option_list = BaseCommand.option_list + (
        make_option('--basic', dest='basic_template', default='', 
            help='Create an initial template with this name. It will have MAX_DISTRICTS empty districts.'),
    )

    configs = {
        'county': {
            'shapepath' : '/projects/publicmapping/local/data/OH_39_census_countiesviablocks_WM.shp',
            'geolevel' : 'county',
            'name_field' : 'COUNTYNAME',
            'supplemental_id_field' : 'COUNTYFP00',
            'subject_fields' : { 'POPTOT' : 'Total Population' , 'POPBLK' : 'Black Persons' , 'POPHIS' : 'Hispanic or Latino' },
        },
        'tract': {
            'shapepath' : '/projects/publicmapping/local/data/OH_39_census_tractsviablocks2_wm.shp',
            'geolevel' : 'tract',
            'name_field' : 'TRACTNAME',
            'supplemental_id_field' : 'TRACTID',
            'subject_fields' : { 'POPTOT' : 'Total Population' , 'POPBLK' : 'Black Persons' , 'POPHIS' : 'Hispanic or Latino' },
        },
        'block': {
            'shapepath' : '/projects/publicmapping/local/data/OH_39_census_block_web_mercator.shp',
            'geolevel' : 'block',
            'name_field' : 'NAME00',
            'supplemental_id_field' : 'BLKIDFP00',
            'subject_fields' : { 'POPTOT' : 'Total Population' , 'POPBLK' : 'Black Persons' , 'POPHISP' : 'Hispanic or Latino' },
        }
    }

    def import_shape(self,config):
        """
        Import a shapefile, based on a config.

        Parameters:
            config -- A dictionary with 'shapepath', 'geolevel', 'name_field', and 'subject_fields' keys.
        """
        ds = DataSource(config['shapepath'])

        print 'Importing from ', ds

        lyr = ds[0]
        print len(lyr), ' objects in shapefile'
        # print 'Data is in srs: ', lyr.srs, lyr.srs.name
        # print 'Fields contained in layer: ', lyr.fields

        # don't recreate any geolevels that already exist
        level = Geolevel.objects.filter(name__exact=config['geolevel'])
        if len(level) == 0:
            level = Geolevel(name=config['geolevel'])
            level.save()
        else:
            level = level[0]

        supplemental_id_field = config.get('supplemental_id_field', False)

        # Create the subjects we need
        subject_objects = {}
        for attr, name in config['subject_fields'].iteritems():
            # don't recreate any subjects that already exist
            # (in another geolevel, for instance)
            sub = Subject.objects.filter(display=name)
            if len(sub) == 0:
                sub = Subject(name=attr, display=name, short_display=name, is_displayed=True)
                sub.save()
            else:
                sub = sub[0]
            subject_objects[attr] = sub

        for feat in lyr:
            try :
                # Store the geos geometry
                geos = feat.geom.geos
                # Coerce the geometry into a MultiPolygon
                if geos.geom_type == 'MultiPolygon':
                    my_geom = geos
                elif geos.geom_type == 'Polygon':
                    my_geom = MultiPolygon(geos)
                simple = my_geom.simplify(tolerance=settings.SIMPLE_TOLERANCE,preserve_topology=True)
                if simple.geom_type != 'MultiPolygon':
                    simple = MultiPolygon(simple)
                center = my_geom.centroid

                # Ensure the centroid is within the geometry
                if not center.within(my_geom):
                    # Get the first polygon in the multipolygon
                    first_poly = my_geom[0]
                    # Get the extent of the first poly
                    first_poly_extent = first_poly.extent
                    min_x = first_poly_extent[0]
                    max_x = first_poly_extent[2]
                    # Create a line through the bbox and the poly center
                    my_y = first_poly.centroid.y
                    centerline = LineString( (min_x, my_y), (max_x, my_y))
                    # Get the intersection of that line and the poly
                    intersection = centerline.intersection(first_poly)
                    if type(intersection) is MultiLineString:
                        intersection = intersection[0]
                    # the center of that line is my within-the-poly centroid.
                    center = intersection.centroid
                    
                if not my_geom.simple:
                    print 'Geometry %d is not simple.' % feat.fid
                if not my_geom.valid:
                    print 'Geometry %d is not valid.' % feat.fid
                if not simple.simple:
                    print 'Simplified Geometry %d is not simple.' % feat.fid
                if not simple.valid:
                    print 'Simplified Geometry %d is not valid.' % feat.fid

                g = Geounit(geom = my_geom, name = feat.get(config['name_field']), geolevel = level, simple = simple, center = center)
                if supplemental_id_field:
                    g.supplemental_id = feat.get(supplemental_id_field)
                g.save()
            except Exception as ex:
                print 'Failed to import geometry for feature %d' % feat.fid
                traceback.print_exc()
                continue

            for attr, obj in subject_objects.iteritems():
                value = Decimal(str(feat.get(attr))).quantize(Decimal('000000.0000', 'ROUND_DOWN'))
                try:
                    c = Characteristic(subject=obj, number=value, geounit=g)
                    c.save()
                except:
                    c = Characteristic(subject=obj, number='0.0', geounit=g)
                    c.save()
                    print 'Failed to set value "%s" to %d in feature "%s"' % (attr, feat.get(attr), feat.get(config['name_field']),)
            g.save()

    def create_basic_template(self,name):
        """
        Create a default plan with that number of districts created already.

        Only works if MAX_DISTRICTS is set. 
        """
        if settings.MAX_DISTRICTS:
            admin = User.objects.get(pk = 1)
            p = Plan(name=name, owner=admin, is_template=True)
            p.save()
            for district_num in range(1, settings.MAX_DISTRICTS + 1):
                district = District(name="District " + str(district_num) , district_id = district_num, plan = p) 
                district.save()

    def add_unassigned_to_template(self,name):
        """
        Add all geounits to one large, unassigned district for the default
        template.
        """
        p = Plan.objects.get(name__exact=name)
        geom = Geounit.objects.filter(geolevel = 1).aggregate(Union('geom'))
        geom = MultiPolygon(geom["geom__union"])
        simple = geom.simplify(tolerance=settings.SIMPLE_TOLERANCE,preserve_topology=True)
        simple = MultiPolygon(simple)
        district = District(name="Unassigned", district_id = settings.MAX_DISTRICTS + 1, plan = p, geom = geom, simple = simple)
        district.save()

        subjects = Subject.objects.all()
        bigunits = Geounit.objects.filter(geolevel=1)
        for subject in subjects:
            agg = Characteristic.objects.filter(geounit__in = bigunits, subject = subject.id).aggregate(Sum('number'))
            characteristic = ComputedCharacteristic(subject = subject, district = district, number = agg['number__sum'])
            characteristic.save()
            

    def handle(self, *args, **options):
        """
        Perform the command. Import the shapes and assign to unassigned,
        based on configuration options.
        """

        print "This management command is disabled with the introduction of LegislativeBodies."
        return

        tpl_name = options.get('basic_template')
        if tpl_name != '':
            print 'Import creating basic template.'
            self.create_basic_template(tpl_name)

        for lyr in args:
            if lyr in self.configs:
                print 'Importing "%s"' % lyr
                self.import_shape(self.configs[lyr])

        if tpl_name != '':
            print 'Import assigning unassigned to template.'
            self.add_unassigned_to_template(tpl_name)
