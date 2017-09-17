#!/bin/bash
# wait-for-postgres.sh
#  https://docs.docker.com/compose/startup-order/

set -e

host="$1"
shift
cmd="$@"

until curl "http://$host:8080/geoserver/wfs?request=GetFeature&version=1.1.0&typeName=gsml:GeologicUnit"; do
    >&2 echo "geoserver is unavailable - sleeping"
    sleep 1
done

>&2 echo "geoserver is up - executing command"
exec $cmd

