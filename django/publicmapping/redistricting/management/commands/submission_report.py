import os.path
import codecs

from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.management.base import BaseCommand
from django.core import serializers
from django.template import loader
from django.utils import translation

from redistricting.models import ScorePanel, PlanSubmission


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
        # We're going to reuse the summary panel from the main map editing page
        score_panel = ScorePanel.objects.filter(name='plan_submission_summary')[0]
        districts = [d for d in submission.plan.district_set.all() if not d.is_unassigned]
        # The above Score Display is split into two ScorePanels: the top summary panel and the
        # bottom panel of per-district scores. We want the summary panel.
        # The type field is apparently limited to three options: 1) plan 2) plan_summary 3) district
        scores_html = score_panel.render(submission.plan)
        GeoJSONSerializer = serializers.get_serializer('geojson')
        serializer = GeoJSONSerializer()
        # is_unassigned is a property so we can't use queryset filtering
        # The unassigned district is a catch-all for geounits that haven't been assigned to a real
        # district. We don't want to display this on the submission map, so filter it out here.
        geojson = serializer.serialize(
            districts,
            geometry_field='geom',
            fields=('short_label', 'long_label')
        )
        leaflet_css = staticfiles_storage.open('leaflet/leaflet.css').read()
        leaflet_js = staticfiles_storage.open('leaflet/leaflet.js').read()
        context = dict(
            submission=submission,
            scores_html=scores_html,
            leaflet_css=leaflet_css,
            leaflet_js=leaflet_js,
            geojson=geojson
        )

        print('Writing report to {}'.format(output_path))

        with codecs.open(output_path, 'wb', 'UTF-8') as outfile:
            outfile.write(template.render(context))
        print('Done.')
