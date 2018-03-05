"""
Define the models used by the redistricting app.

The classes in redistricting.models define the data models used in the
application. Each class relates to one table in the database; foreign key
fields may define a second, intermediate table to map the records to one
another.

This file is part of The Public Mapping Project
https://github.com/PublicMapping/

License:
    Copyright 2010-2012 Micah Altman, Michael McDonald

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

from celery.task import task
from django.core.exceptions import ValidationError
from django.contrib.gis.db import models
from django.contrib.gis.geos import (MultiPolygon, Polygon, GEOSGeometry,
                                     GEOSException, GeometryCollection, Point)
from django.contrib.gis.db.models.query import GeoQuerySet
from django.contrib.gis.db.models import Collect, Extent
from django.contrib.auth.models import User
from django.db.models import Sum, Max, Q, Count
from django.db.models.signals import pre_save, post_save, m2m_changed
from django.db import connection, transaction
from django.forms import ModelForm
from django.conf import settings
from django.utils import translation
from django.utils.translation import ugettext as _
from django.template.loader import render_to_string
from django_comments.models import Comment
from django.contrib.contenttypes.models import ContentType
from django.template.defaultfilters import title
from redistricting.calculators import Schwartzberg, Contiguity, SumValues
from tagging.models import TaggedItem, Tag
from tagging.registry import register
from datetime import datetime
from copy import copy
import json
from decimal import *
from operator import attrgetter
import polib
from traceback import format_exc
import os, sys, cPickle, types, tagging, re, logging

logger = logging.getLogger(__name__)

# Caches for po files
I18N_CACHE = {}


class BaseModel(models.Model):
    """
    A base class for models that have short labels, labels, and long descriptions.
    Any class that extends this base class must have a 'name' field.
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize the message file cache.
        """
        super(BaseModel, self).__init__(*args, **kwargs)
        # Hardcoding to avoid a bug in Django 1.8 get_language
        # (refer to https://github.com/django-parler/django-parler/issues/90)
        lang = translation.get_language() or settings.LANGUAGE_CODE
        if not lang in I18N_CACHE:
            try:
                path = os.path.join(
                    settings.STATIC_ROOT,
                    '../locale/%s/LC_MESSAGES/xmlconfig.mo' % lang)
                path = os.path.normpath(path)
                I18N_CACHE[lang] = polib.mofile(path)
            except Exception, ex:
                path = os.path.join(
                    settings.STATIC_ROOT,
                    '../locale/%s/LC_MESSAGES/xmlconfig.po' % lang)
                path = os.path.normpath(path)
                I18N_CACHE[lang] = polib.pofile(path)

    def get_short_label(self):
        """
        Get the short label (a.k.a. title) of the object.
        """
        msgid = u'%s short label' % self.name
        try:
            lang = translation.get_language()
            return I18N_CACHE[lang].find(msgid).msgstr
        except Exception, ex:
            logger.debug('Cannot find msgid %s, fallback to msgid', msgid)
            return msgid

    def get_label(self):
        """
        Get the label of the object. This is longer than the short label, and
        shorter than the description. Most often, this is the default text
        representation of an object.
        """
        msgid = u'%s label' % self.name
        try:
            lang = translation.get_language()
            return I18N_CACHE[lang].find(msgid).msgstr
        except Exception, ex:
            logger.debug('Cannot find msgid %s, fallback to msgid', msgid)
            return msgid

    def get_long_description(self):
        """
        Get the description of the object. This is a verbose description of the
        object.
        """
        msgid = u'%s long description' % self.name
        try:
            lang = translation.get_language()
            return I18N_CACHE[lang].find(msgid).msgstr
        except Exception, ex:
            logger.debug('Cannot find msgid %s, fallback to msgid', msgid)
            return msgid

    class Meta:
        abstract = True


class Subject(BaseModel):
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

    # If this subject should be displayed as a percentage,
    # a district's value for this subject will be divided by
    # the value for the given subject.
    # A null value indicates that the subject is not a percentage
    percentage_denominator = models.ForeignKey(
        'Subject', null=True, blank=True)

    # A flag that indicates if this subject should be displayed.
    is_displayed = models.BooleanField(default=True)

    # The position that this subject should be in, relative to all other
    # Subjects, when viewing the subjects in a list.
    sort_key = models.PositiveIntegerField(default=1)

    # The way this Subject's values should be represented.
    format_string = models.CharField(max_length=50, blank=True)

    # The version of this subject, to keep track of uploaded changes
    version = models.PositiveIntegerField(default=1)

    class Meta:
        """
        Additional information about the Subject model.
        """

        # The default method of sorting Subjects should be by 'sort_key'
        ordering = ['sort_key']

        # A unique constraint on the name
        unique_together = ('name', )

    def __unicode__(self):
        """
        Represent the Subject as a unicode string. This is the Subject's
        display name.
        """
        return self.get_label()


class ChoicesEnum(object):
    """
    Helper class for defining enumerated choices in a Model
    """

    def __init__(self, *args, **kwargs):
        super(ChoicesEnum, self).__init__()
        vals = {}
        for key, val in kwargs.iteritems():
            vals[key] = val
        object.__setattr__(self, "_vals", vals)

    def choices(self):
        cho = []
        vals = object.__getattribute__(self, "_vals")
        for key, val in vals.iteritems():
            cho.append(val)
        cho.sort()
        return cho

    def __getattr__(self, name):
        return object.__getattribute__(self, "_vals")[name][0]

    def __setattr__(self, name, value):
        object.__setattr__(self, "_vals")[name][0] = value

    def __delattr__(self, name):
        del object.__setattr__(self, "_vals")[name]


UploadedState = ChoicesEnum(
    UNKNOWN=('NA', 'Not Available'),
    UPLOADING=('UL', 'Uploading'),
    CHECKING=('CH', 'Checking'),
    DONE=('OK', 'Done'),
    ERROR=('ER', 'Error'),
)


class SubjectUpload(models.Model):
    """
    A set of uploaded subjects. This is primarily used to prevent collisions
    during the long verification step.
    """

    # The automatically generated file name
    processing_filename = models.CharField(max_length=256)

    # The user-specified file name
    upload_filename = models.CharField(max_length=256)

    # Subject name
    subject_name = models.CharField(max_length=50)

    # The status of the uploaded subject
    status = models.CharField(
        max_length=2,
        choices=UploadedState.choices(),
        default=UploadedState.UNKNOWN)

    # The task ID that is processing this uploaded subject
    task_id = models.CharField(max_length=36)


class SubjectStage(models.Model):
    """
    A quarantine table for uploaded subjects. This model stores temporary subject
    datasets that are being imported into the system.
    """

    # An identifier to discriminate between multiple uploads.
    upload = models.ForeignKey(SubjectUpload)

    # The GEOID, or FIPS ID of the geounit
    portable_id = models.CharField(max_length=50)

    # The data value of the geounit.
    number = models.DecimalField(max_digits=12, decimal_places=4)


class Region(BaseModel):
    """
    A region is a compartmentalized area of geography, legislative bodies,
    and validation criteria. Each region shares the base geography, but may
    be active over a subsection. In addition, legislative bodies are contained
    within one region at a time.
    """

    # The name of this region
    name = models.CharField(max_length=256)

    # The sorting order for this region relative to other regions
    sort_key = models.PositiveIntegerField(default=0)

    def __unicode__(self):
        """
        Represent the Region as a unicode string. This is the Region's name.
        """
        return self.name

    class Meta:
        """
        Additional information about the Region model.
        """

        # A unique constraint on the name
        unique_together = ('name', )


class LegislativeBody(BaseModel):
    """
    A legislative body that plans belong to. This is to support the
    scenario where one application is supporting both "Congressional"
    and "School District" contests, for example.
    """

    # The name of this legislative body
    name = models.CharField(max_length=256)

    # The maximum number of districts in this body
    max_districts = models.PositiveIntegerField()

    # Whether or not districts of this legislative body are allowed multi-members
    multi_members_allowed = models.BooleanField(default=False)

    # The format to be used for displaying a map label of a multi-member district.
    # This format string will be passed to python's 'format' function with the named
    # arguments: 'label' (district label) and 'num_members' (number of representatives)
    # For example: "{label} - [{num_members}]" will display "District 5 - [3]" for a district named
    # "District 5" that is configured with 3 representatives.
    multi_district_label_format = models.CharField(
        max_length=32, default='{label} - [{num_members}]')

    # The minimimum number of multi-member districts allowed in a plan.
    min_multi_districts = models.PositiveIntegerField(default=0)

    # The maximum number of multi-member districts allowed in a plan.
    max_multi_districts = models.PositiveIntegerField(default=0)

    # The minimimum number of members allowed in a multi-member district.
    min_multi_district_members = models.PositiveIntegerField(default=0)

    # The maximimum number of members allowed in a multi-member district.
    max_multi_district_members = models.PositiveIntegerField(default=0)

    # The minimumum total number of members allowed in a plan.
    min_plan_members = models.PositiveIntegerField(default=0)

    # The maximumum total number of members allowed in a plan.
    max_plan_members = models.PositiveIntegerField(default=0)

    # A flag indicating if this legislative body contains community maps
    is_community = models.BooleanField(default=False)

    # Where in the list of legislative bodies should this item appear?
    sort_key = models.PositiveIntegerField(default=0)

    # The region that this LegislativeBody applies to.
    region = models.ForeignKey(Region)

    def get_members_label(self):
        """
        Get the label for this legislative body's members.
        """
        msgid = u'%s members' % self.name
        try:
            lang = translation.get_language()
            return I18N_CACHE[lang].find(msgid).msgstr
        except Exception, ex:
            logger.debug('Cannot find msgid %s, fallback to msgid', msgid)
            return msgid

    def get_default_subject(self):
        """
        Get the default subject for display. This is related to the
        LegislativeBody via the LegislativeLevel table.

        Returns:
            The default subject for the legislative body.
        """
        ldef = self.legislativelevel_set.filter(parent__isnull=True)
        return ldef[0].subject

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
        levels = self.legislativelevel_set.filter(subject=subj, parent=None)
        return levels[0].geolevel.id

    def get_geolevels(self):
        """
        Get the geolevel heirarchy for this legislative body. This returns
        a list of geolevels that exist in the legislative body, in the
        order in which they are related.
        """
        subject = self.get_default_subject()
        geobodies = self.legislativelevel_set.filter(subject=subject)

        ordered = []
        allgeobodies = len(geobodies)
        while len(ordered) < allgeobodies:
            foundbody = False
            for geobody in geobodies:
                if len(ordered) == 0 and geobody.parent is None:
                    # add the first geobody (the one with no parent)
                    ordered.append(geobody)
                    foundbody = True
                elif len(ordered) > 0 and ordered[len(ordered)
                                                  - 1] == geobody.parent:
                    # add the next geobody if it's parent matches the last
                    # geobody appended
                    ordered.append(geobody)
                    foundbody = True

            if not foundbody:
                allgeobodies -= 1

        def glonly(item):
            return item.geolevel

        ordered = map(glonly, ordered)

        ordered.reverse()
        return ordered

    def is_below(self, legislative_body):
        """
        Compares this legislative body to a second legislative body, and
        determines the nesting order (which one is above or below). This
        assumes the relationship can be determined from max_districts.

        Parameters:
            legislative_body -- The LegislativeBody in which to perform the comparison

        Returns:
            True if this this legislative body is below the one passed in, False otherwise
        """
        return self.max_districts > legislative_body.max_districts

    def __unicode__(self):
        """
        Represent the LegislativeBody as a unicode string. This is the
        LegislativeBody's name.
        """
        return self.name

    def get_short_label(self):
        short_label = super(LegislativeBody, self).get_short_label()
        if short_label == ('%s short label' % self.name):
            short_label = '%(district_id)s'
        return short_label

    def get_label(self):
        label = super(LegislativeBody, self).get_label()
        if label == ('%s label' % self.name):
            label = 'District %(district_id)s'
        return label

    def get_long_description(self):
        long_description = super(LegislativeBody, self).get_long_description()
        if long_description == '':
            long_description = title(self.name)
        return long_description

    class Meta:
        """
        Additional information about the LegislativeBody model.
        """
        verbose_name_plural = "Legislative bodies"

        # A unique constraint on the name
        unique_together = ('name', )


class Geolevel(BaseModel):
    """
    A geographic classification for Geounits.

    For example, a Geolevel is the concept of 'Counties', where each
    Geounit is an instance of a county.  There are many Geounits at a
    Geolevel.
    """

    # The name of the geolevel
    name = models.CharField(max_length=50)

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

        # A unique constraint on the name
        unique_together = ('name', )

    def __unicode__(self):
        """
        Represent the Geolevel as a unicode string. This is the Geolevel's
        name.
        """
        return self.get_label()

    def renest(self, parent, subject=None, spatial=True):
        """
        Renest all geounits in this geolevel, based on the parent (smaller!)
        geography in the parent.

        Parameters:
            parent -- The smaller geographic areas that comprise this geography.
            subject -- The subject to aggregate. Optional. If omitted, i
                aggregate all subjects.
            spatial -- A flag indicating that the spatial aggregates should be
                computed as well as the numerical aggregates.
        """
        if parent is None:
            return True

        progress = 0
        logger.info("Recomputing geometric and numerical aggregates...")
        logger.info('0% .. ')

        geomods = 0
        nummods = 0

        unitqset = self.geounit_set.all()
        count = unitqset.count()
        for i, geounit in enumerate(unitqset):
            if (float(i) / unitqset.count()) > (progress + 0.1):
                progress += 0.1
                logger.info('%2.0f%% .. ', (progress * 100))

            geo, num = geounit.aggregate(parent, subject, spatial)

            geomods += geo
            nummods += num

        logger.info('100%')

        logger.debug("Geounits modified: (geometry: %d, data values: %d)",
                     geomods, nummods)

        return True

    def calc_extent(self):
        """
        Returns the extent (list of four floats) of the geounits belonging to this geolevel
        """
        extent = self.geounit_set.aggregate(Extent('simple'))['simple__extent']

        # Convert the 4-tuple returned by the query to a list
        return list(extent)


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
    parent = models.ForeignKey('LegislativeLevel', null=True, blank=True)

    # The target that refers to this level
    subject = models.ForeignKey(Subject)

    def __unicode__(self):
        """
        Represent the LegislativeLevel as a unicode string. This is the
        LegislativeLevel's LegislativeBody and Geolevel
        """
        return "%s, %s, %s" % (self.legislative_body.get_long_description(),
                               self.geolevel.get_short_label(),
                               self.subject.get_short_label())

    class Meta:
        unique_together = (
            'geolevel',
            'legislative_body',
            'subject',
        )

    @staticmethod
    def get_basest_geolevel_and_count():
        base_levels = LegislativeLevel.objects.filter(parent__isnull=True)
        geolevel = None
        nunits = 0
        for base_level in base_levels:
            if base_level.geolevel.geounit_set.all().count() > nunits:
                nunits = base_level.geolevel.geounit_set.all().count()
                geolevel = base_level.geolevel

        return (
            geolevel,
            nunits,
        )


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
    portable_id = models.CharField(
        max_length=50, db_index=True, blank=True, null=True)

    # An identifier used by the data ingestion process.  This number is a
    # concatenated series of identifiers identifying parent-child relationships
    tree_code = models.CharField(
        max_length=50, db_index=True, blank=True, null=True)

    # The ID of the geounit that contains this geounit
    child = models.ForeignKey('Geounit', null=True, blank=True)

    # The full geometry of the geounit (high detail).
    geom = models.MultiPolygonField(srid=3785)

    # The lite geometry of the geounit (generated from geom via simplify).
    simple = models.MultiPolygonField(srid=3785)

    # The centroid of the geometry (generated from geom via centroid).
    center = models.PointField(srid=3785)

    # The geographic level of this Geounit
    geolevel = models.ManyToManyField(Geolevel)

    # Manage the instances of this class with a geographically aware manager
    objects = models.GeoManager()

    @staticmethod
    def get_mixed_geounits(geounit_ids, legislative_body, geolevel, boundary,
                           inside):
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
                must be strings, not integers.
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
            # there are 0 geounits inside a non-existent boundary
            return []

        # Make sure the geolevel is a number
        geolevel = int(geolevel)
        levels = legislative_body.get_geolevels()
        base_geolevel = levels[-1]
        selection = None
        units = []
        searching = False
        logger.debug(
            'MIXED GEOUNITS SEARCH: Geolevel %d, geounits: %s, levels: %s',
            geolevel, geounit_ids, levels)
        for level in levels:
            # if this geolevel is the requested geolevel
            if geolevel == level.id:
                searching = True
                guFilter = Q(id__in=geounit_ids)

                # Get the area defined by the union of the geounits
                selection = safe_union(Geounit.objects.filter(guFilter))
                selection = enforce_multi(selection, collapse=True)

                # Begin crafting the query to get the id and geom
                q_ids = Q(id__in=geounit_ids)
                # create a boundary if one doesn't exist
                if not boundary:
                    boundary = empty_geom(selection.srid)

                if inside:
                    # Searching inside the boundary
                    if level != base_geolevel:
                        # Search by geometry
                        q_geom = Q(geom__within=boundary)
                    else:
                        # Search by centroid
                        q_geom = Q(center__intersects=boundary)
                else:
                    # Searching outside the boundary
                    if level != base_geolevel:
                        # Search by geometry
                        q_geom = Q(geom__relate=(boundary, 'F********'))
                    else:
                        # Search by centroid
                        q_geom = Q(geom__relate=(boundary, 'F********'))
                results = Geounit.objects.filter(q_ids, q_geom)

                logger.debug('Found %d geounits in boundary at level %s',
                             results.count(), level)
                units += list(results)

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
                    geoms = safe_union(
                        GeometryCollection(
                            map(lambda unit: unit.geom, units),
                            srid=units[0].geom.srid))
                    union = enforce_multi(geoms, collapse=True)

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
                        logger.info(
                            "Caught GEOSException while intersecting 'boundary' with 'intersects'."
                        )
                        logger.debug('Reason:', ex)
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

                        try:
                            remainder = remainder.intersection(intersects)
                        except GEOSException, ex:
                            logger.info(
                                "Caught GEOSException while intersecting 'remainder' with 'intersects'."
                            )
                            logger.debug('Reason:', ex)
                            remainder = empty_geom(boundary.srid)

                    except GEOSException, ex:
                        logger.info(
                            "Caught GEOSException while differencing 'selection' with 'boundary'."
                        )
                        logger.debug('Reason:', ex)
                        remainder = empty_geom(boundary.srid)

                remainder = enforce_multi(remainder)

                # Check if the remainder is empty -- it may have been
                # converted, or errored out above, in which case we just
                # have to move on.
                if not remainder.empty:
                    if level == base_geolevel:
                        # Query by center
                        q_geom = Q(center__intersects=remainder)
                    else:
                        # Query by geom
                        q_geom = Q(geom__within=remainder)

                    units += list(level.geounit_set.filter(q_geom))

        # Send back the collected Geounits
        return units

    def __unicode__(self):
        """
        Represent the Geounit as a unicode string. This is the Geounit's
        name.
        """
        return self.name

    def aggregate(self, parent, subject=None, spatial=True):
        """
        Aggregate this geounit to the composite boundary of the geounits
        in "parent" geolevel.  Compute numerical aggregates on the subject,
        if specified.

        Parameters:
            parent -- The 'parent' geolevel, which contains the smaller
                geographic units that comprise this geounit.
            subject -- The subject to aggregate and compute. If omitted,
                all subjects are computed.
            spatial -- Compute the geometric aggregates as well as
                numeric aggregates.
        """
        geo = 0
        num = 0

        parentunits = Geounit.objects.filter(
            tree_code__startswith=self.tree_code, geolevel__in=[parent])

        parentunits.update(child=self)
        unioned = [x.geom.unary_union for x in parentunits]
        if any([x.geom_type == 'MultiPolygon' for x in unioned]):
            multis = [x for x in unioned if x.geom_type == 'MultiPolygon']
            singles = [x for x in unioned if x.geom_type != 'MultiPolygon']
            newgeo = multis[0].union(MultiPolygon(singles).unary_union)
            for other in multis[1:]:
                newgeo = newgeo.union(other)
        else:
            newgeo = MultiPolygon(unioned).unary_union

        # reform the parent units as a list of IDs
        parentunits = list(parentunits.values_list('id', flat=True))

        if newgeo is None:
            return (
                geo,
                num,
            )

        if spatial:
            difference = newgeo.difference(self.geom).area
            if difference != 0:
                # if there is any difference in the area, then assume that
                # this aggregate is an inaccurate aggregate of it's parents

                # aggregate geometry

                # all geolevels of this geounit should have the same tolerance
                tolerance = self.geolevel.all()[0].tolerance
                newsimple = newgeo.simplify(
                    preserve_topology=True, tolerance=tolerance)

                # enforce_multi is defined in redistricting.models
                self.geom = enforce_multi(newgeo)
                self.simple = enforce_multi(newsimple)
                self.save()

                geo += 1

        if subject is None:
            # No subject provided? Do all of them
            subject_qs = Subject.objects.all()
        else:
            if isinstance(subject, Subject):
                # Subject parameter is a Subject object, wrap it in a list
                subject_qs = [subject]
            elif isinstance(subject, str):
                # Subject parameter is a Subject name, filter by name
                subject_qs = Subject.objects.filter(name=subject)
            else:
                # Subject parameter is an ID, filter by ID
                subject_qs = Subject.objects.filter(id=subject)

        # aggregate data values
        for subject_item in subject_qs:
            qset = Characteristic.objects.filter(
                geounit__in=parentunits, subject=subject_item)
            aggdata = qset.aggregate(Sum('number'))['number__sum']
            percentage = '0000.00000000'
            if aggdata and subject_item.percentage_denominator:
                dset = Characteristic.objects.filter(
                    geounit__in=parentunits,
                    subject=subject_item.percentage_denominator)
                denominator_data = dset.aggregate(Sum('number'))['number__sum']
                if denominator_data > 0:
                    percentage = aggdata / denominator_data

            if aggdata is None:
                aggdata = "0.0"

            mychar = self.characteristic_set.filter(subject=subject_item)
            if mychar.count() < 1:
                mychar = Characteristic(
                    geounit=self,
                    subject=subject_item,
                    number=aggdata,
                    percentage=percentage)
                mychar.save()
                num += 1
            else:
                mychar = mychar[0]

                if aggdata != mychar.number:
                    mychar.number = aggdata
                    mychar.percentage = percentage
                    mychar.save()

                    num += 1

        return (
            geo,
            num,
        )


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
    number = models.DecimalField(max_digits=12, decimal_places=4)
    # The value as a percentage of the value for this geounit of the subject given as
    # the percentage_denominator (if any)
    percentage = models.DecimalField(
        max_digits=12, decimal_places=8, null=True, blank=True)

    class Meta:
        unique_together = ("subject", "geounit")

    def __unicode__(self):
        """
        Represent the Characteristic as a unicode string. The
        Characteristic string is in the form of "Subject for Geounit:
        Number"
        """
        return u'%s for %s: %s' % (self.subject, self.geounit, self.number)


# Enumerated type used for determining a plan's state of processing
ProcessingState = ChoicesEnum(
    UNKNOWN=(-1, 'Unknown'),
    READY=(0, 'Ready'),
    CREATING=(1, 'Creating'),
    REAGGREGATING=(2, 'Reaggregating'),
    NEEDS_REAGG=(3, 'Needs reaggregation'),
)


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

    # The processing state of this plan (see ProcessingState Enum)
    processing_state = models.IntegerField(
        choices=ProcessingState.choices(), default=ProcessingState.UNKNOWN)

    # Is this plan considered a valid plan based on validation criteria?
    is_valid = models.BooleanField(default=False)

    # The most recent version of the districts in this plan.
    version = models.PositiveIntegerField(default=0)

    # The oldest available stored version of this plan.
    min_version = models.PositiveIntegerField(default=0)

    # The time when this Plan was created.
    created = models.DateTimeField(auto_now_add=True)

    # The time when this Plan was edited.
    edited = models.DateTimeField(auto_now=True)

    # The owner of this Plan
    owner = models.ForeignKey(User)

    # The legislative body that this plan is for
    legislative_body = models.ForeignKey(LegislativeBody)

    # A flag to indicate that upon post_save, when a plan is created,
    # it should create an Unassigned district. There are times when
    # this behaviour should be skipped (when copying plans, for example)
    create_unassigned = True

    def __unicode__(self):
        """
        Represent the Plan as a unicode string. This is the Plan's name.
        """
        return self.name

    class Meta:
        """
        Define a unique constraint on 2 fields of this model.
        """
        unique_together = (
            'name',
            'owner',
            'legislative_body',
        )

    def is_community(self):
        """
        Determine if this plan is a community map. Community maps have no
        limits to the number of districts -- in practicality, this limit
        is 9999 districts.
        """
        if self.legislative_body is None:
            return False

        return self.legislative_body.is_community

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
        versions = self.district_set.order_by('-version').values(
            'version').annotate(count=Count('version'))

        if steps < len(versions):
            return versions[steps]['version']

        # if the number of steps exceeds the total history of the
        # plan, the version cannot be less than zero. In addition,
        # all plans are guaranteed to have a version 0.
        return 0

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

            ds = self.get_districts_at_version(
                before, include_geom=False, filter_empty=False)

            allQ = Q(plan__isnull=True)
            for d in ds:
                # Filter on this district
                q1 = Q(district_id=d.district_id)

                # Filter on all previous versions
                q2 = Q(version__lt=d.version)

                # Accumulate the criteria
                allQ = allQ | (q1 & q2)

            # get the IDs of all the offenders
            deleteme = self.district_set.filter(allQ)
        else:
            # Purge any districts between the version provided
            # and the latest version
            deleteme = self.district_set.filter(version__gt=after)

        # since comments are loosely bound, manually remove them, too
        pks = deleteme.values_list('id', flat=True)
        pkstr = map(lambda id: str(id), pks)  # some genious uses text as a pk?
        ct = ContentType.objects.get(
            app_label='redistricting', model='district')
        Comment.objects.filter(object_pk__in=pkstr, content_type=ct).delete()

        # since tags are loosely bound, manually remove them, too
        TaggedItem.objects.filter(object_id__in=pks, content_type=ct).delete()

        # delete all districts at once
        deleteme.delete()

    def purge_beyond_nth_step(self, steps):
        """
        Purge portions of this plan's history that
        are beyond N undo steps away.

        Parameters:
            steps -- The number of 'undo' steps away from the current
                     plan's version.
        """
        if (steps >= 0):
            prever = self.get_nth_previous_version(steps)
            if prever > self.min_version:
                self.purge(before=prever)
                self.min_version = prever
                self.save()

    def update_num_members(self, district, num_members):
        """
        Create and save a new district version with the new number of values

        Parameters:
            district -- The district to modify
            num_members -- The new number of representatives for the district
        """

        # Clone the district to a new version, with new num_members
        district_copy = copy(district)
        district_copy.version = self.version
        district_copy.num_members = num_members
        district_copy.id = None
        district_copy.save()

        # Clone the characteristics, comments and tags to this new version
        district_copy.clone_relations_from(district)

    @transaction.atomic
    def add_geounits(self,
                     districtinfo,
                     geounit_ids,
                     geolevel,
                     version,
                     keep_old_versions=False):
        """
        Add Geounits to a District. When geounits are added to one
        District, they are also removed from whichever district they're
        currently in.

        NOTE: All calls to 'simplify' use the spatial units -- the map
        units in web mercator are meters, so simplify(tolerance=100.0)
        simplifies geometries to 100 meters between points (-ish).

        Parameters:
            districtinfo -- The district_id (NOT the id) of the
                destination District OR the district_id (NOT the id) of
                the destination District and the district name, as a
                tuple.
            geounit_ids -- A list of Geounit ids that are to be added
                to the District.
            geolevel -- The Geolevel of the geounit_ids.
            version -- The version of the Plan that is being modified.
            keep_old_versions -- Optional. If true, no older versions are purged.

        Returns:
            Either 1) the number of Districts changed if adding geounits
            to a district that already exists; 2) the name of the district
            created with the passed geounits.
        """

        # fix the district id so that it is definitely an integer
        if type(districtinfo) == tuple:
            districtid = int(districtinfo[0])
            districtshort = districtinfo[1]
            districtlong = districtinfo[2]
        else:
            districtid = int(districtinfo)
            districtshort = self.legislative_body.get_short_label() % {
                'district_id': districtid
            }
            districtlong = self.legislative_body.get_label() % {
                'district_id': districtid
            }

        # fix the version so that it is definitely an integer
        version = int(version)

        # incremental is the geometry that is changing
        incremental = safe_union(Geounit.objects.filter(id__in=geounit_ids))

        fixed = False

        # Get the districts in this plan, at the specified version.
        districts = self.get_districts_at_version(version, include_geom=True)

        # Check if the target district is locked
        if any((ds.is_locked and ds.district_id == districtid)
               for ds in districts):
            return False

        # Collect locked district geometries, and remove locked sections
        locked = safe_union(
            District.objects.filter(
                id__in=[d.id for d in districts if d.is_locked]))
        incremental = incremental if locked is None else incremental.difference(
            locked)

        self.purge(after=version)

        target = None

        # First, remove the aggregate values from districts that are
        # not the target, and intersect the geounits provided
        for district in districts:
            if district.district_id == districtid:
                # If the district_id is the target, save the target.
                target = district
                continue

            if district.geom is None:
                # Nothing can interact with no geometry
                continue

            if not district.geom.relate_pattern(incremental, 'T********'):
                # if this district has later edits, REVERT them to
                # this version of the district
                if not district.is_latest_version():
                    # Clone the district to a new version, with a different
                    # shape
                    district_copy = copy(district)
                    district_copy.version = self.version + 1
                    district_copy.id = None
                    district_copy.save()

                    # Clone the characteristics, comments, and tags to this
                    # new version
                    district_copy.clone_relations_from(district)

                    fixed = True

                # go onto the next district
                continue

            # compute the geounits before changing the boundary
            geounits = Geounit.get_mixed_geounits(
                geounit_ids, self.legislative_body, geolevel, district.geom,
                True)

            # Set the flag to indicate that the districts have been fixed
            if len(geounits) > 0:
                fixed = True

            # Difference the district with the selection
            # This may throw a GEOSException, in which case this function
            # will not complete successfully, and all changes will be
            # rolled back, thanks to the decorator atomic
            try:
                geom = district.geom.difference(incremental)
            except GEOSException, ex:
                # Can this be logged?
                raise ex

            # Make sure the geom is a multi-polygon.
            district.geom = enforce_multi(geom)

            # Clone the district to a new version, with a different shape
            district_copy = copy(district)
            district_copy.version = self.version + 1
            district_copy.id = None
            district_copy.save()  # this auto-generates a district_id

            # There is always a geometry for the district copy
            district_copy.simplify()  # implicit save

            # Clone the characteristcs, comments, and tags to this new version
            district_copy.clone_relations_from(district)

            # Update the district stats
            district_copy.delta_stats(geounits, False)

        new_target = False
        if target is None:
            target = District(
                short_label=districtshort,
                long_label=districtlong,
                plan=self,
                district_id=districtid,
                version=self.version,
                geom=MultiPolygon([]))
            target.save()
            new_target = True

        # If there are locked districts: augment the district boundary with the
        # boundary of the locked area, because get_mixed_geounits is getting
        # the geounits that lie outside of the provided geometry, but
        # within the boundaries of the geounit ids.
        if locked:
            if target.geom:
                bounds = target.geom.union(locked)
            else:
                bounds = locked
        else:
            bounds = target.geom

        # get the geounits before changing the target geometry
        geounits = Geounit.get_mixed_geounits(
            geounit_ids, self.legislative_body, geolevel, bounds, False)

        # set the fixed flag, since the target has changed
        if len(geounits) > 0:
            fixed = True

        # If there exists geometry in the target district
        if target.geom:
            # Combine the incremental (changing) geometry with the existing
            # target geometry
            # This may throw a GEOSException, in which case this function
            # will not complete successfully, and all changes will be
            # rolled back, thanks to the decorator atomic
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

        target_copy.simplify()  # implicit save happens here

        # Clone the characteristics, comments, and tags to this new version
        target_copy.clone_relations_from(target)

        # Update the district stats
        target_copy.delta_stats(geounits, True)

        # invalidate the plan, since it has been modified
        self.is_valid = False

        # save any changes to the version of this plan
        self.version += 1
        self.save()

        # purge old versions
        if settings.MAX_UNDOS_DURING_EDIT > 0 and not keep_old_versions:
            self.purge_beyond_nth_step(settings.MAX_UNDOS_DURING_EDIT)

        # purge the old target if a new one was created
        if new_target:
            District.objects.filter(id=target.id).delete()

        # Return a flag indicating any districts changed
        return fixed

    def get_biggest_geolevel(self):
        """
        A convenience method to get the "biggest" geolevel that could
        be used in this plan.  Helpful for get_mixed_geounits

        Returns:
            The geolevel in this plan with the minimum zoom level
        """

        leg_district = (LegislativeLevel.objects.filter(
            legislative_body=self.legislative_body)
                        .order_by('geolevel__min_zoom').first())
        if leg_district:
            return leg_district.geolevel
        else:
            raise LegislativeLevel.DoesNotExist

    def paste_districts(self, districts, version=None):
        """
        Add the districts with the given plan into the plan
        Parameters
            districts -- A list of districts to add to
                this plan
            version -- The plan version that requested the
                change.  Upon success, the plan will be one
                version greater.

        Returns:
            A list of the ids of the new, pasted districts
        """

        if version == None:
            version = self.version
        # Check to see if we have enough room to add these districts
        # without going over MAX_DISTRICTS for the legislative_body
        current_districts = self.get_districts_at_version(
            version, include_geom=False)
        allowed_districts = self.legislative_body.max_districts + 1
        for d in current_districts:
            if d.district_id == 0 or not d.geom.empty:
                allowed_districts -= 1

        if allowed_districts <= 0:
            raise Exception('Tried to merge too many districts')

        # We've got room.  Add the districts.
        if version < self.version:
            self.purge(after=version)
        pasted_list = list()
        others = None
        for district in districts:
            new_district_id, others = self.paste_district(
                district, version=version, others=others)
            if new_district_id > 0:
                pasted_list.append(new_district_id)
        if len(pasted_list) > 0:
            self.version = version + 1
            self.save()
        return pasted_list

    # We'll use these types every time we paste.  Instantiate once in the class.
    global acceptable_intersections
    acceptable_intersections = ('Polygon', 'MultiPolygon', 'LinearRing')

    def paste_district(self, district, version=None, others=None):
        """
        Add the district with the given primary key into this plan

        Parameters:
            district -- The district to paste into the plan.
            version -- the plan version that requested the change.
                The saved districts will be one version greater.
                NB: If these districts are in a different plan, the ordering
                of the addition could have unexpected results

        Returns:
            The id of the created district
        """

        # Get the old districts from before this one is pasted
        if version == None:
            version = self.version
        new_version = version + 1
        if others == None:
            first_run = True
            others = self.get_districts_at_version(version, include_geom=True)
        else:
            first_run = False

        slot = None
        for d in others:
            if d.district_id != 0 and d.geom.empty:
                slot = d.district_id
                break

        biggest_geolevel = self.get_biggest_geolevel()

        # Pass this list of districts through the paste_districts chain
        edited_districts = list()

        # Save the new district to the plan to start
        newshort = '' if slot == None else self.legislative_body.get_short_label(
        ) % {
            'district_id': slot
        }
        newlong = '' if slot == None else self.legislative_body.get_label() % {
            'district_id': slot
        }
        pasted = District(
            short_label=newshort,
            long_label=newlong,
            plan=self,
            district_id=slot,
            geom=district.geom,
            simple=district.simple,
            version=new_version,
            num_members=district.num_members)
        pasted.save()
        if newshort == '':
            pasted.short_label = self.legislative_body.get_short_label() % {
                'district_id': pasted.district_id
            }
            pasted.long_label = self.legislative_body.get_label() % {
                'district_id': pasted.district_id
            }
            pasted.save()
        pasted.clone_relations_from(district)

        # For the remaning districts in the plan,
        for existing in others:
            edited_districts.append(existing)
            # This existing district may be empty/removed
            if not existing.geom or not pasted.geom:
                continue
            # See if the pasted existing intersects any other existings
            if existing.geom.intersects(pasted.geom):
                intersection = existing.geom.intersection(pasted.geom)
                # We don't want touching districts (LineStrings in common) in our collection
                if intersection.geom_type == 'GeometryCollection':
                    intersection = filter(
                        lambda g: g.geom_type in acceptable_intersections,
                        intersection)
                    if len(intersection) == 0:
                        continue
                    intersection = MultiPolygon(intersection)
                elif intersection.empty == True or intersection.geom_type not in acceptable_intersections:
                    continue
                # If the target is locked, we'll update pasted instead;
                if existing.is_locked == True:
                    difference = pasted.geom.difference(existing.geom)
                    if difference.empty == True:
                        # This pasted district is consumed by others. Delete the record and return no number
                        pasted.delete()
                        return None
                    else:
                        pasted.geom = enforce_multi(difference)
                        pasted.simplify()
                    geounit_ids = map(
                        str,
                        biggest_geolevel.geounit_set.filter(
                            geom__bboverlaps=enforce_multi(intersection))
                        .values_list('id', flat=True))
                    geounits = Geounit.get_mixed_geounits(
                        geounit_ids, self.legislative_body,
                        biggest_geolevel.id, intersection, True)
                    pasted.delta_stats(geounits, False)
                else:
                    # We'll be updating the existing district and incrementing the version
                    difference = enforce_multi(
                        existing.geom.difference(pasted.geom))
                    if first_run == True:
                        new_district = copy(existing)
                        new_district.id = None
                        new_district.save()
                        new_district.clone_relations_from(existing)
                    else:
                        new_district = existing
                    new_district.geom = difference
                    new_district.version = new_version
                    new_district.simplify()
                    new_district.save()

                    # If we've edited the district, pop it on the new_district list
                    edited_districts.pop()
                    edited_districts.append(new_district)

                    geounit_ids = biggest_geolevel.geounit_set.filter(
                        geom__bboverlaps=intersection).values_list(
                            'id', flat=True)
                    geounit_ids = map(str, geounit_ids)

                    geounits = Geounit.get_mixed_geounits(
                        geounit_ids, self.legislative_body,
                        biggest_geolevel.id, intersection, True)

                    # Don't save Characteristics for this version if it's an empty district
                    if new_district.geom.empty:
                        new_district.computedcharacteristic_set.all().delete()
                    else:
                        new_district.delta_stats(geounits, False)
        return (pasted.id, edited_districts)

    def get_wfs_districts(self,
                          version,
                          subject_id,
                          extents,
                          geolevel,
                          district_ids=None):
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
            district_ids -- Optional array of district_ids to filter by.

        Returns:
            GeoJSON describing the Plan.
        """

        # If explicitly asked for no district ids, return no features
        if district_ids == []:
            return []

        qset = self.get_district_ids_at_version(version)

        bounds = Polygon.from_bbox(extents)
        bounds.srid = 3785

        qset = self.district_set.filter(id__in=qset)
        qset = qset.extra(
            select={
                'chop':
                "st_intersection(st_geometryn(simple,%d),st_geomfromewkt('%s'))"
                % (geolevel, bounds.ewkt)
            },
            where=[
                "st_intersects(st_geometryn(simple,%d),st_geomfromewkt('%s'))"
                % (geolevel, bounds.ewkt)
            ])
        qset = qset.defer('simple')

        exclude_unassigned = True

        # Filter by district_ids if the parameter is present
        if district_ids:
            # The 'int' conversion will throw an exception if the value isn't an integer.
            # This is desired, and will keep any harmful array values out of the query.
            qset = qset.filter(
                district_id__in=[int(id) for id in district_ids])
            exclude_unassigned = len(
                filter(lambda x: int(x) == 0, district_ids)) == 0

        # Don't return Unassigned district unless it was explicitly requested
        if exclude_unassigned:
            qset = qset.filter(~Q(district_id=0))

        features = []

        subj = Subject.objects.get(id=int(subject_id))

        # Grab ScoreFunctions so we can use cached scores for districts if they exist
        computed_district_score = ComputedDistrictScore()
        schwartzberg_function = ScoreFunction.objects.get(
            name='district_schwartzberg')
        contiguity_function = ScoreFunction.objects.get(
            name='district_contiguous')

        # Need to use filter for optional calculators because they may not be in database
        # if they are not in config.xml
        convex_function = ScoreFunction.objects.filter(name='district_convex')
        adjacency_function = ScoreFunction.objects.filter(
            name='district_adjacency')

        for district in qset:
            computed_compactness = computed_district_score.compute(
                schwartzberg_function, district=district)
            computed_contiguity = computed_district_score.compute(
                contiguity_function, district=district)

            # Optional Choropleths/Calculators
            if settings.CONVEX_CHOROPLETH:
                computed_convex = computed_district_score.compute(
                    convex_function[0], district=district)
            if settings.ADJACENCY:
                computed_adjacency = computed_district_score.compute(
                    adjacency_function[0], district=district)

            # If this district contains multiple members, change the label
            label = district.translated_label
            if (self.legislative_body.multi_members_allowed
                    and (district.num_members > 1)):
                format = self.legislative_body.multi_district_label_format
                label = format.format(
                    name=label, num_members=district.num_members)

            features_dict = {
                'id': district.id,
                'properties': {
                    'district_id':
                    district.district_id,
                    'name':
                    district.long_label,
                    'label':
                    label,
                    'is_locked':
                    district.is_locked,
                    'version':
                    district.version,
                    'number':
                    str(
                        district.computedcharacteristic_set.get(
                            subject=subj).number),
                    'contiguous':
                    computed_contiguity['value'],
                    'compactness':
                    computed_compactness['value'],
                    'num_members':
                    district.num_members
                },
                'geometry': json.loads(GEOSGeometry(district.chop).geojson)
            }

            if settings.ADJACENCY:
                features_dict['properties']['adjacency'] = computed_adjacency[
                    'value']
            if settings.CONVEX_CHOROPLETH:
                features_dict['properties']['convexhull'] = computed_convex[
                    'value']
            features.append(features_dict)

        # Return a python dict, which gets serialized into geojson
        return features

    def get_district_ids_at_version(self, version):
        """
        Get IDs of Districts in this Plan at a specified version.

        Parameters:
            version -- The version of the Districts to fetch.

        Returns:
            An unevaluated QuerySet that gets the IDs of the Districts
            in this plan at the specified version.
        """
        qset = self.district_set.filter(version__lte=version)
        qset = qset.values('district_id')
        qset = qset.annotate(latest=Max('version'), max_id=Max('id'))
        return qset.values_list('max_id', flat=True)

    def get_districts_at_version(self,
                                 version,
                                 include_geom=False,
                                 filter_empty=True):
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
        qset = self.district_set.filter(
            id__in=self.get_district_ids_at_version(version))
        if not include_geom:
            qset = qset.defer('geom', 'simple')

        districts = sorted(list(qset), key=lambda d: d.sortKey())
        simplest_level = self.legislative_body.get_geolevels()[-1]

        if filter_empty:
            # Don't return any districts that are empty (asside from the Unassigned district)
            return filter(
                lambda x: x.district_id == 0 or x.simple[simplest_level.id - 1].num_coords > 0,
                districts)
        else:
            return districts

    @staticmethod
    def create_default(name,
                       body,
                       owner=None,
                       template=True,
                       processing_state=ProcessingState.READY,
                       create_unassigned=True):
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
        plan = Plan(
            name=name,
            legislative_body=body,
            is_template=template,
            version=0,
            owner=owner,
            processing_state=processing_state)
        plan.create_unassigned = create_unassigned

        try:
            plan.save()
        except Exception as ex:
            logger.warn("Couldn't save plan: %s\n", ex)
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
        geolevel = Geolevel.objects.get(
            id=self.legislative_body.get_base_geolevel())
        b_out = geolevel.geounit_set.filter(
            center__within=simple.buffer(threshold))
        b_in = geolevel.geounit_set.filter(
            center__within=simple.buffer(-1 * threshold))

        # Find the geounits that are different between the two queries,
        # and check if they are within the unsimplified district
        b_in_values_set = set(b_in.values_list('id', 'portable_id'))
        b_out_values_set = set(b_out.values_list('id', 'portable_id'))
        diff = set(b_out_values_set ^ b_in_values_set)
        diffwithin = []
        if len(diff) > 0:
            diffids = reduce(lambda x, y: x + y, list(diff))
            diffwithin = [(unit.id, unit.portable_id)
                          for unit in Geounit.objects.filter(id__in=diffids)
                          if unit.center.within(geom)]

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
            district ids, and num_members that lie within this Plan.
        """

        # Collect the geounits for each district in this plan
        geounits = []
        for district in self.get_districts_at_version(
                self.version, include_geom=True):
            # Unassigned is district 0
            if district.district_id > 0:
                districtunits = district.get_base_geounits(threshold)
                # Add extra district data to the tuples
                geounits.extend([(gid, pid, district.district_id,
                                  district.num_members)
                                 for (gid, pid) in districtunits])

        return geounits

    def get_assigned_geounits(self, threshold=100, version=None):
        """
        Get a list of the geounit ids of the geounits that comprise
        this plan at the base level. This is different than
        get_base_geounits, because it doesn't return district ids
        along with the geounit ids, and should therefore be more performant.

        Parameters:
            threshold - distance threshold used for buffer in/out optimization
            version -- The version of the Plan.

        Returns:
            A list of tuples containing Geounit IDs and portable ids
            that lie within this Plan.
        """

        if version == None:
            version = self.version

        # TODO: enhance performance. Tried various ways to speed this up by
        # creating a union of simplified geometries and passing it to get_base_geounits.
        # This seems like it would be faster, since the amount of query overhead is
        # reduced, but this offered no performance improvement, and instead caused
        # some accuracty issues. This needs further examination.
        geounits = []
        for district in self.get_districts_at_version(
                version, include_geom=True):
            if district.district_id > 0:
                geounits.extend(district.get_base_geounits(threshold))

        return geounits

    def get_unassigned_geounits(self, threshold=100, version=None):
        """
        Get a list of the geounit ids of the geounits that do not belong to
        any district of this plan at the base level.

        Parameters:
            threshold - distance threshold used for buffer in/out optimization
            version -- The version of the Plan.

        Returns:
            A list of tuples containing Geounit IDs and portable ids
            that do not belong to any districts within this Plan.
        """

        # The unassigned district contains all the unassigned items.
        if version:
            unassigned = self.district_set.filter(
                district_id=0, version__lte=version).order_by('-version')[0]
        else:
            unassigned = self.district_set.filter(
                district_id=0).order_by('-version')[0]

        # Return the base geounits of the unassigned district
        return unassigned.get_base_geounits(threshold)

    def get_available_districts(self, version=None):
        """
        Get the number of districts that are available in the current plan.

        Returns:
            The number of districts that may added to this plan.
        """
        if version == None:
            version = self.version

        current_districts = len(self.get_districts_at_version(version))
        available_districts = self.legislative_body.max_districts

        return available_districts - current_districts + 1  #add one for unassigned

    def fix_unassigned(self, version=None, threshold=100):
        """
        Assign unassigned base geounits that are fully contained within
        or adjacent to another district

        First fix any unassigned geounits that are fully contained within a district.
        Only fix other adjacent geounits if the minimum percentage of assigned
        geounits has been reached.

        Parameters:
            version -- The version of the Plan that is being fixed.
            threshold - distance threshold used for buffer in/out optimization

        Returns:
            Whether or not the fix was successful, and a message
        """

        if version == None:
            version = self.version

        num_unassigned = 0
        geolevel = Geolevel.objects.get(
            id=self.legislative_body.get_base_geolevel())

        # Check that there are unassigned geounits to fix
        unassigned_district = self.district_set.filter(
            district_id=0, version__lte=version).order_by('-version')[0]
        unassigned_geom = unassigned_district.geom
        if not unassigned_geom or unassigned_geom.empty:
            return False, _('There are no unassigned units that can be fixed.')

        # Get the unlocked districts in this plan with geometries
        districts = self.get_districts_at_version(version, include_geom=False)
        districts = District.objects.filter(id__in=[
            d.id for d in districts if d.district_id != 0 and not d.is_locked
        ])
        districts = [d for d in districts if d.geom and not d.geom.empty]

        # Storage for geounits that need to be added. Map of tuples: geounitid -> (district_id, dist_val)
        to_add = {}

        # Check if any unassigned clusters are within the exterior of a district
        for unassigned_poly in unassigned_geom:
            for district in districts:
                for poly in district.geom:
                    if unassigned_poly.within(Polygon(poly.exterior_ring)):
                        for tup in self.get_base_geounits_in_geom(
                                unassigned_poly, threshold=threshold):
                            to_add[tup[0]] = (district.district_id, 0)

        # Check if all districts have been assigned
        num_districts = len(
            self.get_districts_at_version(version, include_geom=False)) - 1
        not_all_districts_assigned = num_districts < self.legislative_body.max_districts
        if not_all_districts_assigned and not to_add:
            return False, _(
                'All districts need to be assigned before fixing can occur. Currently: '
            ) + str(num_districts)

        # Only check for adjacent geounits if all districts are assigned
        if not not_all_districts_assigned:
            # Get unassigned geounits, and subtract out any that have been added to to_add
            unassigned = self.get_unassigned_geounits(
                threshold=threshold, version=version)
            unassigned = [t[0] for t in unassigned]
            num_unassigned = len(unassigned)
            unassigned = list(set(unassigned) - set(to_add.keys()))

            # Check that the percentage of assigned base geounits meets the requirements
            num_total_units = geolevel.geounit_set.count()
            pct_unassigned = 1.0 * num_unassigned / num_total_units
            pct_assigned = 1 - pct_unassigned
            min_pct = settings.FIX_UNASSIGNED_MIN_PERCENT / 100.0
            below_min_pct = pct_assigned < min_pct
            if below_min_pct and not to_add:
                return False, _('The percentage of assigned units is: ') + str(
                    int(pct_assigned * 100)) + '. ' + _(
                        'Fixing unassigned requires a minimum percentage of: '
                    ) + str(settings.FIX_UNASSIGNED_MIN_PERCENT)

            if not below_min_pct:
                # Get the unassigned geounits from the ids
                unassigned = list(Geounit.objects.filter(pk__in=unassigned))

                # Remove any unassigned geounits that aren't on the edge
                temp = []
                for poly in unassigned_geom:
                    exterior = Polygon(poly.exterior_ring)
                    for g in unassigned:
                        if not g in temp and g.geom.intersects(
                                unassigned_geom):
                            temp.append(g)
                unassigned = temp

                # Set up calculator/storage for comparator values (most likely population)
                calculator = SumValues()
                calculator.arg_dict['value1'] = (
                    'subject', settings.FIX_UNASSIGNED_COMPARATOR_SUBJECT)

                # Test each unassigned geounit with each unlocked district to see if it should be assigned
                for district in districts:
                    # Calculate the comparator value for the district
                    calculator.compute(district=district)
                    dist_val = calculator.result['value']

                    # Check if geounits are touching the district
                    for poly in district.geom:
                        exterior = Polygon(poly.exterior_ring)
                        for geounit in unassigned:
                            if geounit.geom.touches(exterior):
                                if (geounit.id not in to_add
                                        or dist_val < to_add[geounit.id][1]):
                                    to_add[geounit.id] = (district.district_id,
                                                          dist_val)

        # Add all geounits that need to be fixed
        if to_add:
            # Compile lists of geounits to add per district
            district_units = {}
            for gid, tup in to_add.items():
                did = tup[0]
                if did in district_units:
                    units = district_units[did]
                else:
                    units = []
                    district_units[did] = units
                units.append(gid)

            # Add units for each district, and update version, since it changes when adding geounits
            for did, units in district_units.items():
                self.add_geounits(did, [str(p) for p in units], geolevel.id,
                                  version, True)
                version = self.version

            # Fix versions so a single undo can undo the entire set of fixes
            num_adds = len(district_units.items())
            if num_adds > 1:
                # Delete interim unassigned districts
                self.district_set.filter(
                    district_id=0,
                    version__in=range(self.version - num_adds + 1,
                                      self.version)).delete()

                # Set all changed districts to the current version
                for dist in self.district_set.filter(
                        version__in=range(self.version - num_adds + 1,
                                          self.version)):
                    dist.version = self.version
                    dist.save()

            # Return status message
            num_fixed = len(to_add)
            text = _('Number of units fixed: ') + str(num_fixed)
            num_remaining = num_unassigned - num_fixed
            if (num_remaining > 0):
                text += ', ' + _('Number of units remaining: ') + str(
                    num_remaining)
            return True, text

        return False, _(
            'No unassigned units could be fixed. Ensure the appropriate districts are not locked.'
        )

    @transaction.atomic
    def combine_districts(self, target, components, version=None):
        """
        Given a target district, add the components and combine
        their scores and geography.  Target and components should
        be districts within this plan
        Parameters:
            target - A district within this plan
            components - A list of districts within this plan
                to combine with the target

        Returns:
            Whether the operation was successful
        """
        # Check to be sure they're all in the same version and don't
        # overlap - that should never happen
        if version == None:
            version = self.version
        if version != self.version:
            self.purge(after=version)

        district_keys = set(map(lambda d: d.id, components))
        district_keys.add(target.id)

        district_version = self.get_districts_at_version(version)
        version_keys = set(map(lambda d: d.id, district_version))
        if not district_keys.issubset(version_keys):
            raise Exception(
                'Attempted to combine districts not in the same plan or version'
            )
        if target.is_locked:
            raise Exception('You cannot combine with a locked district')

        try:
            target.id = None
            target.version = version + 1
            target.save()

            # Combine the stats for all of the districts
            all_characteristics = ComputedCharacteristic.objects.filter(
                district__in=district_keys)
            all_subjects = Subject.objects.order_by(
                '-percentage_denominator').all()
            for subject in all_subjects:
                relevant_characteristics = filter(
                    lambda c: c.subject == subject, all_characteristics)
                number = sum(map(lambda c: c.number, relevant_characteristics))
                percentage = Decimal('0000.00000000')
                if subject.percentage_denominator:
                    denominator = ComputedCharacteristic.objects.get(
                        subject=subject.percentage_denominator,
                        district=target)
                    if denominator:
                        if denominator.number > 0:
                            percentage = number / denominator.number
                cc = ComputedCharacteristic(
                    district=target,
                    subject=subject,
                    number=number,
                    percentage=percentage)
                cc.save()

            # Create a new copy of the target geometry
            all_geometry = map(lambda d: d.geom, components)
            all_geometry.append(target.geom)
            target.geom = enforce_multi(
                safe_union(
                    GeometryCollection(all_geometry, srid=target.geom.srid)),
                collapse=True)
            target.simplify()

            # Eliminate the component districts from the version
            for component in components:
                if component.district_id == target.district_id:
                    # Pasting a district to itself would've been handled earlier
                    continue
                component.id = None
                component.geom = MultiPolygon([], srid=component.geom.srid)
                component.version = version + 1
                component.simplify()  # implicit save

            self.version += 1
            self.save()
            return True, self.version
        except Exception as ex:
            return False, -1

    def get_district_info(self, version=None):
        """
        Get a set of tuples for each district in this plan. This will
        generate a list of tuples sorted by the 'district_id' field that
        contains the district name, and the number of members in the
        district.

        Parameters:
            version -- Optional; if specified, it will get the district
                       info for the specified version of the plan. If
                       omitted, the most recent plan version will be used.
        """
        version = version if not version is None else self.version
        districts = self.get_districts_at_version(version, include_geom=False)
        districts = sorted(districts, key=attrgetter('district_id'))
        districts = filter(lambda d: d.district_id != 0, districts)
        districts = map(lambda d:(d.long_label,d.num_members,), districts)

        return districts

    @staticmethod
    def find_relationships(above_id,
                           below_id,
                           above_version=None,
                           below_version=None,
                           de_9im='T********'):
        """
        Finds all relationships between two layers using the supplied intersection matrix

        Parameters:
            above_id -- The id of the layer that is 'above' the below plan hierarchically.
                        The id is in the form of either 'plan.XXX' or 'geolevel.XXX'

            below_id -- The id of the layer that is 'below' the above plan hierarchically.
                        The id is in the form of either 'plan.XXX' or 'geolevel.XXX'

            above_version -- Required only if the above_id is a Plan

            below_version -- Required only if the below_id is a Plan

            de_9im -- Dimensionally extended nine-intersection model string. Optional, by
                      default this is set to a standard intersection. ST_Relate is called
                      on each permutation of the two layers with the first parameter being
                      the above geometry, the second parameter being the below geometry,
                      and de_9im being the third parameter. Some examples:

                      T*F**FFF* (Equals)
                      FF*FF**** (Disjoint)
                      T******** (Intersects)
                      FT******* (Touches)
                      T*T****** (Crosses)
                      T*F**F*** (Within)
                      T*****FF* (Contains)
                      T*T***T** (Overlaps)
                      T*****FF* (Covers)
                      T*F**F*** (CoveredBy)

        Returns:
            An array of relationships, given as tuples, where the first item is the id of
            the district in the above layer of the relationship, the second
            item is the id of the district in the below layer of the relationship,
            the third item is the name associated with the first, and
            the fourth item is the name associated with the second.
        """
        # Determine whether the layers are plans or geolevels, and extract id
        is_above_plan = above_id.startswith('plan')
        above_id = int(above_id.split('.')[1])
        above_col_id = 'district_id' if is_above_plan else 'portable_id'
        above_table = 'redistricting_district' if is_above_plan else 'redistricting_geounit'
        above_name = 'long_label' if is_above_plan else 'name'

        is_below_plan = below_id.startswith('plan')
        below_id = int(below_id.split('.')[1])
        below_col_id = 'district_id' if is_below_plan else 'portable_id'
        below_table = 'redistricting_district' if is_below_plan else 'redistricting_geounit'
        below_name = 'long_label' if is_below_plan else 'name'

        # Ensure version is set on plans
        if is_above_plan and above_version is None:
            raise Exception('Version must be specified for above plan.')

        if is_below_plan and below_version is None:
            raise Exception('Version must be specified for below plan.')

        # Ensure DE-9IM string is valid
        if not re.match('[012TF\*]{9}', de_9im):
            raise Exception('DE-9IM string is invalid.')

        select = "SELECT above.%s, below.%s, above.%s, below.%s FROM %s as below" % (
            above_col_id, below_col_id, above_name, below_name, below_table)
        version_join = """
