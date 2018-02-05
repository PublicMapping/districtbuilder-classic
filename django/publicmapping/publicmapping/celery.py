from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from . import REDIS_URL

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "publicmapping.settings")

# Configure Celery app to use Redis as both the results backend and the message broker.
app = Celery('publicmapping', backend=REDIS_URL, broker=REDIS_URL)

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()
