--
-- Add support for the i18n libraries and methods.
--
ALTER TABLE publicmapping.redistricting_scoredisplay ADD COLUMN "name" character varying(50) NOT NULL DEFAULT '';
ALTER TABLE publicmapping.redistricting_scorepanel ADD COLUMN "name" character varying(50) NOT NULL DEFAULT '';
ALTER TABLE publicmapping.redistricting_validationcriteria ADD COLUMN title character varying(50) NOT NULL DEFAULT '';