JOIN (
    SELECT max(version) as version, district_id FROM redistricting_district
    WHERE plan_id = %d
    AND version <= %d
    GROUP BY district_id
) AS lmt
"""
        district_cross_join = """
CROSS JOIN (
    SELECT sub.id, sub.district_id, sub.long_label, sub.geom
    FROM redistricting_district as sub
    %s ON sub.district_id = lmt.district_id
    WHERE sub.plan_id = %d AND sub.version = lmt.version AND sub.district_id > 0
) AS above
"""
        geo_cross = "CROSS JOIN redistricting_geounit as above"
        on_lmt = "ON below.district_id = lmt.district_id"
        relate = "AND ST_Relate(above.geom, below.geom, '%s')" % de_9im
        order = "ORDER BY above.%s, below.%s" % (above_col_id, below_col_id)
        below_join = version_join % (
            below_id, below_version) if below_version is not None else ""
        above_join = version_join % (
            above_id, above_version) if above_version is not None else ""
        above_cross = district_cross_join % (above_join, above_id)
        below_district_cross_join = district_cross_join % (below_join,
                                                           below_id)
        below_and = "AND below.district_id > 0 AND below.version = lmt.version"
        plan_where = "WHERE below.plan_id = %d" % below_id
        geolevel_join = "JOIN redistricting_geounit_geolevel gl on %s.id = gl.geounit_id"
        geolevel_below_join = geolevel_join % "below"
        geolevel_above_join = geolevel_join % "above"
        geolevel_where = "WHERE gl.geolevel_id = %d" % below_id
        geolevel_and = "AND gl.geolevel_id = %d" % above_id

        # Two Plans
        if is_above_plan and is_below_plan:
            query = "%s %s %s %s %s %s %s %s" % (select, below_join, on_lmt,
                                                 above_cross, plan_where,
                                                 below_and, relate, order)

        # Plan above, Geolevel below
        elif is_above_plan and not is_below_plan:
            query = "%s %s %s %s %s %s" % (select, above_cross,
                                           geolevel_below_join, geolevel_where,
                                           relate, order)

        # Geolevel above, Plan below
        elif not is_above_plan and is_below_plan:
            query = "%s %s %s %s %s %s %s %s %s %s" % (select, below_join,
                                                       on_lmt, geo_cross,
                                                       geolevel_above_join,
                                                       plan_where, below_and,
                                                       geolevel_and, relate,
                                                       order)

        # Two geolevels
        else:
            raise Exception('Geolevel-geolevel relationships not implemented.')

        cursor = connection.cursor()
        cursor.execute(query)
        return cursor.fetchall()

    def find_plan_relationships(self,
                                other_plan,
                                version=None,
                                other_version=None,
                                inverse=False,
                                de_9im='T********'):
        """
        Finds all relationships between this plan and the below one.

        Parameters:
            other_plan -- The plan that is 'below' this plan hierarchically. The below
                          plan should most likely have a larger number of districts. A split occurs
                          when a district in this plan crosses the boundary of a district
                          in the other plan.

            version -- Optional; if specified, splits will be calculated using
                       districts in the specified version of the plan. If
                       omitted, the most recent plan version will be used.

            other_version -- Optional; if specified, splits will be calculated using
                             districts in the specified version of the other plan. If
                             omitted, the most recent version of the other plan
                             will be used.

            inverse -- Optional; if specified, performs the inverse split operation

            de_9im -- Dimensionally extended nine-intersection model string. Optional, by
                      default this is set to a standard intersection.

        Returns:
            An array of relationships, given as tuples, where the first item is the id of
            the district in the above layer of the relationship, the second
            item is the id of the district in the below layer of the relationship,
            the third item is the name associated with the first, and
            the fourth item is the name associated with the second.
        """
        if not other_plan:
            raise Exception(
                'Other plan must be specified for use in finding relationships.'
            )

        version = version if not version is None else self.version
        other_version = other_version if not other_version is None else other_plan.version

        top_id = 'plan.%d' % other_plan.id if inverse else 'plan.%d' % self.id
        top_version = other_version if inverse else version

        bottom_id = 'plan.%d' % self.id if inverse else 'plan.%d' % other_plan.id
        bottom_version = version if inverse else other_version

        return Plan.find_relationships(top_id, bottom_id, top_version,
                                       bottom_version, de_9im)

    def find_plan_splits(self,
                         other_plan,
                         version=None,
                         other_version=None,
                         inverse=False):
        """
        Helper method that finds plan splits. See find_plan_relationships for parameter details.
        """
        return self.find_plan_relationships(other_plan, version, other_version,
                                            inverse, '***T*****')

    def find_plan_components(self,
                             other_plan,
                             version=None,
                             other_version=None,
                             inverse=False):
        """
        Helper method that finds the components of districts. See find_plan_relationships for parameter details.
        Returns a map of all other districts that are fully contained within each district of this plan.
        """
        return self.find_plan_relationships(other_plan, version, other_version,
                                            inverse, 'T*****FF*')

    def find_plan_intersections(self,
                                other_plan,
                                version=None,
                                other_version=None,
                                inverse=False):
        """
        Helper method that finds intersecting districts. See find_plan_relationships for parameter details.
        Returns a map of all other districts that intersect each district of this plan.
        """
        return self.find_plan_relationships(other_plan, version, other_version,
                                            inverse, 'T********')

    def find_geolevel_relationships(self,
                                    geolevelid,
                                    version=None,
                                    inverse=False,
                                    de_9im='T********'):
        """
        Finds all relationships between this plan and the below geolevel layer.

        Parameters:
            geolevelid -- The geolevel that is 'below' this plan hierarchically.
                          A split occurs when a district in this plan crosses the
                          boundary of a geounit in the geolevel.

            version -- Optional; if specified, splits will be calculated using
                       districts in the specified version of the plan. If
                       omitted, the most recent plan version will be used.

            inverse -- Optional; if specified, performs the inverse split operation

            de_9im -- Dimensionally extended nine-intersection model string. Optional, by
                      default this is set to a standard intersection.

        Returns:
            An array of relationships, given as tuples, where the first item is the id of
            the district in the above layer of the relationship, the second
            item is the portable_id of the geounit in the below layer of the relationship,
            the third item is the name associated with the first, and
            the fourth item is the name associated with the second.
        """
        if not geolevelid:
            raise Exception(
                'geolevelid must be specified for use in finding splits.')

        version = version if not version is None else self.version

        top_id = 'geolevel.%d' % geolevelid if inverse else 'plan.%d' % self.id
        top_version = None if inverse else version

        bottom_id = 'plan.%d' % self.id if inverse else 'geolevel.%d' % geolevelid
        bottom_version = version if inverse else None

        return Plan.find_relationships(top_id, bottom_id, top_version,
                                       bottom_version, de_9im)

    def find_geolevel_splits(self, geolevelid, version=None, inverse=False):
        """
        Helper method that finds geolevel splits. See find_plan_relationships for parameter details.
        """
        return self.find_geolevel_relationships(geolevelid, version, inverse,
                                                '***T*****')

    def find_geolevel_components(self, geolevelid, version=None,
                                 inverse=False):
        """
        Helper method that finds components of geolevel units. See find_plan_relationships for parameter details.
        Returns a map of all geolevel units that are fully contained within each district of this plan.
        """
        return self.find_geolevel_relationships(geolevelid, version, inverse,
                                                'T*****FF*')

    def find_geolevel_intersections(self,
                                    geolevelid,
                                    version=None,
                                    inverse=False):
        """
        Helper method that finds intersections with geounits. See find_plan_relationships for parameter details.
        Returns a map of all geolevel units that intersect each district of this plan.
        """
        return self.find_geolevel_relationships(geolevelid, version, inverse,
                                                'T********')

    def get_community_types(self, version=None):
        """
        Given a plan, return a dictionary with community types, keyed on district_id
        """
        community_types = {}

        for d in self.get_districts_at_version(version):
            typetags = filter(lambda tag: tag.name[:4] == 'type', d.tags)
            if typetags:
                typetags = map(lambda tag: tag.name[5:], typetags)
                community_types[d.district_id] = typetags
        return community_types

    def count_community_types(self, version=None):
        """
        Given a plan, return a list of dictionaries, with each community type
        as the value for the 'type' key and the number of times it appears
        in the plan as the value for the 'number' key
        """
        districts = self.get_districts_at_version(version)
        items = TaggedItem.objects.filter(
            object_id__in=[d.id for d in districts])
        types = {}
        for i in items:
            name = i.tag.name
            if name.startswith('type='):
                name = name[5:]
            else:
                continue

            if name in types:
                types[name] += 1
            else:
                types[name] = 1
        return [{'type': key, 'number': value} for key, value in types.items()]

    @staticmethod
    def tag_plan_names(names, types):
        """
        Given a dictionary of names and a dictionary of types, return a dictionary of
        names with optional community types, keyed on district id
        """
        name_dict = {}
        for d in names.keys():
            name_dict[d] = '%s - %s' % (
                names[d], ', '.join(types[d])) if d in types else names[d]
        return name_dict

    def compute_splits(self, target, version=None, inverse=None,
                       extended=None):
        results = {
            'splits': None,
            'interiors': [],
            'named_splits': None,
            'plan_name': self.name,
            'other_name': None,
            'is_geolevel': False,
            'is_community': False
        }
        other_names = None

        id = int(target[target.find('.') + 1:])
        my_names = dict((d.district_id, d.long_label)
                        for d in self.get_districts_at_version(version))

        if target.startswith('geolevel'):
            results['other_name'] = Geolevel.objects.get(
                pk=id).get_short_label()
            results['is_geolevel'] = True
            results['splits'] = self.find_geolevel_splits(
                id, version=version, inverse=inverse)
            if extended is True:
                results['interiors'] = self.find_geolevel_components(
                    id, version=version, inverse=inverse)
        elif target.startswith('plan'):
            other_plan = Plan.objects.get(pk=id)
            results['other_name'] = other_plan.name
            if self.is_community():
                results['is_community'] = True

            results['splits'] = self.find_plan_splits(
                other_plan, version=version, inverse=inverse)
            if extended is True:
                results['interiors'] = self.find_plan_components(
                    other_plan, version=version, inverse=inverse)
            other_names = dict((d.district_id, d.long_label)
                               for d in other_plan.get_districts_at_version(
                                   other_plan.version))

        community_types = self.get_community_types(version=version)
        my_names = Plan.tag_plan_names(my_names, community_types)

        if other_names:
            other_community_types = other_plan.get_community_types(
                other_plan.version)
            other_names = Plan.tag_plan_names(other_names,
                                              other_community_types)

        # Swap names if inversed
        if inverse:
            if other_names:
                results['named_splits'] = [(other_names[s[0]], my_names[s[1]],
                                            True) for s in results['splits']]
                results['named_splits'] += [(other_names[s[0]],
                                             my_names[s[1]], False)
                                            for s in results['interiors']]
            else:
                results['named_splits'] = [(s[2], my_names[s[1]], True)
                                           for s in results['splits']]
                results['named_splits'] += [(s[2], my_names[s[1]], False)
                                            for s in results['interiors']]

            results['plan_name'] = results['other_name']
            results['other_name'] = self.name
        else:
            if other_names:
                results['named_splits'] = [(my_names[s[0]], other_names[s[1]],
                                            True) for s in results['splits']]
                results['named_splits'] += [(my_names[s[0]],
                                             other_names[s[1]], False)
                                            for s in results['interiors']]
            else:
                results['named_splits'] = [(my_names[s[0]], s[3], True)
                                           for s in results['splits']]
                results['named_splits'] += [(my_names[s[0]], s[3], False)
                                            for s in results['interiors']]

        # Get dictionaries on which we can regroup
        results['named_splits'] = [{
            'geo': x,
            'interior': y,
            'split': z
        } for x, y, z in results['named_splits']]
        return results

    def get_community_type_info(self,
                                target,
                                version=None,
                                inverse=None,
                                include_counts=True):
        """
        Given a Plan, return the community type tables used in the split report.
        If the Plan on the "bottom" of the split report request is not a community map,
        this method will return None
        """
        # We only return this for the community on the "bottom" layer
        target_id = int(target[target.find('.') + 1:])
        community = None
        if target.startswith(
                'geolevel') and inverse is True and self.is_community():
            # Get our splits
            intersections = self.find_geolevel_intersections(
                target_id, version=version, inverse=inverse)
            community = self
        elif target.startswith('plan'):
            target = Plan.objects.get(pk=target_id)
            if inverse is True and self.is_community():
                community = self
            elif inverse is False and target.is_community():
                community = target
                version = target.version
            intersections = self.find_plan_intersections(
                target, version=version, inverse=inverse)
        if community is None:
            # There's not community map as the "bottom" layer
            return
        types = community.get_community_types(version=version)
        my_names = dict((d.district_id, d.long_label)
                        for d in community.get_districts_at_version(version))
        district_dict = {}
        for i in intersections:
            community_id = i[1]
            district_name = i[2]
            if district_name not in district_dict:
                district_dict[district_name] = {}
            current_dist = district_dict[district_name]
            try:
                for t in types[community_id]:
                    if t in current_dist:
                        current_dist[t] += 1
                    else:
                        current_dist[t] = 1
            except KeyError:
                # This community has no types
                continue

        type_splits = []
        for district, split in district_dict.items():
            for split_type, number in district_dict[district].items():
                type_splits.append({
                    'name': district,
                    'type': split_type,
                    'number': number
                })

        type_counts = community.count_community_types(
            version=version) if include_counts else None
        return {'type_splits': type_splits, 'type_counts': type_counts}

    def get_last_district_changed(self):
        """
        Get the last district that has been changed in this plan.

        Returns:
            The district with the version number that matches this plan.
        """
        districts = self.district_set.filter(version=self.version)
        if districts.count() == 0:
            return None
        return districts[0]

    def get_friendly_name(self):
        """
        Get an os-friendly name. This removes wildcards, path separators, and
        line terminators from the plan name.
        """
        cleanRE = re.compile('\W+')
        return cleanRE.sub('_', self.name)

    def get_largest_geolevel(self):
        """
        Get the geolevel relevant to this plan that has the largest geounits
        """
        leg_levels = LegislativeLevel.objects.filter(
            legislative_body=self.legislative_body)
        geolevel = leg_levels[0].geolevel
        for l in leg_levels:
            if l.geolevel.min_zoom < geolevel.min_zoom:
                geolevel = l.geolevel
        return geolevel

    def reaggregate(self):
        """
        Reaggregate all computed characteristics for each district in this plan.

        @return: An integer count of the number of districts reaggregated
        """
        # Set the reaggregating flag
        self.processing_state = ProcessingState.REAGGREGATING
        self.save()

        try:
            # Find the geolevel relevant to this plan that has the largest geounits
            geolevel = self.get_largest_geolevel()

            # Get all of the geounit_ids for that geolevel
            geounit_ids = map(
                str,
                Geounit.objects.filter(geolevel=geolevel).values_list(
                    'id', flat=True))

            # Cycle through each district and update the statistics
            updated = 0
            for d in self.district_set.all():
                success = d.reaggregate(geounit_ids=geounit_ids)
                if success == True:
                    updated += 1

            # Reaggregation successful, unset the reaggregating flag
            self.processing_state = ProcessingState.READY
            self.save()

        except Exception as ex:
            logger.info('Unable to fully reaggreagate %d', self.id)
            logger.debug('Reason:', ex)

            # Reaggregation unsuccessful, set state back to needs reaggregation
            self.processing_state = ProcessingState.NEEDS_REAGG
            self.save()

        return updated


class PlanForm(ModelForm):
    """
    A form for displaying and editing a Plan.
    """

    class Meta:
        """
        A helper class that describes the PlanForm.
        """

        # This form's model is a Plan
        model = Plan
        exclude = ['id']


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
        ordering = ['short_label']

    # The district_id of the district, this is not the primary key ID,
    # but rather, an ID of the district that remains constant over all
    # versions of the district.
    district_id = models.PositiveIntegerField(default=None)

    # The short name of the district
    short_label = models.CharField(max_length=10)

    # The long name of the district
    long_label = models.CharField(max_length=256)

    # The parent Plan that contains this District
    plan = models.ForeignKey(Plan)

    # The geometry of this district (high detail)
    geom = models.MultiPolygonField(srid=3785, default=MultiPolygon([]))

    # The simplified geometry of this district
    simple = models.GeometryCollectionField(
        srid=3785, default=GeometryCollection([]))

    # The version of this district.
    version = models.PositiveIntegerField(default=0)

    # A flag that indicates if this district should be edited
    is_locked = models.BooleanField(default=False)

    # The number of representatives configured for this district
    num_members = models.PositiveIntegerField(default=1)

    # This is a geographic model, so use the geomanager for objects
    objects = models.GeoManager()

    def sortKey(self):
        """
        Sort districts by name, with numbered districts first.

        Returns:
            The Districts, sorted in numerical order.
        """
        name = self.short_label
        prefix = self.plan.legislative_body.get_short_label()
        index = prefix.find('%')
        if index >= 0:
            prefix = prefix[0:index]
        else:
            index = 0

        try:
            if name.startswith(prefix):
                name = name[index:]
        except UnicodeDecodeError:
            pass
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

    @property
    def is_unassigned(self):
        """
        Convenience property for readability (or a change in the district_id of
        Unassigned)
        """
        return self.district_id == 0

    @property
    def translated_label(self):
        """
        Returns a translated long district label
        """
        # a district label ends with the district id, and potentially other things,
        # such as a multi-member district suffix. in order to translate it, we need
        # to translate just the first part of the string.
        a, b, c = self.long_label.partition(' ')
        return '%s%s%s' % (_(a), b, c)

    def __unicode__(self):
        """
        Represent the District as a unicode string. This is the District's
        name.
        """
        return self.short_label

    def delta_stats(self, geounits, combine):
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
        all_subjects = Subject.objects.order_by(
            '-percentage_denominator').all()
        changed = False

        # For all subjects
        for subject in all_subjects:
            # Aggregate all Geounits Characteristic values
            aggregate = Characteristic.objects.filter(
                geounit__in=geounits, subject__exact=subject).aggregate(
                    Sum('number'))['number__sum']
            # If there are aggregate values for the subject and geounits.
            if not aggregate is None:
                # Get the pre-computed values
                defaults = {'number': Decimal('0000.00000000')}
                computed, created = ComputedCharacteristic.objects.get_or_create(
                    subject=subject, district=self, defaults=defaults)

                if combine:
                    # Add the aggregate to the computed value
                    computed.number += aggregate
                else:
                    # Subtract the aggregate from the computed value
                    computed.number -= aggregate

                # If this subject is viewable as a percentage, do the math
                # using the already calculated value for the denominator
                if subject.percentage_denominator:
                    denominator = ComputedCharacteristic.objects.get(
                        subject=subject.percentage_denominator, district=self)
                    if denominator:
                        if denominator.number > 0:
                            computed.percentage = computed.number / denominator.number
                        else:
                            computed.percentage = '0000.00000000'

                # If there are aggregate values for the subject & geounits.
                computed.save()

                changed = True

        return changed

    def reset_stats(self):
        """
        Reset the statistics to zero for this district. This method walks
        through all available subjects, and sets the computed
        characteristic for this district to zero.

        Returns:
            True if the district stats were changed.
        """
        all_subjects = Subject.objects.all()
        changed = False

        # For all subjects
        for subject in all_subjects:
            # Get the pre-computed values
            defaults = {'number': Decimal('0000.00000000')}
            computed, created = ComputedCharacteristic.objects.get_or_create(
                subject=subject, district=self, defaults=defaults)

            if not created:
                # Add the aggregate to the computed value
                computed.number = '0000.00000000'
                computed.percentage = '0000.00000000'

                # Save these values
                computed.save()

                changed = True

        return changed

    def clone_relations_from(self, origin):
        """
        Copy the computed characteristics, comments, and tags from one
        district to another.

        Cloning District Characteristics, Comments and Tags are required when
        cloning, copying, or instantiating a template district.

        Parameters:
            origin -- The source District.
        """
        cc = ComputedCharacteristic.objects.filter(district=origin)
        for c in cc:
            c.id = None
            c.district = self
            c.save()

        ct = ContentType.objects.get(
            app_label='redistricting', model='district')
        cmts = Comment.objects.filter(object_pk=origin.id, content_type=ct)
        for cmt in cmts:
            cmt.id = None
            cmt.object_pk = self.id
            cmt.save()

        items = TaggedItem.objects.filter(object_id=origin.id, content_type=ct)
        for item in items:
            item.id = None
            item.object_id = self.id
            item.save()

    def get_base_geounits(self, threshold=100):
        """
        Get a list of the geounit ids of the geounits that comprise
        this district at the base level.

        We'll check this by seeing whether the centroid of each geounits
        fits within the simplified geometry of this district.

        Parameters:
            threshold - distance threshold used for buffer in/out optimization

        Returns:
            A list of tuples containing Geounit IDs, portable ids, and num_members
            that lie within this District.
        """
        return self.plan.get_base_geounits_in_geom(self.geom, threshold)

    def get_contiguity_overrides(self):
        """
        Retrieve any contiguity overrides that are applicable
        to this district. This is defined by any ContiguityOverride
        objects whose two referenced geounits both fall within
        the geometry of this district.
        """
        if not self.geom:
            return []

        filter = Q(override_geounit__geom__within=self.geom)
        filter = filter & Q(connect_to_geounit__geom__within=self.geom)
        return list(ContiguityOverride.objects.filter(filter))

    def simplify(self, attempts_allowed=5, attempt_step=.80):
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
        levels = sorted(levels, key=lambda l: l.id)
        simples = []
        index = 1
        for level in levels:
            while index < level.id:
                # We want to store the levels within a GeometryCollection, and make it so the level id
                # can be used as the index for lookups. So for disparate level ids, empty geometries need
                # to be stored. Empty GeometryCollections cannot be inserted into a GeometryCollection,
                # so a Point at the origin is used instead.
                simples.append(Point((0, 0), srid=self.geom.srid))
                index += 1
            if self.geom.num_coords > 0:
                simplified = False
                attempts_left = attempts_allowed
                tolerance = level.tolerance

                while simplified is not True and attempts_left >= 1:
                    try:
                        simple_geom = self.geom.simplify(
                            preserve_topology=True, tolerance=tolerance)
                        if simple_geom.valid:
                            simples.append(simple_geom)
                            simplified = True
                            attempts_left -= 1  # We just used one up
                            times_attempted = attempts_allowed - attempts_left
                            if times_attempted > 1:
                                logger.debug(
                                    'Took %d attempts to simplify %s in plan "%s"; '
                                    'Succeeded with tolerance %s',
                                    times_attempted, self.long_label,
                                    self.plan.name, tolerance)
                        else:
                            raise Exception(
                                'Polygon simplifies but isn\'t valid')
                    except Exception as error:
                        logger.debug(
                            'WARNING: Problem when trying to simplify %s at tolerance %s: %s',
                            self.long_label, tolerance, error)
                        tolerance = tolerance * attempt_step
                    attempts_left -= 1

                if not simplified:
                    simples.append(self.geom)
                    logger.debug(
                        'Ran out of attempts to simplify %s in plan "%s" for geolevel %s; using full geometry',
                        self.long_label, self.plan.name,
                        level.get_short_label())
            else:
                simples.append(self.geom)

            index += 1
        self.simple = GeometryCollection(tuple(simples), srid=self.geom.srid)
        self.save()

    def count_community_type_union(self, community_map_id, version=None):
        """
        Count the number of distinct types of communities in the provided
        community map. Only the community types of the communities that
        intersect this district are counted.

        @param community_map_id: A L{Plan} ID linked to the
            community-mapping L{LegislativeBody}.
        @param version: The version of the community_map to examine.
            Defaults to the current plan version.
        @return: An integer count of the number of distinct community
            types intersecting this district.
        """
        return len(
            self.get_community_type_union(community_map_id, version=version))

    def get_community_type_union(self, community_map_id, version=None):
        """
        Get the union of all the types of communities in this district.
        Only the community types of the communities that intersect this
        district are counted.

        @param community_map_id: A L{Plan} ID linked to the
            community-mapping L{LegislativeBody}.
        @param version: The version of the community_map to examine.
            Defaults to the current plan version.
        @return: The set of all community types in this district.
        """
        community_map = Plan.objects.get(id=community_map_id)

        if version is None:
            version = community_map.version

        # Filters - first get all districts
        communities = community_map.get_districts_at_version(
            version, include_geom=True)
        # Filter quickly by envelope
        communities = filter(
            lambda z: True if self.geom.envelope.intersects(z.geom.envelope) else False,
            communities)
        # Filter by relation - must have interior intersection
        communities = filter(
            lambda z: True if self.geom.relate_pattern(z.geom, 'T********') else False,
            communities)

        types = set()
        for community in communities:
            types = types | set(
                Tag.objects.get_for_object(community).filter(
                    name__startswith='type='))
        return types

    def reaggregate(self, geounit_ids=None):
        """
        Reaggregate all computed characteristics for this district.

        @param geounit_ids: Optional set of geounits to filter on. If this is
            not provided, it will be calculatated by using all geounits
            in the largest geolevel of the plan.
        @return: True if reaggregation was successfull, False otherwise.
        """

        # Find the geolevel relevant to this plan that has the largest geounits
        geolevel = self.plan.get_largest_geolevel()

        # If not specified, get all of the geounit_ids for that geolevel
        if geounit_ids is None:
            geounit_ids = map(
                str,
                Geounit.objects.filter(geolevel=geolevel).values_list(
                    'id', flat=True))

        try:
            body = self.plan.legislative_body
            geounits = Geounit.get_mixed_geounits(geounit_ids, body,
                                                  geolevel.id, self.geom, True)

            # Grab all the computedcharacteristics for the district and reaggregate
            for cc in self.computedcharacteristic_set.order_by(
                    '-subject__percentage_denominator'):
                cs = Characteristic.objects.filter(
                    subject=cc.subject, geounit__in=geounits)
                agg = cs.aggregate(Sum('number'))
                cc.number = agg['number__sum']
                cc.percentage = '0000.00000000'
                if cc.subject.percentage_denominator:
                    c = self.computedcharacteristic_set.get(
                        subject=cc.subject.percentage_denominator)
                    denominator = c.number
                    if cc.number and denominator:
                        cc.percentage = cc.number / denominator
                if not cc.number:
                    cc.number = '00000000.0000'
                cc.save()
            return True
        except Exception as ex:
            logger.info('Unable to reaggreagate district "%s"',
                        self.long_label)
            logger.debug('Reason:', ex)
            return False

    def count_splits(self, geolevel_id):
        """
        Count how many times a geolevel is split by this district.

        @param geolevel_id: ID of the geolevel to perform the split
            comparison on.
        @return: The number of times the geolevel is split by the district.
        """
        query = "SELECT COUNT(1) FROM redistricting_district d, redistricting_geounit_geolevel l JOIN redistricting_geounit g on l.geounit_id = g.id WHERE d.id = %d AND l.geolevel_id = %d AND ST_Relate(d.geom, g.geom, '***T*****');" % (
            self.id, geolevel_id)

        cursor = connection.cursor()
        cursor.execute(query)
        return cursor.fetchone()[0]


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
    number = models.DecimalField(max_digits=12, decimal_places=4)

    # The aggregate as a percentage of the percentage_denominator's aggregated value.
    percentage = models.DecimalField(
        max_digits=12, decimal_places=8, null=True, blank=True)

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

    def __unicode__(self):
        """
        Represent the Profile as a unicode string. This is the a string
        with the User's name.
        """
        return "%s's profile" % self.user.username


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
    if district.district_id is None:
        districts = district.plan.get_districts_at_version(
            district.version, include_geom=False)
        ids_in_use = map(lambda d: d.district_id, districts)
        max_districts = district.plan.legislative_body.max_districts + 1
        if len(ids_in_use) >= max_districts:
            raise ValidationError(
                "Plan is at maximum district capacity of %d" % max_districts)
        else:
            # Find one not in use - 0 is unassigned
            # TODO - update this if unassigned is not district_id 0
            for i in range(1, max_districts + 1):
                if i not in ids_in_use:
                    district.district_id = i
                    return


def update_plan_edited_time(sender, **kwargs):
    """
    Update the time that the plan was edited whenever the plan is saved.
    """
    district = kwargs['instance']
    plan = district.plan
    plan.edited = datetime.now()
    plan.save()


def create_unassigned_district(sender, **kwargs):
    """
    When a new plan is saved, all geounits must be inserted into the
    Unassigned districts.
    """
    plan = kwargs['instance']
    created = kwargs['created']

    if created and plan.create_unassigned:
        plan.create_unassigned = False

        unassigned = District(
            short_label=u"\u0398",
            long_label=_("Unassigned"),
            version=0,
            plan=plan,
            district_id=0)

        biggest_geolevel = plan.get_biggest_geolevel()
        all_shapes = [
            x.geom for x in biggest_geolevel.geounit_set.only('geom')
        ]
        joined_shape = reduce(lambda x, y: x.union(y), all_shapes)
        if joined_shape.geom_type == 'MultiPolygon':
            all_geom = joined_shape.cascaded_union
        else:
            all_geom = joined_shape

        if plan.district_set.count() > 0:
            taken = MultiPolygon(
                [x.geom.unary_union for x in plan.district_set.all()])
            unassigned.geom = enforce_multi(all_geom.difference(taken))
            unassigned.simplify()  # implicit save
            geounit_ids = map(
                str,
                biggest_geolevel.geounit_set.filter(
                    geom__bboverlaps=unassigned.geom).values_list(
                        'id', flat=True))
            geounits = Geounit.get_mixed_geounits(
                geounit_ids, plan.legislative_body, biggest_geolevel.id,
                unassigned.geom, True)
        else:
            unassigned.geom = enforce_multi(all_geom)
            unassigned.simplify()  #implicit save
            geounits = biggest_geolevel.geounit_set.all()

        unassigned.delta_stats(geounits, True)


# Connect the post_save signal from a User object to the update_profile
# helper method
post_save.connect(
    update_profile,
    sender=User,
    dispatch_uid="publicmapping.redistricting.User")
# Connect the pre_save signal to the set_district_id helper method
pre_save.connect(set_district_id, sender=District)
# Connect the post_save signal to the update_plan_edited_time helper method
post_save.connect(update_plan_edited_time, sender=District)
# Connect the post_save signal from a Plan object to the
# create_unassigned_district helper method (don't remove the dispatch_uid or
# this signal is sent twice)
post_save.connect(
    create_unassigned_district,
    sender=Plan,
    dispatch_uid="publicmapping.redistricting.Plan")


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
    return (plan.owner == user
            or user.is_staff) and not plan.is_template and not plan.is_shared


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
    return plan.owner == user or plan.is_shared or plan.is_template


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
    Create an empty MultiPolygon.

    Parameters:
        srid -- The spatial reference for this empty geometry.

    Returns:
        An empty geometry.
    """
    return MultiPolygon([], srid=srid)


