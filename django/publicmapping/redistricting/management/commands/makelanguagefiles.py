#!/usr/bin/python
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
    option_list = BaseCommand.option_list + (
        make_option('-t', '--templates', dest="templates", action="store_true", help="Create template message files.", default=False),
        make_option('-j', '--javascript', dest="javascript", action="store_true", help="Create javascript message files.", default=False),
        make_option('-c', '--compile', dest="compile", action="store_true", help="Compile message files.", default=False),
        make_option('-l', '--locale', dest='locale', default=None, action='store', help='Specify a locale.'),
    )

    def handle(self, *args, **options):
        """
        Create and compile language message files
        """
        # Execute every action if either all or none of the options are specified
        everything = options.get("templates") == options.get("javascript") == options.get("compile")

        # Use the specified locale, or if none are provided, use all defined in settings
        locale = options.get("locale")
        locales = [locale] if locale else [l[0] for l in settings.LANGUAGES]
        
        # Make messages for each available locale
        for locale in locales:
            # Make messages for templates (.html, .txt, .email)
            if everything or options.get("templates"):
                management.call_command('makemessages', locale=locale, extensions=['html','txt','email'], interactive=False)    
        
            # Make messages for javascript
            if everything or options.get("javascript"):
                management.call_command('makemessages', locale=locale, domain='djangojs', interactive=False)

            # Compile message file
            if everything or options.get("compile"):
                management.call_command('compilemessages', locale=locale, interactive=False)
