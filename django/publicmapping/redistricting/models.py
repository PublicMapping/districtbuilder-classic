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
    Andrew Jennings, David Zwarg
"""

from django.core.exceptions import ValidationError
from django.contrib.gis.db import models
from django.contrib.gis.gdal import DataSource
from django.contrib.gis.geos import MultiPolygon,GEOSGeometry,GEOSException,GeometryCollection
from django.contrib.auth.models import User
from django.db.models import Sum, Max, Q
from django.db.models.signals import pre_save, post_save
from django.db import connection, transaction
from django.forms import ModelForm
from django.conf import settings
from django.utils import simplejson as json
from datetime import datetime
from math import sqrt, pi
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

    # The subjects that exist in this legislative body
    subjects = models.ManyToManyField(Subject, through='LegislativeSubject')

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

    # The maximum zoom level
    max_zoom = models.PositiveIntegerField(default=20)

    # The position that this geolevel should be in, relative to all other
    # geolevels, when viewing the geolevels in a list.
    sort_key = models.PositiveIntegerField(default=1)

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


class LegislativeSubject(models.Model):
    """
    A subject available in a legislative body.

    A subject is something like "Total Population", and this subject can
    exist in both "State Senate" and "State House" legislative bodies.
    """

    # The legislative body
    legislative_body = models.ForeignKey(LegislativeBody)

    # The subject for characteristics in this body
    subject = models.ForeignKey(Subject)


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
    parent = models.ForeignKey('LegislativeLevel',null=True)

    def __unicode__(self):
        """
        Represent the LegislativeLevel as a unicode string. This is the
        LegislativeLevel's LegislativeBody and Geolevel
        """
        return self.legislative_body.name + self.geolevel.name


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

    # An optional identifier that can be used with a nested id system such
    # as census block ids or voting division ids
    supplemental_id = models.CharField(max_length=50, db_index=True, blank=True, null=True)

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
    def get_base_geounits(geounit_ids, geolevel):
        """
        Get the list of geounits at the base geolevel inside the 
        geometry of geounit_ids.
        
        This method performs a spatial query to find all the small
        Geounits that are contained within the combined extend of the
        Geounits that are in the list of geounit_ids.
        
        The spatial query unionizes the geometry of the geounit_ids,
        simplifies that geometry, then returns all geounits at the base
        geolevel whose centroid falls within the unionized geometry.

        The performance of this method is directly related to the complexity
        of the geometry of the Geounits. This method will perform the best
        on simplified geometry, or geometries with fewer vertices.

        Parameters:
            geounit_ids -- A list of Geounit IDs. Please note that these 
            must be int datatypes, and not str.
            geolevel -- The ID of the Geolevel that contains geounit_ids

        Returns:
            A list of Geounit ids.
        """
        cursor = connection.cursor()

        # craft a custom sql query to get the IDs of the geounits
        cursor.execute('SELECT id from redistricting_geounit where geolevel_id = %s and St_within(center, (select st_simplify(st_union(geom), 10) from redistricting_geounit where geolevel_id = %s and id in %s))', [int(settings.BASE_GEOLEVEL), int(geolevel), geounit_ids])
        results = []
        ids = cursor.fetchall()
        for row in ids:
            results += row
        return results

    @staticmethod
    def get_base_geounits_within(geom):
        """
        Get the  list of geounits at the base geolevel inside a geometry.

        This method performs a spatial query to find all the small
        Geounits that are contained within the geometry provided.

        The spatial query returns all Geounits at the base Geolevel whose
        centroid falls within the geometry.

        The performance of this method is directly related to the complexity
        of the geometry of the Geounits. This method will perform the best
        on simplified geometry, or geometries with fewer vertices.

        Parameters:
            geom -- The GEOSGeometry that describe the limits for the base 
            Geounits.

        Returns:
            A list of Geounit ids.
        """
        cursor = connection.cursor()
        # craft a custom sql query to get the IDs of the geounits
        cursor.execute("select id from redistricting_geounit where geolevel_id = %s and st_within(center, geomfromewkt(%s))",[settings.BASE_GEOLEVEL, str(geom.ewkt)])
        results = []
        ids = cursor.fetchall()
        for row in ids:
            results += row
        return results

    @staticmethod
    def get_mixed_geounits(geounit_ids, geolevel, boundary, inside):
        """
        Spatially search for the largest Geounits inside or outside a 
        boundary.

        Search for Geounits in a multipass search. The searching method
        gets Geounits inside a boundary at a Geolevel, then determines
        if there is a geographic remainder, then repeats the search at
        a smaller Geolevel, until the base Geolevel is reached.

        Parameters:
            geounit_ids -- A list of Geounit IDs. Please note that these
                must be int datatypes, and not str.
            geolevel -- The ID of the Geolevel that contains geounit_ids
            boundary -- The GEOSGeometry that defines the edge of the
                spatial search area.
            inside -- True or False to search inside or outside of the 
                boundary, respectively.

        Returns:
            A list of Geounit objects, with only the ID and Geometry
            fields populated.
        """

        if not boundary and inside:
            # there are 0 geounits inside a non-existant boundary
            return []


        # Make sure the geolevel is a number
        geolevel = int(geolevel)
        levels = Geolevel.objects.all().values_list('id',flat=True).order_by('id')
        selection = None
        units = []
        for level in levels:
            # if this geolevel is the requested geolevel
            if geolevel == level:
                guFilter = Q(id__in=geounit_ids)

                # Get the area defined by the union of the geounits
                selection = Geounit.objects.filter(guFilter).unionagg()
               
                # Begin crafting the query to get the id and geom
                query = "SELECT id,st_ashexewkb(geom,'NDR') FROM redistricting_geounit WHERE id IN (%s) AND " % (','.join(geounit_ids))

                # create a boundary if one doesn't exist
                if not boundary:
                    boundary = empty_geom(selection.srid)
                simple = boundary.simplify(tolerance=settings.SIMPLE_TOLERANCE,preserve_topology=True)

                if inside:
                    # Searching inside the boundary
                    if level != settings.BASE_GEOLEVEL:
                        # Search by geometry
                        query += "st_within(geom, geomfromewkt('%s'))" % simple.ewkt
                    else:
                        # Search by centroid
                        query += "st_intersects(center, geomfromewkt('%s'))" % simple.ewkt
                else:
                    # Searching outside the boundary
                    if level != settings.BASE_GEOLEVEL:
                        # Search by geometry
                        query += "NOT st_intersects(geom, geomfromewkt('%s'))" % simple.ewkt
                    else:
                        # Search by centroid
                        query += "NOT st_intersects(center, geomfromewkt('%s'))" % simple.ewkt

                # Execute our custom SQL
                cursor = connection.cursor()
                cursor.execute(query)
                rows = cursor.fetchall()
                count = 0
                for row in rows:
                    count += 1
                    geom = GEOSGeometry(row[1])
                    # Create a geounit, and add it to the list of units
                    units.append(Geounit(id=row[0],geom=geom))

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
                    # this always rebuilds the current extent of all the
                    # selected geounits
                    if union is None:
                        union = selected.geom
                    else:
                        union = union.union(selected.geom)


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
                        # it is not clear what this means, or why it happens
                        remainder = empty_geom(boundary.srid)

                # Check if the remainder is a geometry collection. If it is,
                # munge it into a multi-polygon so that we can use it in our
                # custom sql query
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
                    query = "SELECT id,st_ashexewkb(geom,'NDR') FROM redistricting_geounit WHERE geolevel_id = %d AND " % level

                    # Simplify the remainder before performing the query
                    simple = remainder.simplify(tolerance=settings.SIMPLE_TOLERANCE, preserve_topology=True)

                    if level == settings.BASE_GEOLEVEL:
                        # Query by center
                        query += "st_intersects(center, geomfromewkt('%s'))" % simple.ewkt
                    else:
                        # Query by geom
                        query += "st_within(geom, geomfromewkt('%s'))" % simple.ewkt

                    # Execute our custom SQL
                    cursor = connection.cursor()
                    cursor.execute(query)
                    rows = cursor.fetchall()
                    count = 0
                    for row in rows:
                        count += 1
                        units.append(Geounit(id=row[0],geom=GEOSGeometry(row[1])))

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
    # The value as a percentage
    percentage = models.DecimalField(max_digits=6,decimal_places=6, null=True, blank=True)

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

    # The lower data value
    lower = models.PositiveIntegerField()

    # The upper data value
    upper = models.PositiveIntegerField()

    class Meta:
        """
        Additional information about the Target model.
        """
        ordering = ['subject']

    def __unicode__(self):
        """
        Represent the Target as a unicode string. The Target string is
        in the form of "Subject : Lower - Upper"
        """
        return u'%s : %s - %s' % (self.subject, self.lower, self.upper)

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
        unique_together = (('name','owner'),)

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
            The number of Districts changed.
        """
        
        # incremental is the geometry that is changing
        incremental = Geounit.objects.filter(id__in=geounit_ids).unionagg()

        fixed = 0

        # Get the districts in this plan, at the specified version.
        districts = self.get_districts_at_version(int(version))

        # First, remove the aggregate values from districts that are
        # not the target, and intersect the geounits provided
        for district in districts:
            if district.district_id == int(districtid):
                # If the district_id is the target, save the target.
                target = district
                continue

            # if this district does not overlap the selection or
            # if this district does not contain the selection
            if not (district.geom and (district.geom.overlaps(incremental) or district.geom.contains(incremental) or 
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

                    fixed += 1

                # go onto the next district
                continue

            # compute the geounits before changing the boundary
            geounits = Geounit.get_mixed_geounits(geounit_ids, geolevel, district.geom, True)
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
                district.simple = None
            else:
                # The district geometry exists, so save the updated 
                # versions of the geom and simple fields
                district.geom = geom
                simple = geom.simplify(tolerance=settings.SIMPLE_TOLERANCE,preserve_topology=True)
                district.simple = enforce_multi(simple)

            # Clone the district to a new version, with a different shape
            district_copy = copy(district)
            district_copy.version = self.version + 1
            district_copy.id = None
            district_copy.save()

            # Clone the characteristings to this new version
            district_copy.clone_characteristics_from(district)

            # If the district stats change, update the counter.
            if district_copy.delta_stats(geounits,False):
                fixed += 1

        # get the geounits before changing the target geometry
        geounits = Geounit.get_mixed_geounits(geounit_ids, geolevel, target.geom, False)

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

        # If the target geometry exists (no errors from above)
        if target.geom:
            # Simplify the district geometry.
            simple = target.geom.simplify(tolerance=settings.SIMPLE_TOLERANCE,preserve_topology=True)
            target.simple = enforce_multi(simple)
        else:
            # The simplified target geometry is empty, too.
            target.simple = None

        # Clone the district to a new version, with a different shape.
        target_copy = copy(target)
        target_copy.version = self.version + 1
        target_copy.id = None
        target_copy.save();

        # Clone the characteristics to this new version
        target_copy.clone_characteristics_from(target)

        # If the district stats change, update the counter
        if target_copy.delta_stats(geounits,True):
            fixed += 1

        # save any changes to the version of this plan
        self.version += 1
        self.save()

        # Return the number of changed districts
        return fixed


    def get_wfs_districts(self,version,subject_id):
        """
        Get the districts in this plan as a GeoJSON WFS response.
        
        This method behaves much like a WFS service, returning the GeoJSON 
        for each district. This manual view exists because the limitations
        of filtering and the complexity of the version query -- it is 
        impossible to use the WFS layer in Geoserver automatically.

        Parameters:
            version -- The Plan version.
            subject_id -- The Subject attributes to attach to the district.

        Returns:
            GeoJSON describing the Plan.
        """
        
        cursor = connection.cursor()
        query = 'SELECT rd.id, rd.district_id, rd.name, lmt.version, rd.plan_id, rc.subject_id, rc.number, st_asgeojson(rd.simple) AS geom FROM redistricting_district rd JOIN redistricting_computedcharacteristic rc ON rd.id = rc.district_id JOIN (SELECT max(version) as version, district_id FROM redistricting_district WHERE plan_id = %d AND version <= %d GROUP BY district_id) AS lmt ON rd.district_id = lmt.district_id WHERE rd.plan_id = %d AND rc.subject_id = %d AND lmt.version = rd.version' % (int(self.id), int(version), int(self.id), int(subject_id))

        # Execute our custom query
        cursor.execute(query)
        rows = cursor.fetchall()
        features = []
        for row in rows:
            district = District.objects.get(pk=int(row[0]))
            # Maybe the most recent district is empty
            if row[7]:
                geom = json.loads( row[7] )
            else:
                geom = None
            features.append({ 
                'id': row[0],
                'properties': {
                    'district_id': row[1],
                    'name': row[2],
                    'version': row[3],
                    'number': float(row[6]),
                    'contiguous': district.is_contiguous(),
                    'compactness': district.get_schwartzberg_raw()
                    
                },
                'geometry': geom
            })

        # Return a python dict, which gets serialized into geojson
        return features

    def get_districts_at_version(self, version):
        """
        Get Plan Districts at a specified version.

        The districts are versioned to the current plan version when
        they are changed, so this method searches all the districts
        in the plan, returning the districts that have the highest
        version number at or below the version passed in.

        Parameters:
            version -- The version of the Districts to fetch.

        Returns:
            An array of districts that exist in the plan at the version.
        """

        # Get all the districts
        districts = self.district_set.all()

        # Sort the districts by district_id, then version
        districts = sorted(list(districts), key=lambda d: d.sortVer())
        dvers = {}

        # For each district
        for i in range(0, len(districts)):
            district = districts[i]

            # If the district version is higher than the version requested
            if district.version > version:
                # Skip it
                continue

            # Save this district, keyed by the district_id
            dvers[district.district_id] = district

        # Convert the dict of districts into an array of districts
        districts = []
        for value in dvers.itervalues():
            districts.append(value)

        return districts
      
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

    def district_mapping_cursor (self, geounit_id_field="supplemental_id"):
        """
        Given a plan, get the district mapping info.  Each row 
        of the returned cursor represents a geounit id and a
        district_id.

        Parameters:
            geounit_id_field - which id field to return from the geounits

        Returns:
            A database cursor with each row containing a geounit id
            and a district_id, respectively.
        """

        geolevel = settings.BASE_GEOLEVEL

        # This query gets all of the geounit and district ids for the current plan 
        query = 'select g.' + geounit_id_field + ', l.district_id from redistricting_geounit as g join (select d.* from redistricting_district as d join (select max(version) as latest, district_id, plan_id from redistricting_district where plan_id = %s and version <= %s group by district_id, plan_id) as v on d.district_id = v.district_id and d.plan_id = v.plan_id and d.version = v.latest) as l on ST_Contains(l.geom, g.center) where geolevel_id = %s order by g.' + geounit_id_field
        cursor = connection.cursor()
        cursor.execute(query, [self.id, self.version, settings.BASE_GEOLEVEL])

        return cursor

    @staticmethod
    def from_shapefile(name, body, shapefile, idfield, owner=None):
        """
        Import a shapefile into a plan. The plan shapefile must contain
        an ID field.

        Parameters:
            name - The name of the plan
            shapefile - The path to the shapefile
            idfield - The name of the field in the shapefile that contains
                the district ID of each district.
            owner - Optional. The user who owns this plan. If not 
                specified, defaults to the system admin.

        Returns:
            A new plan.
        """
        plan = Plan.create_default(name,body,owner)

        if not plan:
            return False

        datasource = DataSource(shapefile)
        layer = datasource[0]

        # Import each feature in the new plan. 
        # Sort by the district ID field
        for feature in sorted(layer,key=lambda f:int(f.get(idfield))):
            print '\tImporting "District %s"' % (feature.get(idfield),)

            # Import only multipolygon shapes
            geom = feature.geom.geos
            if geom.geom_type == 'Polygon':
                geom = MultiPolygon(geom)
            elif geom.geom_type == 'MultiPolygon':
                geom = geom
            else:
                geom = None

            simple = geom.simplify(tolerance=settings.SIMPLE_TOLERANCE,preserve_topology=True)

            # Import only multipolygon shapes
            if simple.geom_type == 'Polygon':
                simple = MultiPolygon(simple)
            elif geom.geom_type == 'MultiPolygon':
                simple  = simple
            else:
                simple = None

            district = District(
                district_id=int(feature.get(idfield)) + 1,
                name='District %s' % feature.get(idfield),
                plan=plan,
                version=0,
                geom=geom,
                simple=simple)
            district.save()

            geounits = list(district.get_base_geounits_within())

            print '\tUpdating district statistics...'
            district.delta_stats(geounits,True)

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
    simple = models.MultiPolygonField(srid=3785, blank=True, null=True)

    # The version of this district.
    version = models.PositiveIntegerField(default=0)

    # This is a geographic model, so use the geomanager for objects
    objects = models.GeoManager()
    
    def sortKey(self):
        """
        Sort districts by name, with numbered districts first.

        Returns:
            The Districts, sorted in numerical order.
        """
        name = self.name;
        if name.startswith('District '):
            name = name.rsplit(' ', 1)[1]
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
        all_subjects = Subject.objects.all()
        changed = False

        # For all subjects
        for subject in all_subjects:
            # Aggregate all Geounits Characteristic values
            aggregate = Characteristic.objects.filter(geounit__in=geounits, subject__exact=subject).aggregate(Sum('number'))['number__sum']
            # If there are aggregate values for the subject and geounits.
            if aggregate:
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
                computed.save();

                changed = True

        return changed
        

    def get_schwartzberg_raw(self):
        """
        Generate Schwartzberg measure of compactness.
        
        The Schwartzberg measure of compactness measures the perimeter of 
        the district to the circumference of the circle whose area is 
        equal to the area of the district.

        Returns:
            The Schwartzberg measure as a raw number.
        """
        try:
            r = sqrt(self.geom.area / pi)
            perimeter = 2 * pi * r
            ratio = perimeter / self.geom.length
            return ratio
        except:
            return None
        
    def get_schwartzberg(self):
        """
        Generate Schwartzberg measure of compactness.
        
        The Schwartzberg measure of compactness measures the perimeter of 
        the district to the circumference of the circle whose area is 
        equal to the area of the district.

        Returns:
            The Schwartzberg measure, formatted as a percentage.
        """
        ratio = self.get_schwartzberg_raw()
        if ratio:
            return "%.2f%%" % (ratio * 100)
        else: 
            return "n/a"

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

    def get_base_geounits_within(self):
        """
        Get a list of the geounit ids of the geounits that comprise 
        this district at the base level.  
        
        We'll check this by seeing whether the centroid of each geounits 
        fits within the simplified geometry of this district.

        Returns:
            An array of Geounit IDs of Geounits that lie within this 
            District. 
        """    
        if not self.simple:
           return list()
        return Geounit.objects.filter(geolevel = settings.BASE_GEOLEVEL, center__within = self.simple).values_list('id')
        


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

    # The aggregate as a percentage. Of what? Dunno.
    percentage = models.DecimalField(max_digits=6,decimal_places=6, null=True, blank=True)

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
        # Unassigned is not counted in MAX_DISTRICTS
        if district.district_id > settings.MAX_DISTRICTS + 1:
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
    geom = GeometryCollection([])
    geom.srid = srid
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
