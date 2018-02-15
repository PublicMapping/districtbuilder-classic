#!/usr/bin/python
"""
A django management command to export plans.

Plans may be exported as district index files, or ESRI shapefiles.

This file is part of The Public Mapping Project
https://github.com/PublicMapping/

License:
    Copyright 2010-2012 Micah Altman, Michael McDonald

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

from datetime import datetime
from django.core.management.base import BaseCommand
from optparse import make_option
from redistricting.models import *
from redistricting.utils import *


class Command(BaseCommand):
    """
    Export a plan or many plans into an index file or shapefile.
    """
    args = None
    help = 'Export a plan or many plans into an index file or shapefile.'
    option_list = BaseCommand.option_list + (
        make_option(
            '-p',
            '--plan',
            dest='plan_id',
            default=None,
            type='int',
            action='store',
            help='Choose a single plan to export'),
        make_option(
            '-s',
            '--shared',
            dest='is_shared',
            default=False,
            action='store_true',
            help='Only export shared plans'),
        make_option(
            '-t',
            '--type',
            dest='export_type',
            default='index',
            action='store',
            help="'index' = index file, 'shape' = shape file"),
    )

    def handle(self, *args, **options):
        """
        Export the index files
        """
        verbosity = int(options.get('verbosity'))

        # Grab all of the plans from the database
        plan_id = options.get('plan_id')
        plans = [Plan.objects.get(pk=plan_id)
                 ] if plan_id else Plan.objects.all()

        # Filter out all non-shared plans if specified
        if options.get("is_shared"):
            plans = [p for p in plans if p.is_shared]

        if verbosity > 0:
            self.stdout.write('Exporting %d plan(s) - started at %s\n' %
                              (len(plans), datetime.now()))

        for p in plans:
            if verbosity > 0:
                self.stdout.write('Exporting plan with id: %s and name: %s\n' %
                                  (p.id, p.name))
            if options.get('export_type') == 'index':
                # Write each plan to a zipped index file in /tmp
                f = DistrictIndexFile.plan2index(p.id)
            elif options.get('export_type') == 'shape':
                # Write each plan to a zipped shape file in /tmp
                f = DistrictShapeFile.plan2shape(p)

            if verbosity > 0:
                self.stdout.write('Data stored in file: %s\n' % f.name)

        if verbosity > 0:
            self.stdout.write('Export finished at %s\n' % (datetime.now()))
