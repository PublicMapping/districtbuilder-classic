#!/usr/bin/python
"""
Count the number of users of the DistrictBuilder application.

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
    option_list = BaseCommand.option_list + (make_option(
        '-m',
        '--minutes',
        dest='minutes',
        default='5',
        action='store',
        help='Number of minutes'), )

    def handle(self, *args, **options):
        """
        Print the number of active users
        """
        minutes = int(options.get('minutes'))
        users = 0
        for session in Session.objects.all():
            decoded = session.get_decoded()
            if 'activity_time' in decoded and (
                    decoded['activity_time'] -
                    timedelta(0, 0, 0, 0, settings.SESSION_TIMEOUT)) > (
                        datetime.now() - timedelta(0, 0, 0, 0, minutes)):
                users += 1

        self.stdout.write(
            'Number of active users over the last %d minute(s): %d\n' %
            (minutes, users))
