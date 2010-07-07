from django.contrib.gis.db import models
from django.contrib.auth.models import User
from django.forms import ModelForm

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
    created = models.DateTimeField(auto_now_add=True)
    edited = models.DateTimeField(auto_now=True)
    owner = models.ForeignKey(User)
    objects = models.GeoManager()

    def __unicode__(self):
        return self.name

    def add_geounits(self, districtid, geounit_ids):
        """Add the requested geounits to the given district, and remove
        them from whichever district they're currently in
       
        Will return the number of districts effected by the operation
        """
        target = District.objects.get(pk=districtid)
        fixed = self.delete_geounits(districtid, geounit_ids)
        geounits = list(Geounit.objects.filter(id__in=geounit_ids))
        for geounit in geounits:
            if not target.geounits.filter(id=geounit.id):
                target.geounits.add(geounit) 
                target.save();
                fixed += 1
        return fixed


    def delete_geounits(self, districtid, geounit_ids):
        """Delete the requested geounits from given district       
        Will return the number of districts effected by the operation
        """
        target = District.objects.get(pk=districtid)
        fixed = 0
        geounits = list(Geounit.objects.filter(id__in=geounit_ids))
        for geounit in geounits:
            districts = self.district_set.filter(geounits__id__exact=geounit.id)
            # first, remove from the current district if necessary
            if len(districts.all()) == 1 and districts[0] != target:
                districts[0].geounits.remove(geounit)            
                districts[0].save()
                fixed += 1

        return fixed

class PlanForm(ModelForm):
    class Meta:
        model=Plan
    

class District(models.Model):
    name = models.CharField(max_length=200)
    plan = models.ForeignKey(Plan)
    geounits = models.ManyToManyField(Geounit)
    version = models.PositiveIntegerField()

    def __unicode__(self):
        return self.name

