APPDIR="/projects/PublicMapping/DistrictBuilder"

echo <<EOF > /etc/default/celeryd
# Where to chdir at start.
CELERYD_CHDIR="$APPDIR/django/publicmapping/"
# Path to celeryd
CELERYD="$APPDIR/django/publicmapping/manage.py celeryd_detach"
# Options for celeryd that start the scheduler
CELERYD_OPTS='-B -s /tmp/celerybeat-schedule'
# Name of the projects settings module.
export DJANGO_SETTINGS_MODULE='settings'
# Include the 'publicmapping' module
export PYTHONPATH=$PYTHONPATH:"$APPDIR/django/"
# User to run celeryd as. Default is current user.
CELERYD_USER='celery'
# Group to run celeryd as. Default is current user.
CELERYD_GROUP='www-data'
# Where to put the logfile
CELERYD_LOG_FILE='/var/log/celery/celeryd.log'
# Where to track the process id file
CELERYD_PID_FILE='/var/run/celery/celeryd.pid'
EOF
