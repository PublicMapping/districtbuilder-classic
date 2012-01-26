-- Remove is_pending, add processing_state
BEGIN;

ALTER TABLE publicmapping.redistricting_plan DROP COLUMN is_pending;
ALTER TABLE publicmapping.redistricting_plan ADD COLUMN processing_state integer;
UPDATE publicmapping.redistricting_plan SET processing_state = 0;
ALTER TABLE publicmapping.redistricting_plan ALTER COLUMN processing_state SET NOT NULL;

COMMIT;
