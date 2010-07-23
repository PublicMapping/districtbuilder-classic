from django.contrib.gis.db import models
from django.contrib.gis.db.models import Max
from django.contrib.gis.geos import MultiPolygon
from django.contrib.auth.models import User
from django.forms import ModelForm
from django.conf import settings
from datetime import datetime
from django.db.models.signals import pre_save
from django.db.models import Sum

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
        targets = Geounit.objects.filter(id__in=geounit_ids)
        if len(targets) > 0:
            whole_geom = targets[0].geom
            if len(targets) > 1:
                for i in range(1,len(targets)):
                    for target_geom in targets[i].geom:
                        whole_geom.append(target_geom)

        else:
            return []

        qs = Geounit.objects.filter(geom__within=whole_geom, geolevel=settings.BASE_GEOLEVEL)

        # this is frustrating!  this forces the DB query to executue
        # but it would be awesome to use these IDs as a subquery filter
        # instead of fetching the values and sending them back again
        # this is a django bug, I suspect (dz)
        return list(qs.values_list('id', flat=True))

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
            if difference.geom_type != 'MultiPolygon':
                district.geom = MultiPolygon(difference)
            else:
                district.geom = difference
            simple = district.geom.simplify(tolerance=100.0,preserve_topology=True)
            if simple.geom_type != 'MultiPolygon':
                district.simple = MultiPolygon(simple)
            else:
                district.simple = simple

            ComputedCharacteristic.objects.filter(district=district).delete()
            district.save()
            fixed += 1

        if target.geom is None:
            target.geom = incremental
        else:
            union = target.geom.union(incremental)
            if union.geom_type != 'MultiPolygon':
                target.geom = MultiPolygon(union)
            else:
                target.geom = union

        simple = target.geom.simplify(tolerance=100.0,preserve_topology=True)
        if simple.geom_type != 'MultiPolygon':
            target.simple = MultiPolygon(simple)
        else:
            target.simple = simple
           
        ComputedCharacteristic.objects.filter(district=target).delete()
        target.save();
        fixed += 1

        return fixed


    def update_stats(self):
        districts = self.district_set.all()
        numchanged = 0
        for district in districts:
            if district.update_stats():
                numchanged += 1
        return numchanged

#    def delete_geounits(self, geounit_ids, geolevel):
#        """Delete the requested geounits from given district       
#        Will return the number of districts effected by the operation
#        """
#        if (geolevel != settings.BASE_GEOLEVEL):
#            base_geounit_qs = Geounit.get_base_geounits(geounit_ids, geolevel).iterator()
#            base_geounit_ids = []
#            for base_geounit_id in base_geounit_qs:
#                base_geounit_ids.append(base_geounit_id)
#        else:
#            base_geounit_ids = geounit_ids
#
#
#        # get the geometry of all the geounits that are being removed
#        geounits = Geounit.objects.filter(id__in=base_geounit_ids).iterator()
#        incremental = None
#        for geounit in geounits:
#            if incremental is None:
#                incremental = geounit.geom
#            else:
#                incremental = geounit.geom.union(incremental)
#
#        return self.delete_geounits_prefetch(base_geounit_ids, incremental, None)
#
#    def delete_geounits_prefetch(self, base_geounit_ids, incremental, districtid):
#        neighbors = self.district_set.all()
#        if districtid:
#            target = District.objects.filter(district_id=districtid)[0]
#        else:
#            target = {}
#        # neighbors = District.objects.filter(plan=target.plan)
#        fixed = 0
#        for neighbor in neighbors:
#            if neighbor == target:
#                continue
#
#            geounits = neighbor.geounits.filter(id__in=base_geounit_ids).iterator()
#            changed = False
#            for geounit in geounits:
#                neighbor.geounits.remove(geounit)
#                fixed += 1
#                changed = True
#
#            if changed and not neighbor.geom is None:
#                difference = neighbor.geom.difference(incremental)
#                if difference.geom_type != 'MultiPolygon':
#                    neighbor.geom = MultiPolygon(difference)
#                else:
#                    neighbor.geom = difference
#                neighbor.save()
#
#        return fixed

class PlanForm(ModelForm):
    class Meta:
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
        updated = False
        for subject in all_subjects:
            computed = ComputedCharacteristic.objects.filter(subject=subject,district=self).count()
            if computed == 0:
                my_geounits = DistrictGeounitMapping.objects.filter(district=self).values_list('geounit', flat=True)
                aggregate = Characteristic.objects.filter(geounit__in=my_geounits, subject__exact = subject).aggregate(Sum('number'))['number__sum']
                if aggregate:
                    computed = ComputedCharacteristic(subject = subject, district = self, number = aggregate)
                    computed.save()
                    updated = True
        return updated

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
    district = kwargs['instance']
    if (not district.id):
        max_id = District.objects.filter(plan = district.plan).aggregate(Max('district_id'))['district_id__max']
        if max_id:
            district.district_id = max_id + 1

pre_save.connect(set_district_id, sender=District)
