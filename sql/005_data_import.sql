-- This script imports the latest data from the VA census.  The Census Bureau 
-- mistakenly placed the naval base in the wrong block so about 20,000 
-- sailors and their families were misallocated.

-- Create the table with the same column definitions we currently have
create temp table va_data_import as select
    g.id,
    name,
    portable_id,
    number as poptot,
    number as popwnh,
    number as popblk,
    number as pophisp,
    number as popasn,
    number as popnam,
    number as poppild,
    number as vap,
    number as vapwnh,
    number as vapblk,
    number as vaphisp,
    number as vapasn,
    number as vapnam,
    number as vappild,
    number as presdem,
    number as presrep,
    number as govoth,
    number as govdem,
    number as govrep,
    number as govtot
from redistricting_geounit as g join redistricting_characteristic as c on g.id = c.geounit_id where 1 =2;

-- Copy the data from the CSV file extracted from the latest census data
\copy va_data_import from '/projects/PublicMapping/data/va_census_update.csv' with CSV HEADER

-- Add the primary keys to the VA data for fewer joins in the mapping section later.
update va_data_import as v set id = g.id from redistricting_geounit as g where g.portable_id = v.portable_id;

-- Update all of the values with the new data in the CSV
update redistricting_characteristic as c set percentage = 0.00000000, number = poptot from va_data_import as v join redistricting_geounit as g on v.portable_id = g.portable_id where c.geounit_id = g.id and exists (select id from redistricting_subject as s where s.name like 'poptot' and s.id = c.subject_id);

update redistricting_characteristic as c set percentage = 0.00000000, number = popwnh from va_data_import as v join redistricting_geounit as g on v.portable_id = g.portable_id where c.geounit_id = g.id and exists (select id from redistricting_subject as s where s.name like 'popwnh' and s.id = c.subject_id);

update redistricting_characteristic as c set percentage = 0.00000000, number = popblk from va_data_import as v join redistricting_geounit as g on v.portable_id = g.portable_id where c.geounit_id = g.id and exists (select id from redistricting_subject as s where s.name like 'popblk' and s.id = c.subject_id);

update redistricting_characteristic as c set percentage = 0.00000000, number = pophisp from va_data_import as v join redistricting_geounit as g on v.portable_id = g.portable_id where c.geounit_id = g.id and exists (select id from redistricting_subject as s where s.name like 'pophisp' and s.id = c.subject_id);

update redistricting_characteristic as c set percentage = 0.00000000, number = popasn from va_data_import as v join redistricting_geounit as g on v.portable_id = g.portable_id where c.geounit_id = g.id and exists (select id from redistricting_subject as s where s.name like 'popasn' and s.id = c.subject_id);

update redistricting_characteristic as c set percentage = 0.00000000, number = popnam from va_data_import as v join redistricting_geounit as g on v.portable_id = g.portable_id where c.geounit_id = g.id and exists (select id from redistricting_subject as s where s.name like 'popnam' and s.id = c.subject_id);

update redistricting_characteristic as c set percentage = 0.00000000, number = poppild from va_data_import as v join redistricting_geounit as g on v.portable_id = g.portable_id where c.geounit_id = g.id and exists (select id from redistricting_subject as s where s.name like 'poppild' and s.id = c.subject_id);

update redistricting_characteristic as c set percentage = 0.00000000, number = vap from va_data_import as v join redistricting_geounit as g on v.portable_id = g.portable_id where c.geounit_id = g.id and exists (select id from redistricting_subject as s where s.name like 'vap' and s.id = c.subject_id);

update redistricting_characteristic as c set percentage = 0.00000000, number = vapwnh from va_data_import as v join redistricting_geounit as g on v.portable_id = g.portable_id where c.geounit_id = g.id and exists (select id from redistricting_subject as s where s.name like 'vapwnh' and s.id = c.subject_id);

update redistricting_characteristic as c set percentage = 0.00000000, number = vapblk from va_data_import as v join redistricting_geounit as g on v.portable_id = g.portable_id where c.geounit_id = g.id and exists (select id from redistricting_subject as s where s.name like 'vapblk' and s.id = c.subject_id);

update redistricting_characteristic as c set percentage = 0.00000000, number = vaphisp from va_data_import as v join redistricting_geounit as g on v.portable_id = g.portable_id where c.geounit_id = g.id and exists (select id from redistricting_subject as s where s.name like 'vaphisp' and s.id = c.subject_id);

update redistricting_characteristic as c set percentage = 0.00000000, number = vapasn from va_data_import as v join redistricting_geounit as g on v.portable_id = g.portable_id where c.geounit_id = g.id and exists (select id from redistricting_subject as s where s.name like 'vapasn' and s.id = c.subject_id);

