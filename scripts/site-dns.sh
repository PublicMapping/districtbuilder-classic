#!/bin/bash

if [ `whoami` != "root" ]; then
    echo "This script must be run as root."
    exit 1
fi

# Set the 'site' URL to the instance DNS name
DNS=$(curl http://169.254.169.254/latest/meta-data/local-hostname/)

# If DNS is set to the site, this results in problems when spawning new AMIs
# An AMI startup script to set this would be preferable, but also, setting it 
# to 'localhost' seems to work, as long as it's self-contained.
DNS=localhost

su postgres -c "psql -d publicmapping -c \"update publicmapping.django_site set domain='$DNS', name='$DNS' where id=1;\""
