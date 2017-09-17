pushd /projects/PublicMapping/DistrictBuilder
# set password so that postgres doesn't prompt for it
echo "*:*:*:postgres:postgres" > ~/.pgpass
chmod 600 ~/.pgpass
./wait-for-postgres.sh postgres psql -h postgres -U postgres -w -f sql/publicmapping_db.sql
pushd /projects/PublicMapping/DistrictBuilder/django/publicmapping
../../wait-for-geoserver.sh geoserver python setup.py ../../docs/config.xsd ../../docs/config.xml
service celeryd start
python manage.py -h
python manage.py runserver
