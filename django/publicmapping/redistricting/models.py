"""
Define the models used by the redistricting app.

The classes in redistricting.models define the data models used in the 
application. Each class relates to one table in the database; foreign key
fields may define a second, intermediate table to map the records to one
another.

This file is part of The Public Mapping Project
http://sourceforge.net/projects/publicmapping/

License:
    Copyright 2010 Micah Altman, Michael McDonald

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

Author: 
    Andrew Jennings, David Zwarg, Kenny Shepard
"""

from django.core.exceptions import ValidationError
from django.contrib.gis.db import models
from django.contrib.gis.gdal import DataSource
from django.contrib.gis.geos import MultiPolygon,GEOSGeometry,GEOSException,GeometryCollection,Point
from django.contrib.auth.models import User
from django.db.models import Sum, Max, Q, Count
from django.db.models.signals import pre_save, post_save
from django.db import connection, transaction
from django.forms import ModelForm
from django.conf import settings
from django.utils import simplejson as json
from datetime import datetime
from redistricting.calculators import *
from copy import copy
import sys


class Subject(models.Model):
    """
    A classification of a set of Characteristics.

    A Subject classifies theC haracteristics of a Geounit. Or, each Geounit
    has one Characteristic per Subject.

    If you think about it in GIS terms: 
        a Geounit is a Feature,
        a Subject is an Attribute on a Geounit, and
        a Characteristic is a Data Value for a Subject.
    """

    # The name of the subject (POPTOT)
    name = models.CharField(max_length=50)

    # The display name of the subject (Total Population)
    display = models.CharField(max_length=200, blank=True)

    # A short display name of the subject (Tot. Pop.)
    short_display = models.CharField(max_length = 25, blank=True)

    # A description of this subject
    description = models.CharField(max_length= 500, blank=True)

    # If this subject should be displayed as a percentage,
    # a district's value for this subject will be divided by
    # the value for the given subject.
    # A null value indicates that the subject is not a percentage
    percentage_denominator = models.ForeignKey('Subject',null=True,blank=True)

    # A flag that indicates if this subject should be displayed.
    is_displayed = models.BooleanField(default=True)

    # The position that this subject should be in, relative to all other
    # Subjects, when viewing the subjects in a list.
    sort_key = models.PositiveIntegerField(default=1)

    # The way this Subject's values should be represented.
    format_string = models.CharField(max_length=50, blank=True)

    class Meta:
        """
        Additional information about the Subject model.
        """

        # The default method of sorting Subjects should be by 'sort_key'
        ordering = ['sort_key']

    def __unicode__(self):
        """
        Represent the Subject as a unicode string. This is the Geounit's 
        display name.
        """
        return self.display


class LegislativeBody(models.Model):
    """
    A legislative body that plans belong to. This is to support the
    scenario where one application is supporting both "Congressional"
    and "School District" contests, for example.
    """

    # The name of this legislative body
    name = models.CharField(max_length=256)

    # The name of the units in a plan -- "Districts", for example.
    member = models.CharField(max_length=32)

    # The maximum number of districts in this body
    max_districts = models.PositiveIntegerField()

    def get_default_subject(self):
        """
        Get the default subject for display. This is related to the
        LegislativeBody via the LegislativeDefault table.

        Returns:
            The default subject for the legislative body.
        """
        ldef = self.legislativedefault_set.all()
        return ldef[0].target.subject

    def get_base_geolevel(self):
        """
        Get the base geolevel for this legislative body. Each legislative
        body contains multiple geolevels, which are nested. There is only
        one parent geolevel per legislative body, the one with no parent
        above it.

        Returns:
            The base geolevel in this legislative body.
        """
        subj = self.get_default_subject()
        levels = self.legislativelevel_set.filter(target__subject=subj,parent=None)
        return levels[0].geolevel.id

    def get_geolevels(self):
        """
        Get the geolevel heirarchy for this legislative body. This returns
        a list of geolevels that exist in the legislative body, in the
        order in which they are related.
        """
        subject = self.get_default_subject()
        geobodies = self.legislativelevel_set.filter(target__subject=subject)

        ordered = []
        allgeobodies = len(geobodies)
        while len(ordered) < allgeobodies:
            foundbody = False
            for geobody in geobodies:
                if len(ordered) == 0 and geobody.parent is None:
                    # add the first geobody (the one with no parent)
                    ordered.append(geobody)
                    foundbody = True
                elif len(ordered) > 0 and ordered[len(ordered)-1] == geobody.parent:
                    # add the next geobody if it's parent matches the last
                    # geobody appended
                    ordered.append(geobody)
                    foundbody = True

            if not foundbody:
                allgeobodies -= 1

        def glonly(item):
            return item.geolevel

        ordered = map(glonly,ordered)

        ordered.reverse()
        return ordered

    def __unicode__(self):
        """
        Represent the LegislativeBody as a unicode string. This is the 
        LegislativeBody's name.
        """
        return self.name

    class Meta:
        verbose_name_plural = "LegislativeBodies"


class Geolevel(models.Model):
    """
    A geographic classification for Geounits.

    For example, a Geolevel is the concept of 'Counties', where each 
    Geounit is an instance of a county.  There are many Geounits at a
    Geolevel.
    """

    # The name of the geolevel
    name = models.CharField(max_length = 50)

    # Each geolevel has a maximum and a minimum zoom level at which 
    # features on the map can be selected and added to districts

    # The minimum zoom level
    min_zoom = models.PositiveIntegerField(default=0)

    # The position that this geolevel should be in, relative to all other
    # geolevels, when viewing the geolevels in a list.
    sort_key = models.PositiveIntegerField(default=1)

    # The geographic tolerance of this geographic level, for simplification
    tolerance = models.FloatField(default=10)

    class Meta:
        """
        Additional information about the Subject model.
        """

        # The default method of sorting Geolevels should be by 'sort_key'
        ordering = ['sort_key']

    def __unicode__(self):
        """
        Represent the Geolevel as a unicode string. This is the Geolevel's 
        name.
        """
        return self.name


class LegislativeDefault(models.Model):
    """
    The default settings for a legislative body.
    """

    # The legislative body
    legislative_body = models.ForeignKey(LegislativeBody)

    # The subject for characteristics in this body
    target = models.ForeignKey('Target')

    class Meta:
        unique_together = ('legislative_body',)

    def __unicode__(self):
        return '%s - %s' % (self.legislative_body.name, self.target)


