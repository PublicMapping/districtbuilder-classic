--
-- Add a new column to hold subject_id
--
ALTER TABLE publicmapping.redistricting_legislativelevel ADD COLUMN subject_id integer;

UPDATE publicmapping.redistricting_legislativelevel AS ll SET subject_id = (SELECT subject_id FROM publicmapping.redistricting_target AS rt WHERE ll.target_id = rt.id);

ALTER TABLE publicmapping.redistricting_legislativelevel ALTER COLUMN subject_id SET NOT NULL;
ALTER TABLE publicmapping.redistricting_legislativelevel DROP COLUMN target_id;
ALTER TABLE publicmapping.redistricting_legislativelevel ADD CONSTRAINT redistricting_legislativelevel_subject_id_fkey FOREIGN KEY (subject_id) REFERENCES publicmapping.redistricting_subject (id) MATCH SIMPLE ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

--
-- Remove legislative defaults
--
DROP TABLE publicmapping.redistricting_legislativedefault;

--
-- Remove targets table
--
DROP TABLE publicmapping.redistricting_target;
--
-- Add a new column to hold subject_id
--
ALTER TABLE publicmapping.redistricting_legislativelevel ADD COLUMN subject_id integer;

UPDATE publicmapping.redistricting_legislativelevel AS ll SET subject_id = (SELECT subject_id FROM publicmapping.redistricting_target AS rt WHERE ll.target_id = rt.id);

ALTER TABLE publicmapping.redistricting_legislativelevel ALTER COLUMN subject_id SET NOT NULL;
ALTER TABLE publicmapping.redistricting_legislativelevel DROP COLUMN target_id;
ALTER TABLE publicmapping.redistricting_legislativelevel ADD CONSTRAINT redistricting_legislativelevel_subject_id_fkey FOREIGN KEY (subject_id) REFERENCES publicmapping.redistricting_subject (id) MATCH SIMPLE ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

--
-- Remove legislative defaults
--
DROP TABLE publicmapping.redistricting_legislativedefault;

--
-- Remove targets table
--
DROP TABLE publicmapping.redistricting_target;
