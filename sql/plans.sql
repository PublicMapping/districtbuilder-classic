-- View: redistricting_county_geounits

-- DROP VIEW redistricting_county_geounits;

CREATE OR REPLACE VIEW county AS 
 SELECT redistricting_geounit.id, redistricting_geounit.name, redistricting_geounit.geolevel_id, redistricting_geounit.geom
   FROM redistricting_geounit
  WHERE redistricting_geounit.geolevel_id = 1;

ALTER TABLE county OWNER TO publicmapping;


CREATE OR REPLACE VIEW tract AS 
 SELECT redistricting_geounit.id, redistricting_geounit.name, redistricting_geounit.geolevel_id, redistricting_geounit.geom
   FROM redistricting_geounit
  WHERE redistricting_geounit.geolevel_id = 2;

ALTER TABLE tract OWNER TO publicmapping;

CREATE OR REPLACE VIEW block AS 
 SELECT redistricting_geounit.id, redistricting_geounit.name, redistricting_geounit.geolevel_id, redistricting_geounit.geom
   FROM redistricting_geounit
  WHERE redistricting_geounit.geolevel_id = 3;

ALTER TABLE block OWNER TO publicmapping;

-- DROP VIEW redistricting_plan_collect_geom;

CREATE OR REPLACE VIEW plan AS 
 SELECT r_d.id AS district_id, r_d.plan_id, r_d.name AS district_name, st_simplifypreservetopology(st_union(r_g.geom),100) AS geom
   FROM redistricting_district r_d
   JOIN redistricting_district_geounits r_dg ON r_dg.district_id = r_d.id
   JOIN redistricting_geounit r_g ON r_g.id = r_dg.geounit_id
  GROUP BY r_d.id, r_d.plan_id, r_d.name;

ALTER TABLE plan OWNER TO publicmapping;

-- Demographic Views

-- View: demo_block_poptot

-- DROP VIEW demo_block_poptot;

CREATE OR REPLACE VIEW demo_block_poptot AS 

 SELECT rg.id, rg.name, rg.geolevel_id, rg.geom, rc.number, rc.percentage
   FROM redistricting_geounit rg
   JOIN redistricting_characteristic rc ON rg.id = rc.geounit_id
  WHERE rc.subject_id = 1 AND rg.geolevel_id = 3;

ALTER TABLE demo_block_poptot OWNER TO publicmapping;

-- View: demo_tract_poptot

-- DROP VIEW demo_tract_poptot;

CREATE OR REPLACE VIEW demo_tract_poptot AS 

 SELECT rg.id, rg.name, rg.geolevel_id, rg.geom, rc.number, rc.percentage
   FROM redistricting_geounit rg
   JOIN redistricting_characteristic rc ON rg.id = rc.geounit_id
  WHERE rc.subject_id = 1 AND rg.geolevel_id = 2;

ALTER TABLE demo_tract_poptot OWNER TO publicmapping;

-- View: demo_county_poptot

-- DROP VIEW demo_county_poptot;

CREATE OR REPLACE VIEW demo_county_poptot AS 

 SELECT rg.id, rg.name, rg.geolevel_id, rg.geom, rc.number, rc.percentage
   FROM redistricting_geounit rg
   JOIN redistricting_characteristic rc ON rg.id = rc.geounit_id
  WHERE rc.subject_id = 1 AND rg.geolevel_id = 1;

ALTER TABLE demo_county_poptot OWNER TO publicmapping;

-- View: demo_block_pres_rep

-- DROP VIEW demo_block_pres_rep;

CREATE OR REPLACE VIEW demo_block_pres_rep AS 

 SELECT rg.id, rg.name, rg.geolevel_id, rg.geom, rc.number, rc.percentage
   FROM redistricting_geounit rg
   JOIN redistricting_characteristic rc ON rg.id = rc.geounit_id
  WHERE rc.subject_id = 2 AND rg.geolevel_id = 3;

ALTER TABLE demo_block_pres_rep OWNER TO publicmapping;

-- View: demo_tract_pres_rep

-- DROP VIEW demo_tract_pres_rep;

CREATE OR REPLACE VIEW demo_tract_pres_rep AS 

 SELECT rg.id, rg.name, rg.geolevel_id, rg.geom, rc.number, rc.percentage
   FROM redistricting_geounit rg
   JOIN redistricting_characteristic rc ON rg.id = rc.geounit_id
  WHERE rc.subject_id = 2 AND rg.geolevel_id = 2;

ALTER TABLE demo_tract_pres_rep OWNER TO publicmapping;

-- View: demo_county_pres_rep

-- DROP VIEW demo_county_pres_rep;

CREATE OR REPLACE VIEW demo_county_pres_rep AS 

 SELECT rg.id, rg.name, rg.geolevel_id, rg.geom, rc.number, rc.percentage
   FROM redistricting_geounit rg
   JOIN redistricting_characteristic rc ON rg.id = rc.geounit_id
  WHERE rc.subject_id = 2 AND rg.geolevel_id = 1;

ALTER TABLE demo_county_pres_rep OWNER TO publicmapping;


-- View: demo_block_pres_dem

-- DROP VIEW demo_block_pres_dem;

CREATE OR REPLACE VIEW demo_block_pres_dem AS 

 SELECT rg.id, rg.name, rg.geolevel_id, rg.geom, rc.number, rc.percentage
   FROM redistricting_geounit rg
   JOIN redistricting_characteristic rc ON rg.id = rc.geounit_id
  WHERE rc.subject_id = 3 AND rg.geolevel_id = 3;

ALTER TABLE demo_block_pres_dem OWNER TO publicmapping;

-- View: demo_tract_pres_dem

-- DROP VIEW demo_tract_pres_dem;

CREATE OR REPLACE VIEW demo_tract_pres_dem AS 

 SELECT rg.id, rg.name, rg.geolevel_id, rg.geom, rc.number, rc.percentage
   FROM redistricting_geounit rg
   JOIN redistricting_characteristic rc ON rg.id = rc.geounit_id
  WHERE rc.subject_id = 3 AND rg.geolevel_id = 2;

ALTER TABLE demo_tract_pres_dem OWNER TO publicmapping;

-- View: demo_county_pres_dem

-- DROP VIEW demo_county_pres_dem;

CREATE OR REPLACE VIEW demo_county_pres_dem AS 

 SELECT rg.id, rg.name, rg.geolevel_id, rg.geom, rc.number, rc.percentage
   FROM redistricting_geounit rg
   JOIN redistricting_characteristic rc ON rg.id = rc.geounit_id
  WHERE rc.subject_id = 3 AND rg.geolevel_id = 1;

ALTER TABLE demo_county_pres_dem OWNER TO publicmapping;
