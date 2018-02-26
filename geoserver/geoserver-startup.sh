#!/bin/bash
# -----------------------------------------------------------------------------
# Start Script for GEOSERVER cribbed from
# https://github.com/geoserver/geoserver/blob/19d7d4aff291f814c3c2a5f8e27146e5fd2fd459/src/release/bin/startup.sh
#
# This script adds additional support for templating out the database settings for geoserver
# reading them from environment variables
# $Id$
# -----------------------------------------------------------------------------


# Template datastore.xml for District Builder to read from environment variables
DISTRICT_BUILDER_DB_HOST=${DATABASE_HOST}
DISTRICT_BUILDER_DB_PASSWORD=${DATABASE_PASSWORD}
DISTRICT_BUILDER_DB_USER=${DATABASE_USER}
DISTRICT_BUILDER_DB_DATABASE=${DATABASE_DATABASE}
DISTRICT_BUILDER_DB_PORT=${DATABASE_PORT}

# Admin Disabled
DISTRICT_BUILDER_GEOSERVER_ADMIN_DISABLED=${DISTRICT_BUILDER_GEOSERVER_ADMIN_DISABLED:-false}

# I _think_ this isn't necessary but we'll see
# <entry key=\"namespace\">http://opengeo.org/#mub-monitor</entry>

datastore_config="
<dataStore>
  <id>DataStoreInfoImpl--7d8370b0:1504f8982cc:-7fe4</id>
  <name>district_builder</name>
  <type>PostGIS</type>
  <enabled>true</enabled>
  <workspace>
    <id>WorkspaceInfoImpl--7d8370b0:1504f8982cc:-7fe6</id>
  </workspace>
  <connectionParameters>
    <entry key=\"port\">$DISTRICT_BUILDER_DB_PORT</entry>
    <entry key=\"Connection timeout\">20</entry>
    <entry key=\"passwd\">plain:$DISTRICT_BUILDER_DB_PASSWORD</entry>
    <entry key=\"dbtype\">postgis</entry>
    <entry key=\"host\">$DISTRICT_BUILDER_DB_HOST</entry>
    <entry key=\"validate connections\">true</entry>
    <entry key=\"encode functions\">false</entry>
    <entry key=\"max connections\">20</entry>
    <entry key=\"database\">$DISTRICT_BUILDER_DB_DATABASE</entry>
    <entry key=\"Support on the fly geometry simplification\">false</entry>
    <entry key=\"schema\">public</entry>
    <entry key=\"Test while idle\">false</entry>
    <entry key=\"Loose bbox\">true</entry>
    <entry key=\"Expose primary keys\">false</entry>
    <entry key=\"create database\">false</entry>
    <entry key=\"fetch size\">1000</entry>
    <entry key=\"preparedStatements\">true</entry>
    <entry key=\"Estimated extends\">false</entry>
    <entry key=\"user\">$DISTRICT_BUILDER_DB_USER</entry>
    <entry key=\"min connections\">1</entry>
  </connectionParameters>
  <__default>false</__default>
</dataStore>"

# Make sure prerequisite environment variables are set
if [ -z "$JAVA_HOME" ]; then
  echo "The JAVA_HOME environment variable is not defined"
  echo "This environment variable is needed to run this program"
  exit 1
fi
if [ ! -r "$JAVA_HOME"/bin/java ]; then
  echo "The JAVA_HOME environment variable is not defined correctly"
  echo "This environment variable is needed to run this program"
  exit 1
fi
# Set standard commands for invoking Java.
_RUNJAVA="$JAVA_HOME"/bin/java

if [ -z $GEOSERVER_HOME ]; then #If GEOSERVER_HOME not set then guess a few locations before giving
  # up and demanding user set it.
  if [ -r start.jar ]; then
     echo "GEOSERVER_HOME environment variable not found, using current "
     echo "directory.  If not set then running this script from other "
     echo "directories will not work in the future."
     export GEOSERVER_HOME=`pwd`
  else
    if [ -r ../start.jar ]; then
      echo "GEOSERVER_HOME environment variable not found, using current "
      echo "location.  If not set then running this script from other "
      echo "directories will not work in the future."
      export GEOSERVER_HOME=`pwd`/..
    fi
  fi

  if [ -z "$GEOSERVER_HOME" ]; then
    echo "The GEOSERVER_HOME environment variable is not defined"
    echo "This environment variable is needed to run this program"
    echo "Please set it to the directory where geoserver was installed"
    exit 1
  fi

fi

if [ ! -r "$GEOSERVER_HOME"/bin/geoserver-startup.sh ]; then
  echo "The GEOSERVER_HOME environment variable is not defined correctly"
  echo "This environment variable is needed to run this program"
  exit 1
fi

#Find the configuration directory: GEOSERVER_DATA_DIR
if [ -z $GEOSERVER_DATA_DIR ]; then
    if [ -r "$GEOSERVER_HOME"/data_dir ]; then
        export GEOSERVER_DATA_DIR="$GEOSERVER_HOME"/data_dir
    else
        echo "No GEOSERVER_DATA_DIR found, using application defaults"
	      GEOSERVER_DATA_DIR=""
    fi
fi

echo "${datastore_config}" > $GEOSERVER_DATA_DIR/workspaces/district_builder/datastore.xml

cd "$GEOSERVER_HOME"

echo "Starting geoserver..."

echo "GEOSERVER DATA DIR is $GEOSERVER_DATA_DIR"

exec sh bin/startup.sh
