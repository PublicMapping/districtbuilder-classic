--
-- Add support for the i18n libraries and methods.
--
ALTER TABLE publicmapping.redistricting_scoredisplay ADD COLUMN "name" character varying(50) NOT NULL DEFAULT '';
ALTER TABLE publicmapping.redistricting_scorepanel ADD COLUMN "name" character varying(50) NOT NULL DEFAULT '';
ALTER TABLE publicmapping.redistricting_validationcriteria ADD COLUMN title character varying(50) NOT NULL DEFAULT '';
UPDATE publicmapping.redistricting_validationcriteria SET title = "name";
UPDATE publicmapping.redistricting_validationcriteria SET "name" = '';

ALTER TABLE publicmapping.redistricting_legislativebody ADD COLUMN title character varying(256) NOT NULL DEFAULT '';
UPDATE publicmapping.redistricting_legislativebody SET title = "name";
UPDATE publicmapping.redistricting_legislativebody SET "name" = '';
