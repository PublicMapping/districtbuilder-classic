#!/usr/bin/python
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
        make_option('-d', '--district', dest='district_id', default=None, action='store', help='Choose a single district to update'),
        make_option('-p', '--plan', dest='plan_id', default=None, action='store', help='Choose a single plan to update')
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
            self.stdout.write('Reaggregating data - start at %s\n' % datetime.now())

        # Grab all of the plans from the database
        if (plan_id != None):
            plans = Plan.objects.filter(pk=plan_id)
            if plans.count() == 0 and verbosity > 0:
                self.stdout.write('Sorry, no plan with ID %s\n' % plan_id)
                return
        elif (district_id != None):
            districts = District.objects.filter(pk=district_id)
            if districts.count() == 0 and verbosity > 0:
                self.stdout.write('Sorry, no district with ID %s\n' % district_id)
                return
            plans = (districts[0].plan,)
        else:
            plans = Plan.objects.all()

        # Counts of the updated geounits
        updated_plans = 0;
        updated_districts = 0;

        for p in plans:
            if district_id is None:
                all_districts = p.district_set.all()
            else:
                all_districts = District.objects.filter(pk=district_id)
            if verbosity > 0:
                self.stdout.write('Plan ID: %d; %d districts in %s\n' % (p.id, len(all_districts), p.name))

            if district_id is None:
                result = p.reaggregate()
                updated_districts += result
                updated_plans += 1 
                if verbosity > 0:
                    self.stdout.write('Fixed %d districts in plan: "%s"\n' % (result, p.name))
            else:
                all_districts[0].reaggregate()
                updated_districts += 1
                updated_plans += 1 
                if verbosity > 0:
                    self.stdout.write('Fixed 1 district in plan: "%s"\n' % p.name)

        if verbosity > 0:
            self.stdout.write('Fixed %d districts in %d plans - ' % (updated_districts, updated_plans))
            self.stdout.write('finished at %s\n' % datetime.now())
