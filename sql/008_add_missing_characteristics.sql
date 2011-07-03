create temp table va_characteristic as select g.id,g.portable_id,c.subject_id,c.number,c.percentage
from redistricting_geounit g join redistricting_characteristic as c on g.id = c.geounit_id where 1=2;

\copy va_characteristic from '/projects/PublicMapping/data/missing_characteristic.csv' with csv header

update va_characteristic as v set id = g.id from redistricting_geounit as g where g.portable_id = v.portable_id;

-- Add new characteristics to table
--insert into redistricting_characteristic 
--    ( geounit_id, subject_id, number, percentage ) 
--    (
--        select v.id, 7, v.number, v.percentage
--        from va_characteristic as v 
--        where v.subject_id = 4
--    );

--insert into redistricting_characteristic 
--    ( geounit_id, subject_id, number, percentage ) 
--    (
--        select v.id, 8, v.number, v.percentage
--        from va_characteristic as v 
--        where v.subject_id = 2
--    );

--insert into redistricting_characteristic 
--    ( geounit_id, subject_id, number, percentage ) 
--    (
--        select v.id, 9, v.number, v.percentage
--        from va_characteristic as v 
--        where v.subject_id = 3
--    );

--insert into redistricting_characteristic 
--    ( geounit_id, subject_id, number, percentage ) 
--    (
--        select v.id, 10, v.number, v.percentage
--        from va_characteristic as v 
--        where v.subject_id = 5
--    );

--insert into redistricting_characteristic 
--    ( geounit_id, subject_id, number, percentage ) 
--    (
--        select v.id, 11, v.number, v.percentage
--        from va_characteristic as v 
--        where v.subject_id = 6
--    );

--insert into redistricting_characteristic 
--    ( geounit_id, subject_id, number, percentage ) 
--    (
--        select v.id, 12, v.number, v.percentage
--        from va_characteristic as v 
--        where v.subject_id = 7
--    );

--insert into redistricting_characteristic 
--    ( geounit_id, subject_id, number, percentage ) 
--    (
--        select v.id, 13, v.number, v.percentage
--        from va_characteristic as v 
--        where v.subject_id = 9
--    );

--insert into redistricting_characteristic 
--    ( geounit_id, subject_id, number, percentage ) 
--    (
--        select v.id, 14, v.number, v.percentage
--        from va_characteristic as v 
--        where v.subject_id = 12
--    );

--insert into redistricting_characteristic 
--    ( geounit_id, subject_id, number, percentage ) 
--    (
--        select v.id, 15, v.number, v.percentage
--        from va_characteristic as v 
--        where v.subject_id = 13
--    );

--insert into redistricting_characteristic 
--    ( geounit_id, subject_id, number, percentage ) 
--    (
--        select v.id, 16, v.number, v.percentage
--        from va_characteristic as v 
--        where v.subject_id = 14
--    );

--insert into redistricting_characteristic 
--    ( geounit_id, subject_id, number, percentage ) 
--    (
--        select v.id, 17, v.number, v.percentage
--        from va_characteristic as v 
--        where v.subject_id = 15
--    );

--insert into redistricting_characteristic 
--    ( geounit_id, subject_id, number, percentage ) 
--    (
--        select v.id, 18, v.number, v.percentage
--        from va_characteristic as v 
--        where v.subject_id = 16
--    );

insert into redistricting_characteristic 
    ( geounit_id, subject_id, number, percentage ) 
    (
        select v.id, v.subject_id, v.number, v.percentage
        from va_characteristic as v 
        where v.subject_id = 19
    );

--insert into redistricting_characteristic 
--    ( geounit_id, subject_id, number, percentage ) 
--    (
--        select v.id, v.subject_id, v.number, v.percentage
--        from va_characteristic as v 
--        where v.subject_id = 20
--    );

-- Recompute VTDs
select p.id as parent, c.id as child into temp va_vtd_map 
    from redistricting_geounit as p 
    join redistricting_geounit as c 
    on c.child_id = p.id 
    where p.geolevel_id = 2 
    and exists (
        select * 
        from va_characteristic as v 
        where c.id = v.id
    );

select m.parent as geounit_id, c.subject_id, sum (c.number) into temp va_vtd_sums 
    from redistricting_characteristic as c 
    join va_vtd_map as m 
    on c.geounit_id = m.child 
    where c.subject_id = 19
    group by m.parent, c.subject_id;
    
update redistricting_characteristic as c set number = vtd.sum, percentage = 0.00000000 
    from va_vtd_sums as vtd 
    where vtd.geounit_id = c.geounit_id 
    and c.subject_id = vtd.subject_id
    and vtd.subject_id = 19;
    
-- Recompute Counties (into temp va_county_map )
select p.id as parent, c.id as child 
    from redistricting_geounit as p 
    join redistricting_geounit as c 
    on c.child_id = p.id
    where p.geolevel_id = 3;
    
select m.parent as geounit_id, c.subject_id, sum (c.number) into temp va_county_sums 
    from redistricting_characteristic as c 
    join va_county_map as m 
    on c.geounit_id = m.child 
    where c.subject_id = 19
    group by m.parent, c.subject_id;

update redistricting_characteristic as c set number = county.sum, percentage = 0.00000000 
    from va_county_sums as county 
    where county.geounit_id = c.geounit_id 
    and county.subject_id = c.subject_id
    and county.subject_id = 19;
