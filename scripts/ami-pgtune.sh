#!/bin/bash

if [ $(whoami) != 'root' ]; then 
	echo "This script may only be run as root."
	exit 1
fi

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PGCONF=/etc/postgresql/9.1/main/postgresql.conf
PGSHM=/etc/sysctl.d/30-postgresql-shm.conf

# Get the current time
STAMP=$(date +%Y%m%d%H%M%S)

# Make a backup of the config for right now
cp $PGCONF $PGCONF-$STAMP

# Tune the postgres config for this instance size
pgtune -i $PGCONF-$STAMP -T OLTP -o $PGCONF

# Get an approximation of the total memory from the tuned config
MEM=$(awk -f $DIR/ami-pgtune.awk $PGCONF)

# Make a backup of the postgresql kernel shared memory config for now
cp $PGSHM $PGSHM-$STAMP

# Write the new memory max into the shared memory kernel setting
cat $PGSHM-$STAMP | sed -e "s/#\?kernel\.shmmax = .*/kernel.shmmax = $MEM/" > $PGSHM

# Reload the kernel settings for postgresql
sysctl -p $PGSHM

# Restart postgres
service postgresql restart
