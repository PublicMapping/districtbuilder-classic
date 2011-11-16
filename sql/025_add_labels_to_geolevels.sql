-- Adds a "label" column to redistricting_geolevel

CREATE OR REPLACE FUNCTION fn_add_labels()
RETURNS void AS

$$
DECLARE
    label_exists integer;
BEGIN
    SELECT count(*) into label_exists from information_schema.columns where table_name = 'redistricting_geolevel' and column_name = 'label';

    IF label_exists <> 1 THEN
        ALTER TABLE redistricting_geolevel ADD COLUMN "label" character varying(20);
        UPDATE redistricting_geolevel set label = name;
        ALTER TABLE redistricting_geolevel ALTER COLUMN "label" SET NOT NULL;
        RAISE NOTICE 'LABEL column created';
    ELSE
        RAISE NOTICE 'LABEL column already exists';
    END IF;
END
$$ 
LANGUAGE 'plpgsql' VOLATILE;

SELECT fn_add_labels();
