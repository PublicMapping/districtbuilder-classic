# DistrictBuilder

[![Build Status](https://travis-ci.org/PublicMapping/DistrictBuilder.svg?branch=develop)](https://travis-ci.org/PublicMapping/DistrictBuilder)

[DistrictBuilder](http://www.districtbuilder.org/) is software created by the [Public Mapping Project](http://www.publicmapping.org/resources/software).

The development environment is docker-compose for services inside a Vagrant virtual machine.

## Table of Contents
  * [Installation](#installation)
    * [Requirements](#requirements)
    * [Development Environment Setup](#development-environment-setup)
      * [`config.xml`](#configxml)
      * [Setting Up Your Application](#setting-up-your-application)
  * [Translations](#translations)
  * [Support](#support)
  * [Development](#development)
  * [Deployment](#deployment)
    * [Requirements](#requirements-1)
    * [Pre-Deployment Configuration](#pre-deployment-configuration)
    * [Production Environment Setup](#production-environment-setup)


## Installation
### Requirements

- Vagrant 1.8.1
- VirtualBox 4.3
- Ansible 2.2

## tl;dr ##

```bash
$ # Copy config and make any necessary edits
$ cp django/publicmapping/config/config.dist.xml django/publicmapping/config/config.xml
$ # Copy .env file and add passwords
$ cp .env.sample .env
$ ./scripts/setup
$ vagrant ssh
$ ./scripts/update
```

If you want to get DistrictBuilder up and running quickly with demo data, you can then run
```bash
$ ./scripts/configure_va_demo
```

Otherwise, you'll need to provide your own shapefiles and config.xml file. Put your zipped shapefile in
a `data` directory at the project root, put your `config.xml` in `django/publicmapping/config/` 
and then run
```bash
$ ./scripts/configure_custom_data <shapefile-name.zip>
```

More detailed instructions on loading your own data can be found below.

:zzz:

## Development Environment Setup ##

### `config.xml` ###

Your configuration file contains everything specific to your instance of District Builder. As part
of setup, some of the values in the configuration file will be parsed to environment variables, and
others will be used to tell the application setup scripts where to find data and what to do with it.

In broad strokes, the configuration file:

- tells django and other services about secrets they need to know
- tells the setup scripts where data live
- tells the setup scripts what the data contain, i.e., what fields are present on each geographic
  record
- tells the setup scripts how to create calculator functions for manipulating those fields

Ease of interacting with the configuration file is a planned area for future development.

### Setting up your application ###

`./scripts/setup` provisions the virtual machine. It brings up an Ubuntu 14.04 virtual machine
with docker installed. `vagrant ssh` gets you into the virtual machine so you can run commands.
From there, running `./scripts/update` builds containers. The rest of the setup happens either
directly or indirectly through a setup management command. To get started, run
`./scripts/setup`, followed by `vagrant ssh`, followed by `./scripts/update`.
 
Then, run `./scripts/configure_va_demo`. It is not fast. Currently, it takes several hours, with the exact
time depending on hardware. We are working on ways to improve the speed of loading data.

The script will do several things

- Fetch zipped shapefile data for Virginia into a specific location
- Drop and recreate the `district_builder` database
- Run database migrations: create the relationships that data will be loaded into
- Load shapes from shapefiles at different levels: create records for the shapes and characteristics
  in the configured shapefiles
- Nest the shapes at different levels into each other: calculate the spatial relationships between
  shapes at different zoom levels
- Load some template plans: initialize the database with several example plans that users can start
  drawing with
- Create database views: create the database objects that GeoServer will use to
  create tiles of specific subjects
- Configure GeoServer: create layers and styles that will be served as tiles to the frontend

If you want to know what's actually going on in `configure`, these are the setup flags
that the script executes:

- `-g0 -g1 -g2`: load the zeroth through second geolevels. These geolevels are configured in the
  specified configuration file. This step loads geographies and attributes of those geographies
  into the database.
- `-n0 -n1 -n2`: nest the zeroth through second geolevels. This step establishes the spatial
  relationships between the geographies in each geolevel in the database.
- `-t`: create plan templates. This creates some example plans in the database to use as baselines
  for creating user plans. If it can't find information it needs to create a template, it skips that
  template after printing a warning message and doesn't fail.
- `--views`: create database views for geographies and attributes. This step creates a database view
  for each attribute each for each geolevel. These views are what GeoServer uses to create tiles.
- `-G`: configure GeoServer. This step creates the layers and styles that the frontend will
  eventually receive from GeoServer in the database and GeoServer container. This step will fail
  if you don't have a valid database connection configuration for your environment in `config.xml`.
  The example database connection information in `config.xml` is:

```xml
<Database name="district_builder"
          user="district_builder"
          password="district_builder"
          host="postgres.internal.districtbuilder.com"/>
```

- `-l`: generate language files. This step ensures that the files necessary for internationalization
  are present in the django container.

## Translations

DistrictBuilder does translation ["the Django way"](https://docs.djangoproject.com/en/1.11/topics/i18n/translation/) via translation strings. The translation strings are extracted into message files (`.po`) which are compiled into `.mo` files which Django can then use. Both the `.po` and `.mo` files can be found at `django/publicmapping/locale/<LC>/LC_MESSAGES/`, though only `.po` files are committed to source control.

There are two separate processes for generating translations, both of which are necessary for translated text to display properly in the web app:

1. Compile translation strings for templates and Javascript via the `makelanguagefiles` setup command. This happens automatically whenever the web app is run via the `languages` container.
1. Compile labels and descriptions from `config.xml`. This happens upon configuration when any setup command is run (eg. `./manage.py setup config/config.xml` from within `django` container).

### Adding and Modifying Translations

DistrictBuilder uses a Django application called [Rosetta](https://github.com/mbi/django-rosetta) to do translations.

To do translations in a given language, make sure the server is running (`./scripts/server`) and go to `/admin` to log in as an admin (the admin username and password are defined in `.env`). Once logged in, go to `/rosetta`. You should see the different languages available and the paths of the files that correspond to each language. If you make a translation and save, you should see your changes in that file in the `django` container and on the VM. If you restart the server, your translations will be visible in DistrictBuilder.

Once you are happy with your changes, the next step is to get them out of the VM and onto the host so they can be saved in source control.

You can use the command `vagrant ssh-config` to find the host, port, user, and identity file -- all of which you will need to copy the files over -- and then run:

```
scp -i <IdentityFile> -P <Port> -r <User>@<Host>:/vagrant/django/publicmapping/locale/ django/publicmapping/
```

You can then verify the translations are correct and commit those files.

## Support


More information about the application settings, configuration information, and run-time information is available in the PublicMapping/DistrictBuilder [wiki](https://github.com/PublicMapping/DistrictBuilder/wiki).

Bug reports and feature requests can be reported to the PublicMapping/DistrictBuilder [issue tracker](https://github.com/PublicMapping/DistrictBuilder/issues).

## Development


For development and contribution to this repo, it is recommended to install [pre-commit](https://pre-commit.com/) and setup the `yapf` hook as follows:

```bash
$ pip install pre-commit
$ pre-commit install
```

This will help with style of the Python code contributed to District Builder.

## Deployment

### Requirements

- Docker v17+
- Docker-Compose 1.21+
- Git
- PostgreSQL server 9.5
- PostGIS 2.2

### Pre-deployment Configuration  ###

**Note:** This guide assumes you have already deployed PostgreSQL server and created a `district_builder` database. For more information about how to setup a PostgreSQL instance, see [Postgres docs](https://www.postgresql.org/docs/9.5/static/index.html).

#### TL;DR ####
```bash
# Configure User Data
$ mkdir -p /opt/district-builder/user-data
$ touch /opt/district-builder/user-data/config_settings.py
$ cp /path/to/config.xml /opt/district-builder/user-data
$ cp /path/to/shapefile.zip /opt/district-builder/user-data

# Build & start containers
$ git checkout https:/github.com/PublicMapping/DistrictBuilder
$ cd DistrictBuilder
$ cat .env
# docker-compose settings
COMPOSE_PROJECT_NAME=districtbuilder

# districtbuilder settings
WEB_APP_PORT=8080
WEB_APP_PASSWORD=password
ADMIN_USER=admin
ADMIN_EMAIL=systems+districtbuilder@azavea.com
ADMIN_PASSWORD=password
DATABASE_HOST=<DATABASE_URL>
DATABASE_PASSWORD=password
DATABASE_USER=district_builder
DATABASE_DATABASE=district_builder
DATABASE_PORT=5432
KEY_VALUE_STORE_HOST=redis.districtbuilder.internal
KEY_VALUE_STORE_PASSWORD=password
KEY_VALUE_STORE_PORT=6379
KEY_VALUE_STORE_DB=0
MAP_SERVER_ADMIN_PASSWORD=password
MAP_SERVER_HOST=geoserver.districtbuilder.internal
MAP_SERVER_PORT=9091
MAILER_HOST=localhost
MAILER_PORT=587
MAILER_USER=admin
MAILER_PASSWORD=password
MAILER_USE_TLS_OR_SSL=tls

$ ./scripts/update --production
$ ./scripts/load_configured_data --production
$ ./scripts/server --production
```

Before starting, ensure that you've installed all of the [requirements](#deployment-requirements) above. You'll also need to be sure the following files exist:

- `/opt/district-builder/user-data/config.xml` (see the [`config.xml`](#configxml) section of this README)
- `/opt/district-builder/user-data/config_settings.py` (this file can be blank; DistrictBuilder will populate it during setup)
- `/opt/district-builder/user-data/districtbuilder_data.zip`
- `.env` with application values filled in (see [.env.sample](./.env.sample)).

## Production Environment Setup

Once those files exist, clone this repository and run `scripts/update` as described in [Setting Up Your Application](#setting-up-your-application), but use the `--production` flag. 

```bash
$ git clone https://github.com/PublicMapping/DistrictBuilder
$ cd DistrictBuilder

# Build container images, run migrations, set Geoserver password
$ ./scripts/update --production
```

When container images are built, load Shapefile data into the database:

```bash
$ ./scripts/load_configured_data --production
```

Finally, start services:

```bash
$ ./scripts/server --production
```


