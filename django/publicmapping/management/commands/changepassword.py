import getpass
from optparse import make_option

from hashlib import sha1

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import DEFAULT_DB_ALIAS


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (make_option(
        '--database',
        action='store',
        dest='database',
        default=DEFAULT_DB_ALIAS,
        help='Specifies the database to use. Default is "default".'), )
    help = "Change a user's password for django.contrib.auth."

    requires_model_validation = False

    def _get_pass(self, prompt="Password: "):
        p = getpass.getpass(prompt=prompt)
        if not p:
            raise CommandError("aborted")
        return p

    def handle(self, *args, **options):
        if len(args) > 1:
            raise CommandError(
                "need exactly one or zero arguments for username")

        if args:
            username, = args
        else:
            username = getpass.getuser()

        try:
            u = User.objects.get(username__exact=username)
        except User.DoesNotExist:
            raise CommandError("user '%s' does not exist" % username)

        self.stdout.write("Changing password for user '%s'\n" % u)

        MAX_TRIES = 3
        count = 0
        p1, p2 = 1, 2  # To make them initially mismatch.
        while p1 != p2 and count < MAX_TRIES:
            p1 = self._get_pass()
            p2 = self._get_pass("Password (again): ")
            if p1 != p2:
                self.stdout.write(
                    "Passwords do not match. Please try again.\n")
                count = count + 1

        if count == MAX_TRIES:
            raise CommandError(
                "Aborting password change for user '%s' after %s attempts" %
                (u, count))

        # Need to add a custom hash here to replicate
        # what is done with javascript client-side in the change-password
        # forms of district builder. See redistricting.views.emailpassword
        # for another example of this.
        s = sha1()
        s.update(p1)
        u.set_password(s.hexdigest())
        u.save()

        return "Password changed successfully for user '%s'" % u
