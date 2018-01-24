#!/usr/bin/python
"""
Collect internalionalization messages and compile the message files
for use by the gettext library.

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

from django.core.management.base import BaseCommand
from django.conf import settings
from django.core import management
from optparse import make_option


class Command(BaseCommand):
    """
    This command prints creates and compiles language message files
    """
    args = None
    help = 'Create and compile language message files'

    def add_arguments(self, parser):
        parser.add_argument(
            '-t',
            '--templates',
            dest="templates",
            action="store_true",
            help="Create template message files.",
            default=False),
        parser.add_argument(
            '-j',
            '--javascript',
            dest="javascript",
            action="store_true",
            help="Create javascript message files.",
            default=False),
        parser.add_argument(
            '-c',
            '--compile',
            dest="compile",
            action="store_true",
            help="Compile message files.",
            default=False),
        parser.add_argument(
            '-l',
            '--locale',
            dest='locale',
            default=None,
            action='store',
            help='Specify a locale.')

    def handle(self, *args, **options):
        """
        Create and compile language message files
        """
        # Execute every action if either all or none of the options are specified
        everything = options.get("templates") == options.get(
            "javascript") == options.get("compile")

        # Use the specified locale, or if none are provided, use all defined in settings
        locale = options.get("locale")
        locales = [locale] if locale else [l[0] for l in settings.LANGUAGES]

        # Make messages for each available locale
        for locale in locales:
            # Make messages for templates (.html, .txt, .email)
            if everything or options.get("templates"):
                management.call_command(
                    'makemessages',
                    locale=[locale],
                    extensions=['html', 'txt', 'email'],
                    interactive=False,
                    verbosity=options.get('verbosity'),
                    ignore_patterns=['static/jquery/*.*'])

            # Make messages for javascript
            if everything or options.get("javascript"):
                management.call_command(
                    'makemessages',
                    locale=[locale],
                    domain='djangojs',
                    interactive=False,
                    verbosity=options.get('verbosity'),
                    ignore_patterns=['static*'])

            # Compile message file
            if everything or options.get("compile"):
                management.call_command(
                    'compilemessages',
                    locale=[locale],
                    interactive=False,
                    verbosity=options.get('verbosity'))
