CREATE TABLE "redistricting_region" (
    "id" serial NOT NULL PRIMARY KEY,
    "label" varchar(256) NOT NULL,
    "name" varchar(256) NOT NULL,
    "description" varchar(500) NOT NULL,
    "sort_key" integer CHECK ("sort_key" >= 0) NOT NULL
);
INSERT INTO "redistricting_region" ("name", "label", "description", "sort_key") VALUES ('default', 'Default', 'The region serviced by DistrictBuilder.', 1);

ALTER TABLE "redistricting_legislativebody" ADD COLUMN "region_id" integer;
UPDATE "redistricting_legislativebody" SET "region_id" = 1;
ALTER TABLE "redistricting_legislativebody" ALTER COLUMN "region_id" SET NOT NULL;
CREATE INDEX "redistricting_legislativebody_region_id" ON "redistricting_legislativebody" ("region_id");
