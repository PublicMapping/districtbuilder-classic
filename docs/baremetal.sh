#! /bin/bash -x 

# START
# NEED to run this or apt-get and aptitude will miss packages!
sudo apt-get update
# END

sudo aptitude install apache2 libapache2-mod-wsgi python-django \
    python-lxml python-gdal python-rpy2 python-psycopg2 \
    python-setuptools postgresql-8.4-postgis sun-java6-jdk \
    tomcat6 tomcat6-admin 

#START
# NEED: Geoserver

# get geoserver, change to version you want
sudo service tomcat6 stop
wget http://downloads.sourceforge.net/geoserver/geoserver-2.0.2-war.zip
sudo unzip -d /var/lib/tomcat6/webapps/ geoserver-2.0.2-war.zip
sudo chown -R tomcat6 /var/lib/tomcat6/webapps/geoserver.war
sudo chgrp g+w tomcat6 /var/lib/tomcat6/webapps/geoserver.war

# restart
sudo service tomcat6 restart
sudo service apache2 restart
#END   

sudo easy_install celery==2.1.4 django-celery==2.1.4 ghettoq django-staticfiles django-tagging

#START
# NEED: celeryd init.d
cd /etc/init.d
wget --no-check-certificate https://github.com/ask/celery/raw/master/contrib/debian/init.d/celeryd
chmod a+x,a+r celeryd 
CD="# Where to chdir at start.
CELERYD_CHDIR='/projects/publicmapping/trunk/django/publicmapping/'
# Path to celeryd
CELERYD='/projects/publicmapping/trunk/django/publicmapping/manage.py celeryd'
# Name of the projects settings module.
export DJANGO_SETTINGS_MODULE='settings'
# User to run celeryd as. Default is current user.
CELERYD_USER='www-data'
# Group to run celeryd as. Default is current user.
CELERYD_GROUP='www-data'
"
sudo echo "$CD" > /etc/default/celeryd
sudo update-rc.d celeryd defaults
#END

sudo mkdir /projects
cd /projects

sudo apt-get install subversion

sudo svn co https://publicmapping.svn.sourceforge.net/svnroot/publicmapping publicmapping

# START 
# should be on 1.0
#
mv publicmapping/trunk publicmapping/trunk.full
ln -s publicmapping/tags/v1.0/ publicmapping/trunk
# END

sudo -u postgres createdb template_postgis
sudo -u postgres createlang plpgsql template_postgis
sudo -u postgrespsql -d template_postgis -f /usr/share/postgresql/8.4/contrib/postgis-1.5/postgis.sql
sudo -u postgres psql -d template_postgis -f /usr/share/postgresql/8.4/contrib/postgis-1.5/spatial_ref_sys.sql

sudo -u postgres psql -f /projects/publicmapping/trunk/sql/publicmapping_db.sql

# START
# Note: also need auth line for postgres md5
HGPATCH="*** /etc/postgresql/8.4/main/pg_hba.conf        2011-04-30 21:45:20.267825541 +0000
--- pg_hba.conf.new     2011-04-30 21:45:46.557825531 +0000
***************
*** 74,83 ****
--- 74,86 ----
  # (custom daily cronjobs, replication, and similar tasks).
  #
  # Database administrative login by UNIX sockets
+ local   all         postgres                          md5
  local   all         postgres                          ident

  # TYPE  DATABASE    USER        CIDR-ADDRESS          METHOD

+ # local password-protected connections
+ local   all         all                               md5
  # "local" is for Unix domain socket connections only
  local   all         all                               ident
  # IPv4 local connections:
"
echo "$HGPATCH" | patch /etc/postgresql/8.4/main/pg_hba.conf
#END

cd /projects/publicmapping/trunk/docs/loadcensus/

sudo ./configureCensus.py -F 44 -C 2 -H 38 -S 75 --hisp_targ_s=2 --hisp_targ_h=4




