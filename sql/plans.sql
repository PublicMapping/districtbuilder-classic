-- View: redistricting_county_geounits

-- DROP VIEW redistricting_county_geounits;

CREATE OR REPLACE VIEW simple_county AS 
 SELECT redistricting_geounit.id, redistricting_geounit.name, redistricting_geounit.geolevel_id, redistricting_geounit.simple as geom
   FROM redistricting_geounit
  WHERE redistricting_geounit.geolevel_id = 1;

ALTER TABLE simple_county OWNER TO publicmapping;


CREATE OR REPLACE VIEW simple_tract AS 
 SELECT redistricting_geounit.id, redistricting_geounit.name, redistricting_geounit.geolevel_id, redistricting_geounit.simple as geom
   FROM redistricting_geounit
  WHERE redistricting_geounit.geolevel_id = 2;

ALTER TABLE simple_tract OWNER TO publicmapping;

CREATE OR REPLACE VIEW simple_block AS 
 SELECT redistricting_geounit.id, redistricting_geounit.name, redistricting_geounit.geolevel_id, redistricting_geounit.simple as geom
   FROM redistricting_geounit
  WHERE redistricting_geounit.geolevel_id = 3;

ALTER TABLE simple_block OWNER TO publicmapping;

-- View: simple_district

-- DROP VIEW simple_district;

CREATE OR REPLACE VIEW simple_district AS 
 SELECT rd.id, rd.district_id, rd.name, rd.version, rd.plan_id, rc.subject_id, rc.number, rd.simple AS geom
   FROM redistricting_district rd
   JOIN redistricting_computedcharacteristic rc ON rd.id = rc.district_id
  WHERE rd.version = (( SELECT max(redistricting_district.version) AS max
      FROM redistricting_district
     WHERE redistricting_district.district_id = rd.district_id));

ALTER TABLE simple_district OWNER TO publicmapping;


-- Demographic Views

-- View: demo_block_poptot

-- DROP VIEW demo_block_poptot;

CREATE OR REPLACE VIEW demo_block_poptot AS 

 SELECT rg.id, rg.name, rg.geolevel_id, rg.geom, rc.number, rc.percentage
   FROM redistricting_geounit rg
   JOIN redistricting_characteristic rc ON rg.id = rc.geounit_id
  WHERE rc.subject_id = 3 AND rg.geolevel_id = 3;

ALTER TABLE demo_block_poptot OWNER TO publicmapping;

-- View: demo_tract_poptot

-- DROP VIEW demo_tract_poptot;

CREATE OR REPLACE VIEW demo_tract_poptot AS 

 SELECT rg.id, rg.name, rg.geolevel_id, rg.geom, rc.number, rc.percentage
   FROM redistricting_geounit rg
   JOIN redistricting_characteristic rc ON rg.id = rc.geounit_id
  WHERE rc.subject_id = 3 AND rg.geolevel_id = 2;

ALTER TABLE demo_tract_poptot OWNER TO publicmapping;

-- View: demo_county_poptot

-- DROP VIEW demo_county_poptot;

CREATE OR REPLACE VIEW demo_county_poptot AS 

 SELECT rg.id, rg.name, rg.geolevel_id, rg.geom, rc.number, rc.percentage
   FROM redistricting_geounit rg
   JOIN redistricting_characteristic rc ON rg.id = rc.geounit_id
  WHERE rc.subject_id = 3 AND rg.geolevel_id = 1;

ALTER TABLE demo_county_poptot OWNER TO publicmapping;

-- View: demo_block_pophisp

-- DROP VIEW demo_block_pophisp;

CREATE OR REPLACE VIEW demo_block_pophisp AS 

 SELECT rg.id, rg.name, rg.geolevel_id, rg.geom, rc.number, rc.percentage
   FROM redistricting_geounit rg
   JOIN redistricting_characteristic rc ON rg.id = rc.geounit_id
  WHERE rc.subject_id = 1 AND rg.geolevel_id = 3;

ALTER TABLE demo_block_pophisp OWNER TO publicmapping;

-- View: demo_tract_pophisp

