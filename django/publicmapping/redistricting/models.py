from django.contrib.gis.db import models
from django.contrib.gis.geos import MultiPolygon,GEOSGeometry,GEOSException
from django.contrib.auth.models import User
from django.db.models import Sum, Max, Q
from django.db.models.signals import pre_save, post_save
from django.forms import ModelForm
from django.conf import settings
from django.utils import simplejson as json
from datetime import datetime
from math import sqrt, pi
from copy import copy

class Subject(models.Model):
    name = models.CharField(max_length=50)
    display = models.CharField(max_length=200, blank=True)
    short_display = models.CharField(max_length = 25, blank=True)
    description = models.CharField(max_length= 500, blank=True)
    is_displayed = models.BooleanField(default=True)
    sort_key = models.PositiveIntegerField(default=1)
    format_string = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ['sort_key']

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
    center = models.PointField(srid=3785)
    geolevel = models.ForeignKey(Geolevel)
    objects = models.GeoManager()

    @staticmethod
    def get_base_geounits(geounit_ids, geolevel):
        """Get the geounits at the base geolevel that comprise the
        geometry described by the list of geounit_ids. This means
        that the geounit_ids for blocks are returned if a list of
        county ids are passed in along with the county geolevel.
        """
        from django.db import connection
        cursor = connection.cursor()
        cursor.execute('SELECT id from redistricting_geounit where geolevel_id = %s and St_within(center, (select st_simplify(st_union(geom), 10) from redistricting_geounit where geolevel_id = %s and id in %s))', [int(settings.BASE_GEOLEVEL), int(geolevel), geounit_ids])
        results = []
        ids = cursor.fetchall()
        for row in ids:
            results += row
        return results

    @staticmethod
    def get_base_geounits_within(geom):
        from django.db import connection
        cursor = connection.cursor()
        cursor.execute("select id from redistricting_geounit where geolevel_id = %s and st_within(center, geomfromewkt(%s))",[settings.BASE_GEOLEVEL, str(geom.ewkt)])
        results = []
        ids = cursor.fetchall()
        for row in ids:
            results += row
        return results

    @staticmethod
    def get_mixed_geounits(geounit_ids, geolevel, boundary, inside):
        """Get the geounit ids that are inside or outside of the boundary, 
        starting at the highest geolevel, and drilling down to get the 
        edge cases. These geounits comprise the incremental change to 
        the boundary.
        """

        if not boundary and inside:
            # there are 0 geounits inside a non-existant boundary
            return []

        from django.db import connection

        geolevel = int(geolevel)
        levels = Geolevel.objects.all().values_list('id',flat=True).order_by('id')
        current = None
        selection = None
        units = []
        for level in levels:
            #print 'Looking in geolevel: %d (%d)' % (level,len(units))
            # if this geolevel is the requested geolevel
            if geolevel == level:
                guFilter = Q(id__in=geounit_ids)

                selection = Geounit.objects.filter(guFilter).unionagg()
                
                query = "SELECT id,st_ashexewkb(geom,'NDR') FROM redistricting_geounit WHERE id IN (%s) AND " % (','.join(geounit_ids))

                if not boundary:
                    boundary = empty_geom(selection.srid)

                if inside:
                    if level != settings.BASE_GEOLEVEL:
                        query += "st_within(geom, geomfromewkt('%s'))" % boundary.ewkt
                    else:
                        query += "st_intersects(center, geomfromewkt('%s'))" % center.ewkt
                else:
                    if level != settings.BASE_GEOLEVEL:
                        query += "NOT st_intersects(geom, geomfromewkt('%s'))" % boundary.ewkt
                    else:
                        query += "NOT st_intersects(center, geomfromewkt('%s')" % center.ewkt

                #print "Query: '%s'" % query

                cursor = connection.cursor()
                cursor.execute(query)
                rows = cursor.fetchall()
                count = 0
                for row in rows:
                    count += 1
                    geom = GEOSGeometry(row[1])
                    units.append(Geounit(id=row[0],geom=geom))

                #print "Found %d geounits at geolevel %d (by id)" % (count, level)

                # if we're at the base level, and haven't collected any
                # geometries, return the units here
                if level == settings.BASE_GEOLEVEL:
                    return units

            # only query geolevels at or below (smaller in size, bigger
            # in id) the geolevel parameter
            elif geolevel < level:
                # union the selected geometries
                union = None
                for selected in units:
                    # this always rebuilts the current extent of all the
                    # selected geounits
                    if union is None:
                        union = selected.geom
                    else:
                        union = union.union(selected.geom)

                #print 'Union: %s' % union

                # set or merge this onto the existing selection
                if union is None:
                    intersects = selection
                else:
                    intersects = selection.difference(union)

                #print 'Intersection %s' % intersects

                if inside:
                    # the remainder geometry is the intersection of the 
                    # district and the difference of the selected geounits
                    # and the current extent
                    try:
                        #print 'Intersecting selection with %s' % boundary
                        remainder = boundary.intersection(intersects)
                    except GEOSException, ex:
                        #print 'GEOSException, line 148:'
                        #print ex
                        # it is not clear what this means, or why it happens
                        remainder = empty_geom(boundary.srid)
                else:
                    # the remainder geometry is the geounit selection 
                    # differenced with the boundary (leaving the 
                    # selection that lies outside the boundary) 
                    # differenced with the intersection (the selection
                    # outside the boundary and outside the accumulated
                    # geometry)
                    try:
                        remainder = selection.difference(boundary)

                        remainder = remainder.intersection(intersects)
                    except GEOSException, ex:
                        #print 'GEOSException, line 163:'
                        #print ex
                        # it is not clear what this means, or why it happens
                        remainder = empty_geom(boundary.srid)

                if remainder.geom_type == 'GeometryCollection' and not remainder.empty:
                    srid = remainder.srid
                    union = None
                    for geom in remainder:
                        mgeom = enforce_multi(geom)
                        if mgeom.geom_type == 'MultiPolygon':
                            if union is None:
                                union = mgeom
                            else:
                                for poly in mgeom:
                                    union.append(poly)
                        else:
                            # do nothing if it's not some kind of poly
                            #print "Cannot intersect non-area: %s" % remainder[i].geom_type
                            pass

                    remainder = union
                    if remainder:
                        remainder.srid = srid
                    else:
                        remainder = empty_geom(srid)
                elif remainder.empty or (remainder.geom_type != 'MultiPolygon' and remainder.geom_type != 'Polygon'):
                    remainder = empty_geom(boundary.srid)

                #print 'Remainder: %s' % remainder

                if not remainder.empty:
                    query = "SELECT id,st_ashexewkb(geom,'NDR') FROM redistricting_geounit WHERE geolevel_id = %d AND " % level

                    if level == settings.BASE_GEOLEVEL:
                        query += "st_intersects(center, geomfromewkt('%s'))" % remainder.ewkt
                    else:
                        query += "st_within(geom, geomfromewkt('%s'))" % remainder.ewkt

                    #print "geounit q: %s" % query
                    cursor = connection.cursor()
                    cursor.execute(query)
                    rows = cursor.fetchall()
                    count = 0
                    for row in rows:
                        count += 1
                        units.append(Geounit(id=row[0],geom=GEOSGeometry(row[1])))

                    #print "Found %d geounits at geolevel %d (w/in)" % (count, level)

        return units


        

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

    class Meta:
        ordering = ['subject']

    def __unicode__(self):
        return u'%s : %s - %s' % (self.subject, self.lower, self.upper)

