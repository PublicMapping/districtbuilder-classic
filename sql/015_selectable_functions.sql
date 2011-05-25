-- Table: publicmapping.redistricting_scorefunction_selectable_bodies

-- DROP TABLE publicmapping.redistricting_scorefunction_selectable_bodies;

CREATE TABLE publicmapping.redistricting_scorefunction_selectable_bodies
(
  id serial NOT NULL,
  scorefunction_id integer NOT NULL,
  legislativebody_id integer NOT NULL,
  CONSTRAINT redistricting_scorefunction_selectable_bodies_pkey PRIMARY KEY (id),
  CONSTRAINT redistricting_scorefunction_selectable__legislativebody_id_fkey FOREIGN KEY (legislativebody_id)
      REFERENCES publicmapping.redistricting_legislativebody (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED,
  CONSTRAINT scorefunction_id_refs_id_a461ab3 FOREIGN KEY (scorefunction_id)
      REFERENCES publicmapping.redistricting_scorefunction (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED,
  CONSTRAINT redistricting_scorefunction_selectable_bod_scorefunction_id_key UNIQUE (scorefunction_id, legislativebody_id)
)
WITH (
  OIDS=FALSE
);
ALTER TABLE publicmapping.redistricting_scorefunction_selectable_bodies OWNER TO publicmapping;

-- Index: publicmapping.redistricting_scorefunction_selectable_bodies_legislativebody_i

-- DROP INDEX publicmapping.redistricting_scorefunction_selectable_bodies_legislativebody_i;

CREATE INDEX redistricting_scorefunction_selectable_bodies_legislativebody_i
  ON publicmapping.redistricting_scorefunction_selectable_bodies
  USING btree
  (legislativebody_id);

-- Index: publicmapping.redistricting_scorefunction_selectable_bodies_scorefunction_id

-- DROP INDEX publicmapping.redistricting_scorefunction_selectable_bodies_scorefunction_id;

CREATE INDEX redistricting_scorefunction_selectable_bodies_scorefunction_id
  ON publicmapping.redistricting_scorefunction_selectable_bodies
  USING btree
  (scorefunction_id);

CREATE FUNCTION publicmapping.populate_selectable_scorefn()
RETURNS SETOF publicmapping.redistricting_scorefunction_selectable_bodies
AS $$
DECLARE
    lbody RECORD;
    sfn RECORD;
BEGIN
    FOR lbody IN SELECT id FROM publicmapping.redistricting_legislativebody LOOP
    FOR sfn IN SELECT id FROM publicmapping.redistricting_scorefunction WHERE is_user_selectable = TRUE LOOP
        RETURN QUERY SELECT nextval('publicmapping.redistricting_scorefunction_selectable_bodies_id_seq')::integer,
            sfn.id,lbody.id;
    END LOOP;
    END LOOP;
    RETURN;
END;
$$
LANGUAGE plpgsql;

INSERT INTO publicmapping.redistricting_scorefunction_selectable_bodies
    SELECT id, scorefunction_id, legislativebody_id from publicmapping.populate_selectable_scorefn();

DROP FUNCTION publicmapping.populate_selectable_scorefn();

ALTER TABLE publicmapping.redistricting_scorefunction DROP COLUMN is_user_selectable;

