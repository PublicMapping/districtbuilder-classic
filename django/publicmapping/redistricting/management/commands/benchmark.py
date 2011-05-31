#!/usr/bin/python
from datetime import datetime
from django.core.management.base import BaseCommand
from optparse import make_option
from redistricting.models import *
from redistricting.utils import *

class Command(BaseCommand):
    """
    This command runs benchmarking tests and reports results
    """
    args = None
    help = 'Run benchmarking tests'
    option_list = BaseCommand.option_list + (
        make_option('-p', '--plan', dest='plan_id', default=None, action='store', help='Choose a single plan to benchmark'),
        make_option('-t', '--topo', dest='is_topo', default=None, action='store',
                    help='Override for IS_TOPO_SIMPLIFIED setting. Either True or False.'),
    )

    def handle(self, *args, **options):
        """
        Run benchmarking tests
        """

        plan_id = options.get('plan_id')
        if (plan_id == None):
            self.stdout.write('A plan id must be specified.\n')
            return
            
        plans = Plan.objects.filter(pk=plan_id)
        if plans.count() == 0:
            self.stdout.write('Sorry, no plan with ID %s\n' % plan_id)
            return
        plan = plans[0]

        # Override IS_TOPO_SIMPLIFIED if specified
        is_topo = options.get('is_topo')
        if is_topo is not None:
            settings.IS_TOPO_SIMPLIFIED = (is_topo == 'True')
        self.stdout.write('Using topologically simplified geometries: %s\n' % settings.IS_TOPO_SIMPLIFIED)

        # Start benchmarking
        start_time = datetime.now()
        self.stdout.write('Benchmarking started at %s\n' % start_time)

        self.stdout.write('Finding map of all geounits with their districts...\n')
        t0 = datetime.now()
        result = plan.get_assigned_geounits()
        t1 = datetime.now()
        self.stdout.write('Found %d geounits. Time elapsed: %s\n' % (len(result), (t1 - t0)))

        self.stdout.write('Finding splits between the plan and itself...\n')
        t0 = datetime.now()
        result = plan.find_plan_splits(plan)
        t1 = datetime.now()
        self.stdout.write('Found %d splits. Time elapsed: %s\n' % (len(result), (t1 - t0)))

        # Finish benchmarking
        t1 = datetime.now()
        self.stdout.write('Benchmarking finished at %s\n' % t1)
        self.stdout.write('Total time elapsed: %s\n' % (t1 - start_time))
