from base import BaseTestCase

from django.db.models import Sum, Min, Max
from django.test.client import Client
from django.contrib.auth.models import User
from django.contrib.gis.db.models import Collect

from redistricting.models import *
from redistricting.tasks import *
from redistricting.calculators import *
from redistricting.reportcalculators import *
from redistricting.config import *

from django.conf import settings


class PlanTestCase(BaseTestCase):
    """
    Unit tests to test Plan operations
    """

    fixtures = [
        'redistricting_testdata.json', 'redistricting_testdata_geolevel2.json',
        'redistricting_testdata_geolevel3.json'
    ]

    def setUp(self):
        super(PlanTestCase, self).setUp()
        self.geolevel = Geolevel.objects.get(name='middle level')
        self.geolevels = Geolevel.objects.all().order_by('-id')

        self.geounits = {}
        for gl in self.geolevels:
            self.geounits[gl.id] = list(
                Geounit.objects.filter(geolevel=gl).order_by('id'))

    def tearDown(self):
        self.geolevel = None
        self.geolevels = None
        self.geounits = None
        try:
            super(PlanTestCase, self).tearDown()
        except:
            import traceback
            print(traceback.format_exc())
            print('Couldn\'t tear down')

    def test_district_id_increment(self):
        """
        Test the logic for the automatically generated district_id
        """
        # Note: district_id is set to 0 here, because otherwise, the
        # auto-increment code does not get called.
        # It may be best to revisit how district_id is used throughout the app,
        # and to not allow for it to be set,
        # since it should be auto-generated.
        d3 = District(long_label='District 3', version=0)
        d3.plan = self.plan

        p1 = Polygon(((1, 1), (1, 1), (1, 1), (1, 1)))
        mp1 = MultiPolygon(p1)
        d3.geom = mp1

        d3.simplify()
        latest = d3.district_id

        d4 = District(long_label='District 4', version=0)
        d4.plan = self.plan

        p2 = Polygon(((0, 0), (0, 1), (1, 1), (0, 0)))
        mp2 = MultiPolygon(p1)
        d4.geom = mp2

        d4.simplify()
        incremented = d4.district_id
        self.assertEqual(
            latest + 1, incremented,
            'New district did not have an id greater than the previous district. (e:%d, a:%d)'
            % (latest + 1, incremented))

    def test_add_to_plan(self):
        """
        Test the logic for adding geounits to a district.
        """
        district = self.district1
        districtid = district.district_id

        geounitids = [str(self.geounits[self.geolevel.id][0].id)]

        self.plan.add_geounits(districtid, geounitids, self.geolevel.id,
                               self.plan.version)
        district = District.objects.get(
            plan=self.plan, district_id=districtid, version=1)

        self.assertEqual(district.geom.area,
                         self.geounits[self.geolevel.id][0].geom.area,
                         "Geometry area for added district doesn't match")
        self.assertEqual(district.geom.extent,
                         self.geounits[self.geolevel.id][0].geom.extent,
                         "Geometry area for added district doesn't match")
        self.assertEqual(district.geom.length,
                         self.geounits[self.geolevel.id][0].geom.length,
                         "Geometry area for added district doesn't match")

    def test_unassigned(self):
        """
        Test the logic for an unassigned district.
        """
        unassigned = District.objects.filter(
            long_label='Unassigned', plan=self.plan)
        self.assertEqual(
            1, unassigned.count(),
            'No Unassigned district on plan. (e:1, a:%d)' % unassigned.count())

    def test_copyplan(self):
        """
        Test the logic for copying plans.
        """
        geounitids = [str(self.geounits[self.geolevel.id][0].id)]

        this_id = self.plan.id
        # Add geounits to plan
        self.plan.add_geounits(self.district1.district_id, geounitids,
                               self.geolevel.id, self.plan.version)

        # Login
        client = Client()
        client.login(username=self.username, password=self.password)

        # Issue copy command
        copyname = 'MyTestCopy'
        response = client.post('/districtmapping/plan/%d/copy/' % self.plan.id,
                               {
                                   'name': copyname
                               })
        self.assertEqual(200, response.status_code,
                         'Copy handler didn\'t return 200:' + str(response))

        # Ensure copy exists
        copyplan = Plan.objects.get(name=copyname)
        self.assertNotEqual(copyplan, None, 'Copied plan doesn\'t exist')

        # Ensure districts are the same between plans
        numdistricts = len(
            self.plan.get_districts_at_version(self.plan.version))
        numdistrictscopy = len(
            copyplan.get_districts_at_version(copyplan.version))
        self.assertEqual(
            numdistricts, numdistrictscopy,
            'Districts between original and copy are different. (e:%d, a:%d)' %
            (numdistricts, numdistrictscopy))

        # Ensure geounits are the same between plans
        numunits = len(
            Plan.objects.get(pk=self.plan.id).get_base_geounits(0.1))
        numunitscopy = len(
            Plan.objects.get(pk=copyplan.id).get_base_geounits(0.1))
        self.assertEqual(numunits, numunitscopy,
                         'Geounits between original and copy are different')

    def test_district_locking(self):
        """
        Test the logic for locking/unlocking a district.
        """
        geounitids1 = [str(self.geounits[self.geolevel.id][0].id)]
        geounitids2 = [str(self.geounits[self.geolevel.id][-1].id)]

        client = Client()

        # Create a second user, and try to lock a district not belonging to
        # that user
        username2 = 'test_user2'
        user2 = User(username=username2)
        user2.set_password(self.password)
        user2.save()
        client.login(username=username2, password=self.password)

        # Issue lock command when not logged in
        response = client.post('/districtmapping/plan/%d/district/%d/lock/' %
                               (self.plan.id, self.district1.district_id), {
                                   'lock': True,
                                   'version': self.plan.version
                               })
        self.assertEqual(
            403, response.status_code,
            'Non-owner was able to lock district.' + str(response))

        # Login
        client.login(username=self.username, password=self.password)

        self.plan.add_geounits(self.district1.district_id, geounitids1,
                               self.geolevel.id, self.plan.version)
        self.district1 = max(
            District.objects.filter(
                plan=self.plan, district_id=self.district1.district_id),
            key=lambda d: d.version)

        # Issue lock command
        response = client.post('/districtmapping/plan/%d/district/%d/lock/' %
                               (self.plan.id, self.district1.district_id), {
                                   'lock': True,
                                   'version': self.plan.version
                               })
        self.assertEqual(200, response.status_code,
                         'Lock handler didn\'t return 200:' + str(response))

        # Ensure lock exists
        self.district1 = District.objects.get(pk=self.district1.id)
        self.assertTrue(self.district1.is_locked,
                        'District wasn\'t locked.' + str(response))

        prelock_numunits = len(self.district1.get_base_geounits(0.1))

        # Try adding geounits to the locked district (not allowed)
        self.plan.add_geounits(self.district2.district_id, geounitids1,
                               self.geolevel.id, self.plan.version)
        self.assertRaises(
            District.DoesNotExist,
            District.objects.get,
            pk=self.district2.id,
            version=self.plan.version)

        self.district1 = max(
            District.objects.filter(
                plan=self.plan, district_id=self.district1.district_id),
            key=lambda d: d.version)
        numunits = len(self.district1.get_base_geounits(0.1))
        self.assertEqual(
            prelock_numunits, numunits,
            'Geounits were added to a locked district. (e:%d, a:%d)' % (
                prelock_numunits,
                numunits,
            ))

        # Issue unlock command
        response = client.post('/districtmapping/plan/%d/district/%d/lock/' %
                               (self.plan.id, self.district1.district_id), {
                                   'lock': False,
                                   'version': self.plan.version
                               })
        self.assertEqual(200, response.status_code,
                         'Lock handler didn\'t return 200:' + str(response))

        # Ensure lock has been removed
        self.district1 = max(
            District.objects.filter(
                plan=self.plan, district_id=self.district1.district_id),
            key=lambda d: d.version)
        self.assertFalse(self.district1.is_locked,
                         'District wasn\'t unlocked.' + str(response))

        # Add geounits to the plan
        old_geom = self.district1.geom
        self.plan.add_geounits(self.district1.district_id, geounitids2,
                               self.geolevel.id, self.plan.version)
        self.district1 = max(
            District.objects.filter(
                plan=self.plan, district_id=self.district1.district_id),
            key=lambda d: d.version)
        new_geom = self.district1.geom
        self.assertNotEqual(
            old_geom, new_geom,
            "Geounits could not be added to an unlocked district")

    def test_district_locking2(self):
        """
        Test the case where adding a partially selected geometry (due to
        locking) may add the entire geometry's aggregate value.
        """
        geounits = list(
            Geounit.objects.filter(geolevel=self.geolevel).order_by('id'))
        dist1ids = geounits[0:3] + geounits[9:12]
        dist2ids = geounits[18:21] + geounits[27:30] + geounits[36:39]

        dist1ids = map(lambda x: str(x.id), dist1ids)
        dist2ids = map(lambda x: str(x.id), dist2ids)

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevel.id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids,
                               self.geolevel.id, self.plan.version)

        district1 = max(
            District.objects.filter(
                plan=self.plan, district_id=self.district1.district_id),
            key=lambda d: d.version)
        district1units = district1.get_base_geounits(0.1)

        self.assertEqual(54, len(district1units),
                         'Incorrect number of geounits returned in dist1: %d' %
                         len(district1units))

        district2 = max(
            District.objects.filter(
                plan=self.plan, district_id=self.district2.district_id),
            key=lambda d: d.version)
        district2units = district2.get_base_geounits(0.1)

        self.assertEqual(81, len(district2units),
                         'Incorrect number of geounits returned in dist2: %d' %
                         len(district2units))

        geolevel = Geolevel.objects.get(name='biggest level')
        geounits = list(
            Geounit.objects.filter(geolevel=geolevel).order_by('id'))
        dist3ids = geounits[1:3] + geounits[4:6] + geounits[7:9]

        dist3ids = map(lambda x: str(x.id), dist3ids)

        self.plan.add_geounits(self.district2.district_id + 1, dist3ids,
                               geolevel.id, self.plan.version)

        district3 = max(
            District.objects.filter(
                plan=self.plan, district_id=self.district2.district_id + 1),
            key=lambda d: d.version)
        district3units = district3.get_base_geounits(0.1)

        self.assertEqual(486, len(district3units),
                         'Incorrect number of geounits returned in dist3: %d' %
                         len(district3units))

        # Plan looks like this now:
        #
        #  *-----------*-----------*-----------*
        #  |           |                       |
        #  |           |                       |
        #  |           |                       |
        #  |           |                       |
        #  |           |                       |
        #  *           *           *           *
        #  |           |                       |
        #  |           |                       |
        #  +-----------+      District 3       |
        #  |           |                       |
        #  | District 2|                       |
        #  *           *           *           *
        #  |           |                       |
        #  +-----------+                       |
        #  |           |                       |
        #  | District 1|                       |
        #  |           |                       |
        #  *-----------*-----------*-----------*

        # Try locking District 2, selecting the large block that totally
        # contains District 1, and add it to District 3
        district2.is_locked = True
        district2.save()

        subject = Subject.objects.get(name='TestSubject')

        districtpre_computed = ComputedCharacteristic.objects.filter(
            district__in=[district1, district2, district3],
            subject=subject).order_by('district').values_list(
                'number', flat=True)
        presum = 0
        for pre in districtpre_computed:
            presum += pre

        self.plan.add_geounits(district3.district_id, [str(geounits[0].id)],
                               self.geolevels[0].id, self.plan.version)

        district1 = max(
            District.objects.filter(
                plan=self.plan, district_id=self.district1.district_id),
            key=lambda d: d.version)
        district2 = max(
            District.objects.filter(
                plan=self.plan, district_id=self.district2.district_id),
            key=lambda d: d.version)
        district3 = max(
            District.objects.filter(
                plan=self.plan, district_id=district3.district_id),
            key=lambda d: d.version)

        districtpost_computed = ComputedCharacteristic.objects.filter(
            district__in=[district1, district2, district3],
            subject=subject).order_by('district').values_list(
                'number', flat=True)
        postsum = 0
        for post in districtpost_computed:
            postsum += post

        self.assertEqual(
            presum, postsum,
            'The computed districts of the new plan do not match the computed districts of the old plan, when only reassigning geography. (e:%0.2f,a:%0.2f)'
            % (presum, postsum))

    def test_get_base_geounits(self):
        """
        Test getting base geounits
        """
        geounits = self.geounits[self.geolevels[0].id]

        dist1ids = [str(geounits[0].id)]
        dist2ids = [str(geounits[1].id)]

        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevels[0].id, self.plan.version)
        self.plan.add_geounits(self.district2.district_id, dist2ids,
                               self.geolevels[0].id, self.plan.version)

        # Test getting the base geounits for a district
        district1 = max(
            District.objects.filter(
                plan=self.plan, district_id=self.district1.district_id),
            key=lambda d: d.version)
        district1units = district1.get_base_geounits(0.1)
        self.assertEqual(81, len(district1units),
                         'Incorrect number of geounits returned in dist1: %d' %
                         len(district1units))

        district2 = max(
            District.objects.filter(
                plan=self.plan, district_id=self.district2.district_id),
            key=lambda d: d.version)
        district2units = district2.get_base_geounits(0.1)
        self.assertEqual(81, len(district2units),
                         'Incorrect number of geounits returned in dist2: %d' %
                         len(district2units))

        # Test getting the base geounits for a plan
        plan = Plan.objects.get(pk=self.plan.id)
        planunits = plan.get_base_geounits(0.1)
        self.assertEqual(162, len(planunits),
                         'Incorrect number of geounits returned in plan: %d' %
                         len(planunits))

        # Test sorting the units by geounit id
        planunits.sort(key=lambda unit: unit[0])
        lastid = 0
        for unit in planunits:
            self.assertTrue(unit[0] >= lastid,
                            'Not in order: %d < %d' % (unit[0], lastid))
            lastid = unit[0]

        # Test getting assigned geounits
        assigned = plan.get_assigned_geounits(0.1)
        self.assertEqual(162, len(assigned),
                         'Incorrect number of assigned geounits returned: %d' %
                         len(assigned))

        # Test getting unassigned geounits
        unassigned = plan.get_unassigned_geounits(0.1)
        self.assertEqual(729 - 162, len(unassigned),
                         'Incorrect number of unassigned geounits returned: %d'
                         % len(unassigned))

    def test_plan2index(self):
        """
        Test exporting a plan
        """
        geounits = self.geounits[self.geolevels[0].id]
        dist1ids = [str(geounits[0].id)]
        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevels[0].id, self.plan.version)

        archive = DistrictIndexFile.plan2index(self.plan.id)
        zin = zipfile.ZipFile(archive, "r")
        strz = zin.read(self.plan.name + ".csv")
        zin.close()
        os.remove(archive)
        self.assertEqual(1053, len(strz),
                         'Index file was the wrong length: %d' % len(strz))

    def test_community_plan2index(self):
        """
        Test exporting a community plan
        """
        geounits = self.geounits[self.geolevels[0].id]
        dist1ids = [str(geounits[0].id)]
        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevels[0].id, self.plan.version)
        plan = Plan.objects.get(pk=self.plan.id)

        # extract a district to manipulate
        district = None
        for d in plan.get_districts_at_version(
                plan.version, include_geom=False):
            if d.district_id > 0:
                district = d

        # make the plan a community
        plan.legislative_body.is_community = True
        plan.legislative_body.save()

        # add label
        district.long_label = 'My Test Community'
        district.save()

        # add comment
        ct = ContentType.objects.get(
            app_label='redistricting', model='district')
        comment = Comment(
            object_pk=district.id,
            content_type=ct,
            site_id=1,
            user_name=self.username,
            user_email='',
            comment='Test comment: a, b, c || ...')
        comment.save()

        # add types
        Tag.objects.add_tag(district, 'type=%s' % 'type1')
        Tag.objects.add_tag(district, 'type=%s' % 'type2')

        # save the plan
        plan.save()

        # export
        archive = DistrictIndexFile.plan2index(plan.id)
        zin = zipfile.ZipFile(archive, "r")
        strz = zin.read(plan.name + ".csv")
        zin.close()
        os.remove(archive)
        self.assertEqual(5994, len(strz),
                         'Index file was the wrong length: %d' % len(strz))

    def test_sorted_district_list(self):
        """
        Test the sorted district list for reporting
        """
        geounits = self.geounits[self.geolevels[0].id]
        dist1ids = [str(geounits[0].id)]
        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               self.geolevels[0].id, self.plan.version)
        plan = Plan.objects.get(pk=self.plan.id)

        mapping = plan.get_base_geounits()
        mapping.sort(key=lambda unit: unit[0])

        geolevel = plan.legislative_body.get_base_geolevel()
        geounits = Geounit.objects.filter(geolevel=geolevel)
        max_and_min = geounits.aggregate(Min('id'), Max('id'))
        min_id = int(max_and_min['id__min'])
        max_id = int(max_and_min['id__max'])

        sorted_district_list = list()
        row = None
        if len(mapping) > 0:
            row = mapping.pop(0)
        for i in range(min_id, max_id + 1):
            if row and row[0] == i:
                district_id = row[2]
                row = None
                if len(mapping) > 0:
                    row = mapping.pop(0)
            else:
                district_id = 'NA'
            sorted_district_list.append(district_id)

        self.assertEqual(729, len(sorted_district_list),
                         'Sorted district list was the wrong length: %d' %
                         len(sorted_district_list))

    def test_reaggregation(self):
        """
        Test plan reaggregation
        """
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]
        subject = Subject.objects.get(name='TestSubject')

        # Populate district 1
        dist1ids = geounits[0:3] + geounits[9:12] + geounits[18:21]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               geolevelid, self.plan.version)

        # Populate district 2
        dist2ids = geounits[10:13] + geounits[19:22] + geounits[28:31]
        dist2ids = map(lambda x: str(x.id), dist2ids)
        self.plan.add_geounits(self.district2.district_id, dist2ids,
                               geolevelid, self.plan.version)

        # Helper for getting the value of a computed characteristic
        def get_cc_val(district):
            d_id = district.district_id
            district = max(
                District.objects.filter(plan=self.plan, district_id=d_id),
                key=lambda d: d.version)
            return ComputedCharacteristic.objects.get(
                district=district, subject=subject).number

        # Ensure starting values are correct
        self.assertEqual(3, get_cc_val(self.district1),
                         "District1 started with wrong value")
        self.assertEqual(18, get_cc_val(self.district2),
                         "District2 started with wrong value")

        # Modify characteristic values, and ensure the values don't change
        c = Characteristic.objects.get(geounit=geounits[0], subject=subject)
        c.number += 100
        c.save()
        d_id = self.district1.district_id
        self.district1 = max(
            District.objects.filter(plan=self.plan, district_id=d_id),
            key=lambda d: d.version)
        self.assertEqual(3, get_cc_val(self.district1),
                         "District1 value changed unexpectedly")

        c = Characteristic.objects.get(geounit=geounits[10], subject=subject)
        c.number += 100
        c.save()
        d_id = self.district2.district_id
        self.district2 = max(
            District.objects.filter(plan=self.plan, district_id=d_id),
            key=lambda d: d.version)
        self.assertEqual(18, get_cc_val(self.district2),
                         "District2 value changed unexpectedly")

        # Reaggregate each district, and ensure the values have been updated
        self.district1.reaggregate()
        self.assertEqual(103, get_cc_val(self.district1),
                         "District1 not aggregated properly")

        self.district2.reaggregate()
        self.assertEqual(118, get_cc_val(self.district2),
                         "District2 not aggregated properly")

        # Change the values back to what they were
        c = Characteristic.objects.get(geounit=geounits[0], subject=subject)
        c.number -= 100
        c.save()
        d_id = self.district1.district_id
        self.district1 = max(
            District.objects.filter(plan=self.plan, district_id=d_id),
            key=lambda d: d.version)

        c = Characteristic.objects.get(geounit=geounits[10], subject=subject)
        c.number -= 100
        c.save()
        d_id = self.district2.district_id
        self.district2 = max(
            District.objects.filter(plan=self.plan, district_id=d_id),
            key=lambda d: d.version)

        # Reaggregate entire plan, and ensure the values have been updated
        updated = self.plan.reaggregate()
        self.assertEqual(3, get_cc_val(self.district1),
                         "Plan not aggregated properly for District1")
        self.assertEqual(18, get_cc_val(self.district2),
                         "Plan not aggregated properly for District2")
        self.assertEqual(8, updated, "Incorrect number of districts updated")

        # Change the values back to what they were
        c = Characteristic.objects.get(geounit=geounits[0], subject=subject)
        c.number += 100
        c.save()
        d_id = self.district1.district_id
        self.district1 = max(
            District.objects.filter(plan=self.plan, district_id=d_id),
            key=lambda d: d.version)

        c = Characteristic.objects.get(geounit=geounits[10], subject=subject)
        c.number += 100
        c.save()
        d_id = self.district2.district_id
        self.district2 = max(
            District.objects.filter(plan=self.plan, district_id=d_id),
            key=lambda d: d.version)

        # Reaggregate only the first district, and ensure only the one value
        # has been updated
        self.district1.reaggregate()
        self.assertEqual(103, get_cc_val(self.district1),
                         "District1 not aggregated properly")
        self.assertEqual(18, get_cc_val(self.district2),
                         "District2 aggregated when it shouldn't have been")

    def test_paste_districts(self):
        # Set up the test using geounits in the 2nd level
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]
        dist1ids = geounits[0:3] + geounits[9:12] + geounits[18:21]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               geolevelid, self.plan.version)

        district1 = max(
            District.objects.filter(
                plan=self.plan, district_id=self.district1.district_id),
            key=lambda d: d.version)
        target = Plan.create_default(
            'Paste Plan 1',
            self.plan.legislative_body,
            owner=self.user,
            template=False,
            processing_state=ProcessingState.READY)
        target.save()

        # Paste the district and check returned number, geometry and stats
        result = target.paste_districts((district1, ))
        self.assertEqual(1, len(result),
                         "District1 wasn't pasted into the plan")
        target1 = District.objects.get(pk=result[0])
        self.assertTrue(
            target1.geom.equals(district1.geom),
            "Geometries of pasted district doesn't match original")
        # Without any language (.po) message strings, the members generated
        # default to 'District %s'
        self.assertEqual(
            target1.long_label, "District 1",
            "Proper name wasn't assigned to pasted district. (e:'District 1', a:'%s')"
            % target1.long_label)

        target_stats = ComputedCharacteristic.objects.filter(
            district=result[0])
        for stat in target_stats:
            district1_stat = ComputedCharacteristic.objects.get(
                district=district1, subject=stat.subject)
            self.assertEqual(stat.number, district1_stat.number,
                             "Stats for pasted district (number) don't match")
            self.assertEqual(
                stat.percentage, district1_stat.percentage,
                "Stats for pasted district (percentage) don't match")

        # Add district 2 to a new plan so it doesn't overlap district 1
        new_for_2 = Plan.create_default(
            'Paste Plan 2',
            self.plan.legislative_body,
            self.user,
            template=False,
            processing_state=ProcessingState.READY)
        dist2ids = geounits[10:13] + geounits[19:22] + geounits[28:31]
        dist2ids = map(lambda x: str(x.id), dist2ids)
        new_for_2.add_geounits(self.district2.district_id, dist2ids,
                               geolevelid, self.plan.version)
        district2 = max(
            District.objects.filter(
                plan=new_for_2, district_id=self.district2.district_id),
            key=lambda d: d.version)

        # Paste district 2 into our target plan
        result = target.paste_districts((district2, ))
        self.assertEqual(1, len(result),
                         "District2 wasn't pasted into the plan")
        target2 = District.objects.get(pk=result[0])
        self.assertTrue(
            target2.geom.equals(district2.geom),
            "Geometries of pasted district doesn't match original\n")
        self.assertEqual(target2.long_label, "District 2",
                         "Proper name wasn't assigned to pasted district")

        target2_stats = ComputedCharacteristic.objects.filter(district=target2)
        for stat in target2_stats:
            # Check on District 2 stats
            district2_stat = ComputedCharacteristic.objects.get(
                district=district2, subject=stat.subject)

            self.assertEqual(stat.number, district2_stat.number,
                             "Stats for pasted district (number) don't match")
            self.assertEqual(
                stat.percentage, district2_stat.percentage,
                "Stats for pasted district (percentage) don't match")

        # Calculate what district 1 should look like
        unassigned = max(
            District.objects.filter(plan=self.plan, long_label="Unassigned"),
            key=lambda d: d.version)
        self.plan.add_geounits(unassigned.district_id, dist2ids, geolevelid,
                               self.plan.version)
        self.district1 = max(
            District.objects.filter(
                plan=self.plan, district_id=self.district1.district_id),
            key=lambda d: d.version)

        # Get the statistics for the district 1 in the target
        target1 = max(
            District.objects.filter(
                plan=target, district_id=target1.district_id),
            key=lambda d: d.version)
        self.assertTrue(
            target1.geom.equals(self.district1.geom),
            'Geometry of pasted geometry is not correct')
        target_stats = target1.computedcharacteristic_set.all()

        for stat in target_stats:
            district1_stat = ComputedCharacteristic.objects.get(
                district=self.district1, subject=stat.subject)
            self.assertEqual(
                stat.number, district1_stat.number,
                "Stats for pasted district (number) don't match. (e:%f, a:%f)"
                % (stat.number, district1_stat.number))
            self.assertEqual(
                stat.percentage, district1_stat.percentage,
                "Stats for pasted district (percentage) don't match")

        # Make sure that method fails when adding too many districts
        target.legislative_body.max_districts = 2
        target.legislative_body.save()
        self.assertRaises(Exception, target.paste_districts, (district2, ),
                          'Allowed to merge too many districts')

    def test_paste_districts_onto_locked(self):
        # Set up the test using geounits in the 2nd level
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]
        dist1ids = geounits[0:3] + geounits[9:12] + geounits[18:21]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               geolevelid, self.plan.version)

        district1 = max(
            District.objects.filter(
                plan=self.plan, district_id=self.district1.district_id),
            key=lambda d: d.version)
        target = Plan.create_default(
            'Paste Plan 1',
            self.plan.legislative_body,
            owner=self.user,
            template=False,
            processing_state=ProcessingState.READY)
        target.save()

        # Add a district to the Paste Plan
        target.add_geounits(self.district1.district_id, dist1ids, geolevelid,
                            self.plan.version)
        # Lock that district
        district1 = max(
            District.objects.filter(
                plan=target, district_id=self.district1.district_id),
            key=lambda d: d.version)
        district1.is_locked = True
        district1.save()
        # Add a district that would overlap district1 to self.plan
        dist2ids = geounits[10:13] + geounits[19:22] + geounits[28:31]
        dist2ids = map(lambda x: str(x.id), dist2ids)
        self.plan.add_geounits(self.district2.district_id, dist2ids,
                               geolevelid, self.plan.version)
        self.district2 = max(
            District.objects.filter(
                plan=self.plan, district_id=self.district2.district_id),
            key=lambda d: d.version)

        # Paste district2 into our Paste Plan, on top of the locked district1
        result = target.paste_districts((self.district2, ))
        district2 = District.objects.get(pk=result[0])
        # district2 = max(District.objects.filter(plan=target,
        # district_id=self.district2.district_id),key=lambda d: d.version)
        # Create in self.plan the district we want to see in Paste Plan
        unassigned = max(
            District.objects.filter(plan=self.plan, long_label="Unassigned"),
            key=lambda d: d.version)
        self.plan.add_geounits(unassigned.district_id, dist1ids, geolevelid,
                               self.plan.version)
        self.district2 = max(
            District.objects.filter(
                plan=self.plan, district_id=self.district2.district_id),
            key=lambda d: d.version)
        # Check stats and geometry
        self.assertTrue(
            self.district2.geom.equals(district2.geom),
            'Geom for district pasted over locked district doesn\'t match')
        target_stats = district2.computedcharacteristic_set.all()
        for stat in target_stats:
            expected_stat = ComputedCharacteristic.objects.get(
                district=self.district2, subject=stat.subject)
            self.assertEqual(stat.number, expected_stat.number,
                             "Stats for pasted district (number) don't match")
            self.assertEqual(
                stat.percentage, expected_stat.percentage,
                "Stats for pasted district (percentage) don't match")

    def test_paste_multiple_districts(self):
        # Set up the test using geounits in the 2nd level
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]
        dist1ids = geounits[0:3] + geounits[9:12] + geounits[18:21]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               geolevelid, self.plan.version)

        self.district3 = District(
            plan=self.plan, long_label="TestMember 3", district_id=3)
        self.district3.simplify()
        dist3ids = geounits[20:23] + geounits[29:32] + geounits[38:41]
        dist3ids = map(lambda x: str(x.id), dist3ids)
        self.plan.add_geounits(self.district3.district_id, dist3ids,
                               geolevelid, self.plan.version)

        self.district1 = max(
            District.objects.filter(
                plan=self.plan, district_id=self.district1.district_id),
            key=lambda d: d.version)
        self.district3 = max(
            District.objects.filter(
                plan=self.plan, district_id=self.district3.district_id),
            key=lambda d: d.version)

        target = Plan.create_default(
            'Paste Plan',
            self.plan.legislative_body,
            owner=self.user,
            template=False,
            processing_state=ProcessingState.READY)
        target.save()

        # Add a district to the Paste Plan
        dist2ids = geounits[10:12] + geounits[19:22] + geounits[29:31]
        dist2ids = map(lambda x: str(x.id), dist2ids)
        target.add_geounits(self.district2.district_id, dist2ids, geolevelid,
                            target.version)

        # Paste over top of it with two districts, both intersecting the
        # present district
        old_version = target.version
        results = target.paste_districts((self.district1, self.district3))
        new_version = target.version
        # Check that we've only moved up one version
        self.assertTrue(
            new_version == old_version + 1,
            'Adding multiple districts increased plan version by %d rather than 1'
            % (new_version - old_version))
        # Check stats and geometry for all districts in Paste Plan
        self.assertEqual(2, len(results), 'Didn\'t get 2 pasted district IDs')
        district1 = District.objects.get(pk=results[0])
        self.assertTrue(
            self.district1.geom.equals(district1.geom),
            'Geom for pasted district doesn\'t match')
        target_stats = district1.computedcharacteristic_set.all()
        for stat in target_stats:
            expected_stat = ComputedCharacteristic.objects.get(
                district=self.district1, subject=stat.subject)
            self.assertEqual(stat.number, expected_stat.number,
                             "Stats for pasted district (number) don't match")
            self.assertEqual(
                stat.percentage, expected_stat.percentage,
                "Stats for pasted district (percentage) don't match")

        district3 = District.objects.get(pk=results[1])
        self.assertTrue(
            self.district3.geom.equals(district3.geom),
            'Geom for pasted district doesn\'t match')
        target_stats = district3.computedcharacteristic_set.all()
        for stat in target_stats:
            expected_stat = ComputedCharacteristic.objects.get(
                district=self.district3, subject=stat.subject)
            self.assertEqual(stat.number, expected_stat.number,
                             "Stats for pasted district (number) don't match")
            self.assertEqual(
                stat.percentage, expected_stat.percentage,
                "Stats for pasted district (percentage) don't match")

        # Test that already-present district is gone.
        district2 = max(
            District.objects.filter(
                plan=target, district_id=self.district2.district_id),
            key=lambda d: d.version)
        self.assertTrue(
            district2.geom.empty,
            'District 2 geom wasn\'t emptied when it was pasted over')
        self.assertEqual(0, len(district2.computedcharacteristic_set.all()),
                         'District2 still has characteristics')

    def test_get_available_districts(self):
        # Set the max_districts setting for this test
        self.plan.legislative_body.max_districts = 1
        self.plan.legislative_body.save()

        self.assertEqual(1, self.plan.get_available_districts(
        ), 'Wrong number of available districts returned initially. (e:1, a:%d)'
                         % self.plan.get_available_districts())

        # Set up the test using geounits in the 2nd level
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]

        # Add a district
        dist1ids = geounits[0:3] + geounits[9:12] + geounits[18:21]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               geolevelid, self.plan.version)
        self.assertEqual(0, self.plan.get_available_districts(
        ), 'Wrong number of available districts returned after adding a district. (e:0, a:%d)'
                         % self.plan.get_available_districts())

        # Unassign the district
        unassigned = District.objects.filter(
            plan=self.plan, long_label="Unassigned").order_by('-version')[0]
        self.plan.add_geounits(unassigned.district_id, dist1ids, geolevelid,
                               self.plan.version)
        self.assertEqual(1, self.plan.get_available_districts(
        ), 'Wrong number of available districts returned after removing a district. (e:1, a:%d)'
                         % self.plan.get_available_districts())

    def test_combine_districts(self):
        # Set up three districst using geounits in the 2nd level
        geolevelid = self.geolevels[1].id
        geounits = self.geounits[geolevelid]

        # District 1 in the corner
        dist1ids = geounits[0:3] + geounits[9:12] + geounits[18:21]
        dist1ids = map(lambda x: str(x.id), dist1ids)
        self.plan.add_geounits(self.district1.district_id, dist1ids,
                               geolevelid, self.plan.version)

        # District 2 right of that
        dist2ids = geounits[3:6] + geounits[12:15] + geounits[21:24]
        dist2ids = map(lambda x: str(x.id), dist2ids)
        self.plan.add_geounits(self.district2.district_id, dist2ids,
                               geolevelid, self.plan.version)

        # District 3 above district 1
        dist3ids = geounits[27:30] + geounits[36:39] + geounits[45:48]
        dist3ids = map(lambda x: str(x.id), dist3ids)
        dist3_district_id = 4
        self.plan.add_geounits(dist3_district_id, dist3ids, geolevelid,
                               self.plan.version)

        all_4 = self.plan.get_districts_at_version(
            self.plan.version, include_geom=True)
        all_3 = filter(lambda x: x.long_label != "Unassigned", all_4)
        initial_state = {}
        total = 0
        for district in all_3:
            initial_state[district.district_id] = district

        totals = {}
        for subject in Subject.objects.all():
            total = ComputedCharacteristic.objects.filter(
                district__in=all_3, subject=subject).aggregate(Sum('number'))
            totals[subject] = total['number__sum']
        total_geom = enforce_multi(
            District.objects.filter(plan=self.plan,
                                    district_id__gt=0).aggregate(
                                        Collect('geom'))['geom__collect'],
            collapse=True)

        # Paste them all together now
        district1 = initial_state[self.district1.district_id]
        district2 = initial_state[self.district2.district_id]
        district3 = initial_state[dist3_district_id]

        result = self.plan.combine_districts(district1, (district2, district3))
        self.assertTrue(result, 'Combine operation returned false')

        # Refresh our plan version
        plan = Plan.objects.get(pk=self.plan.id)
        combined = max(
            District.objects.filter(
                plan=plan, district_id=self.district1.district_id),
            key=lambda d: d.version)
        self.assertTrue(
            combined.geom.equals(total_geom),
            "Geometries of combined districts don't match")

        # Check our statistics
        for subject in Subject.objects.all():
            characteristic = ComputedCharacteristic.objects.get(
                subject=subject, district=combined)
            self.assertEqual(
                characteristic.number, totals[subject],
                'Stats (number) don\'t match on combined district e:%d,a:%d' %
                (totals[subject], characteristic.number))

    def test_fix_unassigned(self):
        """
        Test the logic for fixing unassigned geounits in a plan
        """

        plan = self.plan
        geounits = list(
            Geounit.objects.filter(geolevel=self.geolevel).order_by('id'))

        # Ensure the min % setting is set, and then hardcode it for testing
        self.assertTrue(settings.FIX_UNASSIGNED_MIN_PERCENT > -1,
                        'FIX_UNASSIGNED_MIN_PERCENT is not set')
        settings.FIX_UNASSIGNED_MIN_PERCENT = 15
        self.assertEqual(15, settings.FIX_UNASSIGNED_MIN_PERCENT,
                         'FIX_UNASSIGNED_MIN_PERCENT did not change')

        # Ensure the comparator subject is set, and then hardcode it for
        # testing
        self.assertTrue(settings.FIX_UNASSIGNED_COMPARATOR_SUBJECT,
                        'FIX_UNASSIGNED_COMPARATOR_SUBJECT is not set')
        settings.FIX_UNASSIGNED_COMPARATOR_SUBJECT = 'TestSubject2'
        self.assertEqual('TestSubject2',
                         settings.FIX_UNASSIGNED_COMPARATOR_SUBJECT,
                         'FIX_UNASSIGNED_COMPARATOR_SUBJECT did not change')

        # Try fixing when not all districts exist
        result = plan.fix_unassigned(threshold=0.1)
        self.assertFalse(result[0], ('Not all districts exist', result))

        # Change the max number of districts, so we don't have to assign them
        # all for testing
        leg_body = plan.legislative_body
        leg_body.max_districts = 1
        leg_body.save()

        # Try fixing when < min % geounits are assigned
        result = plan.fix_unassigned(threshold=0.1)
        self.assertFalse(result[0], ('Not enough % assigned blocks', result))

        # Add all geounits to District1
        plan.add_geounits(self.district1.district_id,
                          [str(x.id) for x in geounits], self.geolevel.id,
                          plan.version)
        district1 = max(
            District.objects.filter(
                plan=plan, district_id=self.district1.district_id),
            key=lambda d: d.version)

        # Ensure geounits were assigned correctly
        unassigned = plan.get_unassigned_geounits(threshold=0.1)
        self.assertEqual(0, len(unassigned),
                         ("Unassigned has geounits", len(unassigned), result))
        num = len(district1.get_base_geounits(0.1))
        self.assertEqual(
            729, num,
            ("District 1 doesn't contain all of the geounits", num, result))

        # Fixing unassigned should fail, since there are no unassigned geounits
        result = plan.fix_unassigned(threshold=0.1)
        self.assertFalse(result[0], ('No unassigned geounits', result))

        # Create one small and one large unassigned holes in district 1
        units = geounits[10:12] + geounits[19:21] + geounits[28:30] + [
            geounits[47]
        ]
        plan.add_geounits(0, [str(x.id) for x in units], self.geolevel.id,
                          plan.version)
        district1 = max(
            District.objects.filter(
                plan=plan, district_id=self.district1.district_id),
            key=lambda d: d.version)
        version_with_holes = district1.version

        # Ensure geounits were unassigned correctly
        unassigned = plan.get_unassigned_geounits(threshold=0.1)
        self.assertEqual(63, len(unassigned),
                         ("Unassigned has wrong number of geounits",
                          len(unassigned), result))
        num = len(district1.get_base_geounits(0.1))
        self.assertEqual(
            729 - 63, num,
            ("District 1 has the wrong number of the geounits", num, result))

        # Fix the holes
        result = plan.fix_unassigned(threshold=0.1)
        self.assertTrue(result[0], ('Holes should have been closed', result))
        unassigned = plan.get_unassigned_geounits(threshold=0.1)
        self.assertEqual(
            0, len(unassigned),
            ("Unassigned should be empty", len(unassigned), result))

        # Try the same thing when the district with holes is locked
        district1 = District.objects.get(
            plan=plan,
            district_id=self.district1.district_id,
            version=version_with_holes)
        district1.is_locked = True
        district1.save()
        result = plan.fix_unassigned(threshold=0.1, version=version_with_holes)
        self.assertFalse(result[0],
                         ('District locked, nothing should be fixed', result))

        # Unassign some units on the edges (not holes)
        units = geounits[0:1] + geounits[9:10] + [geounits[3]]
        plan.add_geounits(0, [str(x.id) for x in units], self.geolevel.id,
                          plan.version)
        district1 = max(
            District.objects.filter(
                plan=plan, district_id=self.district1.district_id),
            key=lambda d: d.version)
        version_with_edges = district1.version

        # Ensure geounits were unassigned correctly
        unassigned = plan.get_unassigned_geounits(threshold=0.1)
        self.assertEqual(27, len(unassigned),
                         ("Unassigned has wrong number of geounits",
                          len(unassigned), result))
        num = len(district1.get_base_geounits(0.1))
        self.assertEqual(
            729 - 27, num,
            ("District 1 has the wrong number of the geounits", num, result))

        # Fix the edges -- this only fixes some of the base geounits
        result = plan.fix_unassigned(threshold=0.1)
        self.assertTrue(result[0], ('Edges should have been assigned', result))
        unassigned = plan.get_unassigned_geounits(threshold=0.1)
        self.assertEqual(
            12, len(unassigned),
            ("Unassigned shouldn't quite be empty", len(unassigned), result))

        # Fix again -- this fixes some more of the base geounits
        result = plan.fix_unassigned(threshold=0.1)
        self.assertTrue(result[0], ('Edges should have been assigned', result))
        unassigned = plan.get_unassigned_geounits(threshold=0.1)
        self.assertEqual(
            4, len(unassigned),
            ("Unassigned should still have some", len(unassigned), result))

        # Fix again -- this should complete the fix
        result = plan.fix_unassigned(threshold=0.1)
        self.assertTrue(result[0], ('Edges should have been assigned', result))
        unassigned = plan.get_unassigned_geounits(threshold=0.1)
        self.assertEqual(0, len(unassigned),
                         ("Unassigned should be empty after 3 fixes",
                          len(unassigned), result))

        # Create a small second district in the lower-left
        units = geounits[0:1] + geounits[9:10]
        plan.add_geounits(self.district2.district_id,
                          [str(x.id) for x in units], self.geolevel.id,
                          plan.version)

        # Create an area of unassigned districts between the two districts
        # (right angle)
        units = geounits[18:20] + [geounits[2], geounits[11]]
        plan.add_geounits(0, [str(x.id) for x in units], self.geolevel.id,
                          plan.version)

        # Ensure geounits were unassigned correctly
        district1 = max(
            District.objects.filter(
                plan=plan, district_id=self.district1.district_id),
            key=lambda d: d.version)
        district2 = max(
            District.objects.filter(
                plan=plan, district_id=self.district2.district_id),
            key=lambda d: d.version)
        unassigned = plan.get_unassigned_geounits(threshold=0.1)
        self.assertEqual(
            36, len(unassigned),
            ("Unassigned shouldn't be empty", len(unassigned), result))
        num = len(district2.get_base_geounits(0.1))
        self.assertEqual(
            18, num,
            ("District 2 has the wrong number of the geounits", num, result))
        num = len(district1.get_base_geounits(0.1))
        self.assertEqual(
            729 - 18 - 36, num,
            ("District 1 has the wrong number of the geounits", num, result))

        # Fix, and ensure the blocks are partially assigned to the one with the
        # lower population
        result = plan.fix_unassigned(threshold=0.1)
        district1 = max(
            District.objects.filter(
                plan=plan, district_id=self.district1.district_id),
            key=lambda d: d.version)
        district2 = max(
            District.objects.filter(
                plan=plan, district_id=self.district2.district_id),
            key=lambda d: d.version)
        self.assertTrue(
            result[0],
            ('Right-angle should have been partially fixed', result))
        unassigned = plan.get_unassigned_geounits(threshold=0.1)
        self.assertEqual(
            10, len(unassigned),
            ("Unassigned shouldn't quite be empty", len(unassigned), result))
        num = len(district2.get_base_geounits(0.1))
        self.assertEqual(
            18 + 4, num,
            ("District 2 has the wrong number of the geounits", num, result))
        num = len(district1.get_base_geounits(0.1))
        self.assertEqual(
            729 - 18 - 36 + 22, num,
            ("District 1 has the wrong number of the geounits", num, result))
        version_before = plan.version

        # Fix again -- this fixes the remaining base geounits
        result = plan.fix_unassigned(threshold=0.1)
        district1 = max(
            District.objects.filter(
                plan=plan, district_id=self.district1.district_id),
            key=lambda d: d.version)
        district2 = max(
            District.objects.filter(
                plan=plan, district_id=self.district2.district_id),
            key=lambda d: d.version)
        self.assertTrue(result[0],
                        ('Right-angle should have been fixed', result))
        unassigned = plan.get_unassigned_geounits(threshold=0.1)
        self.assertEqual(
            0, len(unassigned),
            ("Unassigned should be empty", len(unassigned), result))
        num = len(district2.get_base_geounits(0.1))
        self.assertEqual(
            18 + 4 + 5, num,
            ("District 2 has the wrong number of the geounits", num, result))
        num = len(district1.get_base_geounits(0.1))
        self.assertEqual(
            729 - 18 - 36 + 22 + 5, num,
            ("District 1 has the wrong number of the geounits", num, result))

        # Try that again with the smaller district locked
        district2 = District.objects.get(
            plan=plan,
            district_id=self.district2.district_id,
            version=version_before)
        district2.is_locked = True
        district2.save()
        result = plan.fix_unassigned(threshold=0.1, version=version_before)
        district1 = max(
            District.objects.filter(
                plan=plan, district_id=self.district1.district_id),
            key=lambda d: d.version)
        district2 = max(
            District.objects.filter(
                plan=plan, district_id=self.district2.district_id),
            key=lambda d: d.version)
        self.assertTrue(result[0],
                        ('Right-angle should have been fixed', result))
        unassigned = plan.get_unassigned_geounits(threshold=0.1)
        self.assertEqual(
            0, len(unassigned),
            ("Unassigned should be empty", len(unassigned), result))
        num = len(district2.get_base_geounits(0.1))
        self.assertEqual(
            18 + 4, num,
            ("District 2 has the wrong number of the geounits", num, result))
        num = len(district1.get_base_geounits(0.1))
        self.assertEqual(
            729 - 18 - 36 + 22 + 10, num,
            ("District 1 has the wrong number of the geounits", num, result))
