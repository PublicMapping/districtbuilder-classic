#!/bin/bash

if [ `whoami` != "root" ]; then
    echo "This script must be run as root."
    exit 1
fi

# Set the 'site' URL to the instance DNS name
DNS=$(curl http://169.254.169.254/latest/meta-data/local-hostname/)

su postgres -c "psql -d publicmapping -c \"update publicmapping.django_site set domain='$DNS', name='$DNS' where id=1;\""
