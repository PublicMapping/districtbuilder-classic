-- This fixes the badly nested geometry that's in the shapefiles

select substring(supplemental_id, 3, 3) as county , st_union(geom) into temp_county from redistricting_geounit where geolevel_id = 1 group by county;

update redistricting_geounit set geom = st_multi(st_union), simple = ST_MULTI(ST_SIMPLIFYPRESERVETOPOLOGY(st_union, 10)) from temp_county where temp_county.county = supplemental_id and geolevel_id = 3;

select substring(supplemental_id, 0, 12) || '.0' as tract , st_union(geom) into temp_tracts from redistricting_geounit where geolevel_id = 1 group by tract;

update redistricting_geounit set geom = st_multi(st_union), simple = ST_MULTI(ST_SIMPLIFYPRESERVETOPOLOGY(st_union, 10)) from temp_tracts where temp_tracts.tract = supplemental_id and geolevel_id = 2;

drop table temp_county;
drop table temp_tracts;
