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
        make_option('-p', '--plan', dest='plan_id', default=None, action='store', help='Choose a single plan to update'),
	make_option('-t', '--thread', dest='thread', default=1, type='int', action='store', help='Which thread to use? 1-4'),
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
            plancount = plans.count()
            begin = int((options.get('thread')-1) * (plancount/4))
            end = int(options.get('thread') * (plancount/4))
            plans = plans[begin:end]

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

            self.stdout.write('\t%d / %d\n' % (updated_plans, len(plans),))

            # Get all of the geounit_ids for that geolevel
            geounit_ids = map(str, Geounit.objects.filter(geolevel = geolevel).values_list('id', flat=True))
            if verbosity > 1:
                self.stdout.write("Found largest-geometry geolevel of %s, which has %d geounits\n" % (geolevel, len(geounit_ids)))
            # Cycle through each district and update the statistics
            if district_id == None:
                all_districts = p.district_set.all()
                if verbosity > 0:
                    self.stdout.write('Plan ID: %d; %d districts in %s\n' % (p.id, len(all_districts), p.name))
            else:
                all_districts = list(districts,)
                if verbosity > 1:
                    self.stdout.write('About to update %s in plan %s\n' % (district.long_label, p.name))
            for d in all_districts:
                success = self.reaggregate_district(d, body=p.legislative_body)
                if success == True:
                    updated_districts +=1  
            updated_plans += 1 

        if verbosity > 0:
            self.stdout.write('Fixed %d districts in %d plans - finished at %s\n' % (updated_districts, updated_plans, datetime.now()))

    def reaggregate_district(self, district, body=None):
        try:
            if body == None:
                body = district.plan.legislative_body
            geounits = Geounit.get_mixed_geounits(geounit_ids, body, geolevel.id, district.geom, True)
        
            # Grab all the computedcharacteristics for the district/subject combo and reaggregate
            for subj in Subject.objects.all().order_by('-percentage_denominator'):
                agg = Characteristic.objects.filter(subject = subj, geounit__in = geounits).aggregate(Sum('number'))
                if agg['number__sum'] is None:
                    aggval = '0000.00000000'
                else:
                    aggval = agg['number__sum']

                cc, created = ComputedCharacteristic.objects.get_or_create(district=district, subject=subj, defaults={'number':aggval, 'percentage':'0000.00000000'})
                if not created:
                    cc.number = aggval
                    cc.percentage = '0000.00000000'

                if cc.subject.percentage_denominator:
                    denominator = district.computedcharacteristic_set.get(subject = cc.subject.percentage_denominator).number
                    if cc.number and denominator:
                        cc.percentage = cc.number / denominator
                if not cc.number:
                    cc.number = '00000000.0000'
                cc.save()
            return True
        except Exception as ex:
            if verbosity > 0:
                self.stdout.write('Unable to reaggreagate %s because \n%s' % (district.long_label, ex))
