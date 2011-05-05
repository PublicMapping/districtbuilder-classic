#!/usr/bin/python
from datetime import datetime
from django.core.management.base import BaseCommand
from optparse import make_option
from redistricting.models import *
from redistricting.utils import *

class Command(BaseCommand):
    """
    This command exports the index file for a single plan, or all plans in the system
    """
    args = None
    help = 'Export the index files for a single plan, or all plans in the system'
    option_list = BaseCommand.option_list + (
        make_option('-p', '--plan', dest='plan_id', default=None, action='store', help='Choose a single plan to export'),
    )

    def handle(self, *args, **options):
        """
        Export the index files
        """
        verbosity = int(options.get('verbosity'))

        # Grab all of the plans from the database
        plan_id = options.get('plan_id')
        plans = [Plan.objects.get(pk=plan_id)] if plan_id else Plan.objects.all()
            
        if verbosity > 0:
            self.stdout.write('Exporting %d plan(s) - started at %s\n' % (len(plans), datetime.now()))

        for p in plans:
            if verbosity > 0:
                self.stdout.write('Exporting plan with id: %s and name: %s\n' % (p.id, p.name))
            # Write each plan to a zipped index file in /tmp
            f = DistrictIndexFile.plan2index(p)
            if verbosity > 0:
                self.stdout.write('Data stored in file: %s\n' % f.name)

        if verbosity > 0:
            self.stdout.write('Export finished at %s\n' % (datetime.now()))
