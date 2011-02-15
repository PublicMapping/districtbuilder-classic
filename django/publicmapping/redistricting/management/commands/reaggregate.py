#!/usr/bin/python
from datetime import datetime
from django.core.management.base import BaseCommand
from optparse import make_option
from redistricting.models import *

class Command(BaseCommand):
    """
    This command reaggregates the data for all of the districts
    in the database
    """
    args = None
    help = 'Reaggregate all data for districts or for a given plan'
    option_list = BaseCommand.option_list + (make_option('-p', '--plan', dest='plan_id', default=None, action='store', help='Choose a single plan to update'), )

    def handle(self, *args, **options):
        """
        Reaggregate the district stats
        """

        verbosity = int(options.get('verbosity'))
        plan_id = options.get('plan_id')
        if verbosity > 0:
            self.stdout.write('Reaggregating data - start at %s\n' % datetime.now())

        # Grab all of the plans from the database
        if (plan_id != None):
                plans = Plan.objects.filter(pk=plan_id)
                if plans.count() == 0 and verbosity > 0:
                    self.stdout.write('Sorry, no plan with ID %s\n' % plan_id)
                    return
        else:
            plans = Plan.objects.all()

        # Counts of the updated geounits
        updated_plans = 0;
        updated_districts = 0;

        for p in plans:
            # Find the geolevel relevant to this plan that has the largest geounits
            leg_levels = LegislativeLevel.objects.filter(legislative_body = p.legislative_body)
            geolevel = leg_levels[0].geolevel
            for l in leg_levels:
                if l.geolevel.min_zoom < geolevel.min_zoom:
                    geolevel = l.geolevel

            # Get all of the geounit_ids for that geolevel
            geounit_ids = map(str, Geounit.objects.filter(geolevel = geolevel).values_list('id', flat=True))
            if verbosity > 0:
                self.stdout.write("Found largest-geometry geolevel of %s, which has %d geounits\n" % (geolevel, len(geounit_ids)))
            # Cycle through each district and update the statistics
            all_districts = p.district_set.all()
            if verbosity > 1:
                self.stdout.write('%d districts in plan %s\n' % (len(all_districts), p.name))
            for d in all_districts:
                geounits = Geounit.get_mixed_geounits(geounit_ids, p.legislative_body, geolevel.id, d.geom, True)
            
                for cc in d.computedcharacteristic_set.order_by('-subject__percentage_denominator'):
                    agg = Characteristic.objects.filter(subject = cc.subject, geounit__in = geounits).aggregate(Sum('number'))
                    cc.number = agg['number__sum']
                    cc.percentage = '0000.00000000'
                    if cc.subject.percentage_denominator:
                        denominator = d.computedcharacteristic_set.get(subject = cc.subject.percentage_denominator).number
                        if cc.number and denominator:
                            cc.percentage = cc.number / denominator
                    if not cc.number:
                        cc.number = '00000000.0000'
                    cc.save()
                updated_districts += 1
            updated_plans += 1 

        if verbosity > 0:
            self.stdout.write('Fixed %d districts in %d plans - finished at %s\n' % (updated_districts, updated_plans, datetime.now()))