def enforce_multi(geom, collapse=False):
    """
    Make a geometry a multi-polygon geometry.

    This method wraps Polygons in MultiPolygons. If geometry exists, but is
    neither polygon or multipolygon, an empty geometry is returned. If no
    geometry is provided, no geometry (None) is returned.

    Parameters:
        geom -- The geometry to check/enforce.
        collapse -- A flag indicating that this method should collapse
                    the resulting multipolygon via cascaded_union. With
                    this flag, the method still returns a multipolygon.
    Returns:
        A multi-polygon from any geometry type.
    """
    mpoly = MultiPolygon([])
    if not geom is None:
        mpoly.srid = geom.srid

    if geom.empty:
        pass
    elif geom.geom_type == 'MultiPolygon':
        if collapse:
            mpoly = enforce_multi(geom.cascaded_union)
        else:
            mpoly = geom
    elif geom.geom_type == 'Polygon':
        # Collapse has no meaning if this is a single polygon
        mpoly.append(geom)
    elif geom.geom_type == 'GeometryCollection':
        components = []
        for item in geom:
            for component in enforce_multi(item):
                mpoly.append(component)

        if collapse:
            # Collapse the multipolygon group
            mpoly = enforce_multi(mpoly, collapse)

    return mpoly


def safe_union(collection):
    """
    Attempt to safely union a set of geometries. Sometimes, the default
    union() method on a geometry collection and/or geoqueryset results
    in a TopologyException. This method attempts to create a safe union
    of geometries by buffering the collection to 0, then performing a
    cascaded union on the remainder (if the result of the buffer is a
    multipolygon).
    """
    if isinstance(collection, GeoQuerySet):
        # collection is a GeoQuerySet
        geom = collection.aggregate(Collect('geom'))['geom__collect']
        if collection.count() == 0:
            return geom
    elif isinstance(collection, GeometryCollection):
        # collection is a GeometryCollection
        geom = collection

    geom = geom.buffer(0)

    if geom.geom_type == 'MultiPolygon':
        geom = geom.cascaded_union

    return geom


