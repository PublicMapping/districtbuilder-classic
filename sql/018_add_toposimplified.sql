-- Add toposimplified column to district and geounit tables
SELECT AddGeometryColumn ('publicmapping','redistricting_geounit','toposimplified',3785,'MULTIPOLYGON',2);
SELECT AddGeometryColumn ('publicmapping','redistricting_district','toposimplified',3785,'MULTIPOLYGON',2);
