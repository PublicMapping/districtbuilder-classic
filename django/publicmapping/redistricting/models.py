from django.contrib.gis.db import models
from django.contrib.gis.geos import MultiPolygon
from django.contrib.auth.models import User
from django.db.models import Sum, Max
from django.db.models.signals import pre_save, post_save
from django.forms import ModelForm
from django.conf import settings
from datetime import datetime
from math import sqrt, pi

class Subject(models.Model):
    name = models.CharField(max_length=50)
    display = models.CharField(max_length=200, blank=True)
    short_display = models.CharField(max_length = 25, blank=True)
    description = models.CharField(max_length= 500, blank=True)
    is_displayed = models.BooleanField(default=True)
    format_string = models.CharField(max_length=50, blank=True)

    def __unicode__(self):
        return self.display

class Geolevel(models.Model):
    name = models.CharField(max_length = 50)

    def __unicode__(self):
        return self.name

class Geounit(models.Model):
    name = models.CharField(max_length=200)
    geom = models.MultiPolygonField(srid=3785)
    simple = models.MultiPolygonField(srid=3785)
    geolevel = models.ForeignKey(Geolevel)
    objects = models.GeoManager()

    @staticmethod
    def get_base_geounits(geounit_ids, geolevel):
        from django.db import connection, transaction
        cursor = connection.cursor()
        cursor.execute('SELECT id from redistricting_geounit where geolevel_id = %s and St_within(st_centroid(geom), (select st_simplify(st_union(geom), 10) from redistricting_geounit where geolevel_id = %s and id in %s))', [int(settings.BASE_GEOLEVEL), int(geolevel), geounit_ids])
        results = []
        ids = cursor.fetchall()
        for row in ids:
            results += row
        return results

    def __unicode__(self):
        return self.name

class Characteristic(models.Model):
    subject = models.ForeignKey(Subject)
    geounit = models.ForeignKey(Geounit)
    number = models.DecimalField(max_digits=12,decimal_places=4)
    percentage = models.DecimalField(max_digits=6,decimal_places=6, null=True, blank=True)
    objects = models.GeoManager()

    def __unicode__(self):
        return u'%s for %s: %s' % (self.subject, self.geounit, self.number)

class Target(models.Model):
    subject = models.ForeignKey(Subject)
    lower = models.PositiveIntegerField()
    upper = models.PositiveIntegerField()

    def __unicode__(self):
        return u'%s : %s - %s' % (self.subject, self.lower, self.upper)

class Plan(models.Model):
    name = models.CharField(max_length=200,unique=True)
    is_template = models.BooleanField(default=False)
    is_temporary = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)
    edited = models.DateTimeField(auto_now=True)
    owner = models.ForeignKey(User)
    objects = models.GeoManager()

    def __unicode__(self):
        return self.name

    def add_geounits(self, districtid, geounit_ids, geolevel):
        """Add the requested geounits to the given district, and remove
        them from whichever district they're currently in
       
        Will return the number of districts effected by the operation
        """
        if (geolevel != settings.BASE_GEOLEVEL):
            base_geounit_ids = Geounit.get_base_geounits(geounit_ids, geolevel)
        else:
            base_geounit_ids = geounit_ids

        # get the geometry of all these geounits that are being added
        geounits = Geounit.objects.filter(id__in=geounit_ids).iterator()
        incremental = None
        for geounit in geounits:
            if incremental is None:
                incremental = geounit.geom
            else:
                incremental = geounit.geom.union(incremental)

        # incremental is the geometry that is changing

        target = self.district_set.get(district_id=districtid)

        DistrictGeounitMapping.objects.filter(geounit__in=base_geounit_ids, plan=self).update(district=target)

        fixed = 0
        districts = self.district_set.filter(geom__intersects=incremental)
        for district in districts:
            difference = district.geom.difference(incremental)
            if difference.geom_type == 'MultiPolygon':
                district.geom = difference
            elif difference.geom_type == 'Polygon':
                district.geom = MultiPolygon(difference)
            else:
                # can't process this geometry, so don't change it
                continue

            simple = district.geom.simplify(tolerance=100.0,preserve_topology=True)
            if simple.geom_type != 'MultiPolygon':
                district.simple = MultiPolygon(simple)
            else:
                district.simple = simple
            district.save()

            district.computedcharacteristic_set.all().delete()
            district.update_stats()
            fixed += 1

        if target.geom is None:
            if incremental.geom_type == 'Polygon':
                target.geom = MultiPolygon(incremental)
            elif incremental.geom_type == 'MultiPolygon':
                target.geom = incremental
        else:
            union = target.geom.union(incremental)
            if union.geom_type == 'Polygon':
                target.geom = MultiPolygon(union)
            elif union.geom_type == 'MultiPolygon':
                target.geom = union

        simple = target.geom.simplify(tolerance=100.0,preserve_topology=True)
        if simple.geom_type == 'Polygon':
            target.simple = MultiPolygon(simple)
        elif simple.geom_type == 'MultiPolygon':
            target.simple = simple
           
        target.save();

        target.computedcharacteristic_set.all().delete()
        target.update_stats()
        fixed += 1

        return fixed


    def update_stats(self):
        districts = self.district_set.all()
        changed = 0
        for district in districts:
            if district.update_stats():
                changed += 1
        return changed