class LegislativeLevel(models.Model):
    """
    A geographic classification in a legislative body.

    A geographic classification can be "Counties", and this classification
    can exist in both "State Senate" and "State House" legislative
    bodies.
    """

    # The geographic classification
    geolevel = models.ForeignKey(Geolevel)

    # The legislative body
    legislative_body = models.ForeignKey(LegislativeBody)

    # Parent geographic classification in this legislative level
    parent = models.ForeignKey('LegislativeLevel',null=True,blank=True)

    # The target that refers to this level
    target = models.ForeignKey('Target',null=True)

    def __unicode__(self):
        """
        Represent the LegislativeLevel as a unicode string. This is the
        LegislativeLevel's LegislativeBody and Geolevel
        """
        return "%s, %s, %s" % (self.legislative_body.name, self.geolevel.name, self.target)

    class Meta:
        unique_together = ('geolevel','legislative_body','target',)


class Geounit(models.Model):
    """
    A discrete areal unit.

    A Geounit represents an area at a Geolevel. There are many Geounits at
    a Geolevel. If 'Counties' was a Geolevel, 'Adams County' would be a
    Geounit at that Geolevel.
    """

    # The name of the geounit. If a geounit doesn't have a name (in the
    # instance of a census tract or block), this can be the ID or FIPS code.
    name = models.CharField(max_length=200)

    # The field used when exporting or importing plans from District Index Files
    portable_id = models.CharField(max_length=50, db_index=True, blank=True, null=True)

    # An identifier used by the data ingestion process.  This number is a
    # concatenated series of identifiers identifying parent-child relationships
    tree_code = models.CharField(max_length=50, db_index=True, blank=True, null=True)

    # The ID of the geounit that contains this geounit
    child = models.ForeignKey('Geounit',null=True,blank=True)

    # The full geometry of the geounit (high detail).
    geom = models.MultiPolygonField(srid=3785)

    # The lite geometry of the geounit (generated from geom via simplify).
    simple = models.MultiPolygonField(srid=3785)

    # The centroid of the geometry (generated from geom via centroid).
    center = models.PointField(srid=3785)

    # The geographic level of this Geounit
    geolevel = models.ForeignKey(Geolevel)

    # Manage the instances of this class with a geographically aware manager
    objects = models.GeoManager()

    @staticmethod
    def get_mixed_geounits(geounit_ids, legislative_body, geolevel, boundary, inside):
        """
        Spatially search for the largest Geounits inside or outside a 
        boundary.

        Search for Geounits in a multipass search. The searching method
        gets Geounits inside a boundary at a Geolevel, then determines
        if there is a geographic remainder, then repeats the search at
        a smaller Geolevel inside the specified LegislativeBody, until 
        the base Geolevel is reached.

        Parameters:
            geounit_ids -- A list of Geounit IDs. Please note that these
                must be int datatypes, and not str.
            legislative_body -- The LegislativeBody that contains this 
                geolevel.
            geolevel -- The ID of the Geolevel that contains geounit_ids
            boundary -- The GEOSGeometry that defines the edge of the
                spatial search area.
            inside -- True or False to search inside or outside of the 
                boundary, respectively.

        Returns:
            A list of Geounit objects, with the ID, child, geolevel,
            and Geometry fields populated.
        """
        if not boundary and inside:
            # there are 0 geounits inside a non-existant boundary
            return []

        # Make sure the geolevel is a number
        geolevel = int(geolevel)
        levels = legislative_body.get_geolevels()
        base_geolevel = levels[len(levels)-1]
        selection = None
        units = []
        searching = False
        for level in levels:
            # if this geolevel is the requested geolevel
            if geolevel == level.id:
                searching = True
                guFilter = Q(id__in=geounit_ids)

                # Get the area defined by the union of the geounits
                selection = Geounit.objects.filter(guFilter).collect()

                # Union as a cascade - this is faster than the union
                # spatial aggregate function off the filter
                polycomponents = []
                for geom in selection:
                    if geom.geom_type == 'MultiPolygon':
                        for poly in geom:
                            polycomponents.append(poly)
                    elif geom.geom_type == 'Polygon':
                        polycomponents.append(geom)
                selection = MultiPolygon(polycomponents,srid=selection.srid).cascaded_union
               
                # Begin crafting the query to get the id and geom
                query = "SELECT id,child_id,geolevel_id,st_ashexewkb(geom,'NDR') FROM redistricting_geounit WHERE id IN (%s) AND " % (','.join(geounit_ids))

                # create a boundary if one doesn't exist
                if not boundary:
                    boundary = empty_geom(selection.srid)

                if inside:
                    # Searching inside the boundary
                    if level != base_geolevel:
                        # Search by geometry
                        query += "st_within(geom, geomfromewkt('%s'))" % boundary.ewkt
                    else:
                        # Search by centroid
                        query += "st_intersects(center, geomfromewkt('%s'))" % boundary.ewkt
                else:
                    # Searching outside the boundary
                    if level != base_geolevel:
                        # Search by geometry
                        query += "NOT st_intersects(geom, geomfromewkt('%s'))" % boundary.ewkt
                    else:
                        # Search by centroid
                        query += "NOT st_intersects(center, geomfromewkt('%s'))" % boundary.ewkt

                # Execute our custom SQL
                cursor = connection.cursor()
                cursor.execute(query)
                rows = cursor.fetchall()
                count = 0
                for row in rows:
                    count += 1
                    geom = GEOSGeometry(row[3])
                    # Create a geounit, and add it to the list of units
                    units.append(Geounit(id=row[0],geom=geom,child_id=row[1],geolevel_id=row[2]))

                # if we're at the base level, and haven't collected any
                # geometries, return the units here
                if level == base_geolevel:
                    return units

            # only query geolevels below (smaller in size, after the 
            # primary search geolevel) the geolevel parameter
            elif searching:
                # union the selected geometries
                if len(units) == 0:
                    union = None
                else:
                    # this always rebuilds the current extent of all the
                    # selected geounits
                    geoms = []
                    for unit in units:
                        if unit.geom.geom_type == 'MultiPolygon':
                            for geo in unit.geom:
                                geoms.append(geo)
                        elif unit.geom.geom_type == 'Polygon':
                            geoms.append(unit.geom)
                    # cascaded union is faster than unioning each unit
                    # to it's neighbor
                    union = MultiPolygon(geoms).cascaded_union

                # set or merge this onto the existing selection
                if union is None:
                    intersects = selection
                else:
                    intersects = selection.difference(union)

                if inside:
                    # the remainder geometry is the intersection of the 
                    # district and the difference of the selected geounits
                    # and the current extent
                    try:
                        remainder = boundary.intersection(intersects)
                    except GEOSException, ex:
                        # it is not clear what this means
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
                        # it is not clear what this means, or why it happens
                        remainder = empty_geom(boundary.srid)

                # Check if the remainder is a geometry collection. If it 
                # is, munge it into a multi-polygon so that we can use it 
                # in our custom sql query
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
                            pass

                    remainder = union
                    if remainder:
                        remainder.srid = srid
                    else:
                        remainder = empty_geom(srid)
                elif remainder.empty or (remainder.geom_type != 'MultiPolygon' and remainder.geom_type != 'Polygon'):
                    remainder = empty_geom(boundary.srid)

                # Check if the remainder is empty -- it may have been 
                # converted, or errored out above, in which case we just
                # have to move on.
                if not remainder.empty:
                    query = "SELECT id,child_id,geolevel_id,st_ashexewkb(geom,'NDR') FROM redistricting_geounit WHERE geolevel_id = %d AND " % level.id

                    if level == base_geolevel:
                        # Query by center
                        query += "st_intersects(center, geomfromewkt('%s'))" % remainder.ewkt
                    else:
                        # Query by geom
                        query += "st_within(geom, geomfromewkt('%s'))" % remainder.ewkt

                    # Execute our custom SQL
                    cursor = connection.cursor()
                    cursor.execute(query)
                    rows = cursor.fetchall()
                    count = 0
                    for row in rows:
                        count += 1
                        units.append(Geounit(id=row[0],geom=GEOSGeometry(row[3]),child_id=row[1],geolevel_id=row[2]))

        # Send back the collected Geounits
        return units

    def __unicode__(self):
        """
        Represent the Geounit as a unicode string. This is the Geounit's 
        name.
        """
        return self.name

