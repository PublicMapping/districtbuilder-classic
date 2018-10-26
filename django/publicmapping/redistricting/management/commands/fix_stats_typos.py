from django.core.management.base import BaseCommand
from django.db import connection

import subprocess

from redistricting.models import ComputedDistrictScore, Plan, ScoreFunction, Subject


class Command(BaseCommand):
    """
    A one-off command for fixing stats in-place in the database.
    """
    help = 'Fixes stats for subjects containing typos'

    def add_arguments(self, parser):
        """
        Parses arguments for determining subject and field ids
        """
        parser.add_argument('subject_ids', type=str, help='Comma separated subject ids')
        parser.add_argument('field_ids', type=str, help='Comma separated field ids for subjects')

    def handle(self, *args, **options):
        """
        Performs the steps
        """
        subject_ids = options['subject_ids'].split(",")
        field_ids = options['field_ids'].split(",")

        if len(subject_ids) != len(field_ids):
            print('Subject and field ids need to be the same length!')
            return

        print('Fixing stats for: {}'.format(zip(subject_ids, field_ids)))
        get_shapefile()
        map(reload_characteristics, field_ids)
        renest_geolevels()
        map(insert_computed_characteristics, subject_ids)
        reaggregate_plans()
        map(clear_computed_scores, subject_ids)
        print('Finished!')

def get_shapefile():
    """
    Fetches the shapefile and unzips it. This is because data is not persisted in the container.
    """
    print('Fetching and unzipping shapefile')
    subprocess.check_call('wget -q -O /data/districtbuilder_data.zip http://s3.amazonaws.com/global-districtbuilder-data-us-east-1/pa/pa_3785_census.zip', shell=True)
    subprocess.check_call('unzip -o /data/districtbuilder_data.zip -d /data', shell=True)

def reload_characteristics(field_id):
    """
    Reloads characteristics for a given field
    """
    print('Reloading characteristics for {}'.format(field_id))
    subprocess.check_call('./manage.py setup config/config.xml -g0 -g1 -u={}'.format(field_id), shell=True)

def renest_geolevels():
    """
    Renests all geolevels, so the new characteristics are propagated
    """
    print('Renesting geolevels')
    subprocess.check_call('./manage.py setup config/config.xml -n0 -n1', shell=True)

def insert_computed_characteristics(subject_id):
    """
    Inserts computed characteristics for the new subject.

    This is done via raw SQL due to memory problems that were encountered when iterating over the
    district objects directly. The raw SQL is also much faster.
    """
    print('Inserting computed characteristics for {}'.format(subject_id))
    subject_id = Subject.objects.get(name=subject_id).id
    with connection.cursor() as cursor:
       cursor.execute('delete from redistricting_computedcharacteristic where subject_id = %s', [subject_id])
       cursor.execute('insert into redistricting_computedcharacteristic (number, percentage, district_id, subject_id) select 0.0, 0.0, id, %s from redistricting_district', [subject_id])

def reaggregate_plans():
    """
    Reaggreates all plans to incorporate the new data.

    This is a very time consuming process, and may take several days depending on number of plans
    """
    print('Reaggregating plans')
    num_plans = Plan.objects.count()
    for index, plan in enumerate(Plan.objects.all()):
        print('Reaggregating plan #{}/{}'.format(index + 1, num_plans))
        plan.reaggregate()

def clear_computed_scores(subject_id):
    """
    Clears cached scores, so they can be recomputed with the new values
    """
    print('Clearing computed scores for {}'.format(subject_id))
    sfs = ScoreFunction.objects.filter(name__contains=subject_id)
    ComputedDistrictScore.objects.filter(function__in=sfs).delete()