class Plan(models.Model):
    """A plan contains a collection of districts that divide up a state.
    A plan may also be a template, in which case it is usable as a starting
    point by all other users on the system.
    """
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
        them from whichever district they're currently in. 
        Will return the number of districts effected by the operation.
        """
        
        # incremental is the geometry that is changing
        incremental = Geounit.objects.filter(id__in=geounit_ids).unionagg()

        # get the most recent version of the target
        tversion = self.district_set.filter(district_id=districtid).aggregate(Max('version'))['version__max']
        target = self.district_set.get(district_id=districtid,version=tversion)

        fixed = 0
        districts = self.district_set.filter(~Q(id=target.id))
        for district in districts:
            if not district.is_latest_version():
                # the version of this district is not the most recent; skip
                continue

            if not (district.geom and (district.geom.overlaps(incremental) or district.geom.contains(incremental))):
                # if this district does not overlap the selection or
                # if this district does not contain the selection; skip
                continue

            # compute the geounits before changing the boundary
            geounits = Geounit.get_mixed_geounits(geounit_ids, geolevel, district.geom, True)
            try:
                geom = district.geom.difference(incremental)
            except GEOSException, ex:
                #print 'GEOSException, line 280:'
                #print ex
                # this geometry cannot be computed, move on to the 
                # next district
                geom = empty_geom(incremental.srid)

            geom = enforce_multi(geom)

            if not geom.empty:
                district.geom = geom
                simple = geom.simplify(tolerance=100.0,preserve_topology=True)
                district.simple = enforce_multi(simple)
            else:
                district.geom = None
                district.simple = None

            # save the original district id for copyingi
            # ComputedCharacteristics 
            oldid = district.id

            district = copy(district)
            district.version = self.version + 1
            district.id = None
            district.save()

            # Clone the computed stats to this newly versioned district
            computedChars = ComputedCharacteristic.objects.filter(district=oldid)
            for computed in computedChars:
                computed.id = None
                computed.district = district
                computed.save()

            if district.delta_stats(geounits,False):
                fixed += 1

        # get the geounits before changing the target geometry
        geounits = Geounit.get_mixed_geounits(geounit_ids, geolevel, target.geom, False)

        if target.geom is None:
            target.geom = enforce_multi(incremental)
        else:
            try:
                union = target.geom.union(incremental)
                target.geom = enforce_multi(union)
            except GEOSException, ex:
                #print 'GEOSException, line 307:'
                #print ex
                # can't process the union, so don't change the
                # target geometry
                target.geom = None

        if target.geom:
            simple = target.geom.simplify(tolerance=100.0,preserve_topology=True)
            target.simple = enforce_multi(simple)
        else:
            target.simple = None

        # save the original district id for copyingi
        # ComputedCharacteristics 
        oldid = target.id

        target = copy(target)
        target.version = self.version + 1
        target.id = None
        target.save();

        # Clone the computed stats to this newly versioned district
        computedChars = ComputedCharacteristic.objects.filter(district=oldid)
        for computed in computedChars:
            computed.id = None
            computed.district = target
            computed.save()

        if target.geom and target.delta_stats(geounits,True):
            fixed += 1

        # save any changes to the version of this plan
        self.version += 1
        self.save()

        return fixed


    def get_versioned_districts(self,version,subject_id):
        """Get the districts in this plan at a specific version. This 
        method behaves much like a WFS service, returning the GeoJSON for
        each district. This is due to the limitations of filtering and the
        complexity of the version query -- it makes it impossible to use
        the WFS layer in Geoserver automatically.
        """
        
        from django.db import connection
        cursor = connection.cursor()

        query = 'SELECT rd.id, rd.district_id, rd.name, rd.version, rd.plan_id, rc.subject_id, rc.number, st_asgeojson(rd.simple) AS geom FROM redistricting_district rd JOIN redistricting_computedcharacteristic rc ON rd.id = rc.district_id WHERE rd.version = (SELECT max(redistricting_district.version) FROM redistricting_district WHERE redistricting_district.district_id = rd.district_id AND redistricting_district.version <= %d ) AND rd.plan_id = %d AND rc.subject_id = %d' % (int(version), int(self.id), int(subject_id))

        cursor.execute(query)
        rows = cursor.fetchall()
        features = []
        for row in rows:
            features.append({ 
                'id': row[0],
                'properties': {
                    'district_id': row[1],
                    'name': row[2],
                    'version': row[3],
                    'number': float(row[6])
                },
                'geometry': json.loads( row[7] )
            })
        return features

class PlanForm(ModelForm):
    class Meta:
        model=Plan
    

class District(models.Model):
    class Meta:
        ordering = ['name']
    district_id = models.PositiveIntegerField(default=1)
    name = models.CharField(max_length=200)
    plan = models.ForeignKey(Plan)
    geom = models.MultiPolygonField(srid=3785, blank=True, null=True)
    simple = models.MultiPolygonField(srid=3785, blank=True, null=True)
    version = models.PositiveIntegerField(default=0)
    objects = models.GeoManager()
    
    
    def sortKey(self):
        """This can be used to sort districts by name, with numbered districts first
        """
        name = self.name;
        if name.startswith('District '):
            name = name.rsplit(' ', 1)[1]
        if name.isdigit():
            return '%03d' % int(name)
        return name 

    def sortVer(self):
        """This method generates a key that is used to sort a list of
        districts first by district_id, then by version number."""
        return self.district_id * 10000 + self.version

    def is_latest_version(self):
        """Determine if this district is the latest version of the district
        stored. If a district is not assigned to a plan, it is always 
        considered the latest version.
        """
        if self.plan:
            qset = self.plan.district_set.filter(district_id=self.district_id)
            maxver = qset.aggregate(Max('version'))['version__max']

            return self.version == maxver
        return true

    def __unicode__(self):
        return self.name

#    def update_stats(self,force=False):
#        """Update the stats for this district, and save them in the
#        ComputedCharacteristic table. This method aggregates the statistics
#        for all the geounits in the mapping table for this district.
#        """
#        all_subjects = Subject.objects.all().order_by('name').reverse()
#        changed = False
#        for subject in all_subjects:
#            computed = self.computedcharacteristic_set.filter(subject=subject).count()
#            if computed > 0 and not force:
#                continue
#
#            if force:
#                my_geounits = Geounit.get_base_geounits_within(self.geom)
#                DistrictGeounitMapping.objects.filter(geounit__in=my_geounits,plan=self.plan).update(district=self)
#            else:
#                my_geounits = DistrictGeounitMapping.objects.filter(district=self).values_list('geounit', flat=True)
#
#            aggregate = Characteristic.objects.filter(geounit__in=my_geounits, subject__exact = subject).aggregate(Sum('number'))['number__sum']
#
#            if aggregate:
#                computed = None
#                if force:
#                    computed = ComputedCharacteristic.objects.filter(subject=subject, district=self)
#                    if computed.count() > 0:
#                        computed.update(number=aggregate)
#                        changed = True
#                    else:
#                        computed = None
#
#                if computed is None:
#                    computed = ComputedCharacteristic(subject = subject, district = self, number = aggregate)
#                    computed.save()
#                    changed = True
#
#        return changed

    def delta_stats(self,geounits,combine):
        """Update the stats for this district incrementally. This method
        iterates over all the computed characteristics and adds or removes
        the characteristic values for the specific geounits only.
        """
        all_subjects = Subject.objects.all()
        changed = False
        for subject in all_subjects:
            aggregate = Characteristic.objects.filter(geounit__in=geounits, subject__exact=subject).aggregate(Sum('number'))['number__sum']
            if aggregate:
                computed = ComputedCharacteristic.objects.filter(subject=subject,district=self)
                if computed:
                    computed = computed[0]
                else:
                    computed = ComputedCharacteristic(subject=subject,district=self,number=0)

                if combine:
                    # #print "Adding %f to district '%s' for subject '%s'" % (aggregate, self.name, subject.display)
                    computed.number += aggregate
                else:
                    # #print "Removing %f from district '%s' for subject '%s'" % (aggregate, self.name, subject.display)
                    computed.number -= aggregate
                computed.save();
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

    class Meta:
        ordering = ['subject']

