ALTER TABLE publicmapping.redistricting_legislativebody ADD COLUMN sort_key integer CHECK (sort_key >= 0);
UPDATE publicmapping.redistricting_legislativebody SET sort_key = id;
ALTER TABLE publicmapping.redistricting_legislativebody ALTER COLUMN sort_key SET NOT NULL;
