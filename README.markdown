DistrictBuilder
===============

[![Build Status](https://travis-ci.org/PublicMapping/DistrictBuilder.svg?branch=develop)](https://travis-ci.org/PublicMapping/DistrictBuilder)

[DistrictBuilder](http://www.districtbuilder.org/) is software created by the [Public Mapping Project](http://www.publicmapping.org/resources/software).

The development environment is docker-compose for services inside a Vagrant virtual machine.


Installation
------------

### Requirements ###

Vagrant 1.8.1
VirtualBox 4.3
Ansible 2.2

### tl;dr ###

```bash
$ cp django/publicmapping/config/config.dist.xml django/publicmapping/config/config.xml
$ ./scripts/setup
$ vagrant ssh
$ ./scripts/update
$ ./scripts/configure
```

:zzz:

#### Development Environment Setup ####

##### `config.xml` #####

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

##### Setting up your application #####

`./scripts/setup` provisions the virtual machine. It brings up an Ubuntu 14.04 virtual machine
with docker installed. `vagrant ssh` gets you into the virtual machine so you can run commands.
From there, running `./scripts/update` builds containers. The rest of the setup happens either
directly or indirectly through a setup management command. To get started, run
`./script/setup`, followed by `vagrant ssh`, followed by `./scripts/update`.
 
Then, run `./scripts/configure`. It is not fast. Currently, it takes several hours, with the exact
time depending on hardware. We are working on ways to improve the speed of loading data.

The script will do several things

- Fetch zipped shapefile data for Virginia into a specific location
- Drop and recreate the `district_builder**
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

Support
-------

More information about the application settings, configuration information, and run-time information is available in the PublicMapping/DistrictBuilder [wiki](https://github.com/PublicMapping/DistrictBuilder/wiki).

Bug reports and feature requests can be reported to the PublicMapping/DistrictBuilder [issue tracker](https://github.com/PublicMapping/DistrictBuilder/issues).

Development
-----------

For development and contribution to this repo, it is recommended to install [pre-commit](https://pre-commit.com/) and setup the `yapf` hook as follows:

```bash
$ pip install pre-commit
$ pre-commit install
```

This will help with style of the Python code contributed to District Builder.
