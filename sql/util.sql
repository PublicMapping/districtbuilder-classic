-- update the district with the ID of 1
-- emulate a district by adding all the geounits contained in
-- geounit 25, geolevel 1 (all blocks in a country)
insert into redistricting_district_geounits (district_id, geounit_id) (
    select 1, gu1.id from redistricting_geounit as gu1
        inner join redistricting_geounit as gu2 on st_contains(gu2.geom, gu1.geom)
        where gu2.id = 25 and gu1.geolevel_id = 3
        order by gu1.id
);

-- update the district with the ID of 2
-- emulate a district by adding all the geounits contained in
-- geounit 46, geolevel 1 (all blocks in a county)
insert into redistricting_district_geounits (district_id, geounit_id) (
    select 2, gu1.id from redistricting_geounit as gu1
        inner join redistricting_geounit as gu2 on st_contains(gu2.geom, gu1.geom)
        where gu2.id = 46 and gu1.geolevel_id = 3
        order by gu1.id
);

-- set the geometry of each district to a simplified version from the view
update redistricting_district as static set geom = (
    select st_force_collection(geom)
        from redistricting_plan_collect_geom as computed
        where computed.district_id::character varying = static.district_id
);

-- set the geometry of each district to a non-simplified version
update redistricting_district as static set geom = (
    select st_force_collection(geom) from (
        SELECT r_d.id AS district_id, r_d.plan_id, r_d.name AS district_name, st_union(r_g.geom) AS geom
           FROM redistricting_district r_d
           JOIN redistricting_district_geounits r_dg ON r_dg.district_id = r_d.id
           JOIN redistricting_geounit r_g ON r_g.id = r_dg.geounit_id
          GROUP BY r_d.id, r_d.plan_id, r_d.name) as computed
        where computed.district_id::character varying = static.district_id
)
