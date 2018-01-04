DistrictBuilder
===============

[DistrictBuilder](http://www.districtbuilder.org/) is software created by the [Public Mapping Project](http://www.publicmapping.org/resources/software).


Installation
------------

### Requirements ###

Vagrant 1.8.1
VirtualBox 4.3
Ansible 2.2

### tl;dr ###

```bash
$ ./scripts/setup
$ vagrant ssh
$ ./scripts/update
$ ./scripts/load_development_data
```

#### Django Application Setup ####

The django application includes a management command that handles application configuration
based on two input files: `settings.py` in the `publicmapping` app in `django/publicmapping`
and `config.xml`. Below is an explanation of what each of these flags does:

##### Internationalization #####

To compile language files, use the `-l` flag.

##### Static Files #####

To collect static files, use the `-s` flag.

##### Database Views #####

The `-V` flag creates some kind of database views. It doesn't currently work though.

##### Data Setup #####

The following flags are all executed as part of `scripts/load_development_data`.

###### `-gX`: Loading Geolevels ######

The `-gX` flag loads geolevel `X` into the database. Where to find those geolevels is determined
by the `config.xml` file. Each geolevel in the xml has an entry like:

```xml
<Shapefile path="/data/some_path.shp">
  <Fields>
  ...
  </Fields>
</Shapefile>
```

that tells the management command where to look for geounits in this level, and what fields to
care about in each shapefile record. The lowest numbered geolevel is for the smallest size, so
if you had only counties and states, for example, counties would be `-g0`, and states would be
`-g1`.

###### `-nX`: Nesting Geolevels ######

Nesting geolevels rolls up smaller geounits into their larger parents, based on geography,
accumulating record information along the way.

###### `-t`: Create plan templates ######

The `-t` flag creates some example plans in the database to use as baselines for creating user
plans. If it can't find information it needs to create a template, it skips that template after
printing a warning message and doesn't fail.

###### `-G`: Configure Geoserver ######

The `-G` flag configures the geoserver container. To succeed, you must have correct database
connection information in `config.xml` and a correct `SLD_ROOT` in `settings.py`.

The example database connection information in `config.xml` is:

```xml
<Database name="district_builder"
          user="district_builder"
          password="district_builder"
          host="postgres.internal.districtbuilder.com"/>
```

The default `SLD_ROOT` in `settings.py` is `/opt/sld`.

Support
-------

More information about the application settings, configuration information, and run-time information is available in the PublicMapping/DistrictBuilder [wiki](https://github.com/PublicMapping/DistrictBuilder/wiki).

Bug reports and feature requests can be reported to the PublicMapping/DistrictBuilder [issue tracker](https://github.com/PublicMapping/DistrictBuilder/issues).
