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
#       Create mappings from urls to Django views.
#
#       This file wires up urls from HTTP requests to the methods used
#       in the web application to generate the views(content).
#
#   Author: David Zwarg, Andrew Jennings
#

from django.conf.urls.defaults import *
from django.conf import settings

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    # Example:
    # (r'^publicmapping/', include('publicmapping.foo.urls')),

    # Uncomment the admin/doc line below and add 'django.contrib.admindocs' 
    # to INSTALLED_APPS to enable admin documentation:
    # (r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    (r'^admin/', include(admin.site.urls)),
    (r'^accounts/register/$', 'publicmapping.views.userregister'),
    (r'^accounts/login/$', 'django.contrib.auth.views.login', {'template_name': 'index.html'}),
    (r'^accounts/logout/$', 'publicmapping.views.userlogout'),
    (r'^accounts/forgot/$', 'publicmapping.views.forgotpassword'),
    (r'^districtmapping/', include('publicmapping.redistricting.urls')),
    (r'^$', 'publicmapping.views.index'),
    (r'^proxy$', 'publicmapping.views.proxy'),
)

# Only if this application is running in debug mode, serve up the static
# content via django. In a production environment, these files should be 
# served by apache.
if settings.DEBUG:
    urlpatterns += patterns('',
        (r'^site-media/(?P<path>.*)$', 'django.views.static.serve', {'document_root': settings.MEDIA_ROOT }),
        (r'^sld/(?P<path>.*)$', 'django.views.static.serve', {'document_root': settings.SLD_ROOT }),
    )

