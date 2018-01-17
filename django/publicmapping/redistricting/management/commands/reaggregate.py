#!/usr/bin/python
"""
Reaggregate one or more plans in the DistrictBuilder web application.

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


class Command(BaseCommand):
    """
    This command reaggregates the data for given plans or district
    """
    args = None
    help = 'Reaggregate data for a give district or plan'
    option_list = BaseCommand.option_list + (
        make_option(
            '-d',
            '--district',
            dest='district_id',
            default=None,
            action='store',
            help='Choose a single district to update'),
        make_option(
            '-p',
            '--plan',
            dest='plan_id',
            default=None,
            action='store',
            help='Choose a single plan to update'),
        make_option(
            '-t',
            '--thread',
            dest='thread',
            default=1,
            type='int',
            action='store',
            help='Which thread to use? 1-4'),
    )

    def handle(self, *args, **options):
        """
        Reaggregate the district stats
        """
        global verbosity
        global geolevel
        global geounit_ids

        verbosity = int(options.get('verbosity'))
        plan_id = options.get('plan_id')
        district_id = options.get('district_id')

        if verbosity > 0:
            self.stdout.write(
                'Reaggregating data - start at %s\n' % datetime.now())

        # Grab all of the plans from the database
        if (plan_id != None):
            plans = Plan.objects.filter(pk=plan_id)
            if plans.count() == 0 and verbosity > 0:
                self.stdout.write('Sorry, no plan with ID %s\n' % plan_id)
                return
        elif (district_id != None):
            districts = District.objects.filter(pk=district_id)
            if districts.count() == 0 and verbosity > 0:
                self.stdout.write(
                    'Sorry, no district with ID %s\n' % district_id)
                return
            plans = (districts[0].plan, )
        else:
            plans = Plan.objects.all()
            plancount = plans.count()
            begin = int((options.get('thread') - 1) * (plancount / 4))
            end = int(options.get('thread') * (plancount / 4))
            plans = plans[begin:end]

        # Counts of the updated geounits
        updated_plans = 0
        updated_districts = 0

        for p in plans:
            if district_id is None:
                all_districts = p.district_set.all()
            else:
                all_districts = District.objects.filter(pk=district_id)
            if verbosity > 0:
                self.stdout.write('Plan ID: %d; %d districts in %s\n' %
                                  (p.id, len(all_districts), p.name))

            if district_id is None:
                result = p.reaggregate()
                updated_districts += result
                updated_plans += 1
                if verbosity > 0:
                    self.stdout.write('Fixed %d districts in plan: "%s"\n' %
                                      (result, p.name))
            else:
                all_districts[0].reaggregate()
                updated_districts += 1
                updated_plans += 1
                if verbosity > 0:
                    self.stdout.write(
                        'Fixed 1 district in plan: "%s"\n' % p.name)

        if verbosity > 0:
            self.stdout.write('Fixed %d districts in %d plans - ' %
                              (updated_districts, updated_plans))
            self.stdout.write('finished at %s\n' % datetime.now())
