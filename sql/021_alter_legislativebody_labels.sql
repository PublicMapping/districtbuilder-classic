-- Add 'short_label' and 'long_label' to the legislative body table
ALTER TABLE publicmapping.redistricting_legislativebody ADD COLUMN long_label character varying(256) NOT NULL DEFAULT 'District %s';
ALTER TABLE publicmapping.redistricting_legislativebody ADD COLUMN short_label character varying(10) NOT NULL DEFAULT '%s';

UPDATE publicmapping.redistricting_legislativebody SET long_label = member;

ALTER TABLE publicmapping.redistricting_legislativebody DROP COLUMN member;

-- Add 'short_label' and 'long_label' to the district table
ALTER TABLE publicmapping.redistricting_district ADD COLUMN long_label character varying(256);
ALTER TABLE publicmapping.redistricting_district ADD COLUMN short_label character varying(10);

UPDATE publicmapping.redistricting_district SET long_label = "name";
UPDATE publicmapping.redistricting_district AS rd SET short_label = (SELECT 
    (CASE 
        WHEN rd."name" = 'Unassigned' 
        THEN E'\xC3\x98' 
        ELSE regexp_replace(rd."name", regexp_replace(rl.long_label, '%s', E'(\\d+)'),E'\\1')
        END)::character varying(10))
FROM 
    publicmapping.redistricting_plan AS rp,
    publicmapping.redistricting_legislativebody AS rl
WHERE 
    rd.plan_id = rp.id AND
    rp.legislative_body_id = rl.id;

ALTER TABLE publicmapping.redistricting_district DROP COLUMN "name";
ALTER TABLE publicmapping.redistricting_district ALTER COLUMN long_label SET NOT NULL;
ALTER TABLE publicmapping.redistricting_district ALTER COLUMN short_label SET NOT NULL;