class ScoreFunction(BaseModel):
    """
    Score calculation definition
    """

    # Namepace of the calculator module to use for scoring
    calculator = models.CharField(max_length=500)

    # Name of this score function
    name = models.CharField(max_length=50)

    # Whether or not this score function is for a plan
    is_planscore = models.BooleanField(default=False)

    # Whether a user can select this function for use in a
    # statistics set, per legislative levelqq
    selectable_bodies = models.ManyToManyField(LegislativeBody)

    class Meta:
        """
        Additional information about the Subject model.
        """

        # The default method of sorting Subjects should be by 'sort_key'
        ordering = ['name']

        # A unique constraint on the name
        unique_together = ('name', )

    def get_calculator(self):
        """
        Retrieve a calculator instance by name.

        Parameters:
            name -- The fully qualified name of the calculator class.

        Returns:
            An instance of the requested calculator.
        """
        parts = self.calculator.split('.')
        module = ".".join(parts[:-1])
        m = __import__(module)
        for comp in parts[1:]:
            m = getattr(m, comp)
        return m()

    def score(self,
              districts_or_plans,
              format='raw',
              version=None,
              score_arguments=None):
        """
        Calculate the score for the object or list of objects passed in.

        Parameters:
            districts_or_plans -- Either a single district, a single plan,
                a list of districts, or a list of plans. Whether or not
                this deals with districts or plans must be in sync with
                the value of is_planscore.
            format -- One of 'raw', 'html', or 'json'.
                Determines how the results should be returned.
            score_arguments -- a list of ScoreArguments to override the entries
                linked through the database

        Returns:
            A score for each district or plan contained within
            districts_or_plans. If districts_or_plans is a single
            district or plan, a single result will be returned. If it
            is a list, a list of results in the same order as
            districts_or_plans will be returned.
        """
        # Raises an ImportError if there is no calculator with the given name
        calc = self.get_calculator()

        # Is districts_or_plans a list, or a single district/plan?
        is_list = isinstance(districts_or_plans, list)

        # Calculate results for every item in the list
        results = []
        for dp in (districts_or_plans if is_list else [districts_or_plans]):
            # Add all arguments that are defined for this score function
            if score_arguments is not None:
                args = score_arguments
            else:
                args = ScoreArgument.objects.filter(function=self)
            arg_lst = []
            for arg in args:
                # For 'score' types, calculate the score, and then pass the result on
                if (arg.type != 'score'):
                    calc.arg_dict[arg.argument] = (arg.type, arg.value)
                else:
                    score_fn = ScoreFunction.objects.get(name=arg.value)

                    # If this is a plan score and the argument is a
                    # district score, extract the districts from the
                    # plan, score each individually, # and pass into the
                    # score function as a list
                    if not (self.is_planscore and not score_fn.is_planscore):
                        calc.arg_dict[arg.argument] = ('literal',
                                                       score_fn.score(
                                                           dp,
                                                           format=format,
                                                           version=version))
                    else:
                        version = dp.version if version is None else version
                        for d in dp.get_districts_at_version(version):
                            res = score_fn.score(
                                d, format=format, version=version)
                            if isinstance(res, dict) and 'value' in res:
                                res = res['value']
                            arg_lst.append(res)

            # Build the keyword arguments based on whether this is for districts, plans, or list
            if len(arg_lst) > 0:
                kwargs = {'list': arg_lst}
            elif self.is_planscore:
                kwargs = {
                    'plan': dp,
                    'version': version if version is not None else dp.version
                }
            else:
                kwargs = {'district': dp}

            # Ask the calculator instance to compute the result
            calc.compute(**kwargs)

            # Format the result
            fl = format.lower()
            r = calc.html() if fl == 'html' else (calc.json() if fl == 'json'
                                                  else calc.result)
            results.append(r)

        return results if is_list else results[0]

    def __unicode__(self):
        """
        Get a unicode representation of this object. This is the
        ScoreFunction's name.
        """
        return self.get_label()


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

    def __unicode__(self):
        """
        Get a unicode representation of this object. This is the Argument's
        arg/value/type.
        """
        return "%s / %s / %s" % (self.argument, self.type, self.value)


