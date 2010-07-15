from django.contrib.gis.db import models
from django.contrib.gis.geos import MultiPolygon
from django.contrib.auth.models import User
from django.forms import ModelForm
from django.conf import settings
from datetime import datetime

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
    geolevel = models.ForeignKey(Geolevel)
    objects = models.GeoManager()

    @staticmethod
    def get_base_geounits(geounit_ids, geolevel):
        new_geounit_ids = []
        for geounit_id in geounit_ids:
            target = Geounit.objects.get(pk=geounit_id).geom
            base_geounits = Geounit.objects.filter(geom__within=target, geolevel=settings.BASE_GEOLEVEL).values_list('id', flat=True)
            new_geounit_ids.extend(base_geounits)
        return new_geounit_ids

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
    value = models.PositiveIntegerField()

    def __unicode__(self):
        return u'%s : %s' % (self.subject, self.value)

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
        # get the geometry of all these geounits that are being added
        geounits = Geounit.objects.filter(id__in=geounit_ids).iterator()
        incremental = None
        for geounit in geounits:
            if incremental is None:
                incremental = geounit.geom
            else:
                incremental = geounit.geom.union(incremental)

        # incremental is the geometry that is changing

        target = District.objects.filter(district_id=districtid)[0]

        fixed = self.delete_geounits_prefetch(base_geounit_ids, incremental, districtid)
        geounits = list(Geounit.objects.filter(id__in=base_geounit_ids))
        for geounit in geounits:
            if not target.geounits.filter(id=geounit.id):
                target.geounits.add(geounit) 
                fixed += 1

        if not target.geom is None:
            union = target.geom.union(incremental)
            if union.geom_type != 'MultiPolygon':
                target.geom = MultiPolygon(union)
            else:
                target.geom = union
            
        target.save();
        return fixed


    def delete_geounits(self, districtid, geounit_ids, geolevel):
        """Delete the requested geounits from given district       
        Will return the number of districts effected by the operation
        """
        if (geolevel != settings.BASE_GEOLEVEL):
            base_geounit_ids = Geounit.get_base_geounits(geounit_ids, geolevel)

        # get the geometry of all the geounits that are being removed
        geounits = Geounit.objects.filter(id__in=geounit_ids).iterator()
        incremental = None
        for geounit in geounits:
            if incremental is None:
                incremental = geounit.geom
            else:
                incremental = geounit.geom.union(incremental)

        return self.delete_geounits_prefetch(base_geounit_ids, geounits, incremental, districtid)

    def delete_geounits_prefetch(self, base_geounit_ids, incremental, districtid):

        target = District.objects.filter(district_id=districtid)[0]
        neighbors = District.objects.filter(plan=target.plan)
        fixed = 0
        for neighbor in neighbors:
            if neighbor == target:
                continue

            geounits = neighbor.geounits.filter(id__in=base_geounit_ids).iterator()
            changed = False
            for geounit in geounits:
                neighbor.geounits.remove(geounit)
                fixed += 1
                changed = True

            if changed and not neighbor.geom is None:
                neighbor.geom = neighbor.geom.difference(incremental)
                neighbor.save()

        return fixed

class PlanForm(ModelForm):
    class Meta:
        model=Plan
    

class District(models.Model):
    district_id = models.CharField(max_length=200)
    name = models.CharField(max_length=200)
    plan = models.ForeignKey(Plan)
    geounits = models.ManyToManyField(Geounit)
    geom = models.MultiPolygonField(srid=3785, blank=True, null=True)
    version = models.PositiveIntegerField(default=0)
    objects = models.GeoManager()
    
#    def save(self):
#        super(District, self).save()
#        self.geom = self.geounits.collect()
#        super(District, self).save()

    def __unicode__(self):
        return self.name

def collect_geom(sender, **kwargs):
    kwargs['instance'].geom = kwargs['instance'].geounits.collect()

#// pre_save.connect(collect_geom, sender=District)
