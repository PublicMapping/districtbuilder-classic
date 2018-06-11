import os.path
import codecs

from django.core.management.base import BaseCommand
from django.core import serializers
from django.template import loader
from django.utils import translation

from django.contrib.auth.models import User
from redistricting.models import ScoreDisplay, PlanSubmission


class Command(BaseCommand):
    help = 'Generates an HTML summary page for the specified plan submission ID'

    def add_arguments(self, parser):
        parser.add_argument('submission_id', type=int)

    def handle(self, *args, **options):
        translation.activate('en')
        submission = PlanSubmission.objects.get(pk=options['submission_id'])
        output_path = '{}.html'.format(submission.pk)
        if os.path.exists(output_path):
            print('Report file already exists!')
            return

        template = loader.get_template('submission_summary.html')
        admin = User.objects.get(username='admin')
        # We're going to reuse the summary panel from the main map editing page
        score_display = ScoreDisplay.objects.get(
            owner=admin,
            legislative_body=submission.plan.legislative_body,
            title='Basic Information'
        )
        # The above Score Display is split into two ScorePanels: the top summary panel and the
        # bottom panel of per-district scores. We want the summary panel.
        # The type field is apparently limited to three options: 1) plan 2) plan_summary 3) district
        score_panel = score_display.scorepanel_set.filter(type='plan_summary')[0]
        scores_html = score_panel.render(submission.plan)
        GeoJSONSerializer = serializers.get_serializer('geojson')
        serializer = GeoJSONSerializer()
        geojson = serializer.serialize(
            submission.plan.district_set.all(),
            geometry_field='geom',
            fields=('short_label', 'long_label')
        )
        context = dict(
            submission=submission,
            scores_html=scores_html,
            geojson=geojson
        )

        print('Writing report to {}'.format(output_path))

        with codecs.open(output_path, 'wb', 'UTF-8') as outfile:
            outfile.write(template.render(context))
        print('Done.')