"""
Create mappings from urls to Django views.

This file wires up urls from HTTP requests to the methods used
in the reporting application to generate the report content.

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

from views import loadbard, getreport, index

urlpatterns = patterns(
    '',
    # Example:
    # (r'^reporting/', include('reporting.foo.urls')),
    (r'^$', index),
    (r'^loadbard/', loadbard),
    (r'^getreport/$', getreport),
)