class ScoreDisplay(BaseModel):
    """
    Container for displaying score panels
    """

    # The name of the score display
    name = models.CharField(max_length=50)

    # The title of the score display, user-specifiable
    title = models.CharField(max_length=50)

    # The legislative body that this score display is for
    legislative_body = models.ForeignKey(LegislativeBody)

    # Whether or not this score display belongs on the leaderboard page
    is_page = models.BooleanField(default=False)

    # The style to be assigned to this score display
    cssclass = models.CharField(max_length=50, blank=True)

    # The owner of this ScoreDisplay
    owner = models.ForeignKey(User)

    class Meta:
        """
        Define a unique constraint on 2 fields of this model.
        """
        unique_together = ('name', 'title', 'owner', 'legislative_body')

    def __unicode__(self):
        """
        Get a unicode representation of this object. This is the Display's
        title.
        """
        if not self.title is None and self.title != '':
            return self.title
        else:
            return self.get_short_label()

    def copy_from(self, display=None, functions=[], owner=None, title=None):
        """
        Given a scoredisplay and a list of functions, this method
        will copy the display and assign the copy to the new owner

        Parameters:
            display -- a ScoreDisplay to copy - the current
               Demographics display
            functions -- a list of ScoreFunctions or the primary
                keys of ScoreFunctions to replace in the display's
                first "district" ScorePanel
            owner -- the owner of the new ScoreDisplay - only set if we're not copying self
            title -- the title of the new scorefunction - only set if we're not copying self

        Returns:
            The new ScoreDisplay
        """

        if display == None:
            return

        if self != display:
            self = copy(display)
            self.id = None
            self.name = ''

            self.owner = owner if owner != None else display.owner

            # We can't have duplicate titles per owner so append "copy" if we must
            if self.owner == display.owner:
                self.title = title if not title is None else "%s copy" % display.__unicode__(
                )
            else:
                self.title = title if not title is None else display.__unicode__(
                )

            self.save()
            self.scorepanel_set = display.scorepanel_set.all()

        else:
            self = display

        try:
            public_demo = self.scorepanel_set.get(type='district')
            if self != display:
                self.scorepanel_set.remove(public_demo)
                demo_panel = copy(public_demo)
                demo_panel.id = None
                demo_panel.name = '%(display_title)s Demographics' % {
                    'display_title': self.title
                }
                demo_panel.save()
                self.scorepanel_set.add(demo_panel)
            else:
                demo_panel = public_demo

            demo_panel.score_functions.clear()
            if len(functions) == 0:
                return self
            for function in functions:
                if isinstance(function, types.IntType):
                    function = ScoreFunction.objects.get(pk=function)
                if isinstance(function, types.StringTypes):
                    function = ScoreFunction.objects.get(pk=int(function))
                if type(function) == ScoreFunction:
                    demo_panel.score_functions.add(function)
            demo_panel.save()
            self.scorepanel_set.add(demo_panel)
            self.save()
        except Exception, ex:
            logger.info('Failed to copy ScoreDisplay %s to %s',
                        display.__unicode__(), self.__unicode__())
            logger.debug('Reason: %s', ex)

        return self

    def render(self,
               dorp,
               context=None,
               version=None,
               components=None,
               function_ids=None):
        """
        Generate the markup for all the panels attached to this display.

        If the is_page property is set, render expects to receive a list
        of valid plans.

        If the is_page property is not set, render expects to receive a
        single plan, or a list of districts.

        Parameters:
            dorp -- A list of districts, plan, or list of plans.
            context -- Optional object that can be used for advanced rendering
            components -- Optional list of tuples that can be used to recompose
                the elements of a ScoreDisplay at runtime.  Each tuple should
                consist of a ScorePanel at index 0, followed by any number of
                ScoreFunctions tuples - a ScoreFunction followed by its arguments.
            version -- Optional; the version of the plan or district to render.
            function_ids -- Optional list of ScoreFunction ids in which to restrict rendering

        Returns:
            The markup for this display.
        """
        is_list = isinstance(dorp, list)

        if self.is_page and \
            (is_list and \
                any(not isinstance(item,Plan) for item in dorp)):
            # If this display is a page, it should receive a list of plans
            return ''
        elif not self.is_page:
            if is_list and \
                any(not isinstance(item,District) for item in dorp):
                # If this display is not a page, the list should be a set
                # of districts.
                return ''
            elif not is_list and \
                not isinstance(dorp,Plan):
                # If this display is not a page, the item should be a plan.
                return ''

        markup = ''
        if components is not None:
            for component in components:
                panel = component[0]
                if len(component) > 1:
                    markup += panel.render(
                        dorp,
                        context=context,
                        version=version,
                        components=list(component[1:]),
                        function_ids=function_ids)
                else:
                    markup += panel.render(
                        dorp,
                        context=context,
                        version=version,
                        function_ids=function_ids)
        else:
            panels = self.scorepanel_set.all().order_by('position')

            for panel in panels:
                markup += panel.render(
                    dorp,
                    context=context,
                    version=version,
                    function_ids=function_ids)

        return markup


