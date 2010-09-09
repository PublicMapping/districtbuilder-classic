"""
Create required database views for simplified geometry and demographic
data.

This management command will create 3 types of views:
     1) simple_geo: simplified views of the basic geography -- this is used
        by the user interface, because it's faster to use less geometry.
     2) demo_geo_type: demographic views on each of the demographic and
        geography combinations, for display in geoserver as map tiles
     3) identify_geounit: a view of the geography that links to the 
        demographic data for use when identifying geographic units.
        
This file is part of The Public Mapping Project
http://sourceforge.net/projects/publicmapping/

License:
    Copyright 2010 Micah Altman, Michael McDonald

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

Author: 
    Andrew Jennings, David Zwarg
"""

from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    """
    A command that creates application views.
    """
    args = None
    help = 'Create redistricting database views.'
    
    def handle(self, *args, **options):
        """
        Perform the command. Run the SQL for creating redistricting views.
        """
        cursor = connection.cursor()
        
        sql = """CREATE OR REPLACE VIEW simple_district AS 
 SELECT rd.id, rd.district_id, rd.name, rd.version, rd.plan_id, rc.subject_id, rc.number, rd.simple AS geom
   FROM redistricting_district rd
   JOIN redistricting_computedcharacteristic rc ON rd.id = rc.district_id
  WHERE rd.version = (( SELECT max(redistricting_district.version) AS max
      FROM redistricting_district
     WHERE redistricting_district.district_id = rd.district_id));"""
        cursor.execute(sql)
        print '\tCreated simple_district view ...'
        
        sql = """CREATE OR REPLACE VIEW identify_geounit AS
 SELECT rg.id, rg.name, rg.geolevel_id, rg.geom, rc.number, rc.percentage, rc.subject_id
   FROM redistricting_geounit rg
   JOIN redistricting_characteristic rc ON rg.id = rc.geounit_id;"""
        cursor.execute(sql)
        print '\tCreated identify_geounit view ...'

        for geolevel in Geolevel.objects.all():
            sql = """CREATE OR REPLACE VIEW simple_%s AS 
 SELECT id, name, geolevel_id, simple as geom
   FROM redistricting_geounit
  WHERE geolevel_id = %d;""" % (geolevel.name, geolevel.id,)
            cursor.execute(sql)
            print '\tCreated simple_%s view ...' % geolevel.name
            
            for subject in Subject.objects.all():
                sql = """CREATE OR REPLACE VIEW demo_%s_%s AS 
 SELECT rg.id, rg.name, rg.geolevel_id, rg.geom, rc.number, rc.percentage
   FROM redistricting_geounit rg
   JOIN redistricting_characteristic rc ON rg.id = rc.geounit_id
  WHERE rc.subject_id = %d AND rg.geolevel_id = %d;""" % 
                    (geolevel.name, subject.name, subject.id, geolevel.id,)
                cursor.execute(sql)
                
                print '\tCreated demo_%s_%s view ...' % (geolevel.name, subject.name)
               
        print '\tDone.'