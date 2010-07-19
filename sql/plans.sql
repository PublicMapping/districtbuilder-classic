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
 SELECT id, district_id, name, version, simple AS geom, plan_id
   FROM redistricting_district; 

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
