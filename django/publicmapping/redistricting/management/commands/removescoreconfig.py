#!/usr/bin/python
from datetime import datetime
from django.core.management.base import BaseCommand
from optparse import make_option
from redistricting.models import *
from redistricting.utils import *

class Command(BaseCommand):
    """
    This command deletes all score configuration from the database
    """
    args = None
    help = 'Delete all score configuration database rows including: displays, panels, arguments, and validation criteria'

    def handle(self, *args, **options):
        """
        Delete all score configuration
        """
        verbosity = int(options.get('verbosity'))

        if verbosity > 0:
            self.stdout.write('Deleting all score configuration\n')

        for m in [ValidationCriteria, ScorePanel, ScoreDisplay, ScoreArgument, ScoreFunction]:
            m.objects.all().delete()

        if verbosity > 0:
            self.stdout.write('Complete!\n')
