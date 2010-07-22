from ConfigParser import RawConfigParser

config = RawConfigParser()
config.read('/projects/publicmapping/local/settings.ini')

# Django settings for publicmapping project.

DEBUG = True
TEMPLATE_DEBUG = DEBUG

ADMINS = (
    (config.get('publicmapping','ADMIN_USER'), 
     config.get('publicmapping','ADMIN_EMAIL')),
)

MANAGERS = ADMINS

DATABASE_ENGINE = 'postgresql_psycopg2'   # 'postgresql_psycopg2', 'postgresql', 'mysql', 'sqlite3' or 'oracle'.
DATABASE_NAME = config.get('database','DATABASE_NAME')  # Or path to database file if using sqlite3.
DATABASE_USER = config.get('database', 'DATABASE_USER')  # Not used with sqlite3.
DATABASE_PASSWORD = config.get('database', 'DATABASE_PASSWORD')   # Not used with sqlite3.
DATABASE_HOST = ''             # Set to empty string for localhost. Not used with sqlite3.
DATABASE_PORT = ''             # Set to empty string for default. Not used with sqlite3.

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'America/Chicago'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# Absolute path to the directory that holds media.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = '/projects/publicmapping/trunk/django/publicmapping/site-media/'

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://media.lawrence.com", "http://example.com/media/"
MEDIA_URL = '/site-media/'

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = '/media/'

# Make this unique, and don't share it with anybody.
SECRET_KEY = 'azscw8%!^i+((pwgvobc)peppb=hx3hmd7yo)3rxxqehe5d(v!'

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.load_template_source',
    'django.template.loaders.app_directories.load_template_source',
#     'django.template.loaders.eggs.load_template_source',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
)

ROOT_URLCONF = 'publicmapping.urls'

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
    '/projects/publicmapping/trunk/django/publicmapping/templates',
)

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.admin',
    'django.contrib.gis',
    'redistricting',
)

LOGIN_URL = '/'
MAP_SERVER = config.get('publicmapping', 'MAP_SERVER')
BASE_GEOLEVEL = 3
TEST_RUNNER = 'django.contrib.gis.tests.run_tests'
POSTGIS_TEMPLATE='template_postgis'
MAX_DISTRICTS = 18
PLAN_TEMPLATE = 'default'
