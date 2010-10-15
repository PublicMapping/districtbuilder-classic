"""
Create a default plan for use as a template.

A default plan should be something like the current congressional boundaries
for a state.  A shapefile with polygons that describe the districts and
coverage that exist, or ideally exist.

The values for the districts inside this plan will be computed based on the
Geounits inside of the bounds of each district.

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

from django.contrib.gis.gdal import *
from django.contrib.gis.geos import *
from redistricting.models import *
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from optparse import make_option
import csv, datetime

class Command(BaseCommand):
    """
    A command that imports a default set of boundaries into a system
    template.
    """
    args = ''
    help = 'Imports a default plan into the redistricting django app.'
    option_list = BaseCommand.option_list + (
        make_option('--shape', dest='shapefile', default='',
            help="The path to the Plan's shapefile."),
        make_option('--field', dest='idfield', default='',
            help='The field in the shapefile with the district ID.'),
        make_option('--name', dest='name', default='Congressional',
            help='The name of the default plan, defaults to "Congressional".'),
        make_option('--blockfile', dest='blockfile', default='',
            help='The path to a block equivalency file.'),
    )

    def handle(self, *args, **options):
        """
        Perform the command. Import the shapes and assign the Geounits to
        the districts, based on their boundaries.
        """

        shapefile = options.get('shapefile')
        idfield = options.get('idfield')
        name = options.get('name')
        blockfile = options.get('blockfile')

        if blockfile == '' and shapefile == '':
            print 'Please provide the path to a shapefile or a blockfile.'
            return

        if blockfile != '':
            import_via_blockfile(name, blockfile)
            return

        if shapefile == '':
            print 'Please provide the path to a shapefile.'
            return

        if idfield == '':
            print 'Please provide the field in the shapefile to use as the district ID.'
            return
        
        import_via_shapefile(name, shapefile, idfield)


def import_via_shapefile(name, shapefile, idfield):
    """
    Imports a plan from a shapefile, using the feature attribute named after
    the idfield parameter to name a district.  All geounits of the BASE_GEOUNIT_LEVEL
    defined in the settings will be put into the district named by the idfield
    """
    plan = create_default_plan(name)

    datasource = DataSource(shapefile)
    layer = datasource[0]

    # Import each feature in the new plan. Sort by the district ID field
    for feature in sorted(layer,key=lambda f:int(f.get(idfield))):
        print '\tImporting "District %s"' % (feature.get(idfield),)

        # Import only multipolygon shapes
        geom = feature.geom.geos
        if geom.geom_type == 'Polygon':
            geom = MultiPolygon(geom)
        elif geom.geom_type == 'MultiPolygon':
            geom = geom
        else:
            geom = None

        simple = geom.simplify(tolerance=settings.SIMPLE_TOLERANCE,preserve_topology=True)

        # Import only multipolygon shapes
        if simple.geom_type == 'Polygon':
            simple = MultiPolygon(simple)
        elif geom.geom_type == 'MultiPolygon':
            simple  = simple
        else:
            simple = None

        district = District(
            district_id=int(feature.get(idfield)) + 1,
            name='District %s' % feature.get(idfield),
            plan=plan,
            version=0,
            geom=geom,
            simple=simple)
        district.save()

        geounits = list(district.get_base_geounits_within())

        print '\tUpdating district statistics...'
        district.delta_stats(geounits,True)


def import_via_blockfile(name, blockfile):
    """
    Imports a plan using a block equivalency file in csv format.  There should be only
    two columns: a CODE matching the supplemental ids of geounits and a DISTRICT integer
    representing the district to which the geounit should belong
    """
    plan = create_default_plan(name)
            
    # initialize the dicts we'll use to store the supplemental_ids, keyed on the district_id of this plan
    new_districts = dict()
    
    csv_file = open(blockfile)
    reader = csv.DictReader(csv_file, fieldnames = ['code', 'district']) 
    for row in reader:
        try:
            dist_id = int(row['district'])
            # If the district key is present, add this row's code; else make a new list
            if dist_id in new_districts:
                new_districts[dist_id].append(row['code'])
            else:
                new_districts[dist_id] = list()
                new_districts[dist_id].append(row['code'])
        except Exception as ex:
            print 'Didn\'t import row: %s' % row 
            print '\t%s' % ex
            continue

    
    subjects = Subject.objects.all()

    # Create the district geometry from the lists of geounits
    for district_id in new_districts.keys():
        # Get a filter using supplemental_id
        code_list = new_districts[district_id]
        guFilter = Q(supplemental_id__in = code_list)

        try:
            # Build our new geometry from the union of our geounit geometries
            new_geom = Geounit.objects.filter(guFilter).unionagg()
            new_simple = new_geom.simplify(tolerance = settings.SIMPLE_TOLERANCE, preserve_topology=True)

            # Create a new district and save it
            new_district = District(name='District %s' % district_id, district_id = district_id + 1, plan=plan, geom=enforce_multi(new_geom), simple = enforce_multi(new_simple))
            new_district.save()
            print 'Created %s at %s' % (new_district.name, datetime.datetime.now())
        except Exception as ex:
            print 'Wasn\'t able to create district %s: %s' % (district_id, ex)
            continue
    
        # For each district, create the ComputedCharacteristics
        geounit_ids = Geounit.objects.filter(guFilter).values_list('id', flat=True).order_by('id')
        for subject in subjects:
            try:
                cc_value = Characteristic.objects.filter(geounit__in = geounit_ids, subject = subject).aggregate(Sum('number'))
                cc = ComputedCharacteristic(subject = subject, number = cc_value['number__sum'], district = new_district)
                cc.save()
            except Exception as ex:
                print 'Wasn\'t able to create ComputedCharacteristic for district %, subject %s: %s' % (district_id, subject.name, ex)
                continue

def create_default_plan (name):
    """
    Create a Plan object as a template
    """
    # whoever admin is, they get this template
    owner = User.objects.get(username=settings.ADMINS[0][0])

    # Create a new plan. This will also create an Unassigned district
    # in the the plan.
    plan = Plan(name=name, is_template=True, version=0, owner=owner)
    try:
        plan.save()
    except Exception as ex:
        print 'Couldn\'t save plan: %s' % ex 
        sys.exit(-1)
    return plan