class PlanForm(ModelForm):
    class _meta:
        model=Plan
    

class District(models.Model):
    district_id = models.PositiveIntegerField(default=1)
    name = models.CharField(max_length=200)
    plan = models.ForeignKey(Plan)
    geom = models.MultiPolygonField(srid=3785, blank=True, null=True)
    simple = models.MultiPolygonField(srid=3785, blank=True, null=True)
    version = models.PositiveIntegerField(default=0)
    objects = models.GeoManager()
    
    def __unicode__(self):
        return self.name

    def update_stats(self):
        all_subjects = Subject.objects.all().order_by('name').reverse()
        changed = False
        for subject in all_subjects:
            computed = self.computedcharacteristic_set.filter(subject=subject).count()
            if computed == 0:
                my_geounits = DistrictGeounitMapping.objects.filter(district=self).values_list('geounit', flat=True)
                aggregate = Characteristic.objects.filter(geounit__in=my_geounits, subject__exact = subject).aggregate(Sum('number'))['number__sum']
                if aggregate:
                    computed = ComputedCharacteristic(subject = subject, district = self, number = aggregate)
                    computed.save()
                    changed = True
        return changed

    def get_schwartzberg(self):
        """This is the Schwartzberg measure of compactness, which is the measure of the perimeter of the district 
        to the circumference of the circle whose area is equal to the area of the district
        """
        try:
            r = sqrt(self.geom.area / pi)
            perimeter = 2 * pi * r
            ratio = perimeter / self.geom.length
            return "%.2f%%" % (ratio * 100)
        except:
            return "n/a"

    def is_contiguous(self):
        """Checks to see if the district is contiguous.  The district is already a unioned geom.  Any multipolygon
        with more than one poly in it will not be contiguous.  There is one case where this test may give a false 
        negative - if all of the polys in a multipolygon each meet another poly at one point. In GIS terms, this is
        connected but not contiguous.  But the real-word case may be different.
        http://webhelp.esri.com/arcgisdesktop/9.2/index.cfm?TopicName=Coverage_topology
        """
        if not self.geom == None:
            return len(self.geom) == 1
        else:
            return False

class DistrictGeounitMapping(models.Model):
    district = models.ForeignKey(District)
    geounit = models.ForeignKey(Geounit)
    plan = models.ForeignKey(Plan)
    objects = models.GeoManager()

    def __unicode__(self):
        return "Plan '%s', district '%s': '%s'" % (self.plan.name,self.district.name, self.geounit.name)


class ComputedCharacteristic(models.Model):
    subject = models.ForeignKey(Subject)
    district = models.ForeignKey(District)
    number = models.DecimalField(max_digits=12,decimal_places=4)
    percentage = models.DecimalField(max_digits=6,decimal_places=6, null=True, blank=True)
    objects = models.GeoManager()

def collect_geom(sender, **kwargs):
    kwargs['instance'].geom = kwargs['instance'].geounits.collect()

def set_district_id(sender, **kwargs):
    """When a new district is saved, it should get an incremented id that is unique to the plan
    """
    from django.core.exceptions import ValidationError
    district = kwargs['instance']
    if (not district.id):
        max_id = District.objects.filter(plan = district.plan).aggregate(Max('district_id'))['district_id__max']
        if max_id:
            district.district_id = max_id + 1
        # Unassigned is not counted in MAX_DISTRICTS
        if district.district_id > settings.MAX_DISTRICTS + 1:
            raise ValidationError("Too many districts already.  Reached Max Districts setting")

pre_save.connect(set_district_id, sender=District)

def set_geounit_mapping(sender, **kwargs):
    """When a new plan is saved, all geounits must be inserted into the Unassigned districts and a 
    corresponding set of DistrictGeounitMappings should be applied to it.
    """
    plan = kwargs['instance']
    created = kwargs['created']
    
    if created:
        unassigned = District(name="Unassigned", version = 0, plan = plan)
        unassigned.save()
        
        # clone all the geounits manually
        from django.db import connection, transaction
        cursor = connection.cursor()

        sql = "insert into %s (district_id, geounit_id, plan_id) select %s as district_id, geounit.id as geounit_id, %s as plan_id from %s as geounit where geounit.geolevel_id = %s" % (DistrictGeounitMapping._meta.db_table, unassigned.id, plan.id, Geounit._meta.db_table, settings.BASE_GEOLEVEL)
        cursor.execute(sql)
        transaction.commit_unless_managed()

# don't remove the dispatch_uid or this signal is sent twice.
post_save.connect(set_geounit_mapping, sender=Plan, dispatch_uid="publicmapping.redistricting.Plan")

def can_edit(user, plan):
    """Return whether a user can edit the given plan.  They must own it or be a staff member.  Templates
    cannot be edited, only copied
    """
    return (plan.owner == user or user.is_staff) and not plan.is_template

def can_copy(user, plan):
    """Return whether a user can copy the given plan.  The user must be the owner, or a staff member to copy
    a plan they own.  Anyone can copy a template
    """
    return plan.is_template or plan.owner == user or user.is_staff
