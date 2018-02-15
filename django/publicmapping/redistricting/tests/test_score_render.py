from base import BaseTestCase

import os
from redistricting.models import (Geolevel, Geounit, Plan, ScorePanel,
                                  ScoreDisplay, ScoreFunction, ScoreArgument)
from django.conf import settings


class ScoreRenderTestCase(BaseTestCase):
    fixtures = [
        'redistricting_testdata.json', 'redistricting_testdata_geolevel2.json',
        'redistricting_testdata_scoring.json'
    ]

    def setUp(self):
        super(ScoreRenderTestCase, self).setUp()
        self.geolevel = Geolevel.objects.get(name='middle level')
        self.geounits = list(
            Geounit.objects.filter(geolevel=self.geolevel).order_by('id'))

    def tearDown(self):
        self.geolevel = None
        self.geounits = None
        super(ScoreRenderTestCase, self).tearDown()

    def test_panelrender_plan(self):
        geolevelid = self.geolevel.id
        geounits = self.geounits

        dist1ids = geounits[0:3] + geounits[9:12]
        dist2ids = geounits[6:9] + geounits[15:18]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               geolevelid, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids,
                               geolevelid, self.plan.version)

        dist1ids = geounits[3:6] + geounits[12:15]
        dist2ids = geounits[9:12] + geounits[18:21]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan2.add_geounits(1, dist1ids, geolevelid, self.plan2.version)
        self.plan2.add_geounits(1, dist2ids, geolevelid, self.plan2.version)

        panels = ScorePanel.objects.filter(type='plan')

        for panel in panels:
            tplfile = settings.TEMPLATES[0]['DIRS'][0] + '/' + panel.template
            template = open(tplfile, 'w')
            template.write(
                '{% for planscore in planscores %}{{planscore.plan.name}}:' +
                '{{ planscore.score|safe }}{% endfor %}')
            template.close()

            panel.is_ascending = False
            markup = panel.render([self.plan, self.plan2])
            expected = 'testPlan:<span>9</span>' + \
                'testPlan2:<span>9</span>' + \
                'testPlan:18.18%' + \
                'testPlan2:10.64%'

            self.assertEqual(expected, markup,
                             'The markup was incorrect. (e:"%s", a:"%s")' %
                             (expected, markup))

            os.remove(tplfile)

    def test_panelrender_district(self):
        geolevelid = self.geolevel.id
        geounits = self.geounits

        dist1ids = geounits[0:3] + geounits[9:12]
        dist2ids = geounits[6:9] + geounits[15:18]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               geolevelid, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids,
                               geolevelid, self.plan.version)

        panels = ScorePanel.objects.filter(type='district')

        for panel in panels:
            districts = self.plan.get_districts_at_version(
                self.plan.version, include_geom=False)

            tplfile = settings.TEMPLATES[0]['DIRS'][0] + '/' + panel.template
            template = open(tplfile, 'w')
            template.write('{% for dscore in districtscores %}' +
                           '{{dscore.district.long_label }}:' +
                           '{% for score in dscore.scores %}' +
                           '{{ score.score|safe }}{% endfor %}{% endfor %}')
            template.close()

            markup = panel.render(districts)
            expected = ('District 1:86.83%<img class="yes-contiguous" '
                        'src="/static/images/icon-check.png">'
                        'District 2:86.83%<img class="yes-contiguous" '
                        'src="/static/images/icon-check.png">'
                        'Unassigned:0.00%<img class="yes-contiguous" '
                        'src="/static/images/icon-check.png">')
            self.assertEqual(
                expected, markup,
                'The markup for districts was incorrect. (e:"%s", a:"%s")' %
                (expected, markup))

            os.remove(tplfile)

    def test_display_render_page(self):
        geolevelid = self.geolevel.id
        geounits = self.geounits

        dist1ids = geounits[0:3] + geounits[9:12]
        dist2ids = geounits[6:9] + geounits[15:18]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               geolevelid, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids,
                               geolevelid, self.plan.version)
        self.plan.is_valid = True
        self.plan.save()

        dist1ids = geounits[3:6] + geounits[12:15]
        dist2ids = geounits[9:12] + geounits[18:21]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan2.add_geounits(1, dist1ids, geolevelid, self.plan2.version)
        self.plan2.add_geounits(1, dist2ids, geolevelid, self.plan2.version)
        self.plan2.is_valid = True
        self.plan2.save()

        display = ScoreDisplay.objects.filter(is_page=True)[0]
        plans = list(Plan.objects.filter(is_valid=True))

        panel = display.scorepanel_set.all()[0]
        tplfile = settings.TEMPLATES[0]['DIRS'][0] + '/' + panel.template
        template = open(tplfile, 'w')
        template.write(
            '{% for planscore in planscores %}{{planscore.plan.name}}:' +
            '{{ planscore.score|safe }}{% endfor %}')
        template.close()

        markup = display.render(plans)

        expected = 'testPlan2:10.64%' + \
            'testPlan:18.18%' + \
            'testPlan:<span>9</span>' + \
            'testPlan2:<span>9</span>'
        self.assertEqual(expected, markup,
                         'The markup was incorrect. (e:"%s", a:"%s")' %
                         (expected, markup))

        os.remove(tplfile)

    def test_display_render_div(self):
        geolevelid = self.geolevel.id
        geounits = self.geounits

        dist1ids = geounits[0:3] + geounits[9:12]
        dist2ids = geounits[6:9] + geounits[15:18]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               geolevelid, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids,
                               geolevelid, self.plan.version)

        display = ScoreDisplay.objects.filter(is_page=False)[0]

        panel = display.scorepanel_set.all()[0]
        tplfile = settings.TEMPLATES[0]['DIRS'][0] + '/' + panel.template
        template = open(tplfile, 'w')
        template.write('{% for dscore in districtscores %}' +
                       '{{dscore.district.long_label }}:' +
                       '{% for score in dscore.scores %}' +
                       '{{ score.score|safe }}{% endfor %}{% endfor %}')
        template.close()

        markup = display.render(self.plan)
        expected = ('District 1:86.83%<img class="yes-contiguous" '
                    'src="/static/images/icon-check.png">'
                    'District 2:86.83%<img class="yes-contiguous" '
                    'src="/static/images/icon-check.png">'
                    'Unassigned:0.00%<img class="yes-contiguous" '
                    'src="/static/images/icon-check.png">')
        self.assertEqual(expected, markup,
                         'The markup was incorrect. (e:"%s", a:"%s")' %
                         (expected, markup))

        markup = display.render(
            self.plan.get_districts_at_version(
                self.plan.version, include_geom=False))

        expected = ('District 1:86.83%<img class="yes-contiguous" '
                    'src="/static/images/icon-check.png">'
                    'District 2:86.83%<img class="yes-contiguous" '
                    'src="/static/images/icon-check.png">'
                    'Unassigned:0.00%<img class="yes-contiguous" '
                    'src="/static/images/icon-check.png">')
        self.assertEqual(expected, markup,
                         'The markup was incorrect. (e:"%s", a:"%s")' %
                         (expected, markup))

        os.remove(tplfile)

    def test_scoredisplay_with_overrides(self):
        # Get a ScoreDisplay
        display = ScoreDisplay.objects.get(title='TestScoreDisplay')
        display.is_page = False

        # Make up a ScorePanel - don't save it
        panel = ScorePanel(
            title="My Fresh Panel",
            type="district",
            template="sp_template2.html")
        # Create two functions, one with an arg and one without
        function = ScoreFunction(
            calculator="redistricting.calculators.SumValues",
            name="My Fresh Calc",
            is_planscore=False)

        arg1 = ScoreArgument(argument="value1", value="5", type="literal")
        arg2 = ScoreArgument(
            argument="value2", value="TestSubject", type="subject")

        tplfile = settings.TEMPLATES[0]['DIRS'][0] + '/' + panel.template
        template = open(tplfile, 'w')
        template.write('{% for dscore in districtscores %}' +
                       '{{dscore.district.long_label }}:' +
                       '{% for score in dscore.scores %}' +
                       '{{ score.score|safe }}{% endfor %}{% endfor %}')
        template.close()

        # Render the ScoreDisplay
        components = [(panel, [(function, arg1, arg2)])]
        district_result = display.render(
            [self.district1], components=components)
        expected = 'District 1:<span>5</span>'
        self.assertEqual(
            expected, district_result,
            'Didn\'t get expected result when overriding district\'s display '
            + '(e:"%s", a:"%s")' % (expected, district_result))

        os.remove(tplfile)

        # Add some districts to our plan
        geolevelid = self.geolevel.id
        geounits = self.geounits

        dist1ids = geounits[0:3] + geounits[9:12]
        dist2ids = geounits[6:9] + geounits[15:18]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               geolevelid, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids,
                               geolevelid, self.plan.version)

        # Set up the elements to work for a plan
        panel.type = 'plan'
        panel.template = 'sp_template1.html'
        function.is_planscore = True
        components = [(panel, [(function, arg1, arg2)])]

        tplfile = settings.TEMPLATES[0]['DIRS'][0] + '/' + panel.template
        template = open(tplfile, 'w')
        template.write(
            '{% for planscore in planscores %}{{planscore.plan.name}}:' +
            '{{ planscore.score|safe }}{% endfor %}')
        template.close()

        # Check the result
        plan_result = display.render(self.plan, components=components)
        expected = "testPlan:[u'<span>24</span>']"
        self.assertEqual(
            expected, plan_result,
            'Didn\'t get expected result when overriding plan\'s display' +
            ' (e: "%s", a:"%s")' % (expected, plan_result))

        os.remove(tplfile)

    def test_splitcounter_display(self):
        # Create a plan with two districts - one crosses both 5 and 8
        p1 = self.plan
        d1a_id = 1
        dist1ids = self.geounits[20:23] + self.geounits[29:32] + \
            self.geounits[38:41] + self.geounits[47:50] + \
            self.geounits[56:59]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        p1.add_geounits(d1a_id, dist1ids, self.geolevel.id, p1.version)

        # the other is entirely within 5
        d2a_id = 5
        dist2ids = [self.geounits[32], self.geounits[41], self.geounits[50]]
        dist2ids = map(lambda x: str(x.id), dist2ids)
        p1.add_geounits(d2a_id, dist2ids, self.geolevel.id, p1.version)

        # Get a ScoreDisplay and components to render
        display = ScoreDisplay.objects.get(title='TestScoreDisplay')
        display.is_page = False
        display.save()

        panel = ScorePanel(
            title="Splits Report",
            type="plan",
            template="sp_template1.html",
            cssclass="split_panel")
        function = ScoreFunction(
            calculator="redistricting.calculators.SplitCounter",
            name="splits_test",
            is_planscore=True)
        geolevel = self.plan.legislative_body.get_geolevels()[0]
        arg1 = ScoreArgument(
            argument="boundary_id",
            value="geolevel.%d" % geolevel.id,
            type="literal")

        components = [(panel, [(function, arg1)])]

        expected_result = (
            '%s:[u\'<div class="split_report"><div>Total '
            'districts which split a biggest level short label: 2</div>'
            '<div>Total number of splits: 7</div>'
            '<div class="table_container"><table class="report"><thead><tr>'
            '<th>Testplan</th><th>Biggest level short label</th></tr></thead>'
            '<tbody><tr><td>District 1</td><td>Unit 1-0</td></tr><tr>'
            '<td>District 1</td><td>Unit 1-1</td></tr><tr><td>District 1</td>'
            '<td>Unit 1-3</td></tr><tr><td>District 1</td><td>Unit 1-4</td>'
            '</tr><tr><td>District 1</td><td>Unit 1-6</td></tr><tr>'
            '<td>District 1</td><td>Unit 1-7</td></tr><tr><td>District 5</td>'
            '<td>Unit 1-4</td></tr></tbody></table></div></div>\']') % p1.name

        tplfile = settings.TEMPLATES[0]['DIRS'][0] + '/' + panel.template
        template = open(tplfile, 'w')
        template.write(
            '{% for planscore in planscores %}{{planscore.plan.name}}:' +
            '{{ planscore.score|safe }}{% endfor %}')
        template.close()

        # Check the result
        plan_result = display.render(p1, components=components)

        self.assertEqual(expected_result, plan_result,
                         "Didn't get expected result when rendering " +
                         "SplitCounter:\ne:%s\na:%s" %
                         (expected_result, plan_result))

        os.remove(tplfile)
