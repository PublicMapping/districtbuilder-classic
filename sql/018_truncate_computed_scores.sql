--
-- Truncate the computed score tables. This is due to a change in the
-- serialization when ticket #294 was closed.
--
TRUNCATE TABLE publicmapping.redistricting_computeddistrictscore, publicmapping.redistricting_computedplanscore RESTART IDENTITY;
