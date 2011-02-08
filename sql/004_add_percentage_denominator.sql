-- Add the percentage_denominator field
SET search_path = publicmapping;
ALTER TABLE redistricting_subject ADD COLUMN percentage_denominator_id integer;
ALTER TABLE redistricting_subject
  ADD CONSTRAINT percentage_denominator_refs_subject_id FOREIGN KEY (percentage_denominator_id)
      REFERENCES redistricting_subject (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

-- Drop your views because they depend on the percentage field
DROP VIEW 
    identify_geounit,
    demo_county_poptot,
    demo_tract_poptot,
    demo_block_poptot,
    demo_county_pophisp,
    demo_tract_pophisp,
    demo_block_pophisp,
    demo_county_popblk,
    demo_tract_popblk,
    demo_block_popblk
;

-- Update the percentage field to have significant digits before the decimal
ALTER TABLE redistricting_characteristic ALTER percentage TYPE numeric(12,8);
ALTER TABLE redistricting_computedcharacteristic ALTER percentage TYPE numeric(12,8);

-- IMPORTANT!! --
-- Now rerun setup.py with the -v command to recreate your views;
