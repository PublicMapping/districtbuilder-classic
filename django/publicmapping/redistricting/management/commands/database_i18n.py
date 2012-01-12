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
from redistricting.config import *

logger = logging.getLogger(__name__)

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

            poutil = PoUtils(locale)

            for region in Region.objects.all():
                # The label of the region
                poutil.add_or_update(
                    msgid=u'%s label' % region.name,
                    msgstr=region.label
                )
                # The description of the region
                poutil.add_or_update(
                    msgid=u'%s description' % region.name,
                    msgstr=region.description
                )

                for legislativebody in region.legislativebody_set.all():
                    # The name of the legislative body
                    poutil.add_or_update(
                        msgid=u'%s name' % legislativebody.name,
                        msgstr=legislativebody.name
                    )
                    # The short label for all districts in this body
                    poutil.add_or_update(
                        msgid=u'%s short label' % legislativebody.name,
                        msgstr=legislativebody.short_label.replace('%s', '%(district_id)s')
                    )
                    # The long label for all districts in this body
                    poutil.add_or_update(
                        msgid=u'%s long label' % legislativebody.name,
                        msgstr=legislativebody.long_label.replace('%s', '%(district_id)s')
                    )

                    # No messages in plans or districts or computed scores of any type

            for geolevel in Geolevel.objects.all():
                # The label for the geolevel
                poutil.add_or_update(
                    msgid=u'%s label' % geolevel.name,
                    msgstr=geolevel.label
                )

            for scoredisplay in ScoreDisplay.objects.all():
                # The title for the score display
                if 'name' in scoredisplay.__dict__:
                    sdname = scoredisplay.name
                else:
                    sdname = scoredisplay.title

                poutil.add_or_update(
                    msgid=u'%s title' % sdname,
                    msgstr=scoredisplay.title
                )

            for scorefunction in ScoreFunction.objects.all():
                # The label for the score function
                poutil.add_or_update(
                    msgid=u'%s label' % scorefunction.name,
                    msgstr=scorefunction.label
                )

                # The description for the score function
                poutil.add_or_update(
                    msgid=u'%s description' % scorefunction.name,
                    msgstr=scorefunction.description
                )

            for scorepanel in ScorePanel.objects.all():
                # The title for the score panel
                if 'name' in scorepanel.__dict__:
                    spname = scorepanel.name
                else:
                    spname = scorepanel.title

                poutil.add_or_update(
                    msgid=u'%s title' % spname,
                    msgstr=scorepanel.title
                )

            for subject in Subject.objects.all():
                # The display of the subject
                poutil.add_or_update(
                    msgid=u'%s display' % subject.name,
                    msgstr=subject.display
                )
                # The short display of the subject
                poutil.add_or_update(
                    msgid=u'%s short display' % subject.name,
                    msgstr=subject.short_display
                )
                # The description of the subject
                poutil.add_or_update(
                    msgid=u'%s description' % subject.name,
                    msgstr=subject.description
                )

            for validationcriterion in ValidationCriteria.objects.all():
                # The description of the validation criterion
                poutil.add_or_update(
                    msgid=u'%s description' % validationcriterion.name,
                    msgstr=validationcriterion.description
                )

            poutil.save()
