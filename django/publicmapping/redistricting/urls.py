"""
Define the urls used in the redistricting app.

This file uses django's extensible url mapping framework to extend the
project urls based on this app's urls.

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
    Andrew Jennings, David Zwarg, Kenny Shepard
"""

from django.conf.urls import url, include

from . import views as redistricting_views

urlpatterns = [
    url(r'plan/$', redistricting_views.viewplan, {'planid': 0}),
    url(r'plan/create/$', redistricting_views.createplan),
    url(r'plan/upload/$', redistricting_views.uploadfile),
    url(r'plan/(?P<planid>\d*)/view/$',
        redistricting_views.viewplan,
        name='plan-view'),
    url(r'plan/(?P<planid>\d*)/edit/$', redistricting_views.editplan),
    url(r'plan/(?P<planid>\d*)/print/$', redistricting_views.printplan),
    url(r'plan/(?P<planid>\d*)/getcalculatorreport/$',
        redistricting_views.getcalculatorreport),
    url(r'plan/(?P<planid>\d*)/attributes/$',
        redistricting_views.editplanattributes),
    url(r'plan/(?P<planid>\d*)/delete/$', redistricting_views.deleteplan),
    url(r'plan/(?P<planid>\d*)/copy/$', redistricting_views.copyplan),
    url(r'plan/(?P<planid>\d*)/unload/$', redistricting_views.unloadplan),
    url(r'plan/(?P<planid>\d*)/score/$', redistricting_views.scoreplan),
    url(r'plan/(?P<planid>\d*)/reaggregate/$',
        redistricting_views.reaggregateplan),
    url(r'plan/(?P<planid>\d*)/district/(?P<districtid>\d*)/add/',
        redistricting_views.addtodistrict),
    url(r'plan/(?P<planid>\d*)/district/(?P<district_id>\d*)/lock/',
        redistricting_views.setdistrictlock),
    url(r'plan/(?P<planid>\d*)/district/(?P<district_id>\d*)/info/$',
        redistricting_views.district_info),
    url(r'plan/(?P<planid>\d*)/demographics/$',
        redistricting_views.get_statistics),
    url(r'plan/(?P<planid>\d*)/districts/$', redistricting_views.getdistricts),
    url(r'plan/(?P<planid>\d*)/district/new/$',
        redistricting_views.newdistrict),
    url(r'plan/(?P<planid>\d*)/shareddistricts/$',
        redistricting_views.get_shared_districts),
    url(r'plan/(?P<planid>\d*)/pastedistricts/$',
        redistricting_views.add_districts_to_plan),
    url(r'plan/(?P<planid>\d*)/districtmembers/$',
        redistricting_views.assign_district_members),
    url(r'plan/(?P<planid>\d*)/combinedistricts/$',
        redistricting_views.combine_districts),
    url(r'plan/(?P<planid>\d*)/fixunassigned/$',
        redistricting_views.fix_unassigned),
    url(r'plan/(?P<planid>\d*)/district/versioned/$',
        redistricting_views.simple_district_versioned),
    url(r'plan/(?P<planid>\d*)/unlockedgeometries/$',
        redistricting_views.get_unlocked_simple_geometries),
    url(r'plan/(?P<planid>\d*)/districtfile/$',
        redistricting_views.getdistrictfile),
    url(r'plan/(?P<planid>\d*)/districtindexfilesend/$',
        redistricting_views.emaildistrictindexfile),
    url(r'plan/(?P<planid>\d*)/districtfilestatus/$',
        redistricting_views.getdistrictfilestatus),
    url(r'plan/(?P<planid>\d*)/statisticssets/$',
        redistricting_views.statistics_sets),
    url(r'plan/(?P<planid>\d*)/splits/(?P<othertype>\w+)/(?P<otherid>\d*)/$',
        redistricting_views.get_splits),
    url(r'plan/(?P<planid>\d*)/splitsreport/$',
        redistricting_views.get_splits_report),
    url(r'getplans/$', redistricting_views.getplans),
    url(r'getleaderboard/$', redistricting_views.getleaderboard),
    url(r'getleaderboardcsv/$', redistricting_views.getleaderboardcsv),
    url(r'health/$', redistricting_views.get_health),
    url(r'processingstatus/$', redistricting_views.get_processing_status),
    url(r'feed/plans/$', redistricting_views.plan_feed, name='plan-feed'),
    url(r'feed/shared/$', redistricting_views.share_feed, name='share-feed'),
    url(r'i18n/', include('django.conf.urls.i18n')),
]
