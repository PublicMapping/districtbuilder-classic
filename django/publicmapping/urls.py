"""
Create mappings from urls to Django views.

This file wires up urls from HTTP requests to the methods used
in the web application to generate the views(content).

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
    Andrew Jennings, David Zwarg
"""

from django.conf.urls.defaults import *
from django.conf import settings
from django.contrib import admin

admin.autodiscover()

js_info_dict = { 
    'domain': 'djangojs',
    'packages': ('publicmapping','redistricting',), 
} 

urlpatterns = patterns('',
    (r'^i18n/', include('django.conf.urls.i18n')), 
    (r'^rosetta/', include('rosetta.urls')), 
    (r'^jsi18n/$', 'django.views.i18n.javascript_catalog', js_info_dict), 
    (r'^admin/', include(admin.site.urls)),
    (r'^accounts/register/$', 'publicmapping.views.userregister'),
    (r'^accounts/login/$', 'django.contrib.auth.views.login', {'template_name': 'index.html'}),
    (r'^accounts/logout/$', 'publicmapping.views.userlogout'),
    (r'^accounts/forgot/$', 'publicmapping.views.forgotpassword'),
    (r'^accounts/update/$', 'publicmapping.views.userupdate'),
    (r'^districtmapping/', include('publicmapping.redistricting.urls')),
    (r'^comments/', include('django.contrib.comments.urls')),
    (r'^$', 'publicmapping.views.index'),
    (r'^proxy', 'publicmapping.views.proxy'),
    (r'^session/$', 'publicmapping.views.session'),
)

# Only if this application is running in debug mode, serve up the static
# content via django. In a production environment, these files should be 
# served by apache.
if settings.DEBUG:
    urlpatterns += patterns('',
        (r'^site-media/(?P<path>.*)$/', 'django.views.static.serve', {'document_root': settings.MEDIA_ROOT }),
        (r'^static-media/(?P<path>.*)/$', 'django.views.static.serve', {'document_root': settings.STATIC_ROOT }),
        (r'^sld/(?P<path>.*)/$', 'django.views.static.serve', {'document_root': settings.SLD_ROOT }),
    )

