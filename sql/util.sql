insert into redistricting_district (district_id,name,plan_id,version) values (0, 'Unassigned', 1, 0);

-- update the district with the ID of 2 (District 1)
-- emulate a district by adding all the geounits contained in
-- geounit 25, geolevel 1 (all blocks in a country)
insert into redistricting_district (district_id,name,plan_id,version) values (1, 'District 1', 1, 0);
insert into redistricting_districtgeounitmapping (plan_id, district_id, geounit_id) (
    select 1, 2, gu1.id from redistricting_geounit as gu1
        inner join redistricting_geounit as gu2 on st_within(st_centroid(gu1.geom), gu2.geom)
        where gu2.id = 25 and gu1.geolevel_id = 3
        order by gu1.id
);

-- update the district with the ID of 3 (District 2)
-- emulate a district by adding all the geounits contained in
-- geounit 46, geolevel 1 (all blocks in a county)
insert into redistricting_district (district_id,name,plan_id,version) values (2, 'District 2', 1, 0);
insert into redistricting_districtgeounitmapping (plan_id, district_id, geounit_id) (
    select 1, 3, gu1.id from redistricting_geounit as gu1
        inner join redistricting_geounit as gu2 on st_within(st_centroid(gu1.geom), gu2.geom)
        where gu2.id = 46 and gu1.geolevel_id = 3
        order by gu1.id
);

-- update the district with the ID of 4 (District 3)
-- emulate a district by adding all the geounits contained in
-- geounit 12, geolevel 1 (all blocks in a county)
insert into redistricting_district (district_id,name,plan_id,version) values (3, 'District 3', 1, 0);
insert into redistricting_districtgeounitmapping (plan_id, district_id, geounit_id) (
    select 1, 4, gu1.id from redistricting_geounit as gu1
        inner join redistricting_geounit as gu2 on st_within(st_centroid(gu1.geom), gu2.geom)
        where gu2.id = 12 and gu1.geolevel_id = 3
        order by gu1.id
);

-- update the district with the ID of 5 (District 4)
-- emulate a district by adding all the geounits contained in
-- geounit 34, geolevel 1 (all blocks in a county)
insert into redistricting_district (district_id,name,plan_id,version) values (4, 'District 4', 1, 0);
insert into redistricting_districtgeounitmapping (plan_id, district_id, geounit_id) (
    select 1, 5, gu1.id from redistricting_geounit as gu1
        inner join redistricting_geounit as gu2 on st_within(st_centroid(gu1.geom), gu2.geom)
        where gu2.id = 34 and gu1.geolevel_id = 3
        order by gu1.id
);

-- set the geometry of each district from the base units -- full detail
update redistricting_district as static set geom = (
    select st_multi(geom) from (
        SELECT r_d.id AS district_id, r_d.plan_id, r_d.name AS district_name, st_union(r_g.geom) AS geom
           FROM redistricting_district r_d
           JOIN redistricting_district_geounits r_dg ON r_dg.district_id = r_d.id
           JOIN redistricting_geounit r_g ON r_g.id = r_dg.geounit_id
          GROUP BY r_d.id, r_d.plan_id, r_d.name) as computed
        where computed.district_id = static.district_id
);

-- set the simplified geometry of each district to the simplified version
update redistricting_district set simple = st_simplifypreservetopology(geom,10.0);
