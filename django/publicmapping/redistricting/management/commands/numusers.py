#!/usr/bin/python
from datetime import datetime, time, timedelta
from django.core.management.base import BaseCommand
from optparse import make_option
from redistricting.models import *
from redistricting.utils import *

class Command(BaseCommand):
    """
    This command prints the number of active users in the system over a period of time
    """
    args = None
    help = 'Print the number of active users in the system over a period of time'
    option_list = BaseCommand.option_list + (
        make_option('-m', '--minutes', dest='minutes', default='5', action='store', help='Number of minutes'),
    )

    def handle(self, *args, **options):
        """
        Print the number of active users
        """
        minutes = int(options.get('minutes'))
        users = 0
        for session in Session.objects.all():
            decoded = session.get_decoded()
            if 'activity_time' in decoded and (decoded['activity_time'] - timedelta(0,0,0,0,settings.SESSION_TIMEOUT)) > (datetime.now() - timedelta(0,0,0,0,minutes)):
                users += 1

        self.stdout.write('Number of active users over the last %d minute(s): %d\n' % (minutes, users))
