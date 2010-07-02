-- View: redistricting_county_geounits

-- DROP VIEW redistricting_county_geounits;

CREATE OR REPLACE VIEW redistricting_county_geounits AS 
 SELECT redistricting_geounit.id, redistricting_geounit.name, redistricting_geounit.geolevel_id, redistricting_geounit.geom
   FROM redistricting_geounit
  WHERE redistricting_geounit.geolevel_id = 4;

ALTER TABLE redistricting_county_geounits OWNER TO publicmapping;


-- View: redistricting_plan_collect_geom

-- DROP VIEW redistricting_plan_collect_geom;

CREATE OR REPLACE VIEW redistricting_plan_collect_geom AS 
 SELECT r_d.id AS district_id, r_d.plan_id, r_d.name AS district_name, st_union(r_g.geom) AS geom
   FROM redistricting_district r_d
   JOIN redistricting_district_geounits r_dg ON r_dg.district_id = r_d.id
   JOIN redistricting_geounit r_g ON r_g.id = r_dg.geounit_id
  GROUP BY r_d.id, r_d.plan_id, r_d.name;

ALTER TABLE redistricting_plan_collect_geom OWNER TO publicmapping;


-- View: redistricting_plan_geom

-- DROP VIEW redistricting_plan_geom;

CREATE OR REPLACE VIEW redistricting_plan_geom AS 
 SELECT r_d.id AS district_id, r_d.name AS district_name, r_g.id AS geounit_id, r_g.name AS geounit_name, r_g.geom
   FROM redistricting_district r_d
   JOIN redistricting_district_geounits r_dg ON r_dg.district_id = r_d.id
   JOIN redistricting_geounit r_g ON r_g.id = r_dg.geounit_id;

ALTER TABLE redistricting_plan_geom OWNER TO publicmapping;

