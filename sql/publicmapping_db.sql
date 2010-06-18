-- Role: "publicmapping"

-- DROP ROLE publicmapping;

CREATE ROLE publicmapping LOGIN
  ENCRYPTED PASSWORD 'md50eb21ab7f658fe8dba10a343d987eed3'
  NOSUPERUSER INHERIT CREATEDB NOCREATEROLE;

-- Database: publicmapping

-- DROP DATABASE publicmapping;

CREATE DATABASE publicmapping
  WITH OWNER = publicmapping
       ENCODING = 'UTF8'
       LC_COLLATE = 'en_US.UTF-8'
       LC_CTYPE = 'en_US.UTF-8'
       CONNECTION LIMIT = -1
	   TEMPLATE = template_postgis;
	   
\c publicmapping

ALTER TABLE geometry_columns OWNER TO publicmapping;
ALTER TABLE spatial_ref_sys OWNER TO publicmapping;

