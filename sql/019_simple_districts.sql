-- Create a simple view for looking at the districts.
CREATE VIEW simple_district AS
    SELECT redistricting_district.id, redistricting_district.district_id, 
           redistricting_district.plan_id, st_geometryn(redistricting_district.simple,3) as geom 
      FROM redistricting_district;
