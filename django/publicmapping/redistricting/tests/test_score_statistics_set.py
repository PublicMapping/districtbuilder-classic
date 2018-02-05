from base import BaseTestCase

from django.contrib.auth.models import User

from redistricting.models import *


class StatisticsSetTestCase(BaseTestCase):
    fixtures = [
        'redistricting_testdata.json',
        'redistricting_testdata_geolevel2.json',
        'redistricting_statisticssets.json',
    ]

    def setUp(self):
        super(StatisticsSetTestCase, self).setUp()

        display = ScoreDisplay.objects.get(title='Demographics')
        summary = ScorePanel.objects.get(title='Plan Summary')
        demographics = ScorePanel.objects.get(title='Demographics')

        display.scorepanel_set.add(summary)
        display.scorepanel_set.add(demographics)

        functions = ScoreFunction.objects.filter(
            name__in=('Voting Age Population',
                      'Hispanic voting-age population', 'Total Population'))
        demographics.score_functions = functions.all()
        demographics.save()

        self.functions = functions.all()
        self.demographics = demographics
        self.summary = summary
        self.display = display

    def tearDown(self):
        self.display.delete()
        super(StatisticsSetTestCase, self).tearDown()

    def test_copy_scoredisplay(self):
        user = User(username="Stats User")
        user.save()
        # We'll set the owner but it's overwritten
        copy = ScoreDisplay(owner=user)
        copy = copy.copy_from(display=self.display)
        self.assertEqual(
            "%s copy" % self.display.__unicode__(), copy.__unicode__(),
            "ScoreDisplay title copied, allowing same name for user more than once"
        )
        self.assertEqual(
            len(copy.scorepanel_set.all()),
            len(self.display.scorepanel_set.all()),
            "Copied scoredisplay has wrong number of panels attached")
        self.assertNotEqual(
            user, copy.owner,
            "ScoreDisplay copied owner rather than copying owner from ScoreDisplay"
        )

        copy = ScoreDisplay(owner=user)
        copy = copy.copy_from(display=self.display, owner=user)
        self.assertEqual(self.display.__unicode__(), copy.__unicode__(),
                         "Title of scoredisplay not copied")
        self.assertEqual(
            len(copy.scorepanel_set.all()),
            len(self.display.scorepanel_set.all()),
            "Copied scoredisplay has wrong number of panels attached")

        vap = ScoreFunction.objects.get(name="Voting Age Population")
        copy = copy.copy_from(
            display=self.display,
            functions=[unicode(str(vap.id))],
            title="Copied from")
        self.assertEqual(
            len(copy.scorepanel_set.all()),
            len(self.display.scorepanel_set.all()),
            "Copied scoredisplay has wrong number of panels attached")

        new_demo = ScoreDisplay.objects.get(title="Copied from")
        panels_tested = 0
        for panel in new_demo.scorepanel_set.all():
            if panel.title == "Plan Summary":
                self.assertEqual(
                    len(self.summary.score_functions.all()),
                    len(panel.score_functions.all()),
                    "Copied plan summary panel didn't have correct number of functions"
                )
                panels_tested += 1
            elif panel.title == "Demographics":
                self.assertEqual(1, len(
                    panel.score_functions.all()
                ), "Copied demographics panel didn't have correct number of functions"
                                 )
                panels_tested += 1
        self.assertEqual(2, panels_tested,
                         "Copied scoredisplay didn't have both panels needed")

        # Let's try just updating those score functions
        new_copy = ScoreDisplay(owner=user)
        new_copy = copy.copy_from(display=copy, functions=self.functions)
        self.assertEqual(copy.title, new_copy.title,
                         "Title of scoredisplay not copied")
        self.assertEqual(copy.id, new_copy.id,
                         "Scorefunctions not added to current display")
        self.assertEqual(
            len(copy.scorepanel_set.all()), len(new_copy.scorepanel_set.all()),
            "Copied scoredisplay has wrong number of panels attached")

        panels_tested = 0
        for panel in new_copy.scorepanel_set.all():
            if panel.title == "Plan Summary":
                self.assertEqual(
                    len(self.summary.score_functions.all()),
                    len(panel.score_functions.all()),
                    "Copied plan summary panel didn't have correct number of functions"
                )
                panels_tested += 1
            elif panel.title == "Demographics":
                self.assertEqual(
                    len(self.functions), len(panel.score_functions.all()),
                    "Copied demographics panel didn't have correct number of functions; e:%d,a:%d"
                    % (3, len(panel.score_functions.all())))
                panels_tested += 1
        self.assertEqual(2, panels_tested,
                         "Copied scoredisplay didn't have both panels needed")
