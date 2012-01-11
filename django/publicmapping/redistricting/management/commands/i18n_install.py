"""
Install the internationalization messages for a running DistrictBuilder
instance. This management command reads the database fields for all strings
that should be internationalized, and places them in and xmlconfig.po file
for use in localization.

This file is part of The Public Mapping Project
https://github.com/PublicMapping/

License:
    Copyright 2011 Micah Altman, Michael McDonald

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
from rosetta import polib
from redistricting.models import *
import os
from datetime import datetime, tzinfo, timedelta

logger = logging.getLogger(__name__)

class UTC(tzinfo):
    """UTC"""
    def utcoffset(self, dt):
        return timedelta(0)
    def tzname(self, dt):
        return 'UTC'
    def dst(self, dt):
        return timedelta(0)

class Command(BaseCommand):
    """
    This command migrates all database configured strings into a set of 
    message files in the 'xmlconfig' domain.
    """
    args = None
    help = 'Migrate database labels into internationalized message files.'
    option_list = BaseCommand.option_list + (
        make_option('-l', '--locale', dest='locale', default=None, action='store', help='Specify a locale.'),
    )

    def setup_logging(self, verbosity):
        """
        Setup the logging facility.
        """
        level = logging.WARNING
        if verbosity > 1:
            level = logging.DEBUG
        elif verbosity > 0:
            level = logging.INFO

        logging.basicConfig(level=level, format='%(message)s')
        logging._srcfile = None
        logging.logThreads = 0
        logging.logProcesses = 0

    def add_or_update(self, msgid='', msgstr=''):
        entry = self.pofile.find(msgid)
        if entry is None:
            entry = polib.POEntry(msgid=msgid, msgstr=msgstr)
            self.pofile.append(entry)
        else:
            entry.msgstr = msgstr

    def handle(self, *args, **options):
        """
        Migrate database settings for labels, descriptions, and other text
        into .po message files.
        """
        self.setup_logging(int(options.get('verbosity')))

        # Use the specified locale, or if none are provided, use all defined in settings
        locale = options.get("locale")
        locales = [locale] if locale else [l[0] for l in settings.LANGUAGES]
        
        # Make messages for each available locale
        for locale in locales:
            logger.info('Processing locale %(locale)s', {'locale':locale})

            pofilepath = 'locale/%s/LC_MESSAGES/xmlconfig.po' % locale
            if os.path.exists(pofilepath):
                logger.debug('Using existing xmlconfig message catalog.')
                self.pofile = polib.pofile(pofilepath, check_for_duplicates=True)
            else:
                logger.debug('Creating new xmlconfig message catalog.')
                now = datetime.utcnow()
                now = now.replace(tzinfo=UTC())

                self.pofile = polib.POFile(check_for_duplicates=True)
                self.pofile.metadata = {
                    'Project-Id-Version': '1.0',
                    'Report-Msgid-Bugs-To': 'districtbuilder-dev@googlegroups.com',
                    'POT-Creation-Date': now.strftime('%Y-%m-%d %H:%M%z'),
                    'PO-Revision-Date': now.strftime('%Y-%m-%d %H:%M%z'),
                    'Last-Translator': '%s <%s>' % (settings.ADMINS[0][0], settings.ADMINS[0][1]),
                    'Language-Team': '%s <%s>' % (settings.ADMINS[0][0], settings.ADMINS[0][1]),
                    'Language': locale,
                    'MIME-Version': '1.0',
                    'Content-Type': 'text/plain; charset=UTF-8',
                    'Content-Transfer-Encoding': '8bit'
                }

            for region in Region.objects.all():
                # The label of the region
                self.add_or_update(
                    msgid=u'%s label' % region.name,
                    msgstr=region.label
                )
                # The description of the region
                self.add_or_update(
                    msgid=u'%s description' % region.name,
                    msgstr=region.description
                )

                for legislativebody in region.legislativebody_set.all():
                    # The name of the legislative body
                    self.add_or_update(
                        msgid=u'%s name' % legislativebody.name,
                        msgstr=legislativebody.name
                    )
                    # The short label for all districts in this body
                    self.add_or_update(
                        msgid=u'%s short label' % legislativebody.name,
                        msgstr=legislativebody.short_label.replace('%s', '%(district_id)s')
                    )
                    # The long label for all districts in this body
                    self.add_or_update(
                        msgid=u'%s long label' % legislativebody.name,
                        msgstr=legislativebody.long_label.replace('%s', '%(district_id)s')
                    )

                    # No messages in plans or districts or computed scores of any type

            for geolevel in Geolevel.objects.all():
                # The label for the geolevel
                self.add_or_update(
                    msgid=u'%s label' % geolevel.name,
                    msgstr=geolevel.label
                )

            for scoredisplay in ScoreDisplay.objects.all():
                # The title for the score display
                self.add_or_update(
                    msgid=u'%s title' % scoredisplay.title, #TODO: change this to 'name'
                    msgstr=scoredisplay.title
                )

            for scorefunction in ScoreFunction.objects.all():
                # The label for the score function
                self.add_or_update(
                    msgid=u'%s label' % scorefunction.name,
                    msgstr=scorefunction.label
                )

                # The description for the score function
                self.add_or_update(
                    msgid=u'%s description' % scorefunction.name,
                    msgstr=scorefunction.description
                )

            for scorepanel in ScorePanel.objects.all():
                # The title for the score panel
                self.add_or_update(
                    msgid=u'%s title' % scorepanel.title, #TODO: change this to 'name'
                    msgstr=scorepanel.title
                )

            for subject in Subject.objects.all():
                # The display of the subject
                self.add_or_update(
                    msgid=u'%s display' % subject.name,
                    msgstr=subject.display
                )
                # The short display of the subject
                self.add_or_update(
                    msgid=u'%s short display' % subject.name,
                    msgstr=subject.short_display
                )
                # The description of the subject
                self.add_or_update(
                    msgid=u'%s description' % subject.name,
                    msgstr=subject.description
                )

            for validationcriterion in ValidationCriteria.objects.all():
                # The description of the validation criterion
                self.add_or_update(
                    msgid=u'%s description' % validationcriterion.name,
                    msgstr=validationcriterion.description
                )

            logger.debug('Saving file %(po)s.', {'po':pofilepath})
            self.pofile.save(pofilepath)
