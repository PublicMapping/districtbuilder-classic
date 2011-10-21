CREATE TABLE "redistricting_region" (
    "id" serial NOT NULL PRIMARY KEY,
    "name" varchar(256) NOT NULL,
    "description" varchar(500) NOT NULL
);
INSERT INTO "redistricting_region" ("name", "description") VALUES ('Default', 'The region serviced by DistrictBuilder.');

ALTER TABLE "redistricting_legislativebody" ADD COLUMN "region_id" integer;
UPDATE "redistricting_legislativebody" SET "region_id" = 1;
ALTER TABLE "redistricting_legislativebody" ALTER COLUMN "region_id" SET NOT NULL;
CREATE INDEX "redistricting_legislativebody_region_id" ON "redistricting_legislativebody" ("region_id");
