#!/usr/bin/python
from django.core.management.base import BaseCommand
from redistricting.utils import *

class Command(BaseCommand):
    """
    This command prints creates and compiles language message files
    """
    args = None
    help = 'Create and compile language message files'

    def handle(self, *args, **options):
        """
        Create and compile language message files
        """
        # Make messages for each language defined in settings
        for language in settings.LANGUAGES:
            # For django templates
            management.call_command('makemessages', locale=language[0], interactive=False)

            # For javascript files
            management.call_command('makemessages', domain='djangojs', locale=language[0], interactive=False)

        # Compile all message files
        management.call_command('compilemessages', interactive=False)