class Characteristic(models.Model):
    """
    A data value for a Geounit's Subject.

    A Characteristic is the numerical data value measured for a Geounit for
    a specific Subject. For example, this could be 1,200 for the Total 
    Population of Ada County.
    """

    # The subject that this value relates to
    subject = models.ForeignKey(Subject)
    # The Geounit that this value relates to
    geounit = models.ForeignKey(Geounit)
    # The value as a raw decimal number
    number = models.DecimalField(max_digits=12,decimal_places=4)
    # The value as a percentage of the value for this geounit of the subject given as 
    # the percentage_denominator (if any)
    percentage = models.DecimalField(max_digits=12,decimal_places=8, null=True, blank=True)

    def __unicode__(self):
        """
        Represent the Characteristic as a unicode string. The 
        Characteristic string is in the form of "Subject for Geounit: 
        Number"
        """
        return u'%s for %s: %s' % (self.subject, self.geounit, self.number)

class Target(models.Model):
    """
    A set of data values that bound the ComputedCharacteristics of a 
    District.

    A Target contains the upper and lower bounds for a Subject. When 
    editing districts, these targets are used by the symbolizers to 
    represent districts as over or under the target range.
    """

    # The subject that this target relates to
    subject = models.ForeignKey(Subject)

    # The first range value
    range1 = models.DecimalField(max_digits=12,decimal_places=4)

    # The second data value
    range2 = models.DecimalField(max_digits=12,decimal_places=4)

    # The central data value
    value = models.DecimalField(max_digits=12,decimal_places=4)

    class Meta:
        """
        Additional information about the Target model.
        """
        ordering = ['subject']

    def __unicode__(self):
        """
        Represent the Target as a unicode string. The Target string is
        in the form of "Subject : Value (Range1 - Range2)"
        """
        return u'%s : %s (%s - %s)' % (self.subject, self.value, self.range1, self.range2)

