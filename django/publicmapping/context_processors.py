"""
Context processors for the DistrictBuilder web application.

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
    Geoffrey Hing, David Zwarg
"""

from django.conf import settings


def banner_image(request):
    """
    Add a banner_image variable to the template context.

    This context processors has to be added to the 
    TEMPLATE_CONTEXT_PROCESSORS dictionary in settings.py to be available.

    Users will need to set a BANNER_IMAGE variable in settings.py that 
    points to the URL path to the banner image.  The banner image 
    defaults to '/static/images/banner-home.png'

    @param request: The HttpRequest
    """
    context_dict = {}
    if 'BANNER_IMAGE' in settings.__members__:
        context_dict['banner_image'] = settings.BANNER_IMAGE
    else:
        context_dict['banner_image'] = '/static/images/banner-home.png'

    return context_dict
