-- Rename the supplemental_id column to the more descriptive tree_code.  
SET search_path to publicmapping;
ALTER TABLE redistricting_geounit RENAME COLUMN supplemental_id to tree_code;

-- Add the portable_id column
ALTER TABLE redistricting_geounit ADD COLUMN portable_id character varying(50);

-- Update your portable_ids if they're not already present
Update redistricting_geounit set portable_id = tree_code where portable_id is null;