#def collect_geom(sender, **kwargs):
#    kwargs['instance'].geom = kwargs['instance'].geounits.collect()

def set_district_id(sender, **kwargs):
    """When a new district is saved, it should get an incremented id that is unique to the plan
    """
    from django.core.exceptions import ValidationError
    district = kwargs['instance']
    if (not district.district_id):
        max_id = District.objects.filter(plan = district.plan).aggregate(Max('district_id'))['district_id__max']
        #print 'Max id for plan %d' % district.plan_id
        if max_id:
            district.district_id = max_id + 1
        else:
            district.district_id = 1
        # Unassigned is not counted in MAX_DISTRICTS
        if district.district_id > settings.MAX_DISTRICTS + 1:
            raise ValidationError("Too many districts already.  Reached Max Districts setting")

def update_plan_edited_time(sender, **kwargs):
    district = kwargs['instance']
    plan = district.plan;
    plan.edited = datetime.now()
    plan.save()

pre_save.connect(set_district_id, sender=District)
post_save.connect(update_plan_edited_time, sender=District)

def set_geounit_mapping(sender, **kwargs):
    """When a new plan is saved, all geounits must be inserted into the Unassigned districts and a 
    corresponding set of DistrictGeounitMappings should be applied to it.
    """
    plan = kwargs['instance']
    created = kwargs['created']
    
    if created:
        unassigned = District(name="Unassigned", version = 0, plan = plan)
        unassigned.save()
        
#        # clone all the geounits manually
#        from django.db import connection, transaction
#        cursor = connection.cursor()
#
#        sql = "insert into %s (district_id, geounit_id, plan_id) select %s as district_id, geounit.id as geounit_id, %s as plan_id from %s as geounit where geounit.geolevel_id = %s" % (DistrictGeounitMapping._meta.db_table, unassigned.id, plan.id, Geounit._meta.db_table, settings.BASE_GEOLEVEL)
#        cursor.execute(sql)
#        transaction.commit_unless_managed()

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

# this constant is used in places where geometry exceptions occur, or where
# geometry types are incompatible
def empty_geom(srid):
    geom = GEOSGeometry('POINT(0 0)')
    geom = geom.intersection(GEOSGeometry('POINT(1 1)'))
    geom.srid = srid
    return geom

def enforce_multi(geom):
    #print "Enforcing on %s" % geom
    if geom:
        if geom.geom_type == 'MultiPolygon':
            return geom
        elif geom.geom_type == 'Polygon':
            return MultiPolygon(geom)
        else:
            return empty_geom(geom.srid)
    else:
        return geom