update redistricting_characteristic as c set percentage = 0.00000000, number = vapnam from va_data_import as v join redistricting_geounit as g on v.portable_id = g.portable_id where c.geounit_id = g.id and exists (select id from redistricting_subject as s where s.name like 'vapnam' and s.id = c.subject_id);

update redistricting_characteristic as c set percentage = 0.00000000, number = vappild from va_data_import as v join redistricting_geounit as g on v.portable_id = g.portable_id where c.geounit_id = g.id and exists (select id from redistricting_subject as s where s.name like 'vappild' and s.id = c.subject_id);

update redistricting_characteristic as c set percentage = 0.00000000, number = presdem from va_data_import as v join redistricting_geounit as g on v.portable_id = g.portable_id where c.geounit_id = g.id and exists (select id from redistricting_subject as s where s.name like 'presdem' and s.id = c.subject_id);

update redistricting_characteristic as c set percentage = 0.00000000, number = presrep from va_data_import as v join redistricting_geounit as g on v.portable_id = g.portable_id where c.geounit_id = g.id and exists (select id from redistricting_subject as s where s.name like 'presrep' and s.id = c.subject_id);

update redistricting_characteristic as c set percentage = 0.00000000, number = govoth from va_data_import as v join redistricting_geounit as g on v.portable_id = g.portable_id where c.geounit_id = g.id and exists (select id from redistricting_subject as s where s.name like 'govoth' and s.id = c.subject_id);

update redistricting_characteristic as c set percentage = 0.00000000, number = govdem from va_data_import as v join redistricting_geounit as g on v.portable_id = g.portable_id where c.geounit_id = g.id and exists (select id from redistricting_subject as s where s.name like 'govdem' and s.id = c.subject_id);

update redistricting_characteristic as c set percentage = 0.00000000, number = govrep from va_data_import as v join redistricting_geounit as g on v.portable_id = g.portable_id where c.geounit_id = g.id and exists (select id from redistricting_subject as s where s.name like 'govrep' and s.id = c.subject_id);

update redistricting_characteristic as c set percentage = 0.00000000, number = govtot from va_data_import as v join redistricting_geounit as g on v.portable_id = g.portable_id where c.geounit_id = g.id and exists (select id from redistricting_subject as s where s.name like 'govtot' and s.id = c.subject_id);

-- Update the block percentage values where necessary;
update redistricting_characteristic as n set percentage = n.number / d.number from redistricting_subject as s join redistricting_characteristic as d on s.percentage_denominator_id = d.subject_id where n.geounit_id = d.geounit_id and exists (select * from va_data_import as v where v.id = n.geounit_id) and d.number != 0 and n.subject_id = s.id;

-- Update the VTD characteristics
select p.id as parent, c.id as child into temp va_vtd_map from redistricting_geounit as p join redistricting_geounit as c on c.child_id = p.id where p.geolevel_id = 2 and exists (select * from va_data_import as v where c.id = v.id);

select m.parent as geounit_id, c.subject_id, sum (c.number) into temp va_vtd_sums from redistricting_characteristic as c join va_vtd_map as m on c.geounit_id = m.child group by m.parent, c.subject_id;

update redistricting_characteristic as c set number = vtd.sum, percentage = 0.00000000 from va_vtd_sums as vtd where vtd.geounit_id = c.geounit_id and vtd.subject_id = c.subject_id;

update redistricting_characteristic as n set percentage = n.number / d.number from redistricting_subject as s join redistricting_characteristic as d on s.percentage_denominator_id = d.subject_id where n.geounit_id = d.geounit_id and exists (select * from va_vtd_map as m where m.parent = n.geounit_id) and d.number != 0 and n.subject_id = s.id;

-- Update the county characteristics
select p.id as parent, c.id as child into temp va_county_map from redistricting_geounit as p join redistricting_geounit as c on c.child_id = p.id where p.id = 288258;

select m.parent as geounit_id, c.subject_id, sum (c.number) into temp va_county_sums from redistricting_characteristic as c join va_county_map as m on c.geounit_id = m.child group by m.parent, c.subject_id;

update redistricting_characteristic as c set number = county.sum, percentage = 0.00000000 from va_county_sums as county where county.geounit_id = c.geounit_id and county.subject_id = c.subject_id;

update redistricting_characteristic as n set percentage = n.number / d.number from redistricting_subject as s join redistricting_characteristic as d on s.percentage_denominator_id = d.subject_id where n.geounit_id = d.geounit_id and exists (select * from va_county_map as m where m.parent = n.geounit_id) and d.number != 0 and n.subject_id = s.id;

