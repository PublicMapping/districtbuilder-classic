-- Add the child_id column for tiered bookkeeping
SET search_path to publicmapping;
ALTER TABLE redistricting_geounit ADD COLUMN child_id integer;