class Plan(models.Model):
    """
    A collection of Districts for an area of coverage, like a state.

    A Plan is created by a user to represent multiple Districts. A Plan
    may be a template (created by admins, copyable by all users), or shared
    (created by users, copyable by all users).  In addition, Plans are 
    versioned; the Plan version is the most recent version of all Districts
    that are a part of this Plan.
    """

    # The name of this plan
    name = models.CharField(max_length=200)

    # A description of the plan
    description = models.CharField(max_length=500, db_index=True, blank=True)

    # Is this plan a template?
    is_template = models.BooleanField(default=False)

    # Is this plan shared?
    is_shared = models.BooleanField(default=False)

    # Is this plan 'pending'? Pending plans are being constructed in the
    # backend, and should not be visible in the UI
    is_pending = models.BooleanField(default=False)

    # Is this plan considered a valid plan based on validation criteria?
    is_valid = models.BooleanField(default=False)

    # The most recent version of the districts in this plan.
    version = models.PositiveIntegerField(default=0)

    # The time when this Plan was created.
    created = models.DateTimeField(auto_now_add=True)

    # The time when this Plan was edited.
    edited = models.DateTimeField(auto_now=True)

    # The owner of this Plan
    owner = models.ForeignKey(User)

    # The legislative body that this plan is for
    legislative_body = models.ForeignKey(LegislativeBody)

    def __unicode__(self):
        """
        Represent the Plan as a unicode string. This is the Plan's name.
        """
        return self.name

    class Meta:
        """
        Define a unique constraint on 2 fields of this model.
        """
        unique_together = ('name','owner','legislative_body',)

    
    def targets(self):
        """
        Get the targets associated with this plan by stepping back through
        the legislative body and finding distinct targets for displayed subjects
        among all the geolevels in the body. This will return a django queryset
        if successful.
        """
        try:
            levels = LegislativeLevel.objects.filter(legislative_body = self.legislative_body).values('target').distinct()
            targets = Target.objects.filter(id__in=levels, subject__is_displayed = True)
            return targets
        except Exception as ex:
            sys.stderr.write('Unable to get targets for plan %s: %s' % (self.name, ex))
            raise ex

    def get_nth_previous_version(self, steps):
        """
        Get the version of this plan N steps away.

        Since editing a plan in its history purges higher versions of the
        districts in the plan, the version numbers become discontinuous.
        In order to support purging with these discontinuous version 
        numbers, this method assists in finding the valid version number
        of the plan that is so many steps behind the current plan.

        This problem does not occur when purging higher numbered versions 
        from a plan.

        Parameters:
            steps -- The number of 'undo' steps away from the current 
                     plan's version.

        Returns:
            A valid version of this plan in the past.
        """
        versions = self.district_set.order_by('-version').values('version').annotate(count=Count('version'))

        if steps < len(versions):
            return versions[steps]['version']

        # if the number of steps exceeds the total history of the
        # plan, the version cannot be less than zero. In addition,
        # all plans are guaranteed to have a version 0.
        return 0;


    def purge(self, before=None, after=None):
        """
        Purge portions of this plan's history.

        Use one of 'before' or 'after' keywords to purge either direction.
        If both are used, only the versions before will be purged.

        Keywords:
            before -- purge the history of this plan prior to this version.
            after -- purge the history of this plan after this version.
        """
        if before is None and after is None:
            return

        if not before is None:
            # Can't purge before zero, since that's the starting point
            if before <= 0:
                return

            ds = self.get_districts_at_version(before, include_geom=False)
            allQ = Q(plan__isnull=True)
            for d in ds:
                maxqset = self.district_set.filter(district_id=d.district_id)
                maxver = maxqset.aggregate(Max('version'))['version__max']
                # Filter on this district
                q1 = Q(district_id=d.district_id)
                if d.version == maxver:
                    # If the maximum version of this district across all 
                    # edits is the same as this district's version, only 
                    # purge the districts BEFORE the version specified.
                    q2 = Q(version__lt=d.version)
                else:
                    # If the maximum version of this district across all
                    # edits is greater than the version specified, you can
                    # safely purge the district at this version and below
                    # with no harm of deleting the last version of the
                    # district.
                    q2 = Q(version__lte=d.version)
               
                # Accumulate the criteria
                allQ = allQ | (q1 & q2)

            # delete everything all at once
            self.district_set.filter(allQ).delete()

        else:
            # Purge any districts between the version provided
            # and the latest version
            self.district_set.filter(version__gt=after).delete()

    @transaction.commit_on_success
    def add_geounits(self, districtid, geounit_ids, geolevel, version):
        """
        Add Geounits to a District. When geounits are added to one 
        District, they are also removed from whichever district they're 
        currently in. 

        NOTE: All calls to 'simplify' use the spatial units -- the map 
        units in web mercator are meters, so simplify(tolerance=100.0) 
        simplifies geometries to 100 meters between points (-ish).

        Parameters:
            districtid -- The district_id (NOT the id) of the
                destination District.
            geounit_ids -- A list of Geounit ids that are to be added
                to the District.
            geolevel -- The Geolevel of the geounit_ids.
            version -- The version of the Plan that is being modified.

        Returns:
            Either 1) the number of Districts changed if adding geounits 
            to a district that already exists; 2) the name of the district
            created with the passed geounits.
        """

        # fix the district id so that it is definitely an integer
        districtid = int(districtid)

        # fix the version so that it is definitely an integer
        version = int(version)
        
        # incremental is the geometry that is changing
        incremental = Geounit.objects.filter(id__in=geounit_ids).unionagg()

        fixed = False

        # Get the districts in this plan, at the specified version.
        districts = self.get_districts_at_version(version, include_geom=True)

        # Check if the target district is locked
        if any((ds.is_locked and ds.district_id == districtid) for ds in districts):
            return False

        # Collect locked district geometries, and remove locked sections
        locked = District.objects.filter(id__in=[d.id for d in districts if d.is_locked]).collect()
        if locked:
            # GEOS topology exceptions are sometimes thrown when performing a difference
            # on compledx geometries unless a buffer(0) is first performed.
            locked = locked if locked.empty else locked.buffer(0)
            incremental = incremental if locked.empty else incremental.difference(locked)

        self.purge(after=version)

        target = None

        # First, remove the aggregate values from districts that are
        # not the target, and intersect the geounits provided
        for district in districts:
            if district.district_id == districtid:
                # If the district_id is the target, save the target.
                target = district
                continue

            if not (district.geom and \
                (district.geom.overlaps(incremental) or \
                 district.geom.contains(incremental) or \
                 district.geom.within(incremental))):
                # if this district has later edits, REVERT them to
                # this version of the district
                if not district.is_latest_version():
                    # Clone the district to a new version, with a different
                    # shape
                    district_copy = copy(district)
                    district_copy.version = self.version + 1
                    district_copy.id = None
                    district_copy.save()

                    # Clone the characteristings to this new version
                    district_copy.clone_characteristics_from(district)

                    fixed = True

                # go onto the next district
                continue

            # compute the geounits before changing the boundary
            geounits = Geounit.get_mixed_geounits(geounit_ids, self.legislative_body, geolevel, district.geom, True)

            # Set the flag to indicate that the districts have been fixed
            if len(geounits) > 0:
                fixed = True

            # Difference the district with the selection
            # This may throw a GEOSException, in which case this function
            # will not complete successfully, and all changes will be
            # rolled back, thanks to the decorator commit_on_success
            try:
                geom = district.geom.difference(incremental)
            except GEOSException, ex:
                # Can this be logged?
                raise ex

            # Make sure the geom is a multi-polygon.
            geom = enforce_multi(geom)

            # If the geometry of this district is empty
            if geom.empty:
                # The district geometry is empty (probably all geounits in
                # the district were removed); empty the geom and simple 
                # fields
                district.geom = None
            else:
                # The district geometry exists, so save the updated 
                # versions of the geom and simple fields
                district.geom = geom

            # Clone the district to a new version, with a different shape
            district_copy = copy(district)
            district_copy.version = self.version + 1
            district_copy.id = None
            district_copy.save() # this auto-generates a district_id

            # There is always a geometry for the district copy
            district_copy.simplify() # implicit save

            # Clone the characteristings to this new version
            district_copy.clone_characteristics_from(district)

            # Update the district stats
            district_copy.delta_stats(geounits,False)

        new_target = False
        if target is None:
            # create a temporary district
            try:
                name = self.legislative_body.member % (districtid-1)
            except:
                name = str(districtid-1)
            target = District(name=name, plan=self, district_id=districtid, version=self.version)
            target.save()
            new_target = True
                
        # If there are locked districts: augment the district boundary with the
        # boundary of the locked area, because get_mixed_geounits is getting
        # the geounits that lie outside of the provided geometry, but
        # within the boundaries of the geounit ids.
        bounds = target.geom.union(locked) if locked else target.geom

        # get the geounits before changing the target geometry
        geounits = Geounit.get_mixed_geounits(geounit_ids, self.legislative_body, geolevel, bounds, False)

        # set the fixed flag, since the target has changed
        if len(geounits) > 0:
            fixed = True

        # If there exists geometry in the target district
        if target.geom:
            # Combine the incremental (changing) geometry with the existing
            # target geometry
            # This may throw a GEOSException, in which case this function
            # will not complete successfully, and all changes will be
            # rolled back, thanks to the decorator commit_on_success
            try:
                union = target.geom.union(incremental)
                target.geom = enforce_multi(union)
            except GEOSException, ex:
                # Can this be logged?
                raise ex
        else:
            # Set the target district's geometry to the sum of the changing
            # Geounits
            target.geom = enforce_multi(incremental)

        # Clone the district to a new version, with a different shape.
        target_copy = copy(target)
        target_copy.version = self.version + 1
        target_copy.id = None

        target_copy.simplify() # implicit save happens here

        # Clone the characteristics to this new version
        target_copy.clone_characteristics_from(target)

        # Update the district stats
        target_copy.delta_stats(geounits,True)

        # save any changes to the version of this plan
        self.version += 1
        self.save()

        # Turn this on once client-side undo is limited to 5 versions.
        # Tweak or make the parameter to get_nth_previous_version 
        # configurable.
        #
        #prever = self.get_nth_previous_version(5)
        #if prever > 0:
        #    self.purge(before=prever)
        #

        # purge the old target if a new one was created
        if new_target:
            District.objects.filter(id=target.id).delete()

        # Return a flag indicating any districts changed
        return fixed


    def get_wfs_districts(self,version,subject_id,extents,geolevel):
        """
        Get the districts in this plan as a GeoJSON WFS response.
        
        This method behaves much like a WFS service, returning the GeoJSON 
        for each district. This manual view exists because the limitations
        of filtering and the complexity of the version query -- it is 
        impossible to use the WFS layer in Geoserver automatically.

        Parameters:
            version -- The Plan version.
            subject_id -- The Subject attributes to attach to the district.
            extent -- The map extents.

        Returns:
            GeoJSON describing the Plan.
        """
        
        cursor = connection.cursor()
        query = "SELECT rd.id, rd.district_id, rd.name, rd.is_locked, lmt.version, rd.plan_id, rc.subject_id, rc.number, st_asgeojson(st_geometryn(rd.simple,%d)) AS geom FROM redistricting_district rd JOIN redistricting_computedcharacteristic rc ON rd.id = rc.district_id JOIN (SELECT max(version) as version, district_id FROM redistricting_district WHERE plan_id = %d AND version <= %d GROUP BY district_id) AS lmt ON rd.district_id = lmt.district_id WHERE rd.plan_id = %d AND rc.subject_id = %d AND lmt.version = rd.version AND st_intersects(st_geometryn(rd.simple,%d),st_envelope(('SRID='||(select st_srid(rd.simple))||';LINESTRING(%f %f,%f %f)')::geometry))" % (geolevel, int(self.id), int(version), int(self.id), int(subject_id), geolevel, extents[0], extents[1], extents[2], extents[3])

        # Execute our custom query
        cursor.execute(query)
        rows = cursor.fetchall()
        features = []
        for row in rows:
            district = District.objects.get(pk=int(row[0]))
            # Maybe the most recent district is empty
            if row[8]:
                geom = json.loads( row[8] )
            else:
                geom = None
            features.append({ 
                'id': row[0],
                'properties': {
                    'district_id': row[1],
                    'name': row[2],
                    'is_locked': row[3],
                    'version': row[4],
                    'number': float(row[7]),
                    'contiguous': district.is_contiguous(),
                    'compactness': Schwartzberg(district).calculate()
                },
                'geometry': geom
            })

        # Return a python dict, which gets serialized into geojson
        return features

    def get_districts_at_version(self, version, include_geom=False):
        """
        Get Plan Districts at a specified version.

        When a district is changed, a copy of the district is inserted
        into the database with an incremented version number. The plan version
        is also incremented.  This method returns all of the districts
        in the given plan at a particular version.

        Parameters:
            version -- The version of the Districts to fetch.
            include_geom -- Should the geometry of the district be fetched?

        Returns:
            A list of districts that exist in the plan at the version.
        """

        if include_geom:
            fields = 'd.*'
        else:
            fields = 'd.id, d.district_id, d.name, d.plan_id, d.version, d.is_locked'

        return sorted(list(District.objects.raw('select %s from redistricting_district as d join (select max(version) as latest, district_id, plan_id from redistricting_district where plan_id = %%s and version <= %%s group by district_id, plan_id) as v on d.district_id = v.district_id and d.plan_id = v.plan_id and d.version = v.latest' % fields, [ self.id, version ])), key=lambda d: d.sortKey())

    @staticmethod
    def create_default(name,body,owner=None,template=True,is_pending=True):
        """
        Create a default plan.

        Parameters:
            name - The name of the plan to create.
            owner - The system user that will own this plan.

        Returns:
            A new plan, owned by owner, with one district named 
            "Unassigned".
        """

        if not owner:
            # if no owner, admin gets this template
            owner = User.objects.get(username=settings.ADMINS[0][0])

        # Create a new plan. This will also create an Unassigned district
        # in the the plan.
        plan = Plan(name=name, legislative_body=body, is_template=template, version=0, owner=owner, is_pending=is_pending)
        try:
            plan.save()
        except Exception as ex:
            sys.stderr.write( "Couldn't save plan: %s\n" % ex )
            return None

        return plan

    def get_base_geounits_in_geom(self, geom, threshold=100, simplified=False):
        """
        Get a list of the geounit ids of the geounits that comprise 
        this geometry at the base level.  

        Parameters:
            threshold - distance threshold used for buffer in/out optimization
            simplified - denotes whether or not the geom passed in is already simplified

        Returns:
            A list of tuples containing Geounit IDs and portable ids
            that lie within this geometry. 
        """

        if not geom:
           return list()

        # Simplify by the same distance threshold used for buffering
        # Note: the preserve topology parameter of simplify is needed here
        simple = geom if simplified else geom.simplify(threshold, True)

        # If the simplification makes the polygon empty, use the unsimplified polygon
        simple = simple if not simple.empty else geom

        # Perform two queries against the simplified district, one buffered in,
        # and one buffered out using the same distance as the simplification tolerance
        geolevel = self.legislative_body.get_base_geolevel()
        b_out = Geounit.objects.filter(geolevel=geolevel, center__within=simple.buffer(threshold))
        b_in = Geounit.objects.filter(geolevel=geolevel, center__within=simple.buffer(-1 * threshold))

        # Find the geounits that are different between the two queries,
        # and check if they are within the unsimplified district
        b_in_values_set = set(b_in.values_list('id', 'portable_id'))
        b_out_values_set = set(b_out.values_list('id', 'portable_id'))
        diff = set(b_out_values_set ^ b_in_values_set)
        diffwithin = []
        if len(diff) > 0:
            diffids = reduce(lambda x,y: x+y, list(diff))
            diffwithin = [(unit.id, unit.portable_id) for unit in Geounit.objects.filter(id__in=diffids) if unit.center.within(geom)]

        # Combine the geounits that were within the unsimplifed district with the buffered in list
        return list(b_in_values_set | set(diffwithin))

    def get_base_geounits(self, threshold=100):
        """
        Get a list of the geounit ids of the geounits that comprise 
        this plan at the base level.  

        Parameters:
            threshold - distance threshold used for buffer in/out optimization

        Returns:
            A list of tuples containing Geounit IDs, portable ids,
            and district ids that lie within this Plan. 
        """

        # Collect the geounits for each district in this plan
        geounits = []
        for district in self.get_districts_at_version(self.version, include_geom=True):
            districtunits = district.get_base_geounits(threshold)
            # Add the district_id to the tuples
            geounits.extend([(gid, pid, district.district_id) for (gid, pid) in districtunits])
        
        return geounits

    def get_assigned_geounits(self, threshold=100):
        """
        Get a list of the geounit ids of the geounits that comprise 
        this plan at the base level. This is different than
        get_base_geounits, because it doesn't return district ids
        along with the geounit ids, and should therefore be more performant.

        Parameters:
            threshold - distance threshold used for buffer in/out optimization

        Returns:
            A list of tuples containing Geounit IDs and portable ids
            that lie within this Plan. 
        """

        # TODO: enhance performance. Tried various ways to speed this up by
        # creating a union of simplified geometries and passing it to get_base_geounits.
        # This seems like it would be faster, since the amount of query overhead is
        # reduced, but this offered no performance improvement, and instead caused
        # some accuracty issues. This needs further examination.
        geounits = []
        for district in self.get_districts_at_version(self.version,include_geom=True):
            geounits.extend(district.get_base_geounits(threshold))
        
        return geounits

    def get_unassigned_geounits(self, threshold=100):
        """
        Get a list of the geounit ids of the geounits that do not belong to
        any district of this plan at the base level. 

        Parameters:
            threshold - distance threshold used for buffer in/out optimization

        Returns:
            A list of tuples containing Geounit IDs and portable ids
            that do not belong to any districts within this Plan. 
        """

        # Find all geounits
        geolevel = self.legislative_body.get_base_geolevel()
        all = Geounit.objects.filter(geolevel=geolevel).values_list('id', 'portable_id')

        # Find all assigned geounits
        assigned = self.get_assigned_geounits(threshold)

        # Return the difference
        return list(set(all) ^ set(assigned))


