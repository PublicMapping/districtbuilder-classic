-- This adds a column to indicate the oldest available stored version of the plan
SET search_path to publicmapping;
ALTER TABLE redistricting_plan ADD COLUMN min_version integer;
UPDATE redistricting_plan SET min_version = 0;
ALTER TABLE redistricting_plan ALTER COLUMN min_version SET NOT NULL;
