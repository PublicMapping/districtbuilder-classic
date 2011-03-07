-- This adds a column to indicate whether a plan is valid
SET search_path to publicmapping;
ALTER TABLE redistricting_scorepanel ADD COLUMN is_ascending boolean;
UPDATE redistricting_scorepanel SET is_ascending = false;
ALTER TABLE redistricting_scorepanel ALTER COLUMN is_ascending SET NOT NULL;
