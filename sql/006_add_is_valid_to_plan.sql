-- This adds a column to indicate whether a plan is valid
SET search_path to publicmapping;
ALTER TABLE redistricting_plan ADD COLUMN is_valid boolean;
UPDATE redistricting_plan SET is_valid = false;
ALTER TABLE redistricting_plan ALTER COLUMN is_valid SET NOT NULL;
