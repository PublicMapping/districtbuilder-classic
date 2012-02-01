--
-- Remove the non-i18n labels from the data model.
--
ALTER TABLE publicmapping.redistricting_geolevel DROP COLUMN label;
ALTER TABLE publicmapping.redistricting_geolevel ADD CONSTRAINT redistricting_geolevel_name_check UNIQUE ("name");

ALTER TABLE publicmapping.redistricting_legislativebody DROP COLUMN long_label;
ALTER TABLE publicmapping.redistricting_legislativebody DROP COLUMN short_label;
ALTER TABLE publicmapping.redistricting_legislativebody DROP COLUMN title;
ALTER TABLE publicmapping.redistricting_legislativebody ADD CONSTRAINT redistricting_legislativebody_name_check UNIQUE ("name");

ALTER TABLE publicmapping.redistricting_region DROP COLUMN label;
ALTER TABLE publicmapping.redistricting_region DROP COLUMN description;
ALTER TABLE publicmapping.redistricting_region ADD CONSTRAINT redistricting_region_name_check UNIQUE ("name");

ALTER TABLE publicmapping.redistricting_scoredisplay DROP CONSTRAINT redistricting_scoredisplay_title_key;
ALTER TABLE publicmapping.redistricting_scoredisplay ADD CONSTRAINT redistricting_scoredisplay_title_key UNIQUE (legislative_body_id, title, "name", owner_id);
UPDATE publicmapping.redistricting_scoredisplay SET title='';

ALTER TABLE publicmapping.redistricting_scorefunction DROP COLUMN label;
ALTER TABLE publicmapping.redistricting_scorefunction DROP COLUMN description;
ALTER TABLE publicmapping.redistricting_scorefunction ADD CONSTRAINT redistricting_scorefunction_name_check UNIQUE ("name");

UPDATE publicmapping.redistricting_scorepanel SET title='';

ALTER TABLE publicmapping.redistricting_subject DROP COLUMN display;
ALTER TABLE publicmapping.redistricting_subject DROP COLUMN short_display;
ALTER TABLE publicmapping.redistricting_subject DROP COLUMN description;
ALTER TABLE publicmapping.redistricting_subject ADD CONSTRAINT redistricting_subject_name_check UNIQUE ("name");

ALTER TABLE publicmapping.redistricting_validationcriteria DROP COLUMN title;
ALTER TABLE publicmapping.redistricting_validationcriteria DROP COLUMN description;
ALTER TABLE publicmapping.redistricting_validationcriteria ADD UNIQUE ("name");