class PlanForm(ModelForm):
    """
    A form for displaying and editing a Plan.
    """
    class Meta:
        """
        A helper class that describes the PlanForm.
        """

        # This form's model is a Plan
        model=Plan
    

class District(models.Model):
    """
    A collection of Geounits, aggregated together.

    A District is a part of a Plan, and is composed of many Geounits. 
    Districts have geometry, simplified geometry, and pre-computed data
    values for Characteristics.
    """

    class Meta:
        """
        A helper class that describes the District class.
        """

        # Order districts by name, by default.
        ordering = ['name']

    # The district_id of the district, this is not the primary key ID,
    # but rather, an ID of the district that remains constant over all
    # versions of the district.
    district_id = models.PositiveIntegerField(default=1)

    # The name of the district
    name = models.CharField(max_length=200)

    # The parent Plan that contains this District
    plan = models.ForeignKey(Plan)

    # The geometry of this district (high detail)
    geom = models.MultiPolygonField(srid=3785, blank=True, null=True)

    # The simplified geometry of this district
    simple = models.GeometryCollectionField(srid=3785, blank=True, null=True)

    # The version of this district.
    version = models.PositiveIntegerField(default=0)

    # A flag that indicates if this district should be edited
    is_locked = models.BooleanField(default=False)

    # This is a geographic model, so use the geomanager for objects
    objects = models.GeoManager()
    
    def sortKey(self):
        """
        Sort districts by name, with numbered districts first.

        Returns:
            The Districts, sorted in numerical order.
        """
        name = self.name;
        prefix = self.plan.legislative_body.member
        index = prefix.find('%')
        if index >= 0:
            prefix = prefix[0:index]
        else:
            index = 0

        if name.startswith(prefix):
            name = name[index:]
        if name.isdigit():
            return '%03d' % int(name)
        return name 

    def sortVer(self):
        """
        Sort a list of districts first by district_id, then by 
        version number.

        Returns:
            district_id * 1000 + self.version
        """
        return self.district_id * 10000 + self.version

    def is_latest_version(self):
        """
        Determine if this district is the latest version of the district
        stored. If a district is not assigned to a plan, it is always 
        considered the latest version.
        """
        if self.plan:
            qset = self.plan.district_set.filter(district_id=self.district_id)
            maxver = qset.aggregate(Max('version'))['version__max']

            return self.version == maxver
        return true

    def __unicode__(self):
        """
        Represent the District as a unicode string. This is the District's 
        name.
        """
        return self.name

    def delta_stats(self,geounits,combine):
        """
        Update the stats for this district incrementally. This method
        iterates over all the computed characteristics and adds or removes
        the characteristic values for the specific geounits only.

        Parameters:
            geounits -- The Geounits to add or remove to this districts
                ComputedCharacteristic value.
            combine -- The aggregate value computed should be added or
                removed from the ComputedCharacteristicValue

        Returns:
            True if the stats for this district have changed.
        """
        # Get the subjects that don't rely on others first - that will save us
        # from computing characteristics for denominators twice
        all_subjects = Subject.objects.order_by('-percentage_denominator').all()
        changed = False

        # For all subjects
        for subject in all_subjects:
            # Aggregate all Geounits Characteristic values
            aggregate = Characteristic.objects.filter(geounit__in=geounits, subject__exact=subject).aggregate(Sum('number'))['number__sum']
            # If there are aggregate values for the subject and geounits.
            if not aggregate is None:
                # Get the pre-computed values
                computed = ComputedCharacteristic.objects.filter(subject=subject,district=self)

                # If precomputed values exist
                if computed:
                    # Grab the first one. (One value should be returned)
                    computed = computed[0]
                else:
                    # Create a new computed value
                    computed = ComputedCharacteristic(subject=subject,district=self,number=0)

                if combine:
                    # Add the aggregate to the computed value
                    computed.number += aggregate
                else:
                    # Subtract the aggregate from the computed value
                    computed.number -= aggregate

                # If this subject is viewable as a percentage, do the math using the already calculated 
                # value for the denominator
                if subject.percentage_denominator:
                    denominator = ComputedCharacteristic.objects.get(subject=subject.percentage_denominator,district=self)
                    if denominator:
                        if denominator.number > 0:
                            computed.percentage = computed.number / denominator.number
                        else:
                            computed.percentage = '0000.00000000'

                # If there are aggregate values for the subject and geounits.
                computed.save();

                changed = True

        return changed
        
    def is_contiguous(self):
        """
        Checks to see if the district is contiguous.
        
        The district is already a unioned geom.  Any multipolygon with 
        more than one poly in it will not be contiguous.  There is one 
        case where this test may give a false negative - if all of the 
        polys in a multipolygon each meet another poly at one point. In 
        GIS terms, this is connected but not contiguous.  But the 
        real-word case may be different.  

        http://webhelp.esri.com/arcgisdesktop/9.2/index.cfm?TopicName=Coverage_topology.

        Returns:
            True if the district is contiguous.
        """
        if not self.geom == None:
            return len(self.geom) == 1
        else:
            return False

    def clone_characteristics_from(self, origin):
        """
        Copy the computed characteristics from one district to another.

        Cloning District Characteristics is required when cloning, 
        copying, or instantiating a template district.

        Parameters:
            origin -- The source District.
        """
        cc = ComputedCharacteristic.objects.filter(district=origin)
        for c in cc:
            c.id = None
            c.district = self
            c.save()

    def get_base_geounits(self, threshold=100):
        """
        Get a list of the geounit ids of the geounits that comprise 
        this district at the base level.  
        
        We'll check this by seeing whether the centroid of each geounits 
        fits within the simplified geometry of this district.

        Parameters:
            threshold - distance threshold used for buffer in/out optimization

        Returns:
            A list of tuples containing Geounit IDs and portable ids
            that lie within this District. 
        """
        return self.plan.get_base_geounits_in_geom(self.geom, threshold);

    def simplify(self):
        """
        Simplify the geometry into a geometry collection in the simple 
        field.

        Parameters:
            self - The district
        """
        plan = self.plan
        body = plan.legislative_body
        # This method returns the geolevels from largest to smallest
        # but we want them the other direction
        levels = body.get_geolevels()
        levels.reverse()

        if self.geom:
            simples = []
            index = 1
            for level in levels:
                while index < level.id:
                    # We want to store the levels within a GeometryCollection, and make it so the level id
                    # can be used as the index for lookups. So for disparate level ids, empty geometries need
                    # to be stored. Empty GeometryCollections cannot be inserted into a GeometryCollection,
                    # so a Point at the origin is used instead.
                    simples.append(Point((0,0), srid=self.geom.srid))
                    index += 1
                simples.append( self.geom.simplify(preserve_topology=True,tolerance=level.tolerance))
                index += 1
            self.simple = GeometryCollection(tuple(simples),srid=self.geom.srid)
            self.save()
        else:
            self.simple = None
            self.save()


