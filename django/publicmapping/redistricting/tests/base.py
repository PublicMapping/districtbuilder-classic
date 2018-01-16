from django.test import TestCase
from django.contrib.auth.models import User

from redistricting.models import District, Plan


class BaseTestCase(TestCase):
    """
    Only contains setUp and tearDown, which are shared among all other
    TestCases
    """
    fixtures = [
        'redistricting_testdata.json', 'redistricting_testdata_geolevel2.json',
        'redistricting_testdata_geolevel3.json',
        'redistricting_testdata_scoring.json'
    ]

    def setUp(self):
        """
        Setup the general tests. This fabricates a set of data in the
        test database for use later.
        """
        # Get a test Plan
        self.plan = Plan.objects.get(name='testPlan')
        self.plan2 = Plan.objects.get(name='testPlan2')

        for d in District.objects.all():
            d.simplify()

        # Get the test Districts
        self.district1 = District.objects.get(
            long_label='District 1', plan=self.plan)
        self.district2 = District.objects.get(
            long_label='District 2', plan=self.plan)

        # Get a test User
        self.username = 'test_user'
        self.password = 'secret'
        self.user = User.objects.get(username=self.username)

    def tearDown(self):
        self.plan = None
        self.plan2 = None
        self.district1 = None
        self.district2 = None
        self.username = None
        self.password = None
        self.user = None