class ScorePanel(BaseModel):
    """
    Container for displaying multiple scores of a given type
    """

    # The name of this score panel
    name = models.CharField(max_length=50)

    # The title of this score panel - possibly user-specified
    title = models.CharField(max_length=50)

    # The type of the score display (plan, plan summary, district)
    type = models.CharField(max_length=20)

    # The score display this panel belongs to
    displays = models.ManyToManyField(ScoreDisplay)

    # Where this panel belongs within a score display
    position = models.PositiveIntegerField(default=0)

    # The filename of the template to be used for formatting this panel
    template = models.CharField(max_length=500)

    # The style to be assigned to this score display
    cssclass = models.CharField(max_length=50, blank=True)

    # The method of sorting the scores in this panel
    is_ascending = models.BooleanField(default=True)

    # The functions associated with this panel
    score_functions = models.ManyToManyField(ScoreFunction)

    def __unicode__(self):
        """
        Get a unicode representation of this object. This is the Panel's
        title.
        """
        if not self.title is None and self.title != '':
            return self.title
        else:
            return self.get_short_label()

    def render(self,
               dorp,
               context=None,
               version=None,
               components=None,
               function_ids=None):
        """
        Generate the scores for all the functions attached to this panel,
        and render them in the template.

        Only plan type panels are affected by the sorting order.

        Parameters:
            dorp -- A district, list of districts, plan, or list of plans.
            context -- Optional object that can be used for advanced rendering
            version -- Optional; version of the plan or district to render.
            components -- Optional list of ScoreFunction tuples to render
                 instead of any ScoreFunctions linked through the database.
                 Each tuple should be a ScoreFunction at index 0 followed by
                 and ScoreArguments
            function_ids -- Optional list of ScoreFunction ids in which to restrict rendering

        Returns:
            A rendered set of scores.
        """
        is_list = isinstance(dorp, list)

        # If this is a plan panel, it only renders plans
        if (self.type == 'plan' or self.type == 'plan_summary') and \
            not isinstance(dorp,Plan):
            if is_list:
                if any(not isinstance(item, Plan) for item in dorp):
                    return ''
            else:
                return ''

        # Given a plan, it will render using the districts within the plan
        if self.type == 'district' and \
            not isinstance(dorp,District):
            if is_list:
                if any(not isinstance(item, District) for item in dorp):
                    return ''
            elif isinstance(dorp, Plan):
                dorp = dorp.get_districts_at_version(
                    version if version is not None else dorp.version,
                    include_geom=True)
                is_list = True
            else:
                return ''

        # Keep track of whether we're using a parameter or the DB to populate our panel
        function_override = components is not None

        # Render an item for each plan and plan score
        if self.type == 'plan' or self.type == 'plan_summary':
            if is_list:
                plans = dorp
            else:
                plans = [dorp]

            planscores = []

            for plan in plans:
                plan_version = version if version is not None else plan.version

                if function_override:
                    functions = map(lambda f: f[0], components)
                else:
                    functions = self.score_functions.filter(
                        is_planscore=True).order_by('name')

                for function in functions:
                    # Don't process this function if it isn't in the inclusion list
                    if function_ids and not function.id in function_ids:
                        continue

                    if function_override:
                        if len(function) > 1:
                            arguments = function[1:]
                        function = function[0]
                        score = function.score(
                            plans,
                            format='html',
                            version=plan_version,
                            score_arguments=arguments)
                        sort = score

                    else:
                        score = ComputedPlanScore.compute(
                            function,
                            plan,
                            format='html',
                            version=plan_version)
                        sort = ComputedPlanScore.compute(
                            function,
                            plan,
                            format='sort',
                            version=plan_version)

                    planscores.append({
                        'plan':
                        plan,
                        'name':
                        function.get_short_label(),
                        'label':
                        function.get_label(),
                        'description':
                        function.get_long_description(),
                        'score':
                        score,
                        'sort':
                        sort
                    })

            if self.type == 'plan':
                planscores.sort(
                    key=lambda x: x['sort'], reverse=not self.is_ascending)

            return "" if len(planscores) == 0 else render_to_string(
                self.template, {
                    'settings': settings,
                    'planscores': planscores,
                    'functions': functions,
                    'title': self.get_short_label(),
                    'cssclass': self.cssclass,
                    'position': self.position,
                    'description': self.get_long_description(),
                    'planname': '' if len(plans) == 0 else plans[0].name,
                    'context': context
                })

        # Render each district with multiple scores
        elif self.type == 'district':
            if is_list:
                districts = dorp
            else:
                districts = [dorp]

            districtscores = []
            functions = []
            for district in districts:
                districtscore = {'district': district, 'scores': []}

                if function_override:
                    district_functions = reduce(
                        lambda c: not c[0].is_planscore, components)

                else:
                    district_functions = self.score_functions.filter(
                        is_planscore=False)

                for function in district_functions:
                    # Don't process this function if it isn't in the inclusion list
                    if function_ids and not function.id in function_ids:
                        continue

                    if function_override:
                        if len(function) > 1:
                            arguments = function[1:]
                        function = function[0]
                        score = function.score(
                            district, format='html', score_arguments=arguments)
                    else:
                        if not function.get_label() in functions:
                            functions.append(function.get_label())
                        score = ComputedDistrictScore.compute(
                            function, district, format='html')

                    districtscore['scores'].append({
                        'district':
                        district,
                        'name':
                        function.get_short_label(),
                        'label':
                        function.get_label(),
                        'description':
                        function.get_long_description(),
                        'score':
                        score
                    })

                if len(districtscore['scores']) > 0:
                    districtscores.append(districtscore)

            return "" if len(districtscores) == 0 else render_to_string(
                self.template, {
                    'districtscores': districtscores,
                    'functions': functions,
                    'title': self.__unicode__(),
                    'cssclass': self.cssclass,
                    'settings': settings,
                    'position': self.position,
                    'context': context
                })


