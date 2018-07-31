from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.signals import task_failure
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

# Wire up Rollbar
# The Rollbar docs suggest https://www.mattlayman.com/2017/django-celery-rollbar.html so that's what
# I used.
from django.conf import settings
if settings.ROLLBAR is not None and bool(os.environ.get('CELERY_ROLLBAR', False)):
    import rollbar
    rollbar.init(**settings.ROLLBAR)

    def celery_base_data_hook(request, data):
        data['framework'] = 'celery'

    rollbar.BASE_DATA_HOOK = celery_base_data_hook

    @task_failure.connect
    def handle_task_failure(**kw):
        rollbar.report_exc_info(extra_data=kw)