class ComputedCharacteristic(models.Model):
    """
    ComputedCharacteristics are cached, aggregate values of Characteristics
    for Districts.

    ComputedCharacteristics represent the sum of the Characteristic values
    for all Geounits in a District. There will be one 
    ComputedCharacteristic per District per Subject.
    """

    # The subject
    subject = models.ForeignKey(Subject)

    # The district and area
    district = models.ForeignKey(District)

    # The total aggregate as a raw value
    number = models.DecimalField(max_digits=12,decimal_places=4)

    # The aggregate as a percentage of the percentage_denominator's aggregated value.
    percentage = models.DecimalField(max_digits=12, decimal_places=8, null=True, blank=True)

    class Meta:
        """
        A helper class that describes the ComputedCharacteristic class.
        """
        ordering = ['subject']


class Profile(models.Model):
    """
    Extra user information that doesn't fit in Django's default user
    table.

    Profiles for The Public Mapping Project include a password hint,
    and an organization name.
    """
    user = models.OneToOneField(User)

    # A user's organization
    organization = models.CharField(max_length=256)

    # A user's password hint.
    pass_hint = models.CharField(max_length=256)


def update_profile(sender, **kwargs):
    """
    A trigger that creates profiles when a user is saved.
    """
    created = kwargs['created']
    user = kwargs['instance']
    if created:
        profile = Profile(user=user, organization='', pass_hint='')
        profile.save()

