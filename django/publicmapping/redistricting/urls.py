"""
Define the urls used in the redistricting app.

This file uses django's extensible url mapping framework to extend the
project urls based on this app's urls.

This file is part of The Public Mapping Project
https://github.com/PublicMapping/

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
    Andrew Jennings, David Zwarg, Kenny Shepard
"""

from django.conf.urls.defaults import *
from django.conf import settings

urlpatterns = patterns('publicmapping.redistricting.views',
    (r'^$', 'viewplan', { 'planid': 0 }),
    (r'^plan/create/$', 'createplan'),
    (r'^plan/upload/$', 'uploadfile'),
    (r'^plan/(?P<planid>\d*)/view/$', 'viewplan'),
    (r'^plan/(?P<planid>\d*)/edit/$', 'editplan'),
    (r'^plan/(?P<planid>\d*)/print/$', 'printplan'),
    (r'^plan/(?P<planid>\d*)/getreport/$', 'getreport'),
    (r'^plan/(?P<planid>\d*)/getcalculatorreport/$', 'getcalculatorreport'),
    (r'^plan/(?P<planid>\d*)/attributes/$', 'editplanattributes'),
    (r'^plan/(?P<planid>\d*)/delete/$', 'deleteplan'),
    (r'^plan/(?P<planid>\d*)/copy/$', 'copyplan'),
    (r'^plan/(?P<planid>\d*)/unload/$', 'unloadplan'),
    (r'^plan/(?P<planid>\d*)/score/$', 'scoreplan'),
    (r'^plan/(?P<planid>\d*)/district/(?P<districtid>\d*)/add/', 'addtodistrict'),
    (r'^plan/(?P<planid>\d*)/district/(?P<district_id>\d*)/lock/', 'setdistrictlock'),
    (r'^plan/(?P<planid>\d*)/district/(?P<district_id>\d*)/info/$', 'district_info'),
    (r'^plan/(?P<planid>\d*)/demographics/$', 'get_statistics'),
    (r'^plan/(?P<planid>\d*)/districts/$', 'getdistricts'), 
    (r'^plan/(?P<planid>\d*)/district/new/$', 'newdistrict'),
    (r'^plan/(?P<planid>\d*)/shareddistricts/$', 'get_shared_districts'), 
    (r'^plan/(?P<planid>\d*)/pastedistricts/$', 'add_districts_to_plan'),
    (r'^plan/(?P<planid>\d*)/districtmembers/$', 'assign_district_members'),
    (r'^plan/(?P<planid>\d*)/combinedistricts/$', 'combine_districts'),
    (r'^plan/(?P<planid>\d*)/fixunassigned/$', 'fix_unassigned'),
    (r'^plan/(?P<planid>\d*)/district/versioned/$', 'simple_district_versioned'),
    (r'^plan/(?P<planid>\d*)/unlockedgeometries/$', 'get_unlocked_simple_geometries'),
    (r'^plan/(?P<planid>\d*)/districtfile/$', 'getdistrictfile'),
    (r'^plan/(?P<planid>\d*)/districtindexfilesend/$', 'emaildistrictindexfile'),
    (r'^plan/(?P<planid>\d*)/districtfilestatus/$', 'getdistrictfilestatus'),
    (r'^plan/(?P<planid>\d*)/statisticssets/$', 'statistics_sets'),
    (r'^plan/(?P<planid>\d*)/splits/(?P<othertype>\w+)/(?P<otherid>\d*)/$', 'get_splits'),
    (r'^plan/(?P<planid>\d*)/splitsreport/$', 'get_splits_report'),
    (r'^getplans/$', 'getplans'),
    (r'^getleaderboard/$', 'getleaderboard'),
    (r'^getleaderboardcsv/$', 'getleaderboardcsv'),
    (r'^health/$', 'get_health'),
    (r'^feed/plans/$', 'plan_feed'),
    (r'^feed/shared/$', 'share_feed'),
)