class ValidationCriteria(BaseModel):
    """
    Defines the required score functions to validate a legislative body
    """

    # The score function this criteria is for
    function = models.ForeignKey(ScoreFunction)

    # Name of this validation criteria
    name = models.CharField(max_length=50)

    # The legislative body that this validation criteria is for
    legislative_body = models.ForeignKey(LegislativeBody)

    def __unicode__(self):
        return self.get_label()

    class Meta:
        """
        Additional properties about the ValidationCriteria model.
        """
        verbose_name_plural = "Validation criterion"

        unique_together = ('name', )


class ComputedDistrictScore(models.Model):
    """
    A score generated by a score function for a district that can be
    saved for later.

    These computed scores do not store the version number, since each
    district has a unique version.
    """

    # The score function that computes this score
    function = models.ForeignKey(ScoreFunction)

    # The district that this score relates to
    district = models.ForeignKey(District)

    # The actual score value
    value = models.TextField()

    def __unicode__(self):
        name = ''
        if not self.district is None:
            if not self.district.plan is None:
                name = '%s / %s' % (
                    self.district.long_label,
                    self.district.plan.name,
                )
            else:
                name = self.district.long_label

        if not self.function is None:
            name = '%s / %s' % (self.function.get_short_label(), name)
        else:
            name = 'None / %s' % name

        return name

    @staticmethod
    def compute(function, district, format='raw'):
        """
        Get the computed value. This method will leverage the cache when
        it is available, or it will populate the cache if it is not.

        If the cached score exists, it's value is not changed.

        If the cached score does not exist, this method will create it.

        Parameters:
            function -- A ScoreFunction to compute with
            district -- A District to compute on

        Returns:
            The cached value for the district.
        """
        created = False
        try:
            defaults = {'value': ''}
            cache, created = ComputedDistrictScore.objects.get_or_create(
                function=function, district=district, defaults=defaults)

        except Exception as ex:
            logger.info(
                'Could not retrieve nor create computed district score for district %d.',
                district.id)
            logger.debug('Reason:', ex)
            return None

        if created == True:
            score = function.score(district, format='raw')
            cache.value = cPickle.dumps(score)
            cache.save()
        else:
            try:
                score = cPickle.loads(str(cache.value))
            except:
                score = function.score(district, format='raw')

        if format != 'raw':
            calc = function.get_calculator()
            calc.result = score
            if format == 'html':
                return calc.html()
            elif format == 'json':
                return calc.json()
            elif format == 'sort':
                return calc.sortkey()
            else:
                # Unrecognized format!
                return None

        return score

    class Meta:
        unique_together = (('function', 'district'), )


