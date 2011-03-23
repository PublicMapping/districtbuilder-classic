-- Rather than managing the M2M relationship between Panels and Scores
-- ourselves, let's let Django do it.

CREATE TABLE publicmapping.redistricting_scorepanel_score_functions
(
  id serial NOT NULL,
  scorepanel_id integer NOT NULL,
  scorefunction_id integer NOT NULL,
  CONSTRAINT redistricting_scorepanel_score_functions_pkey PRIMARY KEY (id),
  CONSTRAINT redistricting_scorepanel_score_functions_scorefunction_id_fkey FOREIGN KEY (scorefunction_id)
      REFERENCES publicmapping.redistricting_scorefunction (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED,
  CONSTRAINT scorepanel_id_refs_id_ab2be17a FOREIGN KEY (scorepanel_id)
      REFERENCES publicmapping.redistricting_scorepanel (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED,
  CONSTRAINT redistricting_scorepanel_score_functions_scorepanel_id_key UNIQUE (scorepanel_id, scorefunction_id)
)
WITH (
  OIDS=FALSE
);
ALTER TABLE publicmapping.redistricting_scorepanel_score_functions OWNER TO publicmapping;

CREATE INDEX redistricting_scorepanel_score_functions_scorefunction_id
  ON publicmapping.redistricting_scorepanel_score_functions
  USING btree
  (scorefunction_id);

CREATE INDEX redistricting_scorepanel_score_functions_scorepanel_id
  ON publicmapping.redistricting_scorepanel_score_functions
  USING btree
  (scorepanel_id);

-- We have our new table.  Copy our old panelfunction references
INSERT INTO redistricting_scorepanel_score_functions (SELECT id, panel_id AS scorepanel_id, function_id AS scorefunction_id FROM redistricting_panelfunction);

-- Reset the keys
SELECT setval('redistricting_scorepanel_score_functions_id_seq', (select max(id) from redistricting_scorepanel_score_functions) + 1)

-- Drop the old panelfunction table
DROP TABLE redistricting_panelfunction;


