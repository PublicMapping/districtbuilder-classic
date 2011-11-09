--
-- Add uploaded subject quarantine table and metadata table
--
CREATE TABLE "redistricting_subjectupload" (
    "id" serial NOT NULL PRIMARY KEY,
    "processing_filename" varchar(256) NOT NULL,
    "upload_filename" varchar(256) NOT NULL,
    "subject_name" varchar(50) NOT NULL,
    "status" varchar(2) NOT NULL,
    "task_id" varchar(36) NOT NULL
)
;
CREATE TABLE "redistricting_subjectquarantine" (
    "id" serial NOT NULL PRIMARY KEY,
    "upload_id" integer NOT NULL REFERENCES "redistricting_subjectupload" ("id") DEFERRABLE INITIALLY DEFERRED,
    "portable_id" varchar(50) NOT NULL,
    "number" numeric(12, 4) NOT NULL
)
;
CREATE INDEX "redistricting_subjectquarantine_upload_id" ON "redistricting_subjectquarantine" ("upload_id");

