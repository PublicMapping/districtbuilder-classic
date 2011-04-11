-- Add columns to configure multi-member districts in the legislative body
SET search_path to publicmapping;

ALTER TABLE redistricting_legislativebody ADD COLUMN multi_members_allowed boolean;
UPDATE redistricting_legislativebody SET multi_members_allowed = false;
ALTER TABLE redistricting_legislativebody ALTER COLUMN multi_members_allowed SET NOT NULL;

ALTER TABLE redistricting_legislativebody ADD COLUMN multi_district_label_format character varying(32);
UPDATE redistricting_legislativebody SET multi_district_label_format = '';
ALTER TABLE redistricting_legislativebody ALTER COLUMN multi_district_label_format SET NOT NULL;

ALTER TABLE redistricting_legislativebody ADD COLUMN min_multi_districts integer;
UPDATE redistricting_legislativebody SET min_multi_districts = 0;
ALTER TABLE redistricting_legislativebody ALTER COLUMN min_multi_districts SET NOT NULL;

ALTER TABLE redistricting_legislativebody ADD COLUMN max_multi_districts integer;
UPDATE redistricting_legislativebody SET max_multi_districts = 0;
ALTER TABLE redistricting_legislativebody ALTER COLUMN max_multi_districts SET NOT NULL;

ALTER TABLE redistricting_legislativebody ADD COLUMN min_multi_district_members integer;
UPDATE redistricting_legislativebody SET min_multi_district_members = 0;
ALTER TABLE redistricting_legislativebody ALTER COLUMN min_multi_district_members SET NOT NULL;

ALTER TABLE redistricting_legislativebody ADD COLUMN max_multi_district_members integer;
UPDATE redistricting_legislativebody SET max_multi_district_members = 0;
ALTER TABLE redistricting_legislativebody ALTER COLUMN max_multi_district_members SET NOT NULL;

ALTER TABLE redistricting_legislativebody ADD COLUMN min_plan_members integer;
UPDATE redistricting_legislativebody SET min_plan_members = 0;
ALTER TABLE redistricting_legislativebody ALTER COLUMN min_plan_members SET NOT NULL;

ALTER TABLE redistricting_legislativebody ADD COLUMN max_plan_members integer;
UPDATE redistricting_legislativebody SET max_plan_members = 0;
ALTER TABLE redistricting_legislativebody ALTER COLUMN max_plan_members SET NOT NULL;

-- Add column to district table for keeping a tally of members
ALTER TABLE redistricting_district ADD COLUMN num_members integer;
UPDATE redistricting_district SET num_members = 1;
ALTER TABLE redistricting_district ALTER COLUMN num_members SET NOT NULL;
