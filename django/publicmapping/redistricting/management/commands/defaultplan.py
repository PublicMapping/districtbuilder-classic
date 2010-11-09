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
from redistricting.utils import *
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
        make_option('--districtindexfile', dest='districtindexfile', default='',
            help='The path to a district index file.'),
    )

    def handle(self, *args, **options):
        """
        Perform the command. Import the shapes and assign the Geounits to
        the districts, based on their boundaries.
        """

        shapefile = options.get('shapefile')
        idfield = options.get('idfield')
        name = options.get('name')
        districtindexfile = options.get('districtindexfile')

        if districtindexfile == '' and shapefile == '':
            print 'Please provide the path to a shapefile or a district index file.'
            return

        if districtindexfile != '':
            admin = User.objects.get(username=settings.ADMINS[0][0])
            DistrictIndexFile.index2plan(name, districtindexfile, owner=admin, template=True, purge=False)
            return

        if shapefile == '':
            print 'Please provide the path to a shapefile.'
            return

        if idfield == '':
            print 'Please provide the field in the shapefile to use as the district ID.'
            return
        
        Plan.from_shapefile(name, shapefile, idfield)

