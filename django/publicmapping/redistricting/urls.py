"""
Define the urls used in the redistricting app.

This file uses django's extensible url mapping framework to extend the
project urls based on this app's urls.

This file is part of The Public Mapping Project
http://sourceforge.net/projects/publicmapping/

License:
    Copyright 2010 Micah Altman, Michael McDonald

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

from django.conf.urls.defaults import *
from django.conf import settings

urlpatterns = patterns('publicmapping.redistricting.views',
    (r'^$', 'viewplan', { 'planid': 0 }),
    (r'^plan/create/$', 'createplan'),
    (r'^plan/upload/$', 'uploadfile'),
    (r'^plan/(?P<planid>\d*)/view/$', 'viewplan'),
    (r'^plan/(?P<planid>\d*)/edit/$', 'editplan'),
    (r'^plan/(?P<planid>\d*)/getreport/$', 'getreport'),
    (r'^plan/(?P<planid>\d*)/attributes/', 'editplanattributes'),
    (r'^plan/(?P<planid>\d*)/copy/$', 'copyplan'),
    (r'^plan/(?P<planid>\d*)/district/(?P<districtid>\d*)/add', 'addtodistrict'),
    (r'^plan/(?P<planid>\d*)/demographics', 'getdemographics'),
    (r'^plan/(?P<planid>\d*)/geography', 'getgeography'),
    (r'^plan/(?P<planid>\d*)/districts', 'getdistricts'), 
    (r'^plan/(?P<planid>\d*)/district/new', 'newdistrict'),
    (r'^plan/(?P<planid>\d*)/district/versioned', 'simple_district_versioned'),
    (r'^plan/(?P<planid>\d*)/districtindexfile/', 'getdistrictindexfile'),
    (r'^plan/(?P<planid>\d*)/districtindexfilestatus/', 'getdistrictindexfilestatus'),
    (r'^getplans/', 'getplans'),
    (r'^loadbard/$', 'loadbard'),
)
