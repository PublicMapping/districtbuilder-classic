from base import BaseTestCase

from redistricting.models import (Geolevel, Geounit, ScoreFunction,
                                  ComputedDistrictScore, ComputedPlanScore)


class ComputedScoresTestCase(BaseTestCase):
    def test_district1(self):
        geolevel = Geolevel.objects.get(name='middle level')
        geounits = list(
            Geounit.objects.filter(geolevel=geolevel).order_by('id'))

        dist1ids = geounits[0:3] + geounits[9:12]
        dist2ids = geounits[6:9] + geounits[15:18]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               geolevel.id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids,
                               geolevel.id, self.plan.version)

        function = ScoreFunction.objects.get(
            calculator__endswith='SumValues', is_planscore=False)
        numscores = ComputedDistrictScore.objects.all().count()

        self.assertEqual(
            0, numscores,
            'The number of computed district scores is incorrect. (e:0, a:%d)'
            % numscores)

        district1 = self.plan.district_set.filter(
            district_id=self.district1.district_id,
            version=self.plan.version - 1)[0]
        expected = function.score(district1)

        score = ComputedDistrictScore.compute(function, district1)

        self.assertEqual(
            expected['value'], score['value'],
            'The score computed is incorrect. (e:%0.1f, a:%0.1f)' % (
                expected['value'],
                score['value'],
            ))

        numscores = ComputedDistrictScore.objects.all().count()

        self.assertEqual(
            1, numscores,
            'The number of computed district scores is incorrect. (e:1, a:%d)'
            % numscores)

        dist1ids = geounits[3:6]
        dist1ids = map(lambda x: str(x.id), dist1ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               geolevel.id, self.plan.version)

        district1 = self.plan.district_set.filter(
            district_id=self.district1.district_id,
            version=self.plan.version)[0]
        expected = function.score(district1)

        score = ComputedDistrictScore.compute(function, district1)

        self.assertEqual(
            expected['value'], score['value'],
            'The score computed is incorrect. (e:%0.1f, a:%0.1f)' % (
                expected['value'],
                score['value'],
            ))

        numscores = ComputedDistrictScore.objects.all().count()

        self.assertEqual(
            2, numscores,
            'The number of computed district scores is incorrect. (e:2, a:%d)'
            % numscores)

    def test_plan1(self):
        geolevel = Geolevel.objects.get(name='middle level')
        geounits = list(
            Geounit.objects.filter(geolevel=geolevel).order_by('id'))

        dist1ids = geounits[0:3] + geounits[9:12]
        dist2ids = geounits[6:9] + geounits[15:18]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               geolevel.id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids,
                               geolevel.id, self.plan.version)

        function = ScoreFunction.objects.get(
            calculator__endswith='SumValues', is_planscore=True)
        numscores = ComputedPlanScore.objects.all().count()

        self.assertEqual(
            0, numscores,
            'The number of computed plan scores is incorrect. (e:0, a:%d)' %
            numscores)

        score = ComputedPlanScore.compute(function, self.plan)

        self.assertEqual(9, score['value'],
                         'The score computed is incorrect. (e:9.0, a:%0.1f)' %
                         score['value'])

        numscores = ComputedPlanScore.objects.all().count()

        self.assertEqual(
            1, numscores,
            'The number of computed plan scores is incorrect. (e:1, a:%d)' %
            numscores)

        dist1ids = geounits[3:6]
        dist1ids = map(lambda x: str(x.id), dist1ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               geolevel.id, self.plan.version)

        score = ComputedPlanScore.compute(function, self.plan)

        self.assertEqual(9, score['value'],
                         'The score computed is incorrect. (e:9.0, a:%0.1f)' %
                         score['value'])

        numscores = ComputedPlanScore.objects.all().count()

        self.assertEqual(
            2, numscores,
            'The number of computed plan scores is incorrect. (e:2, a:%d)' %
            numscores)
