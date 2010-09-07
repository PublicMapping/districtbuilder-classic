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
    David Zwarg, Andrew Jennings
"""

from django.contrib.gis.gdal import *
from django.contrib.gis.geos import *
from redistricting.models import *
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from optparse import make_option

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
    )

    def handle(self, *args, **options):
        """
        Perform the command. Import the shapes and assign the Geounits to
        the districts, based on their boundaries.
        """

        shapefile = options.get('shapefile')
        idfield = options.get('idfield')
        name = options.get('name')

        if shapefile == '':
            print 'Please provide the path to a shapefile.'
            return

        if idfield == '':
            print 'Please provide the field in the shapefile to use as the district ID.'
            return

        datasource = DataSource(shapefile)
        layer = datasource[0]

        # whoever admin is, they get this template
        owner = User.objects.get(username=settings.ADMINS[0][0])

        # Create a new plan. This will also create an Unassigned district
        # in the the plan.
        plan = Plan(name=name, is_template=True, version=0, owner=owner)
        plan.save()

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