def set_district_id(sender, **kwargs):
    """
    Incremented the district_id (NOT the primary key id) when a district
    is saved. The district_id is unique to the plan/version.  The 
    district_id may already be set, but this method ensures that it is set
    when saved.
    """
    district = kwargs['instance']
    if (not district.district_id):
        max_id = District.objects.filter(plan = district.plan).aggregate(Max('district_id'))['district_id__max']
        if max_id:
            district.district_id = max_id + 1
        else:
            district.district_id = 1
        # Unassigned is not counted in max_districts
        if district.district_id > (district.plan.legislative_body.max_districts + 1):            
            raise ValidationError("Too many districts already.  Reached Max Districts setting")

def update_plan_edited_time(sender, **kwargs):
    """
    Update the time that the plan was edited whenever the plan is saved.
    """
    district = kwargs['instance']
    plan = district.plan;
    plan.edited = datetime.now()
    plan.save()

def create_unassigned_district(sender, **kwargs):
    """
    When a new plan is saved, all geounits must be inserted into the 
    Unassigned districts.
    """
    plan = kwargs['instance']
    created = kwargs['created']
    
    if created:
        unassigned = District(name="Unassigned", version = 0, plan = plan)
        unassigned.save()
        
# Connect the post_save signal from a User object to the update_profile
# helper method
post_save.connect(update_profile, sender=User, dispatch_uid="publicmapping.redistricting.User")
# Connect the pre_save signal to the set_district_id helper method
pre_save.connect(set_district_id, sender=District)
# Connect the post_save signal to the update_plan_edited_time helper method
post_save.connect(update_plan_edited_time, sender=District)
# Connect the post_save signal from a Plan object to the 
# create_unassigned_district helper method (don't remove the dispatch_uid or 
# this signal is sent twice)
post_save.connect(create_unassigned_district, sender=Plan, dispatch_uid="publicmapping.redistricting.Plan")

