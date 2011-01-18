-- This adds a column to indicate whether a district is locked for editing

ALTER TABLE redistricting_district ADD COLUMN is_locked boolean;
UPDATE redistricting_district SET is_locked = false;
ALTER TABLE redistricting_district ALTER COLUMN is_locked SET NOT NULL;