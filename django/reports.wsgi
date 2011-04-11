#!/bin/python
#
#   Copyright 2010 Micah Altman, Michael McDonald
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
#   This file is part of The Public Mapping Project
#   http://sourceforge.net/projects/publicmapping/
#
#   Purpose:
#       reports.wsgi is a mod_wsgi web application configuration file
#
#       This file configures mod_wsgi to run the reporting component of
#       the Python Django web application.  This file is referenced by the 
#       file publicmapping.apache, which configures an Apache web server for
#       The Public Mapping Project.
#
#   Author: 
#       Andrew Jennings, David Zwarg
#


import os
import sys

os.environ['DJANGO_SETTINGS_MODULE'] = 'reporting.settings'

sys.path.append('/projects/publicmapping/trunk/django')
sys.path.append('/projects/publicmapping/trunk/django/reporting')

import django.core.handlers.wsgi
application = django.core.handlers.wsgi.WSGIHandler()

