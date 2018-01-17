#!/usr/bin/python
"""
Delete score configurations from the DistrictBuilder application.

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

        for m in [
                ValidationCriteria, ScorePanel, ScoreDisplay, ScoreArgument,
                ScoreFunction
        ]:
            m.objects.all().delete()

        if verbosity > 0:
            self.stdout.write('Complete!\n')
