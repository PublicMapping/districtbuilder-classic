"""
Extra tags and templates used in the django 
templating system for the redistricting app.

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

from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()

@register.filter
@stringfilter
def truncate(value, length):
    """
    This filter reduces the given string value to length 
    and appends an ellipsis to the end. If the string is
    not of the given length, it is returned as-is
    Parameters:
        value - A string value
        length - The length of the string desired (ellipsis included)
    """
    try:
        length = int(length)
        if len(value) > length:
            short = format('%s%s' % (value[:length - 3], '...'))
            return short
        return value
    except:
        return value
