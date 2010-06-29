#!/bin/python

import os
import sys

os.environ['DJANGO_SETTINGS_MODULE'] = 'publicmapping.settings'

sys.path.append('/projects/publicmapping/trunk/django')
sys.path.append('/projects/publicmapping/trunk/django/publicmapping')

import django.core.handlers.wsgi
application = django.core.handlers.wsgi.WSGIHandler()