def can_edit(user, plan):
    """
    Can a user edit a plan?
    
    In order to edit a plan, Users must own it or be a staff member.  
    Templates cannot be edited, only copied.

    Parameters:
        user -- A User
        plan -- A Plan

    Returns:
        True if the User has permissions to edit the Plan.

    """
    return (plan.owner == user or user.is_staff) and not plan.is_template and not plan.is_shared

def can_view(user, plan):
    """
    Can a user view a plan?

    In order to view a plan, the plan must have the shared flag set.

    Parameters:
        user -- A User
        plan -- A Plan

    Returns:
        True if the User has permissions to view the Plan.
    """
    return plan.is_shared or plan.is_template


def can_copy(user, plan):
    """
    Can a user copy a plan?

    In order to copy a plan, the user must be the owner, or a staff 
    member to copy a plan they own.  Any registered user can copy a 
    template.

    Parameters:
        user -- A User
        plan -- A Plan

    Returns:
        True if the User has permission to copy the Plan.
    """
    return plan.is_template or plan.is_shared or plan.owner == user or user.is_staff

def empty_geom(srid):
    """
    Create an empty GeometryCollection.

    Parameters:
        srid -- The spatial reference for this empty geometry.

    Returns:
        An empty geometry.
    """
    geom = GeometryCollection([], srid=srid)
    return geom

def enforce_multi(geom):
    """
    Make a geometry a multi-polygon geometry.

    This method wraps Polygons in MultiPolygons. If geometry exists, but is
    neither polygon or multipolygon, an empty geometry is returned. If no
    geometry is provided, no geometry (None) is returned.

    Parameters:
        geom -- The geometry to check/enforce.
    Returns:
        A multi-polygon from any polygon type.
    """
    if geom:
        if geom.geom_type == 'MultiPolygon':
            return geom
        elif geom.geom_type == 'Polygon':
            return MultiPolygon(geom)
        else:
            return empty_geom(geom.srid)
    else:
        return geom


class ScoreDisplay(models.Model):
    """
    Container for displaying score panels
    """

    # The title of the score display
    title = models.CharField(max_length=50)

    # The legislative body that this score display is for
    legislative_body = models.ForeignKey(LegislativeBody)

    # Whether or not this score display belongs on the leaderboard page
    is_page = models.BooleanField(default=False)

    # The style to be assigned to this score display
    cssclass = models.CharField(max_length=50, blank=True)


class ScorePanel(models.Model):
    """
    Container for displaying multiple scores of a given type
    """

    # The type of the score display (plan, plan summary, district)
    type = models.CharField(max_length=20)

    # The score display this panel belongs to
    display = models.ForeignKey(ScoreDisplay)

    # Where this panel belongs within a score display
    position = models.PositiveIntegerField(default=0)
    
    # The title of the score panel
    title = models.CharField(max_length=50)
    
    # The filename of the template to be used for formatting this panel
    template = models.CharField(max_length=500, blank=True)

    # The style to be assigned to this score display
    cssclass = models.CharField(max_length=50, blank=True)


class ScoreFunction(models.Model):
    """
    Score calculation definition
    """

    # Namepace of the calculator module to use for scoring
    calculator = models.CharField(max_length=500)

    # Name of this score function
    name = models.CharField(max_length=50)

    # Label to be displayed for scores calculated with this funciton
    label = models.CharField(max_length=100, blank=True)

    # Description of this score function
    description = models.TextField(blank=True)

    # Whether or not this score function is for a plan
    is_planscore = models.BooleanField(default=False)


class ScoreArgument(models.Model):
    """
    Defines the arguments passed into a score function
    """

    # The score function this argument is for
    function = models.ForeignKey(ScoreFunction)

    # The name of the argument of the score function
    argument = models.CharField(max_length=50)

    # The value of the argument to be passed
    value = models.CharField(max_length=50)

    # The type of the argument (literal, score, subject)
    type = models.CharField(max_length=10)

    
class PanelFunction(models.Model):
    """
    Defines the score functions used in a given score panel
    """

    # The score panel
    panel = models.ForeignKey(ScorePanel)

    # The score function
    function = models.ForeignKey(ScoreFunction)


class ValidationCriteria(models.Model):
    """
    Defines the required score functions to validate a legislative body
    """

    # The score function this criteria is for
    function = models.ForeignKey(ScoreFunction)

    # Name of this validation criteria
    name = models.CharField(max_length=50)

    # Description of this validation criteria
    description = models.TextField(blank=True)

    # The legislative body that this validation criteria is for
    legislative_body = models.ForeignKey(LegislativeBody)