-- DROP VIEW demo_tract_pophisp;

CREATE OR REPLACE VIEW demo_tract_pophisp AS 

 SELECT rg.id, rg.name, rg.geolevel_id, rg.geom, rc.number, rc.percentage
   FROM redistricting_geounit rg
   JOIN redistricting_characteristic rc ON rg.id = rc.geounit_id
  WHERE rc.subject_id = 1 AND rg.geolevel_id = 2;

ALTER TABLE demo_tract_pophisp OWNER TO publicmapping;

-- View: demo_county_pophisp

-- DROP VIEW demo_county_pophisp;

CREATE OR REPLACE VIEW demo_county_pophisp AS 

 SELECT rg.id, rg.name, rg.geolevel_id, rg.geom, rc.number, rc.percentage
   FROM redistricting_geounit rg
   JOIN redistricting_characteristic rc ON rg.id = rc.geounit_id
  WHERE rc.subject_id = 1 AND rg.geolevel_id = 1;

ALTER TABLE demo_county_pophisp OWNER TO publicmapping;


-- View: demo_block_popblk

-- DROP VIEW demo_block_popblk;

CREATE OR REPLACE VIEW demo_block_popblk AS 

 SELECT rg.id, rg.name, rg.geolevel_id, rg.geom, rc.number, rc.percentage
   FROM redistricting_geounit rg
   JOIN redistricting_characteristic rc ON rg.id = rc.geounit_id
  WHERE rc.subject_id = 2 AND rg.geolevel_id = 3;

ALTER TABLE demo_block_popblk OWNER TO publicmapping;

-- View: demo_tract_popblk

-- DROP VIEW demo_tract_popblk;

CREATE OR REPLACE VIEW demo_tract_popblk AS 

 SELECT rg.id, rg.name, rg.geolevel_id, rg.geom, rc.number, rc.percentage
   FROM redistricting_geounit rg
   JOIN redistricting_characteristic rc ON rg.id = rc.geounit_id
  WHERE rc.subject_id = 2 AND rg.geolevel_id = 2;

ALTER TABLE demo_tract_popblk OWNER TO publicmapping;

-- View: demo_county_popblk

-- DROP VIEW demo_county_popblk;

CREATE OR REPLACE VIEW demo_county_popblk AS 

 SELECT rg.id, rg.name, rg.geolevel_id, rg.geom, rc.number, rc.percentage
   FROM redistricting_geounit rg
   JOIN redistricting_characteristic rc ON rg.id = rc.geounit_id
  WHERE rc.subject_id = 2 AND rg.geolevel_id = 1;

ALTER TABLE demo_county_popblk OWNER TO publicmapping;

-- View: identify_geounit

-- DROP VIEW identify_geounit;

CREATE OR REPLACE VIEW identify_geounit AS 
 SELECT rg.id, rg.name, rg.geolevel_id, rg.geom, rc.number, rc.percentage, rc.subject_id
   FROM redistricting_geounit rg
   JOIN redistricting_characteristic rc ON rg.id = rc.geounit_id;

ALTER TABLE identify_geounit OWNER TO publicmapping;


-- This will create your default district and update the shapes and computedcharacteristics - but only for plan 1, district 19

-- update redistricting_district as dist set geom = (select st_multi(st_union(geom)) from redistricting_geounit as geo where geo.geolevel_id = 1), simple = (select (st_multi(st_simplify(st_union(geom), 10.0))) from redistricting_geounit as geo where geo.geolevel_id = 1) where dist.id = 19;

-- insert into redistricting_districtgeounitmapping (district_id, geounit_id, plan_id) (Select 19 as district_id, id as geounit_id, 1 as plan_id from redistricting_geounit as unit where unit.geolevel_id = 3)

-- insert into redistricting_computedcharacteristic (subject_id, district_id, number) (Select rc.subject_id as subject_id, 19 as district_id, sum(rc.number) as number from redistricting_characteristic as rc join redistricting_geounit as rg on rc.geounit_id = rg.id join redistricting_geolevel as lev on rg.geolevel_id = lev.id where lev.id = 1 group by rc.subject_id)
