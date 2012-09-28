-- Everything one needs to allow for the personal statistics sets
SET search_path to publicmapping;

-- Allow a M2M relationship so we can re-use ScorePanels across Displays
CREATE TABLE redistricting_scorepanel_displays
(
  id serial NOT NULL,
  scorepanel_id integer NOT NULL,
  scoredisplay_id integer NOT NULL,
  CONSTRAINT redistricting_scorepanel_displays_pkey PRIMARY KEY (id),
  CONSTRAINT redistricting_scorepanel_displays_scoredisplay_id_fkey FOREIGN KEY (scoredisplay_id)
      REFERENCES redistricting_scoredisplay (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED,
  CONSTRAINT scorepanel_id_refs_id_a6148278 FOREIGN KEY (scorepanel_id)
      REFERENCES redistricting_scorepanel (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED,
  CONSTRAINT redistricting_scorepanel_displays_scorepanel_id_key UNIQUE (scorepanel_id, scoredisplay_id)
)
WITH (
  OIDS=FALSE
);
ALTER TABLE redistricting_scorepanel_displays OWNER TO publicmapping;

-- Indexes for searching
CREATE INDEX redistricting_scorepanel_displays_scoredisplay_id
  ON redistricting_scorepanel_displays
  USING btree
  (scoredisplay_id);

CREATE INDEX redistricting_scorepanel_displays_scorepanel_id
  ON redistricting_scorepanel_displays
  USING btree
  (scorepanel_id);

-- Preserve our current links in the one-to-one relationship
INSERT INTO redistricting_scorepanel_displays (scorepanel_id, scoredisplay_id) (Select id, display_id from redistricting_scorepanel);
SELECT setval('redistricting_scorepanel_displays_id_seq', (select max(id) from redistricting_scorepanel_displays) + 1);

-- Remove the old one-to-one relationship
ALTER TABLE redistricting_scorepanel DROP COLUMN display_id;

-- Add owners to a ScoreDisplay
ALTER TABLE redistricting_scoredisplay ADD COLUMN owner_id integer;
UPDATE redistricting_scoredisplay SET owner_id = 1;
ALTER TABLE redistricting_scoredisplay ALTER COLUMN owner_id SET NOT NULL;

ALTER TABLE redistricting_scoredisplay
  ADD CONSTRAINT redistricting_scoredisplay_owner_id_fkey FOREIGN KEY (owner_id)
      REFERENCES auth_user (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

-- Add the is_user_selectable field
 
ALTER TABLE redistricting_scorefunction ADD COLUMN is_user_selectable boolean;
UPDATE redistricting_scorefunction set is_user_selectable = true where calculator ilike 'publicmapping.redistricting.calculators.Sum';
UPDATE redistricting_scorefunction set is_user_selectable = false where is_user_selectable is null;
ALTER TABLE redistricting_scorefunction ALTER COLUMN is_user_selectable SET NOT NULL;

