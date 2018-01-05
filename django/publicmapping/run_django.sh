#!/bin/sh

# Run celery worker in background
# TODO: Don't use C_FORCE_ROOT
C_FORCE_ROOT=1 python manage.py celery worker --loglevel=info &

# Run Django with Gunicorn
/usr/local/bin/gunicorn \
  --workers=2 \
  --timeout=60 \
  --bind=0.0.0.0:8080 \
  --reload \
  --log-level=debug \
  --access-logfile=- \
  --error-logfile=- \
  -kgevent \
  publicmapping.wsgi
