"""
Configuration settings for The Public Mapping Project

This file contains application settings for the web application,
The Public Mapping Project. This file requires a local configuration
file that contains site- and machine-specific configuration settings
in /projects/PublicMapping/local/settings.ini

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
    David Zwarg, Andrew Jennings, Kenny Shepard
"""

# Django settings for publicmapping project.

DEBUG = False
TEMPLATE_DEBUG = DEBUG
SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# Use these settings to localize numbers within the application
USE_L10N = True
NUMBER_GROUPING = 3
USE_THOUSAND_SEPARATOR = True

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://media.lawrence.com", "http://example.com/media/"
MEDIA_URL = '/site-media/'

# URL that handles the media served from STATIC_ROOT. Make sure to
# use a trailing slash
STATIC_URL = '/static-media/'

# django-rosetta still uses this, even if it's obsolete in 1.4
ADMIN_MEDIA_PREFIX = STATIC_URL + 'admin/'

# Sessions expire when browser is close
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# Require https connections to send cookies
SESSION_COOKIE_SECURE = False

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
#     'django.template.loaders.eggs.load_template_source',
)

# configure cache, according to guidelines for configuring django's
# cache framework: http://docs.djangoproject.com/en/1.4/topics/cache
#CACHES = {
#    'default': {
#        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
#        'LOCATION': 'redistricting4ever',
#        'TIMEOUT': 600, # 10 minute timeout
#        'OPTIONS': {
#            'MAX_ENTRIES': 1000
#        }
#    }
#}

# Middleware classes. Please note that cache middleware MUST be placed in
# the first and last positions of the middleware classes.  Order matters.
MIDDLEWARE_CLASSES = (
#    'django.middleware.cache.UpdateCacheMiddleware',
    'django.middleware.gzip.GZipMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.locale.LocaleMiddleware',
#    'django.middleware.cache.FetchFromCacheMiddleware',
)

TEMPLATE_CONTEXT_PROCESSORS = (
    'django.contrib.auth.context_processors.auth',
    'django.core.context_processors.debug',
    'django.core.context_processors.i18n',
    'django.core.context_processors.media',
    'django.contrib.messages.context_processors.messages',
    'publicmapping.context_processors.banner_image',
)

AUTH_PROFILE_MODULE = 'redistricting.Profile'

ROOT_URLCONF = 'publicmapping.urls'

# Settings for django-celery process queue
import djcelery
djcelery.setup_loader()

BROKER_URL = 'django://'

from datetime import timedelta
CELERYBEAT_SCHEDULE = {
    'cleanup-sessions': {
        'task': 'redistricting.tasks.cleanup',
        'schedule': timedelta(hours=1),
        'args': None
    },
}

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.humanize',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.admin',
    'django.contrib.gis',
    'django.contrib.comments',
    'djcelery',
    'djcelery.transport',
    'redistricting',
    'tagging',
    'rosetta',
    'django.contrib.staticfiles',
    'compressor',
    'publicmapping', # needed for i18n
)

# Compressor settings
COMPRESS_ENABLED = not DEBUG
COMPRESS_PARSER = 'compressor.parser.HtmlParser'

STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'compressor.finders.CompressorFinder',
)

# end Compressor settings

#
# Settings specific to The Public Mapping Project
#

# This is the base url for the application, where the login page is
LOGIN_URL = '/'

# Where the user is redirected after login
LOGIN_REDIRECT_URL = '/admin/'

# Enable logging
import sys
LOGGING = {
    'version': 1,
    'handlers': {
        'default': {
            'class': 'logging.StreamHandler',
            'stream': sys.stderr
        }
    },
    'loggers': {
        'django': {
            'handlers':['default'],
            'level': 'CRITICAL'
        },
        'redistricting': {
            'handlers':['default'],
            'level': 'DEBUG' if DEBUG else 'WARNING'
        }
    }
}

BANNER_IMAGE = '/static-media/images/banner-home-es.png'

ADMINS = (
  ('ADMIN-USER-NAME',
  'ADMIN-EMAIL'),
)
MANAGERS = ADMINS

SECRET_KEY = 'gw)fa5$#=&xb+20l!9(61#!jvw+l!iz%_(1ao!2u8&=3zt5_^5'

WEB_TEMP = '/projects/PublicMapping/local/reports'

REPORTS_ENABLED = 'CALC'
TIME_ZONE = 'US/Eastern'
LANGUAGES = (
    ('en', 'English'),
    ('fr', 'French'),
    ('es', 'Spanish'),
    ('ja', 'Japanese'),
)
# Modify to change the language of the application
LANGUAGE_CODE = 'en'


#
# Automatically generated settings.
#
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': 'YOUR-DATABASE-NAME',
        'USER': 'publicmapping',
        'PASSWORD': 'YOUR-DATABASE-PASSWORD',
        'HOST': 'OPTIONAL',
    }
}

MAP_SERVER = ''
BASE_MAPS = 'None'
MAP_SERVER_NS = 'pmp'
MAP_SERVER_NSHREF = 'https://github.com/PublicMapping/'
FEATURE_LIMIT = 100
MAP_SERVER_USER = 'GEOSERVER-ADMIN-USER'
MAP_SERVER_PASS = 'GEOSERVER-ADMIN-PASS'

ADJACENCY = False

CONVEX_CHOROPLETH = False

EMAIL_HOST = 'localhost'
EMAIL_PORT = 25
EMAIL_HOST_USER = ''
EMAIL_HOST_PASSWORD = ''
EMAIL_SUBJECT_PREFIX = 'None '

MEDIA_ROOT = '/projects/PublicMapping/DistrictBuilder/django/publicmapping/site-media/'

STATIC_ROOT = '/projects/PublicMapping/DistrictBuilder/django/publicmapping/static-media/'

TEMPLATE_DIRS = (
  '/projects/PublicMapping/DistrictBuilder/django/publicmapping/templates',
)

SLD_ROOT = '/projects/PublicMapping/DistrictBuilder/sld/'

STATICFILES_DIRS = (
  '/projects/PublicMapping/DistrictBuilder/django/publicmapping/static/',
)

CONCURRENT_SESSIONS = 5 
SESSION_TIMEOUT = 15

GA_ACCOUNT = None
GA_DOMAIN = None

MAX_UPLOAD_SIZE = 5300 * 1024

FIX_UNASSIGNED_MIN_PERCENT = 99

FIX_UNASSIGNED_COMPARATOR_SUBJECT = 'poptot'

MAX_UNDOS_DURING_EDIT = 0

MAX_UNDOS_AFTER_EDIT = 0

LEADERBOARD_MAX_RANKED = 10
