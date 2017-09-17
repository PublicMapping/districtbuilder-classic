#!/bin/bash
# wait-for-postgres.sh
#  https://docs.docker.com/compose/startup-order/

set -e

host="$1"
shift
cmd="$@"

until psql -h "$host" -U postgres -w -c '\l'; do
    >&2 echo "Postgres is unavailable - sleeping"
    sleep 1
done

>&2 echo "Postgres is up - executing command"
exec $cmd

