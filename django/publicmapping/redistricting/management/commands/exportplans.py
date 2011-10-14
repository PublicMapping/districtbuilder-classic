#!/usr/bin/python
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
        make_option('-p', '--plan', dest='plan_id', default=None, type='int',
            action='store', help='Choose a single plan to export'),
        make_option('-s', '--shared', dest='is_shared', default=False, 
            action='store_true', help='Only export shared plans'),
        make_option('-t', '--type', dest='export_type', default='index',
            action='store', help="'index' = index file, 'shape' = shape file"),
    )

    def handle(self, *args, **options):
        """
        Export the index files
        """
        verbosity = int(options.get('verbosity'))

        # Grab all of the plans from the database
        plan_id = options.get('plan_id')
        plans = [Plan.objects.get(pk=plan_id)] if plan_id else Plan.objects.all()

        # Filter out all non-shared plans if specified
        if options.get("is_shared"):
            plans = [p for p in plans if p.is_shared]
            
        if verbosity > 0:
            self.stdout.write('Exporting %d plan(s) - started at %s\n' % (len(plans), datetime.now()))

        for p in plans:
            if verbosity > 0:
                self.stdout.write('Exporting plan with id: %s and name: %s\n' % (p.id, p.name))
            if options.get('export_type') == 'index':
                # Write each plan to a zipped index file in /tmp
                f = DistrictIndexFile.plan2index(p)
            elif options.get('export_type') == 'shape':
                # Write each plan to a zipped shape file in /tmp
                f = DistrictShapeFile.plan2shape(p)

            if verbosity > 0:
                self.stdout.write('Data stored in file: %s\n' % f.name)

        if verbosity > 0:
            self.stdout.write('Export finished at %s\n' % (datetime.now()))