class ComputedPlanScore(models.Model):
    """
    A score generated by a score function for a plan that can be saved
    for later.

    These computed scores contain version numbers, since a plan's version
    number is incremented each time, but scores need to exist for different
    plan version numbers, for history, etc.
    """

    # The score function that computes this score
    function = models.ForeignKey(ScoreFunction)

    # The plan that this score relates to
    plan = models.ForeignKey(Plan)

    # The version of the plan that this relates to
    version = models.PositiveIntegerField(default=0)

    # The actual score value
    value = models.TextField()

    @staticmethod
    def compute(function, plan, version=None, format='raw'):
        """
        Get the computed value. This method will leverage the cache when
        it is available, or it will populate the cache if it is not.

        If the cached score exists, its value is not changed.

        If the cached score does not exist, this method will create it.

        Parameters:
            function -- A ScoreFunction to compute with
            plan -- A Plan to compute on
            version -- Optional; the version of the plan to compute.

        Returns:
            The cached value for the plan.
        """
        created = False
        plan_version = version if version is not None else plan.version
        try:
            defaults = {'value': ''}
            cache, created = ComputedPlanScore.objects.get_or_create(
                function=function,
                plan=plan,
                version=plan_version,
                defaults=defaults)

        except:
            logger.exception(
                'Could not retrieve nor create ComputedPlanScore for plan %d',
                plan.id)
            return None

        if created:
            score = function.score(plan, format='raw', version=plan_version)
            cache.value = cPickle.dumps(score)
            cache.save()
        else:
            try:
                score = cPickle.loads(str(cache.value))
            except:
                score = function.score(
                    plan, format='raw', version=plan_version)
                cache.value = cPickle.dumps(score)
                cache.save()

        if format != 'raw':
            calc = function.get_calculator()
            calc.result = score
            if format == 'html':
                return calc.html()
            elif format == 'json':
                return calc.json()
            elif format == 'sort':
                return calc.sortkey()
            else:
                # Unrecognized format!
                return None

        return score

    def __unicode__(self):
        name = ''
        if not self.plan is None:
            name = self.plan.name

        if not self.function is None:
            name = '%s / %s' % (self.function.get_short_label(), name)
        else:
            name = 'None / %s' % name

        return name


class ContiguityOverride(models.Model):
    """
    Defines a relationship between two geounits in which special
    behavior needs to be applied when calculating contiguity.
    """

    # The geounit that is non-contiguous and needs an override applied
    override_geounit = models.ForeignKey(
        Geounit, related_name="override_geounit")

    # The geounit that the override_geounit is allowed to be considered
    # contiguous with, even in the absense of physical contiguity.
    connect_to_geounit = models.ForeignKey(
        Geounit, related_name="connect_to_geounit")

    # Manage the instances of this class with a geographically aware manager
    objects = models.GeoManager()

    def __unicode__(self):
        return '%s / %s' % (self.override_geounit.portable_id,
                            self.connect_to_geounit.portable_id)


@transaction.atomic
def configure_views():
    """
    Create the spatial views for all the regions, geolevels and subjects.

    This creates views in the database that are used to map the features
    at different geographic levels, and for different choropleth map
    visualizations. All parameters for creating the views are saved
    in the database at this point.
    """
    with connection.cursor() as cursor:
        sql = "CREATE OR REPLACE VIEW identify_geounit AS SELECT rg.id, rg.name, rgg.geolevel_id, rg.geom, rc.number, rc.percentage, rc.subject_id FROM redistricting_geounit rg JOIN redistricting_geounit_geolevel rgg ON rg.id = rgg.geounit_id JOIN redistricting_characteristic rc ON rg.id = rc.geounit_id;"
        cursor.execute(sql)

        logger.debug('Created identify_geounit view ...')

        for geolevel in Geolevel.objects.all():
            if geolevel.legislativelevel_set.all().count() == 0:
                # Skip 'abstract' geolevels if regions are configured
                continue

            lbset = ','.join(
                map(lambda x: str(x.legislative_body_id),
                    geolevel.legislativelevel_set.all()))
            sql = "CREATE OR REPLACE VIEW simple_district_%s AS SELECT rd.id, rd.district_id, rd.plan_id, st_geometryn(rd.simple, %d) AS geom, rp.legislative_body_id FROM redistricting_district as rd JOIN redistricting_plan as rp ON rd.plan_id = rp.id WHERE rp.legislative_body_id IN (%s);" % (
                geolevel.name, geolevel.id, lbset)
            cursor.execute(sql)
            logger.debug('Created simple_district_%s view ...', geolevel.name)

            sql = "CREATE OR REPLACE VIEW simple_%s AS SELECT rg.id, rg.name, rgg.geolevel_id, rg.simple as geom FROM redistricting_geounit rg JOIN redistricting_geounit_geolevel rgg ON rg.id = rgg.geounit_id WHERE rgg.geolevel_id = %%(geolevel_id)s;" % geolevel.name
            cursor.execute(sql, {'geolevel_id': geolevel.id})
            logger.debug('Created simple_%s view ...', geolevel.name)

            for subject in Subject.objects.all():
                sql = "CREATE OR REPLACE VIEW %s AS SELECT rg.id, rg.name, rgg.geolevel_id, rg.geom, rc.number, rc.percentage FROM redistricting_geounit rg JOIN redistricting_geounit_geolevel rgg ON rg.id = rgg.geounit_id JOIN redistricting_characteristic rc ON rg.id = rc.geounit_id WHERE rc.subject_id = %%(subject_id)s AND rgg.geolevel_id = %%(geolevel_id)s;" % get_featuretype_name(
                    geolevel.name, subject.name)
                cursor.execute(sql, {
                    'subject_id': subject.id,
                    'geolevel_id': geolevel.id
                })
                logger.debug('Created %s view ...',
                             get_featuretype_name(geolevel.name, subject.name))


def get_featuretype_name(geolevel_name, subject_name=None):
    """
    A uniform mechanism for generating featuretype names.
    """
    if subject_name is None:
        return 'demo_%s_none' % geolevel_name
    else:
        return 'demo_%s_%s' % (geolevel_name, subject_name)


# Enable tagging of districts by registering them with the tagging module
register(District)
