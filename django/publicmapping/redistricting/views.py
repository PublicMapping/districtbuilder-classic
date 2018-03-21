"""
Django views used by the redistricting application.

The methods in redistricting.views define the views used to interact with
the models in the redistricting application. Each method relates to one
type of output url. There are views that return GeoJSON, JSON, and HTML.

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

from django.http import *
from django.core import serializers
from django.core.exceptions import ValidationError, SuspiciousOperation, ObjectDoesNotExist
from django.db import IntegrityError, connection, transaction
from django.shortcuts import render
from django.core.urlresolvers import reverse
from django_comments.models import Comment
from django_comments.forms import CommentForm
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.sessions.models import Session
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.gis.db.models import Collect
from django.contrib.gis.geos.collections import MultiPolygon
from django.contrib.gis.geos import GEOSGeometry
from django.contrib.gis.gdal import *
from django.contrib.gis.gdal.libgdal import lgdal
from django.contrib.sites.models import Site
from django.contrib import humanize
from django.template import loader
from django.template.context_processors import csrf
from django.utils import translation
from django.utils.translation import ugettext as _, ungettext as _n
from django.template.defaultfilters import slugify, force_escape
from django.conf import settings
from tagging.utils import parse_tag_input
from tagging.models import Tag, TaggedItem
from datetime import datetime, time, timedelta
from decimal import *
from functools import wraps
from redistricting.calculators import *
from redistricting.models import *
from redistricting.tasks import *
import json
import random
import string
import math
import types
import copy
import time
import threading
import traceback
import os
import commands
import sys
import tempfile
import csv
import hashlib
import inflect
import logging
import StringIO
import dateutil.parser

import ModestMaps
from PIL import Image, ImageChops, ImageMath
import urllib, urllib2
from xhtml2pdf.pisa import CreatePDF

logger = logging.getLogger(__name__)

# This constant is reused in multiple places.
UNASSIGNED_DISTRICT_ID = 0


def using_unique_session(u):
    """
    A test to determine if the user of the application is using a unique
    session. Each user is permitted one unique session (one session in the
    django_session table that has not yet expired). If the user exceeds
    this quota, this test fails, and the user will get bounced to the login
    url.

    Parameters:
        u - The user. May be anonymous or registered.

    Returns:
        True - the user is an AnonymousUser or the number of sessions open
               by the user is only 1 (one must be open to make the request)
        False - the user is registered and has more than one open session.
    """
    if u.is_anonymous() or u.is_superuser:
        return True

    sessions = Session.objects.all()
    count = 0
    for session in sessions:
        try:
            decoded = session.get_decoded()

            if '_auth_user_id' in decoded and decoded['_auth_user_id'] == u.id:
                if 'activity_time' in decoded and decoded['activity_time'] < datetime.now(
                ):
                    # delete this session of mine; it is dormant
                    Session.objects.filter(
                        session_key=session.session_key).delete()
                else:
                    count += 1
        except SuspiciousOperation:
            logger.debug(
                "SuspiciousOperation caught while checking the number of sessions a user has open. Session key: %s",
                session.session_key)

    # after counting all the open and active sessions, go back through
    # the session list and assign the session count to all web sessions
    # for this user. (do this for inactive sessions, too)
    for session in sessions:
        try:
            decoded = session.get_decoded()
            if '_auth_user_id' in decoded and decoded['_auth_user_id'] == u.id:
                websession = SessionStore(session_key=session.session_key)
                websession['count'] = count
                websession.save()
        except SuspiciousOperation:
            logger.debug(
                "SuspiciousOperation caught while setting the session count on all user sessions. Session key: %s",
                session.session_key)

    return (count <= 1)


def unique_session_or_json_redirect(function):
    """
    A decorator method.  Any method that accepts this decorator
    should have an HttpRequest as a parameter called "request".
    That request will be checked for a unique session.  If the
    test passes, the original method is returned.  If the session
    is not unique, then a JSON response is returned and the
    client is redirected to log off.
    """

    def decorator(request, *args, **kwargs):
        def return_nonunique_session_result():
            status = {'success': False}
            status['message'] = _(
                "The current user may only have one session open at a time.")
            status['redirect'] = '/?msg=logoff'
            return HttpResponse(
                json.dumps(status), content_type='application/json')

        if not using_unique_session(request.user):
            return return_nonunique_session_result()
        else:
            return function(request, *args, **kwargs)

    return wraps(function)(decorator)


def is_session_available(req):
    """
    Determine if a session is available. This is similar to a user test,
    but requires access to the user's session, so it cannot be used in the
    user_passes_test decorator.

    Parameters:
        req - The HttpRequest object, with user and session information.
    """
    if req.user.is_superuser or req.user.is_staff:
        return True

    sessions = Session.objects.filter(expire_date__gt=datetime.now())
    count = 0
    for session in sessions:
        try:
            decoded = session.get_decoded()
            activity_time = decoded.get('activity_time')
            activity_time_datetime = activity_time and \
                dateutil.parser.parse(activity_time)
            if not req.user.is_anonymous() and activity_time_datetime and \
                    activity_time_datetime > datetime.now():
                count += 1
        except SuspiciousOperation:
            logger.debug(
                "SuspiciousOperation caught while checking the last activity time in a user's session. Session key: %s",
                session.session_key)

    avail = count < settings.CONCURRENT_SESSIONS
    req.session['avail'] = avail

    return avail


def note_session_activity(req):
    """
    Add a session 'timeout' whenever a user performs an action. This is
    required to keep dormant (not yet expired, but inactive) sessions
    from maxing out the concurrent session limit.

    Parameters:
        req - An HttpRequest, with a session attribute
    """
    # The timeout in this timedelta specifies the number of minutes.
    window = timedelta(0, 0, 0, 0, settings.SESSION_TIMEOUT)
    req.session['activity_time'] = (datetime.now() + window).isoformat()


@login_required
def unloadplan(request, planid):
    """
    Unload a plan.

    This view is called anytime a plan is unloaded. Example: navigating
    away from the page, or selecting a new plan. This method allows
    for any required plan cleanup such as purging temporary versions.

    Parameters:
        request -- The HttpRequest, which includes the user.
        planid -- The plan to unload.

    Returns:
        A JSON HttpResponse which includes a status.
    """
    note_session_activity(request)
    status = {'success': False}

    ps = Plan.objects.filter(pk=planid)
    if len(ps) > 0:
        p = ps[0]

        if not can_copy(request.user, p):
            status['message'] = _(
                "User %(user)s doesn't have permission to unload this plan"
            ) % {
                'user': request.user.username
            }
            return HttpResponse(
                json.dumps(status), content_type='application/json')

        # Purge temporary versions
        if settings.MAX_UNDOS_AFTER_EDIT > 0:
            p.purge_beyond_nth_step(settings.MAX_UNDOS_AFTER_EDIT)

    status['success'] = True
    return HttpResponse(json.dumps(status), content_type='application/json')


@login_required
@unique_session_or_json_redirect
def copyplan(request, planid):
    """
    Copy a plan to a new, editable plan.

    This view is called by the plan chooser and the share plan tab. These
    actions take a template or shared plan, and copy the plan without its
    history into an editable plan in the current user's account.

    Parameters:
        request -- The HttpRequest, which includes the user.
        planid -- The original plan to copy.

    Returns:
        A JSON HttpResponse which includes either an error message or the
        copied plan ID.
    """
    note_session_activity(request)

    if not is_plan_ready(planid):
        return HttpResponseRedirect('/')

    status = {'success': False}
    p = Plan.objects.get(pk=planid)
    # Check if this plan is copyable by the current user.
    if not can_copy(request.user, p):
        status['message'] = _("User %(username)s doesn't have permission to " \
            "copy this model" % {'username': request.user.username})
        return HttpResponse(
            json.dumps(status), content_type='application/json')

    # Create a random name if there is no name provided
    newname = p.name + " " + str(random.random())
    if (request.method == "POST"):
        newname = request.POST["name"][0:200]
        shared = request.POST.get("shared",
                                  False) and request.POST["shared"] == "true"

    plan_copy = Plan.objects.filter(
        name=newname, owner=request.user, legislative_body=p.legislative_body)
    # Check that the copied plan's name doesn't already exist.
    if len(plan_copy) > 0:
        status['message'] = _("You already have a plan named that. " \
            "Please pick a unique name.")
        return HttpResponse(
            json.dumps(status), content_type='application/json')

    plan_copy = Plan(
        name=newname,
        owner=request.user,
        is_shared=shared,
        legislative_body=p.legislative_body,
        processing_state=ProcessingState.READY)
    plan_copy.create_unassigned = False
    plan_copy.save()

    # Get all the districts in the original plan at the most recent version
    # of the original plan.
    districts = p.get_districts_at_version(p.version, include_geom=True)
    for district in districts:
        district_copy = copy.copy(district)

        district_copy.id = None
        district_copy.version = 0
        district_copy.is_locked = False
        district_copy.plan = plan_copy

        try:
            district_copy.save()
        except Exception as inst:
            status["message"] = _("Could not save district copies")
            status["exception"] = inst.message
            return HttpResponse(
                json.dumps(status), content_type='application/json')

        # clone the characteristics, comments, and tags from the original
        # district to the copy
        district_copy.clone_relations_from(district)

    # Serialize the plan object to the response.
    data = serializers.serialize("json", [plan_copy])

    return HttpResponse(data, content_type='application/json')


@login_required
@unique_session_or_json_redirect
def scoreplan(request, planid):
    """
    Validate a plan to allow for it to be shown in the leaderboard

    Parameters:
        request -- The HttpRequest, which includes the user.
        planid -- The plan to score.

    Returns:
        A JSON HttpResponse which includes a status, and if applicable,
        a reason why the plan couldn't be validated
    """
    note_session_activity(request)
    status = {'success': False}
    plan = Plan.objects.get(pk=planid)

    criterion = ValidationCriteria.objects.filter(
        legislative_body=plan.legislative_body)
    status['success'] = True
    for criteria in criterion:
        try:
            score = ComputedPlanScore.compute(criteria.function, plan)
        except:
            logger.exception('Failed to compute plan score')

        if not score or not score['value']:
            status['success'] = False
            status['message'] = '<p>%s</p><p>%s</p>' % (
                criteria.get_short_label(), criteria.get_long_description()
                or criteria.function.get_long_description())
            break

    if status['success']:
        status['success'] = True
        status['message'] = _("Validation successful")

        # Set is_valid status on the plan
        plan.is_valid = True
        plan.save()

    return HttpResponse(json.dumps(status), content_type='application/json')


def get_user_info(user):
    """
    Get extended user information for the current user.

    Parameters:
        user -- The user attached to the HttpRequest

    Returns:
        A dict with user information, including profile information.
    """
    if user.is_anonymous():
        return None

    profile = user.profile

    return {
        'username': user.username,
        'email': user.email,
        'password_hint': profile.pass_hint,
        'firstname': user.first_name,
        'lastname': user.last_name,
        'organization': profile.organization,
        'id': user.id
    }


def commonplan(request, planid):
    """
    A common method that gets the same data structures for viewing
    and editing. This method is called by the viewplan and editplan
    views.

    Parameters:
        request -- An HttpRequest
        planid -- The plan ID to fetch.

    Returns:
        A python dict with common plan attributes set to the plan's values.
    """
    note_session_activity(request)

    plan = Plan.objects.filter(id=planid)
    if plan.count() == 1:
        plan = plan[0]
        plan.edited = getutc(plan.edited)
        levels = plan.legislative_body.get_geolevels()
        districts = plan.get_districts_at_version(
            plan.version, include_geom=False)
        editable = can_edit(request.user, plan)
        default_demo = plan.legislative_body.get_default_subject()
        max_dists = plan.legislative_body.max_districts
        body_member_short_label = plan.legislative_body.get_short_label()
        body_member_long_label = plan.legislative_body.get_label()
        body_members = plan.legislative_body.get_members_label()
        reporting_template = 'bard_%s.html' % plan.legislative_body.name if not plan.is_community(
        ) else None

        index = body_member_short_label.find('%(district_id)s')
        if index >= 0:
            body_member_short_label = body_member_short_label[0:index]
        index = body_member_long_label.find('%(district_id)s')
        if index >= 0:
            body_member_long_label = body_member_long_label[0:index]
        if not editable and not can_view(request.user, plan):
            plan = {}
            tags = []
            calculator_reports = []
        else:
            tags = Tag.objects.filter(
                name__startswith='type=').order_by('id').values_list(
                    'name', flat=True)
            tags = map(lambda x: x[5:], tags)

            # Reports defined with calculators (Score Displays, Panels, and Functions)
            # result is a map of relevant panels to score functions with labels and ids,
            # used for generating groups of checkboxes on the evaluate tab.
            calculator_reports = []

            if settings.REPORTS_ENABLED == 'CALC':
                report_displays = ScoreDisplay.objects.filter(
                    name="%s_reports" % plan.legislative_body.name)
                if len(report_displays) > 0:
                    calculator_reports = map(lambda p: {
                                'title': p.__unicode__(),
                                'functions': map(lambda f: {
                                    'label': f.get_label(),
                                    'id': f.id
                                }, p.score_functions.all().filter(selectable_bodies=plan.legislative_body))
                            }, report_displays[0].scorepanel_set.all().order_by('position'))

    else:
        # If said plan doesn't exist, use an empty plan & district list.
        plan = {}
        levels = list()
        districts = {}
        editable = False
        default_demo = None
        max_dists = 0
        body_member_short_label = ''
        body_member_long_label = _('District') + ' '
        body_members = _n('district', 'districts', 2)
        reporting_template = None
        tags = []
        calculator_reports = []
    demos = Subject.objects.all().order_by('sort_key')[0:3]
    layers = []
    snaplayers = []

    study_area_extent = None

    if len(levels) > 0:
        study_area_extent = levels[0].calc_extent()
    else:
        # The geolevels with higher indexes are larger geography
        # Cycle through legislative bodies, since they may be in different regions
        for lb in LegislativeBody.objects.all():
            biglevel = lb.get_geolevels()[0]
            if biglevel.geounit_set.count() > 0:
                study_area_extent = biglevel.calc_extent()
                break

    for level in levels:
        # i18n-ize name here, not in js
        snaplayers.append({
            'geolevel': level.id,
            'level': level.name,
            'layer': 'simple_' + level.name,
            'long_description': level.get_long_description(),
            'min_zoom': level.min_zoom
        })
    default_selected = False
    for demo in demos:
        isdefault = str((not default_demo is None)
                        and (demo.id == default_demo.id)).lower()
        if isdefault == 'true':
            default_selected = True
        # i18n-ize name & short_display here, not in js
        layers.append({
            'id': demo.id,
            'text': demo.get_short_label(),
            'value': demo.name,
            'isdefault': isdefault,
            'isdisplayed': str(demo.is_displayed).lower()
        })
    # If the default demo was not selected among the first three, we'll still need it for the dropdown menus
    if default_demo and not default_selected:
        layers.insert(
            0, {
                'id': default_demo.id,
                'text': default_demo.get_short_label(),
                'value': default_demo.name,
                'isdefault': str(True).lower(),
                'isdisplayed': str(default_demo.is_displayed).lower()
            })

    short_label = body_member_short_label.strip().lower()
    long_label = body_member_long_label.strip().lower()

    has_regions = Region.objects.all().count() > 1
    bodies = LegislativeBody.objects.all().order_by('region__sort_key',
                                                    'sort_key')
    l_bodies = [
        b for b in bodies
        if b in [
            sd.legislative_body
            for sd in ScoreDisplay.objects.filter(is_page=True)
        ]
    ]

    try:
        loader.get_template(reporting_template)
    except:
        reporting_template = None

    return {
        'bodies':
        bodies,
        'has_regions':
        has_regions,
        'leaderboard_bodies':
        l_bodies,
        'plan':
        plan,
        'districts':
        districts,
        'basemaps':
        settings.BASE_MAPS,
        'namespace':
        settings.MAP_SERVER_NS,
        'ns_href':
        settings.MAP_SERVER_NSHREF,
        'feature_limit':
        settings.FEATURE_LIMIT,
        'adjacency':
        settings.ADJACENCY,
        'convexchoropleth':
        settings.CONVEX_CHOROPLETH,
        'demographics':
        layers,
        'snaplayers':
        snaplayers,
        'unassigned_id':
        UNASSIGNED_DISTRICT_ID,
        'is_registered':
        request.user.username != 'anonymous' and request.user.username != '',
        'debugging_staff':
        settings.DEBUG and request.user.is_staff,
        'userinfo':
        get_user_info(request.user),
        'is_editable':
        editable,
        'max_dists':
        max_dists + 1,
        'ga_account':
        settings.GA_ACCOUNT,
        'ga_domain':
        settings.GA_DOMAIN,
        'body_member_short_label':
        short_label,
        'body_member_long_label':
        long_label,
        'body_members':
        body_members,
        'reporting_template':
        reporting_template,
        'study_area_extent':
        study_area_extent,
        'has_leaderboard':
        len(ScoreDisplay.objects.filter(is_page=True)) > 0,
        'calculator_reports':
        json.dumps(calculator_reports),
        'allow_email_submissions': ('EMAIL_SUBMISSION' in settings.__members__
                                    if hasattr(settings, '__members__') else
                                    False),
        'tags':
        tags,
        'site':
        Site.objects.get_current(),
        'plan_text':
        _("community map") if (plan and plan.is_community()) else _("plan"),
        'language_code':
        translation.get_language(),
        'LANGUAGES':
        settings.LANGUAGES  # needed (as CAPS) for language chooser
    }


def is_plan_ready(planid):
    """
    Determines if a plan is in a Ready state
    """
    planid = int(planid)
    return planid == 0 or len(
        Plan.objects.filter(id=planid,
                            processing_state=ProcessingState.READY)) > 0


@user_passes_test(using_unique_session)
def viewplan(request, planid):
    """
    View a plan.

    This template has no editing capability.

    Parameters:
        request -- An HttpRequest, which includes the current user.
        planid -- The plan to view

    Returns:
        A rendered HTML page for viewing a plan.
    """

    if not is_session_available(request) or not is_plan_ready(planid):
        return HttpResponseRedirect('/')

    # Cleanup old versions for logged in users
    if not request.user.is_anonymous() and (int(planid) == 0) and (
            settings.MAX_UNDOS_AFTER_EDIT > 0):
        for p in Plan.objects.filter(owner=request.user):
            p.purge_beyond_nth_step(settings.MAX_UNDOS_AFTER_EDIT)

    return render(request, 'viewplan.html', commonplan(request, planid))


@user_passes_test(using_unique_session)
def editplan(request, planid):
    """
    Edit a plan.

    This template enables editing tools and functionality.

    Parameters:
        request -- An HttpRequest, which includes the current user.
        planid -- The plan to edit.

    Returns:
        A rendered HTML page for editing a plan.
    """
    if request.user.is_anonymous(
    ) or not is_session_available(request) or not is_plan_ready(planid):
        return HttpResponseRedirect('/')

    cfg = commonplan(request, planid)
    if cfg['is_editable'] == False:
        return HttpResponseRedirect('/districtmapping/plan/%s/view/' % planid)
    plan = Plan.objects.get(id=planid, owner=request.user)
    cfg['dists_maxed'] = len(
        cfg['districts']) > plan.legislative_body.max_districts
    cfg['available_districts'] = plan.get_available_districts()

    # Cleanup old versions
    if settings.MAX_UNDOS_AFTER_EDIT > 0:
        plan.purge_beyond_nth_step(settings.MAX_UNDOS_AFTER_EDIT)

    return render(request, 'editplan.html', cfg)


@user_passes_test(using_unique_session)
def printplan(request, planid):
    """
    Print a static map of a plan.

    This template renders a static HTML document for use with xhtml2pdf.

    Parameters:
        request -- An HttpRequest, which includes the current user.
        planid -- The plan to edit.

    Returns:
        A rendered HTML page suitable for conversion to a PDF.
    """
    if not is_session_available(request):
        return HttpResponseRedirect('/')

    cfg = commonplan(request, planid)

    sha = hashlib.sha1()
    sha.update(str(planid) + str(datetime.now()))
    cfg['composite'] = '/reports/print-%s.jpg' % sha.hexdigest()
    cfg['prefix'] = 'http://%s' % request.META['SERVER_NAME']

    if request.method == 'POST':
        if not 'bbox' in request.POST or \
            not 'geography_url' in request.POST or \
            not 'geography_lyr' in request.POST or \
            not 'district_url' in request.POST or \
            not 'district_lyr' in request.POST:
            logger.warning(
                'Missing required "bbox", "geography_url", "geography_lyr", "district_url", or "districts_lyr" parameter.'
            )
            return HttpResponseRedirect('../view/')

        height = 500 * 2
        if 'height' in request.POST:
            height = int(request.POST['height']) * 2
        width = 1024 * 2
        if 'width' in request.POST:
            width = int(request.POST['width']) * 2
        opacity = 0.8
        if 'opacity' in request.POST:
            opacity = float(request.POST['opacity'])

        full_legend = json.loads(request.POST['legend'])

        cfg['geography_url'] = request.POST['geography_url']
        cfg['geography_lyr'] = request.POST['geography_lyr']
        cfg['district_url'] = request.POST['district_url']
        cfg['district_lyr'] = request.POST['district_lyr']
        cfg['geo_legend'] = full_legend['geo']
        cfg['geo_legend_title'] = full_legend['geotitle']
        cfg['dist_legend'] = full_legend['dist']
        cfg['dist_legend_title'] = full_legend['disttitle']
        cfg['plan'] = Plan.objects.get(id=int(request.POST['plan_id']))
        cfg['printed'] = datetime.now()

        # use modestmaps to get the basemap
        bbox = request.POST['bbox'].split(',')

        pt1 = Point(float(bbox[0]), float(bbox[1]), srid=3785)
        pt1.transform(SpatialReference('EPSG:4326'))
        ll = ModestMaps.Geo.Location(pt1.y, pt1.x)

        pt2 = Point(float(bbox[2]), float(bbox[3]), srid=3785)
        pt2.transform(SpatialReference('EPSG:4326'))
        ur = ModestMaps.Geo.Location(pt2.y, pt2.x)

        dims = ModestMaps.Core.Point(width, height)
        provider = ModestMaps.OpenStreetMap.Provider()
        basemap = ModestMaps.mapByExtent(provider, ll, ur, dims)

        # create basemap for compositing
        fullImg = basemap.draw()

        # geography layer
        provider = ModestMaps.WMS.Provider(
            cfg['geography_url'], {
                'LAYERS': cfg['geography_lyr'],
                'TRANSPARENT': 'true',
                'SRS': 'EPSG:3785',
                'HEIGHT': 512,
                'WIDTH': 512
            })
        overlayImg = ModestMaps.mapByExtent(provider, ll, ur, dims).draw()

        # create an invert mask of the geography
        maskImg = ImageChops.invert(overlayImg)

        # district fill layer
        provider = ModestMaps.WMS.Provider(
            cfg['district_url'], {
                'LAYERS': cfg['district_lyr'],
                'TRANSPARENT': 'false',
                'SRS': 'EPSG:3785',
                'SLD_BODY': request.POST['district_sld'],
                'HEIGHT': 512,
                'WIDTH': 512
            })
        overlayImg = Image.blend(overlayImg,
                                 ModestMaps.mapByExtent(
                                     provider, ll, ur, dims).draw(), 0.5)

        # composite the overlay onto the base, using the mask (from geography)
        fullImg = Image.composite(fullImg,
                                  Image.blend(fullImg, overlayImg, opacity),
                                  maskImg)

        # district line & label layer
        provider = ModestMaps.WMS.Provider(
            cfg['district_url'], {
                'LAYERS': cfg['district_lyr'],
                'TRANSPARENT': 'true',
                'SRS': 'EPSG:3785',
                'SLD_BODY': request.POST['label_sld'],
                'HEIGHT': 512,
                'WIDTH': 512
            })
        overlayImg = ModestMaps.mapByExtent(provider, ll, ur, dims).draw()

        # create an invert mask of the labels & lines
        maskImg = ImageChops.invert(overlayImg)

        # composite the district labels on top of the composited basemap, geography & district areas
        fullImg = Image.composite(fullImg,
                                  Image.blend(fullImg, overlayImg, opacity),
                                  maskImg)

        # save
        fullImg.save(
            settings.WEB_TEMP + ('/print-%s.jpg' % sha.hexdigest()),
            'jpeg',
            quality=100)

        # render pg to a string
        t = loader.get_template('printplan.html')
        page = t.render(cfg)
        result = StringIO.StringIO()

        # setting encoding='UTF-8' causes an exception. removing this for now,
        # as allowing the method to set an encoding itself fixes the problem.
        # we may need to find an alternate strategy if it finds encodings that
        # it isn't able to decipher.
        CreatePDF(page, result, show_error_as_pdf=True)

        response = HttpResponse(
            result.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename=plan.pdf'

        return response

    else:
        return HttpResponseRedirect('../view/')


@login_required
@unique_session_or_json_redirect
def createplan(request):
    """
    Create a plan.

    Create a plan from a POST request. This plan will be 'blank', and will
    contain only the Unassigned district initially.

    Parameters:
        request -- An HttpRequest, which contains the current user.

    Returns:
        A JSON HttpResponse, including the new plan's information, or an
        error describing why the plan could not be created.
    """
    note_session_activity(request)

    status = {'success': False}
    if request.method == "POST":
        name = request.POST['name'][0:200]
        body = LegislativeBody.objects.get(
            id=int(request.POST['legislativeBody']))
        plan = Plan(
            name=name,
            owner=request.user,
            legislative_body=body,
            processing_state=ProcessingState.READY)
        try:
            plan.save()
            status = serializers.serialize("json", [plan])
        except:
            status = {'success': False, 'message': _("Couldn't save new plan")}
    return HttpResponse(json.dumps(status), content_type='application/json')


@unique_session_or_json_redirect
def uploadfile(request):
    """
    Accept a block equivalency file, and create a plan based on that
    file.

    Parameters:
        request -- An HttpRequest, with a file upload and plan name.

    Returns:
        A plan view, with additional information about the upload status.
    """
    note_session_activity(request)

    if request.user.is_anonymous():
        # If a user is logged off from another location, they will appear
        # as an anonymous user. Redirect them to the front page. Sadly,
        # they will not get a notice that they were logged out.
        return HttpResponseRedirect('/')

    status = commonplan(request, 0)
    status['upload'] = True
    status['upload_status'] = True

    index_file = request.FILES.get('indexFile', False)
    if not index_file:
        status['upload_status'] = False
        return render(request, 'viewplan.html', status)
    else:
        filename = index_file.name

    if index_file.size > settings.MAX_UPLOAD_SIZE:
        logger.error('File size exceeds allowable size.')
        status['upload_status'] = False
        return render(request, 'viewplan.html', status)

    if not filename.endswith(('.csv', '.zip')):
        logger.error('Uploaded file must be ".csv" or ".zip".')
        status['upload_status'] = False
    elif request.POST['userEmail'] == '':
        logger.error('No email provided for user notification.')
        status['upload_status'] = False
    else:
        try:
            dest = tempfile.NamedTemporaryFile(mode='wb+', delete=False)
            for chunk in request.FILES['indexFile'].chunks():
                dest.write(chunk)
            dest.close()
            if request.FILES['indexFile'].name.endswith('.zip'):
                os.rename(dest.name, '%s%s' % (dest.name, '.zip'))
                filename = '%s%s' % (dest.name, '.zip')
            else:
                filename = dest.name
            os.chmod(filename, 0664)

        except Exception as ex:
            logger.error('Could not save uploaded file')
            logger.error('Reason: %s', ex)
            status['upload_status'] = False
            return render(request, 'viewplan.html', status)

        # Put in a celery task to create the plan and email user on completion
        DistrictIndexFile.index2plan.delay(
            request.POST['txtNewName'],
            request.POST['legislativeBody'],
            filename,
            owner_id=request.user.pk,
            template=False,
            purge=True,
            email=request.POST['userEmail'],
            language=translation.get_language())

    return render(request, 'viewplan.html', status)


def generate_report_hash(qdict):
    """
    Generate a hash based on the query items passed to this report request.
    """

    params = qdict.get('popVar', ' ') + \
        qdict.get('popVarExtra', ' ') + \
        qdict.get('ratioVars[]', ' ') + \
        qdict.get('splitVars', ' ') + \
        qdict.get('blockLabelVar', 'CTID') + \
        qdict.get('repCompactness', ' ') + \
        qdict.get('repCompactnessExtra', ' ') + \
        qdict.get('repSpatial', ' ') + \
        qdict.get('repSpatialExtra', ' ')
    sha = hashlib.sha1()
    sha.update(params)
    return sha.hexdigest()


@unique_session_or_json_redirect
def getcalculatorreport(request, planid):
    """
    Get a report which is generated by using calculators.

    This view will write out an HTML-formatted report to the directory
    given in the settings.

    Parameters:
        request -- An HttpRequest
        planid -- The plan to be reported.

    Returns:
        The HTML for use as a preview in the web application, along with
        the web address of the report.
    """
    note_session_activity(request)

    status = {'success': False}
    try:
        plan = Plan.objects.get(pk=planid)
    except:
        status['message'] = _('No plan with the given id')
        return HttpResponse(
            json.dumps(status), content_type='application/json')

    if not can_view(request.user, plan):
        status['message'] = _("User can't view the given plan")
        return HttpResponse(
            json.dumps(status), content_type='application/json')

    if request.method != 'POST':
        status['message'] = _("Information for report wasn't sent via POST")
        return HttpResponse(
            json.dumps(status), content_type='application/json')

    # extract the function ids from the POST
    function_ids = request.POST.get('functionIds', '')

    # generate a hash of the function ids
    sha = hashlib.sha1()
    sha.update(function_ids)
    stamp = request.POST.get('stamp', sha.hexdigest())

    rptstatus = CalculatorReport.checkreport(planid, stamp)
    if rptstatus == 'ready':
        status = {
            'success': True,
            'url': CalculatorReport.getreport(planid, stamp),
            'retry': 0,
            'message': _('Plan report is ready.'),
            'stamp': stamp
        }
    elif rptstatus == 'busy':
        status = {
            'success': True,
            'url': reverse(getcalculatorreport, args=[planid]),
            'retry': 5,
            'message': _('Report is building.'),
            'stamp': stamp
        }
    elif rptstatus == 'free':
        status = {
            'success': True,
            'url': reverse(getcalculatorreport, args=[planid]),
            'retry': 5,
            'message': _('Report generation started.'),
            'stamp': stamp
        }

        req = {'functionIds': function_ids}
        CalculatorReport.markpending(planid, stamp)
        CalculatorReport.createcalculatorreport.delay(
            planid, stamp, req, language=translation.get_language())
    else:
        status['message'] = _(
            'Unrecognized status when checking report status.')

    return HttpResponse(json.dumps(status), content_type='application/json')


@login_required
@unique_session_or_json_redirect
def newdistrict(request, planid):
    """
    Create a new district.

    The 'geolevel' parameter is required to create a new district. Geounits
    may be added to this new district by setting the 'geounits' key in the
    request.

    Parameters:
        request - An HttpRequest, with the current user.
        planid - The plan id to which the district should be added.

    Returns:
        The new District's name and district_id.
    """
    note_session_activity(request)

    status = {'success': False}
    if len(request.POST.items()) >= 3:
        plan = Plan.objects.get(pk=planid, owner=request.user)

        if 'geolevel' in request.POST:
            geolevel = request.POST['geolevel']
        else:
            geolevel = None
        if 'geounits' in request.POST:
            geounit_ids = string.split(request.POST['geounits'], '|')
        else:
            geounit_ids = None

        if 'district_id' in request.POST:
            district_id = int(request.POST['district_id'])
        else:
            district_id = None

        if 'district_short' in request.POST:
            district_short = request.POST['district_short'][0:10]
        elif not district_id is None:
            district_short = plan.legislative_body.get_short_label() % {
                'district_id': district_id
            }
        else:
            district_short = None

        if 'district_long' in request.POST:
            district_long = request.POST['district_long'][0:256]
        elif not district_id is None:
            district_long = plan.legislative_body.get_label() % {
                'district_id': district_id
            }
        else:
            district_long = None

        if 'version' in request.POST:
            version = request.POST['version']
        else:
            version = plan.version

        if geolevel and geounit_ids and district_id:
            try:
                # add the geounits selected to this district -- this will
                # create a new district w/1 version higher
                fixed = plan.add_geounits((
                    district_id,
                    district_short,
                    district_long,
                ), geounit_ids, geolevel, version)

                # if there are comments, types or multiple members, add them to the district
                district = plan.district_set.filter(
                    district_id=district_id,
                    short_label=district_short,
                    long_label=district_long)[0]
                if plan.legislative_body.multi_members_allowed:
                    district.num_members = plan.legislative_body.min_multi_district_members
                    district.save()
                ct = ContentType.objects.get(
                    app_label='redistricting', model='district')
                if 'comment' in request.POST and request.POST['comment'] != '':
                    comment = Comment(
                        object_pk=district.id,
                        content_type=ct,
                        site_id=Site.objects.get_current().id,
                        user_name=request.user.username,
                        user_email=request.user.email,
                        comment=request.POST['comment'])
                    comment.save()

                if len(request.POST.getlist('type[]')) > 0:
                    strtags = request.POST.getlist('type[]')
                    for strtag in strtags:
                        if strtag == '':
                            continue
                        if strtag.count(' ') > 0:
                            strtag = '"type=%s"' % strtag
                        else:
                            strtag = 'type=%s' % strtag
                        Tag.objects.add_tag(district, strtag)

                status['success'] = True
                status['message'] = _('Created 1 new district')
                plan = Plan.objects.get(pk=planid, owner=request.user)
                status['edited'] = getutc(plan.edited).isoformat()
                status['district_id'] = district_id
                status['version'] = plan.version
            except ValidationError:
                status['message'] = _('Reached Max districts already')
            except Exception, ex:
                logger.warn('Error saving new district')
                logger.debug('Reason: %s', ex)
                status['message'] = _("Couldn't save new district.")
        else:
            status['message'] = _('Must specify name, geolevel, ' \
                'and geounit ids for new district.')
    return HttpResponse(json.dumps(status), content_type='application/json')


@login_required
@unique_session_or_json_redirect
@transaction.atomic
def add_districts_to_plan(request, planid):
    """
    This handler is used to paste existing districts from one
    plan into another plan

    Parameters:
        request -- An HttpRequest object including a list of districtids and
            a version
        planid -- The plan into which to paste the districts

    Returns:
        Some JSON explaining the success or failure of the paste operation
    """

    status = {'success': False}

    # Make sure we can edit the given plan
    try:
        plan = Plan.objects.get(pk=planid)
    except:
        status['message'] = _('No plan with the given id')
        return HttpResponse(
            json.dumps(status), content_type='application/json')

    if not can_edit(request.user, plan):
        status['message'] = _("User can't edit the given plan")
        return HttpResponse(
            json.dumps(status), content_type='application/json')

    # Get the districts we want to merge
    district_list = request.POST.getlist('districts[]')
    if len(district_list) == 0:
        status['message'] = _("No districts selected to add to the given plan")
        return HttpResponse(
            json.dumps(status), content_type='application/json')
    else:
        districts = District.objects.filter(id__in=district_list)
        version = int(request.POST.get('version', None))
        status['message'] = _('Going to merge %(number_of_merged_districts)d' \
            ' districts') % {'number_of_merged_districts': len(districts)}

    # Check to see if we have enough room to add these districts without
    # going over MAX_DISTRICTS for the legislative_body
    allowed_districts = plan.get_available_districts(version=version)

    if len(districts) > allowed_districts:
        status['message'] = _('Tried to merge too many districts; ' \
            '%(allowed_districts)d slots left') % {'allowed_districts': allowed_districts}

    # Everything checks out, let's paste those districts
    try:
        results = plan.paste_districts(districts, version=version)
        status['success'] = True
        status['message'] = _('Merged %(num_merged_districts)d districts') % {
            'num_merged_districts': len(results)
        }
        status['version'] = plan.version
    except Exception as ex:
        status['message'] = str(ex)
        status['exception'] = traceback.format_exc()

    return HttpResponse(json.dumps(status), content_type='application/json')


@login_required
@unique_session_or_json_redirect
@transaction.atomic
def assign_district_members(request, planid):
    """
    This handler is used to assign members to districts

    Parameters:
        request -- An HttpRequest object including a version,
                   and a mapping of districtids to num_members
        planid -- The plan into which to assign district members

    Returns:
        Some JSON explaining the success or failure of the paste operation
    """

    status = {'success': False}

    # Make sure we can edit the given plan
    try:
        plan = Plan.objects.get(pk=planid)
    except:
        status['message'] = _('No plan with the given id')
        return HttpResponse(
            json.dumps(status), content_type='application/json')

    if not can_edit(request.user, plan):
        status['message'] = _("User can't edit the given plan")
        return HttpResponse(
            json.dumps(status), content_type='application/json')

    # Make sure this district allows multi-member assignment
    leg_bod = plan.legislative_body
    if (not leg_bod.multi_members_allowed):
        status['message'] = _(
            'Multi-members not allowed for this legislative body')
        return HttpResponse(
            json.dumps(status), content_type='application/json')

    # Get the districts we want to assign members to
    districts = request.POST.getlist('districts[]')
    counts = request.POST.getlist('counts[]')
    version = int(request.POST.get('version', None))

    # Assign the district members and return status
    try:
        changed = 0
        for i in range(0, len(districts)):
            id = int(districts[i])
            count = int(counts[i])
            district = District.objects.filter(
                plan=plan, district_id=id,
                version__lte=version).order_by('version').reverse()[0]

            if district.num_members != count:
                if (changed == 0):
                    # If there is at least one change, update the plan
                    if version != plan.version:
                        plan.purge(after=version)

                    plan.version = plan.version + 1
                    plan.save()

                plan.update_num_members(district, count)
                changed += 1

        status['success'] = True
        status['version'] = plan.version
        status['modified'] = changed
        status['message'] = _('Modified members for %(num_districts)d '
                              'districts') % {
                                  'num_districts': changed
                              }
    except Exception, ex:
        status['message'] = str(ex)
        status['exception'] = traceback.format_exc()
        logger.warn('Could not assign district members')
        logger.debug('Reason: %s', ex)

    return HttpResponse(json.dumps(status), content_type='application/json')


@login_required
@unique_session_or_json_redirect
def combine_districts(request, planid):
    """
    Take the contents of one district and add them to another districts
    """

    status = {'success': False}

    # Make sure we can edit the given plan
    try:
        plan = Plan.objects.get(pk=planid)
    except:
        status['message'] = _('No plan with the given id')
        return HttpResponse(
            json.dumps(status), content_type='application/json')

    if not can_edit(request.user, plan):
        status['message'] = _("User can't edit the given plan")
        return HttpResponse(
            json.dumps(status), content_type='application/json')

    # Get the districts we want to merge
    version = int(request.POST.get('version', plan.version))
    from_id = int(request.POST.get('from_district_id', -1))
    to_id = int(request.POST.get('to_district_id', None))

    try:
        all_districts = plan.get_districts_at_version(
            version, include_geom=True)

        from_districts = filter(
            lambda d: True if d.district_id == from_id else False,
            all_districts)
        to_district = filter(
            lambda d: True if d.district_id == to_id else False,
            all_districts)[0]

        locked = to_district.is_locked
        for district in from_districts:
            if district.is_locked:
                locked = True

        if locked:
            status['message'] = _("Can't combine locked districts")
            return HttpResponse(
                json.dumps(status), content_type='application/json')

        result = plan.combine_districts(
            to_district, from_districts, version=version)

        if result[0] == True:
            status['success'] = True
            status['message'] = _('Successfully combined districts')
            status['version'] = result[1]
    except Exception, ex:
        status['message'] = _('Could not combine districts')
        status['exception'] = traceback.format_exc()
        logger.warn('Could not combine districts')
        logger.debug('Reason: %s', ex)
    return HttpResponse(json.dumps(status), content_type='application/json')


@login_required
@unique_session_or_json_redirect
def fix_unassigned(request, planid):
    """
    Assign unassigned base geounits that are fully contained
    or adjacent to another district
    """

    status = {'success': False}

    try:
        plan = Plan.objects.get(pk=planid)
    except:
        status['message'] = _('No plan with the given id')
        return HttpResponse(
            json.dumps(status), content_type='application/json')

    if not can_edit(request.user, plan):
        status['message'] = _("User can't edit the given plan")
        return HttpResponse(
            json.dumps(status), content_type='application/json')

    try:
        version = int(request.POST.get('version', plan.version))
        result = plan.fix_unassigned(version)
        status['success'] = result[0]
        status['message'] = result[1]
        status['version'] = plan.version
    except Exception, ex:
        status['message'] = _('Could not fix unassigned')
        status['exception'] = traceback.format_exc()
        logger.warn('Could not fix unassigned')
        logger.debug('Reason: %s', ex)
    return HttpResponse(json.dumps(status), content_type='application/json')


@unique_session_or_json_redirect
def get_splits(request, planid, otherid, othertype):
    """
    Find all splits between this plan and another plan

    Parameters:
        request -- An HttpRequest optionally containing version and/or otherversion
        planid -- The plan ID
        otherid -- The plan ID or geolevel ID to find splits with
        othertype -- One of: 'plan' or 'geolevel'. For specifying otherid

    Returns:
        A JSON HttpResponse that contains an array of splits, given as arrays,
        where the first item is the district_id of the district in this plan
        which causes the split, and the second item is the district_id of the
        district in the other plan or geolevel. When a geolevel is specified,
        the portable_id will be used, rather than the district_id.
    """

    otherid = int(otherid)
    status = {'success': False}

    try:
        plan = Plan.objects.get(pk=planid)
    except:
        status['message'] = _('No plan with the given id')
        return HttpResponse(
            json.dumps(status), content_type='application/json')

    if not can_view(request.user, plan):
        status['message'] = _("User can't view the given plan")
        return HttpResponse(
            json.dumps(status), content_type='application/json')

    version = int(request.GET['version']
                  if 'version' in request.GET else plan.version)
    try:
        if othertype == 'plan':
            try:
                otherplan = Plan.objects.get(pk=otherid)
            except:
                status['message'] = _('No other plan with the given id')
                return HttpResponse(
                    json.dumps(status), content_type='application/json')
            if not can_view(request.user, otherplan):
                status['message'] = _("User can't view the given plan")
                return HttpResponse(
                    json.dumps(status), content_type='application/json')

            otherversion = int(request.GET['otherversion'] if 'otherversion' in
                               request.GET else otherplan.version)
            splits = plan.find_plan_splits(otherplan, version, otherversion)
        elif othertype == 'geolevel':
            splits = plan.find_geolevel_splits(otherid, version)
        else:
            status['message'] = _('othertype not supported: %(other)s') % {
                'other': othertype
            }
            return HttpResponse(
                json.dumps(status), content_type='application/json')

        split_word = _('split') if len(
            splits) == 1 else inflect.engine().plural(_('split'))

        status['success'] = True
        status['message'] = _('Found %(num_splits)d %(split_word)s') % \
                {'num_splits': len(splits), 'split_word': split_word}
        status['splits'] = splits
        status['above_ids'] = list(set([i[0] for i in splits]))
        status['below_ids'] = list(set([i[1] for i in splits]))
    except Exception, ex:
        status['message'] = _('Could not query for splits')
        status['exception'] = traceback.format_exc()
        logger.warn('Could not query for splits')
        logger.debug('Reason: %s', ex)
    return HttpResponse(json.dumps(status), content_type='application/json')


def get_processing_status(request):
    """
    Get the processing status for a list of plan ids
    """
    status = {'success': False}
    plan_ids = request.GET.getlist('planIds[]')
    if len(plan_ids) == 0:
        status['message'] = _('No planIds provided')
    else:
        statuses = {}
        for p in Plan.objects.filter(id__in=plan_ids):
            statuses[str(p.id)] = p.get_processing_state_display()

        status['success'] = True
        status['message'] = statuses

    return HttpResponse(json.dumps(status), content_type='application/json')


def get_splits_report(request, planid):
    """
    Get the rendered splits report
    """
    note_session_activity(request)

    try:
        plan = Plan.objects.get(pk=planid)
    except:
        return HttpResponse(
            _('Plan does not exist.'), content_type='text/plain')

    if not using_unique_session(request.user) or not can_view(
            request.user, plan):
        return HttpResponseForbidden()

    version = int(request.GET['version']
                  if 'version' in request.GET else plan.version)
    inverse = request.GET[
        'inverse'] == 'true' if 'inverse' in request.GET else False
    extended = request.GET[
        'extended'] == 'true' if 'extended' in request.GET else False
    layers = request.GET.getlist('layers[]')
    if len(layers) == 0:
        return HttpResponse(
            _('No layers were provided.'), content_type='text/plain')

    try:
        report = loader.get_template('split_report.html')
        html = ''
        for layer in layers:
            calc_context = {'extended': extended}
            calc_context.update(
                plan.compute_splits(
                    layer, version=version, inverse=inverse,
                    extended=extended))
            last_item = layer is layers[-1]
            community_info = plan.get_community_type_info(
                layer,
                version=version,
                inverse=inverse,
                include_counts=last_item)
            if community_info is not None:
                calc_context.update(community_info)
            html += report.render(calc_context)
            if not last_item:
                html += '<hr />'
        return HttpResponse(html, content_type='text/html')
    except Exception, ex:
        logger.warn('Could not produce split report')
        logger.debug('Reason: %s', ex)
        return HttpResponse(str(ex), content_type='text/plain')


@login_required
@unique_session_or_json_redirect
def addtodistrict(request, planid, districtid):
    """
    Add geounits to a district.

    This method requires both "geolevel" and "geounits" URL parameters.
    The geolevel must be a valid geolevel name and the geounits parameters
    should be a pipe-separated list of geounit ids.

    Parameters:
        request -- An HttpRequest, with the current user, the geolevel, and
        the pipe-separated geounit list.
        planid -- The plan ID that contains the district.
        districtid -- The district ID to which the geounits will be added.

    Returns:
        A JSON HttpResponse that contains the number of districts modified,
        or an error message if adding fails.
    """
    note_session_activity(request)

    status = {'success': False}

    data = request.POST
    if len(data.items()) >= 2:
        try:
            geolevel = data["geolevel"]
            geounit_ids = string.split(data["geounits"], "|")
            plan = Plan.objects.get(pk=planid, owner=request.user)
        except:
            status['exception'] = traceback.format_exc()
            status['message'] = _('Could not add units to district.')

        # get the version from the request or the plan
        if 'version' in data:
            version = data['version']
        else:
            version = plan.version

        try:
            fixed = plan.add_geounits(districtid, geounit_ids, geolevel,
                                      version)
            status['success'] = True
            status['message'] = _('Updated %(num_fixed_districts)d districts') \
                % {'num_fixed_districts': fixed}
            status['updated'] = fixed
            plan = Plan.objects.get(pk=planid, owner=request.user)
            status['edited'] = getutc(plan.edited).isoformat()
            status['version'] = plan.version
        except Exception, ex:
            status['exception'] = traceback.format_exc()
            status['message'] = _('Could not add units to district.')
            logger.warn('Could not add units to district')
            logger.debug('Reason: %s', ex)

    else:
        status['message'] = _("Geounits weren't found in a district.")

    return HttpResponse(json.dumps(status), content_type='application/json')


@unique_session_or_json_redirect
@login_required
def setdistrictlock(request, planid, district_id):
    """
    Set whether this district is locked for editing.

    Parameters:
        request -- An HttpRequest, with a boolean that indicates whether the district
        should be locked or unlocked
        planid -- The plan ID that contains the district.
        district_id -- The district_id to lock or unlock

    Returns:
        A JSON HttpResponse that contains a boolean of whether the district is locked.
    """
    note_session_activity(request)

    status = {'success': False}

    if request.method != 'POST':
        return HttpResponseForbidden()

    lock = request.POST.get('lock').lower() == 'true'
    version = request.POST.get('version')
    if lock == None:
        status['message'] = _('Must include lock parameter.')
    elif version == None:
        status['message'] = _('Must include version parameter.')

    try:
        plan = Plan.objects.get(pk=planid)
        district = plan.district_set.filter(
            district_id=district_id,
            version__lte=version).order_by('version').reverse()[0]
    except ObjectDoesNotExist:
        status['message'] = _('Plan or district does not exist.')
        return HttpResponse(
            json.dumps(status), content_type='application/json')

    if plan.owner != request.user:
        return HttpResponseForbidden()

    district.is_locked = lock
    district.save()
    status['success'] = True
    status['message'] = _('District successfully %(locked_state)s') % \
            {'locked_state': _('locked') if lock else _('unlocked')}

    return HttpResponse(json.dumps(status), content_type='application/json')


@unique_session_or_json_redirect
def getdistricts(request, planid):
    """
    Get the districts in a plan at a specific version.

    Parameters:
        request - An HttpRequest, with the current user.
        planid - The plan id to query for the districts.
    Returns:
    """
    note_session_activity(request)

    status = {'success': False}

    plan = Plan.objects.filter(id=planid)
    if plan.count() == 1:
        plan = plan[0]

        if 'version' in request.GET:
            version = int(request.GET['version'])
        else:
            version = plan.version

        districts = plan.get_districts_at_version(version, include_geom=False)

        status['districts'] = []

        # Same calculation as plan.get_available_districts, but
        # g_a_d fetches districts all over again -- skip that overhead
        status['available'] = plan.legislative_body.max_districts - len(
            districts) + 1

        # Find the maximum version in the returned districts
        max_version = max([d.version for d in districts])

        # Only allow undo if the max version being returned isn't
        # equal to the minimum stored version
        can_undo = max_version > plan.min_version

        for district in districts:
            status['districts'].append({
                'id':
                district.district_id,
                'short_label':
                ' '.join(map(_, district.short_label.split(' '))),
                'long_label':
                ' '.join(map(_, district.long_label.split(' '))),
                'version':
                district.version
            })
        status['canUndo'] = can_undo
        status['success'] = True

    else:
        status['message'] = _('No plan exists with that ID.')

    return HttpResponse(json.dumps(status), content_type='application/json')


def simple_district_versioned(request, planid, district_ids=None):
    """
    Emulate a WFS service for versioned districts.

    This function retrieves one version of the districts in a plan, with
    the value of the subject attached to the feature. This function is
    necessary because a traditional view could not be used to get the
    districts in a versioned fashion.

    This method accepts 'version__eq' and 'subjects__eq' URL parameters.

    This method accepts an optional 'district_ids__eq' parameter, which is
    a comma-separated list of district_ids to filter by

    Parameters:
        request -- An HttpRequest, with the current user.
        planid -- The plan ID from which to get the districts.

    Returns:
        A GeoJSON HttpResponse, describing the districts in the plan.
    """
    note_session_activity(request)

    status = {'type': 'FeatureCollection'}

    plan = Plan.objects.filter(id=planid)
    if plan.count() == 1:
        plan = plan[0]
        if 'version__eq' in request.GET:
            version = request.GET['version__eq']
        else:
            version = plan.version

        subject_id = None
        if 'subject__eq' in request.GET:
            subject_id = request.GET['subject__eq']
        elif plan.legislative_body.get_default_subject():
            subject_id = plan.legislative_body.get_default_subject().id

        geolevel = plan.legislative_body.get_geolevels()[0].id
        if 'level__eq' in request.GET:
            geolevel = int(request.GET['level__eq'])

        if 'district_ids__eq' in request.GET:
            district_ids = request.GET['district_ids__eq']
            if len(district_ids) > 0:
                district_ids = district_ids.split(',')
            else:
                district_ids = []

        if subject_id:
            bbox = None
            if 'bbox' in request.GET:
                bbox = request.GET['bbox']
                # convert the request string into a tuple full of floats
                bbox = tuple(map(lambda x: float(x), bbox.split(',')))
            else:
                bbox = plan.district_set.all().extent(field_name='simple')

            status['features'] = plan.get_wfs_districts(
                version, subject_id, bbox, geolevel, district_ids)
        else:
            status['features'] = []
            status['message'] = _('Subject for districts is required.')
    else:
        status['features'] = []
        status['message'] = _('Query failed.')

    return HttpResponse(json.dumps(status), content_type='application/json')


def get_unlocked_simple_geometries(request, planid):
    """
    Emulate a WFS service for selecting unlocked geometries.

    This function retrieves all unlocked geometries within a geolevel
    for a given plan. This function is necessary because a traditional
    view could not be used to obtain the geometries in a versioned fashion.

    This method accepts 'version__eq', 'level__eq', and 'geom__eq' URL parameters.

    Parameters:
    request -- An HttpRequest, with the current user.
    planid -- The plan ID from which to get the districts.

    Returns:
    A GeoJSON HttpResponse, describing the unlocked simplified geometries
    """
    note_session_activity(request)

    status = {'type': 'FeatureCollection'}

    plan = Plan.objects.filter(id=planid)
    if plan.count() == 1:
        plan = plan[0]
        version = request.POST.get('version__eq', plan.version)
        geolevel = request.POST.get(
            'level__eq',
            plan.legislative_body.get_geolevels()[0].id)
        geom = request.POST.get('geom__eq', None)
        if geom is not None:
            try:
                wkt = request.POST.get('geom__eq', None)
                geom = GEOSGeometry(wkt)
            # If we can't get a poly, try a linestring
            except GEOSException:
                wkt = request.GET['geom__eq'].replace('POLYGON', 'LINESTRING')
                wkt = wkt.replace('((', '(').replace('))', ')')
                try:
                    geom = GEOSGeometry(wkt)
                except GEOSException:
                    # If the line doesn't work, just don't return anything
                    geom = None

            # Selection is the geounits that intersects with the drawing tool used:
            # either a lasso, a rectangle, or a point
            selection = Q(geom__intersects=geom)

            # Create a union of locked geometries
            districts = [
                d.id
                for d in plan.get_districts_at_version(
                    version, include_geom=True) if d.is_locked
            ]
            locked = District.objects.filter(id__in=districts).aggregate(
                Collect('geom'))['geom__collect']

            # Create a simplified locked boundary for fast, but not completely accurate lookups
            # Note: the preserve topology parameter of simplify is needed here
            locked_buffered = locked.simplify(
                100, True).buffer(100) if locked else None

            # Filter first by geolevel, then selection
            filtered = Geolevel.objects.get(
                id=geolevel).geounit_set.filter(selection)
            # Assemble the matching features into geojson
            features = []
            for feature in filtered:
                # We want to allow for the selection of a geometry that is partially split
                # with a locked district, so subtract out all sections that are locked
                geom = feature.simple

                # Only perform additional tests if the fast, innacurate lookup passed
                if locked and geom.intersects(locked_buffered):

                    # If a geometry is fully locked, don't add it
                    if feature.geom.within(locked):
                        continue

                    # Overlapping geometries are the ones we need to subtract pieces of
                    if feature.geom.overlaps(locked):
                        # Since this is just for display, do the difference on the simplified geometries
                        geom = geom.difference(locked_buffered)

                features.append({
                    # Note: OpenLayers breaks when the id is set to an integer, or even an integer string.
                    # The id ends up being treated as an array index, rather than a property list key, and
                    # there are some bizarre consequences. That's why the underscore is here.
                    'id': '_%d' % feature.id,
                    'geometry': json.loads(geom.json),
                    'properties': {
                        'name': feature.name,
                        'geolevel_id': geolevel,
                        'id': feature.id
                    }
                })

            status['features'] = features
            return HttpResponse(
                json.dumps(status), content_type='application/json')

        else:
            status['features'] = []
            status['message'] = _('Geometry is required.')

    else:
        status['features'] = []
        status['message'] = _('Invalid plan.')

    return HttpResponse(json.dumps(status), content_type='application/json')


@unique_session_or_json_redirect
def get_statistics(request, planid):
    note_session_activity(request)

    status = {'success': False}
    try:
        plan = Plan.objects.get(pk=planid)
    except:
        status['message'] = _(
            "Couldn't get geography info from the server. No plan with the given id."
        )
        return HttpResponse(
            json.dumps(status), content_type='application/json', status=500)

    if 'version' in request.POST:
        try:
            version = int(request.POST['version'])
        except:
            version = plan.version
    else:
        version = plan.version

    try:
        display = ScoreDisplay.objects.get(
            legislative_body=plan.legislative_body,
            name="%s_sidebar_demo" % plan.legislative_body.name)
    except:
        status['message'] = _('Unable to get Demographics ScoreDisplay')
        status['exception'] = traceback.format_exc()

    if 'displayId' in request.POST:
        try:
            display = ScoreDisplay.objects.get(pk=request.POST['displayId'])
        except:
            status['message'] = _('Unable to get Personalized ScoreDisplay')
            status['exception'] = traceback.format_exc()

    else:
        logger.warn('No displayId in request.')
        logger.warn(str(request.POST))

    try:
        html = display.render(plan, request, version=version)
        return HttpResponse(html, content_type='text/html')
    except Exception, ex:
        status['message'] = _("Couldn't render display tab.")
        status['exception'] = traceback.format_exc()
        logger.warn("Couldn't render display tab")
        logger.debug('Reason: %s', ex)
        return HttpResponse(
            json.dumps(status), content_type='application/json', status=500)


def getutc(t):
    """
    Given a datetime object, translate to a datetime object for UTC time.
    """
    t_tuple = t.timetuple()
    t_seconds = time.mktime(t_tuple)
    return t.utcfromtimestamp(t_seconds)


@unique_session_or_json_redirect
def getdistrictfilestatus(request, planid):
    """
    Given a plan id, return the status of the district index file
    """
    note_session_activity(request)

    status = {'success': False}
    plan = Plan.objects.get(pk=planid)
    if not can_copy(request.user, plan):
        return HttpResponseForbidden()
    try:
        is_shape = 'type' in request.GET and request.GET['type'] == 'shape'
        file_status = DistrictFile.get_file_status(plan, shape=is_shape)
        status['success'] = True
        status['status'] = file_status
    except Exception as ex:
        status['message'] = _('Failed to get file status')
        status['exception'] = ex
    return HttpResponse(json.dumps(status), content_type='application/json')


@unique_session_or_json_redirect
def getdistrictfile(request, planid):
    """
    Given a plan id, email the user a zipped copy of
    the district index file
    """
    note_session_activity(request)

    # Get the districtindexfile and create a response
    plan = Plan.objects.get(pk=planid)
    if not can_copy(request.user, plan):
        return HttpResponseForbidden()

    is_shape = 'type' in request.GET and request.GET['type'] == 'shape'
    file_status = DistrictFile.get_file_status(plan, shape=is_shape)
    if file_status == 'done':
        if is_shape:
            archive = DistrictShapeFile.plan2shape(plan.id)
        else:
            archive = DistrictIndexFile.plan2index(plan.id)
        response = HttpResponse(
            open(archive).read(), content_type='application/zip')
        response[
            'Content-Disposition'] = 'attachment; filename="%s.zip"' % plan.get_friendly_name(
            )
    else:
        # Put in a celery task to create this file
        if is_shape:
            DistrictShapeFile.plan2shape.delay(plan.id)
        else:
            DistrictIndexFile.plan2index.delay(plan.id)
        response = HttpResponse(
            _('File is not yet ready. Please try again in '
              'a few minutes'))
    return response


@unique_session_or_json_redirect
def emaildistrictindexfile(request, planid):
    """
    Given a plan id, email a zipped copy of the district
    index file to a specified address
    """
    note_session_activity(request)

    if request.method != 'POST':
        return HttpResponseForbidden()

    plan = Plan.objects.get(pk=planid)
    if not can_copy(request.user, plan):
        return HttpResponseForbidden()

    # Put in a celery task to create the file and send the emails
    DistrictIndexFile.emailfile.delay(plan, request.user, request.POST,
                                      translation.get_language())
    return HttpResponse(
        json.dumps({
            'success': True,
            'message': _('Task submitted')
        }),
        content_type='application/json')


def getvalidplans(leg_body, owner=None):
    """
    Returns the valid plans for a given legislative body and owner (optional)
    """
    pfilter = Q(legislative_body=leg_body) & Q(is_valid=True)
    if owner is not None:
        pfilter = pfilter & Q(owner=owner)

    return list(Plan.objects.filter(pfilter))


def getleaderboarddisplay(leg_body, owner_filter):
    """
    Returns the leaderboard ScoreDisplay given a legislative body and owner
    """
    try:
        return ScoreDisplay.objects.get(name="%s_leader_%s" % (leg_body.name,
                                                               owner_filter))
    except:
        return None


def getleaderboard(request):
    """
    Get the rendered leaderboard
    """
    note_session_activity(request)

    if not using_unique_session(request.user):
        return HttpResponseForbidden()

    owner_filter = request.GET['owner_filter']
    body_pk = int(request.GET['legislative_body'])
    leg_body = LegislativeBody.objects.get(pk=body_pk)

    display = getleaderboarddisplay(leg_body, owner_filter)
    if display is None:
        return HttpResponse(
            _('No display configured'), content_type='text/plain')

    plans = getvalidplans(leg_body, request.user
                          if owner_filter == 'mine' else None)

    try:
        html = display.render(plans, request)
        return HttpResponse(html, content_type='text/html; charset=utf-8')
    except Exception, ex:
        logger.warn('Leaderboard could not be fetched.')
        logger.debug('Reason: %s', ex)
        return HttpResponse(str(ex), content_type='text/plain')


def getleaderboardcsv(request):
    """
    Get the leaderboard scores in csv form
    """
    note_session_activity(request)

    if not using_unique_session(request.user):
        return HttpResponseForbidden()

    owner_filter = request.GET['owner_filter']
    body_pk = int(request.GET['legislative_body'])
    leg_body = LegislativeBody.objects.get(pk=body_pk)
    plans = getvalidplans(leg_body, request.user
                          if owner_filter == 'mine' else None)

    display = getleaderboarddisplay(leg_body, owner_filter)
    plans = getvalidplans(leg_body, request.user
                          if owner_filter == 'mine' else None)

    panels = display.scorepanel_set.all().order_by('position')

    try:
        # mark the response as csv, and create the csv writer
        response = HttpResponse(content_type='text/csv')
        response[
            'Content-Disposition'] = 'attachment; filename=leaderboard_scores.csv'
        writer = csv.writer(response)

        # write headers
        writer.writerow(['Plan ID', 'Plan Name', 'User Name'] +
                        [p.__unicode__() for p in panels])

        # write row for each plan
        for plan in plans:
            row = [plan.id, plan.name, plan.owner.username]

            # add each score
            for panel in panels:
                function = panel.score_functions.all()[0]
                score = ComputedPlanScore.compute(function, plan)
                row.append(score['value'])

            # write the row
            writer.writerow(row)

        return response
    except Exception, ex:
        logger.warn("Couldn't generate CSV of leaderboard.")
        logger.debug('Reason: %s', ex)
        return HttpResponse(str(ex), content_type='text/plain')


def getplans(request):
    """
    Get the plans for the given user and return the data in a format readable
    by the jqgrid
    """
    note_session_activity(request)

    if not using_unique_session(request.user):
        return HttpResponseForbidden()

    if request.method == 'POST':
        page = int(request.POST.get('page', 1))
        rows = int(request.POST.get('rows', 10))
        sidx = request.POST.get('sidx', 'id')
        sord = request.POST.get('sord', 'asc')
        owner_filter = request.POST.get('owner_filter')
        body_pk = request.POST.get('legislative_body')
        body_pk = int(body_pk) if body_pk else body_pk
        search = request.POST.get('_search', False)
        search_string = request.POST.get('searchString', '')
        is_community = request.POST.get('is_community', False) == 'true'
    else:
        return HttpResponseForbidden()
    end = page * rows
    start = end - rows

    if owner_filter == 'template':
        available = Q(is_template=True)
    elif owner_filter == 'shared':
        available = Q(is_shared=True)
    elif owner_filter == 'mine':
        if request.user.is_anonymous():
            return HttpResponseForbidden()
        else:
            available = Q(owner__exact=request.user)
    elif owner_filter == 'all_available':
        available = Q(is_template=True) | Q(is_shared=True)
        if not request.user.is_anonymous():
            available = available | Q(owner__exact=request.user)
    else:
        return HttpResponseBadRequest(_("Unknown filter method."))

    not_creating = ~Q(processing_state=ProcessingState.CREATING) & ~Q(
        processing_state=ProcessingState.UNKNOWN)

    # Set up the order_by parameter from sidx and sord in the request
    if sidx.startswith('fields.'):
        sidx = sidx[len('fields.'):]
    if sidx == 'owner':
        sidx = 'owner__username'
    if sidx == 'plan_type':
        sidx = 'legislative_body__name'
    if sord == 'desc':
        sidx = '-' + sidx

    if search:
        search_filter = Q(name__icontains=search_string) | Q(
            description__icontains=search_string) | Q(
                owner__username__icontains=search_string)
    else:
        search_filter = None

    if body_pk:
        body_filter = Q(legislative_body=body_pk)
        all_plans = Plan.objects.filter(available, not_creating, body_filter,
                                        search_filter).order_by(sidx)
    else:
        community_filter = Q(legislative_body__is_community=is_community)
        all_plans = Plan.objects.filter(available, not_creating, search_filter,
                                        community_filter).order_by(sidx)

    if all_plans.count() > 0:
        total_pages = math.ceil(all_plans.count() / float(rows))
    else:
        total_pages = 1

    plans = all_plans[start:end]
    # Create the objects that will be serialized for presentation in the plan chooser
    plans_list = list()
    for plan in plans:
        plans_list.append({
            'pk': plan.id,
            'fields': {
                'name': plan.name,
                'description': plan.description,
                'edited': time.mktime(plan.edited.timetuple()),
                'is_template': plan.is_template,
                'is_shared': plan.is_shared,
                'owner': plan.owner.username,
                'districtCount':
                '--',  # load dynamically -- this is a big performance hit
                'can_edit': can_edit(request.user, plan),
                'plan_type': plan.legislative_body.get_long_description(),
                'processing_state': plan.get_processing_state_display()
            }
        })

    json_response = "{ \"total\":\"%d\", \"page\":\"%d\", \"records\":\"%d\", \"rows\":%s }" % (
        total_pages, page, len(all_plans), json.dumps(plans_list))
    return HttpResponse(json_response, content_type='application/json')


def get_shared_districts(request, planid):
    """
    Get the shared districts in a given plan and return the
    data in a format readable by the jqgrid
    """
    note_session_activity(request)

    if not using_unique_session(request.user):
        return HttpResponseForbidden()

    if request.method == 'POST':
        page = int(request.POST.get('page', 1))
        rows = int(request.POST.get('rows', 10))
    else:
        return HttpResponseForbidden()

    end = page * rows
    start = end - rows

    try:
        plan = Plan.objects.get(pk=planid)
        if not can_copy(request.user, plan):
            return HttpResponseForbidden()

        all_districts = plan.get_districts_at_version(
            plan.version, include_geom=False)
    except:
        plan = None
        all_districts = ()

    if len(all_districts) > 0:
        total_pages = math.ceil(len(all_districts) / float(rows))
    else:
        total_pages = 1

    districts = all_districts[start:end]
    # Create the objects that will be serialized for presentation in the plan chooser
    districts_list = list()
    for district in districts:
        if not district.is_unassigned:
            districts_list.append({
                'pk': district.id,
                'fields': {
                    'short_label': district.short_label,
                    'long_label': district.long_label,
                    'district_id': district.district_id,
                }
            })

    json_response = "{ \"total\":\"%d\", \"page\":\"%d\", \"records\":\"%d\", \"rows\":%s }" % (
        total_pages, page, len(all_districts), json.dumps(districts_list))
    return HttpResponse(json_response, content_type='application/json')


@login_required
@unique_session_or_json_redirect
def editplanattributes(request, planid):
    """
    Edit the attributes of a plan. Attributes of a plan are the name and/or
    description.
    """
    note_session_activity(request)

    status = {'success': False}
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    new_name = request.POST.get('name', None)
    new_description = request.POST.get('description', '')

    if not planid or not (new_name or new_description):
        return HttpResponseBadRequest(
            _('Must declare planId, name and description'))

    plan = Plan.objects.filter(pk=planid, owner=request.user)
    if plan.count() == 1:
        plan = plan[0]
        if not new_name is None:
            plan.name = new_name

        plan.description = new_description
        try:
            plan.save()

            status['success'] = True
            status['message'] = _('Updated plan attributes')
        except Exception, ex:
            status['message'] = _('Failed to save the changes to your plan')
            status['exception'] = ex
            logger.warn('Could not save changes to plan.')
            logger.debug('Reason: %s', ex)
    else:
        status['message'] = _("Cannot edit a plan you don't own.")
    return HttpResponse(json.dumps(status), content_type='application/json')


@login_required
@unique_session_or_json_redirect
def deleteplan(request, planid):
    """
    Delete a plan
    """
    note_session_activity(request)

    status = {'success': False}
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    if not planid:
        return HttpResponseBadRequest(_('Must declare planId'))

    plan = Plan.objects.filter(pk=planid, owner=request.user)
    if plan.count() == 1:
        plan = plan[0]
        try:
            plan.delete()
            status['success'] = True
            status['message'] = _('Deleted plan')
        except Exception, ex:
            status['message'] = _('Failed to delete plan')
            status['exception'] = ex
            logger.warn('Could not delete plan.')
            logger.debug('Reason: %s', ex)
    else:
        status['message'] = _("Cannot delete a plan you don't own.")

    return HttpResponse(json.dumps(status), content_type='application/json')


@login_required
@unique_session_or_json_redirect
def reaggregateplan(request, planid):
    """
    Reaggregate a plan
    """
    note_session_activity(request)

    status = {'success': False}
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    if not planid:
        return HttpResponseBadRequest(_('Must declare planId'))

    plan = Plan.objects.filter(pk=planid, owner=request.user)
    if plan.count() == 1:
        plan = plan[0]
        try:
            reaggregate_plan.delay(plan.id)

            # Set the reaggregating flag
            # (needed for the state to display on immediate refresh)
            plan.processing_state = ProcessingState.REAGGREGATING
            plan.save()

            status['success'] = True
            status['message'] = _('Reaggregating plan')
        except Exception, ex:
            status['message'] = _('Failed to reaggregate plan')
            status['exception'] = ex
            logger.warn('Could not reaggregate plan.')
            logger.debug('Reason: %s', ex)
    else:
        status['message'] = _("Cannot reaggregate a plan you don't own.")
    return HttpResponse(json.dumps(status), content_type='application/json')


def get_health(request):
    def num_users(minutes):
        users = 0
        for session in Session.objects.all():
            try:
                decoded = session.get_decoded()
            except:
                #There's a problem with this session, remove it
                session.delete()
                continue

            if 'activity_time' in decoded:
                activity_delta = decoded['activity_time'] - timedelta(
                    0, 0, 0, 0, settings.SESSION_TIMEOUT)
                if activity_delta > (
                        datetime.now() - timedelta(0, 0, 0, 0, minutes)):
                    users += 1
        return users

    try:
        result = _('Health retrieved at %(time)s\n') % {'time': datetime.now()}
        result += _('%(plan_count)d plans in database\n') % \
                {'plan_count': Plan.objects.all().count()}
        result += _('%(session_count)d sessions in use out of %(session_limit)s\n') % \
                {'session_count': Session.objects.all().count(),
                'session_limit': settings.CONCURRENT_SESSIONS}
        result += _('%(num_users)d active users over the last 10 minutes\n') % \
                {'num_users':  num_users(10)}
        space = os.statvfs(settings.BASE_DIR)
        result += _('%(mb_free)s MB of disk space free\n') % \
                {'mb_free': ((space.f_bsize * space.f_bavail) / (1024*1024))}
        result += _('Memory Usage:\n%(mem_free)s\n') % \
                {'mem_free':  commands.getoutput('free -m')}
        return HttpResponse(result, content_type='text/plain')
    except:
        return HttpResponse(
            _("ERROR! Couldn't get health:\n%s") % traceback.format_exc())


def statistics_sets(request, planid):
    result = {'success': False}

    plan = Plan.objects.filter(id=planid)
    if plan.count() == 0:
        result['message'] = _('No plan with that ID exists.')
        return HttpResponse(
            json.dumps(result), content_type='application/json')
    else:
        plan = plan[0]

    if request.method == 'GET':
        sets = []
        scorefunctions = []

        # Get the functions available for the users
        user_functions = ScoreFunction.objects.filter(
            selectable_bodies=plan.legislative_body).order_by('name')
        for f in user_functions:
            if 'report' not in f.name.lower(
            ) and 'comments' not in f.name.lower():
                scorefunctions.append({
                    'id': f.id,
                    'name': force_escape(f.get_label())
                })
        result['functions'] = scorefunctions

        admin_display_names = [
            "%s_sidebar_demo" % plan.legislative_body.name,
        ]

        if plan.legislative_body.is_community:
            admin_display_names.append(
                "%s_sidebar_comments" % plan.legislative_body.name)
        else:
            admin_display_names.append(
                "%s_sidebar_basic" % plan.legislative_body.name)
        # Get the admin displays
        admin_displays = ScoreDisplay.objects.filter(
            owner__is_superuser=True,
            legislative_body=plan.legislative_body,
            name__in=admin_display_names)

        for admin_display in admin_displays:
            sets.append({
                'id': admin_display.id,
                'name': force_escape(admin_display.get_label()),
                'functions': [],
                'mine': False
            })

        try:
            user_displays = ScoreDisplay.objects.filter(
                owner=request.user,
                legislative_body=plan.legislative_body,
                is_page=False).order_by('title')
            result['displays_count'] = len(user_displays)
            for display in user_displays:
                functions = []
                for panel in display.scorepanel_set.all():
                    if panel.type == 'district':
                        functions = map(lambda x: x.id,
                                        panel.score_functions.all())
                        if len(functions) == 0:
                            result['message'] = _("No functions for %(panel)s") % \
                                                {'panel_name': panel}
                sets.append({
                    'id': display.id,
                    'name': force_escape(display.__unicode__()),
                    'functions': functions,
                    'mine': display.owner == request.user
                })
        except Exception, ex:
            result['message'] = _('No user displays for %(user)s') % \
                 {'user': request.user}
            logger.warn('Error fetching ScoreDisplays for user')
            logger.debug('Reason: %s', ex)

        result['sets'] = sets
        result['success'] = True
    # Delete the requested ScoreDisplay to make some room
    elif request.method == 'POST' and 'delete' in request.POST:
        try:
            display = ScoreDisplay.objects.get(pk=request.POST.get('id', -1))
            result['set'] = {
                'name': force_escape(display.__unicode__()),
                'id': display.id
            }
            qset = display.scorepanel_set.all()
            for panel in qset:
                if panel.displays.count() == 1:
                    panel.delete()
            display.delete()
            result['success'] = True
        except Exception, ex:
            result['message'] = _("Couldn't delete personalized scoredisplay")
            result['exception'] = traceback.format_exc()
            logger.warn("Couldn't delete personalized ScoreDisplay")
            logger.debug('Reason: %s', ex)

    # If it's a post, edit or create the ScoreDisplay and return
    # the id and name as usual
    elif request.method == 'POST':
        # If we're adding a new display, we should make sure they only have 3
        def validate_num(user, limit=3):
            return ScoreDisplay.objects.filter(
                owner=user,
                legislative_body=plan.legislative_body,
                is_page=False).count() < limit

        if 'functions[]' in request.POST:
            functions = request.POST.getlist('functions[]')
            functions = map(lambda x: int(x), functions)
            try:
                display = ScoreDisplay.objects.get(
                    title=request.POST.get('name'), owner=request.user)
                display = display.copy_from(
                    display=display, functions=functions)
            except:
                limit = 3
                if validate_num(request.user, limit):
                    demo = ScoreDisplay.objects.filter(
                        owner__is_superuser=True,
                        legislative_body=plan.legislative_body,
                        is_page=False,
                        title="Demographics")
                    # DO NOT select the ScoreDisplay that contains
                    # the comment calculator
                    for disp in demo:
                        has_comments = False
                        for pnl in disp.scorepanel_set.all():
                            for fn in pnl.score_functions.all():
                                has_comments = has_comments or fn.calculator.endswith(
                                    '.Comments')
                        if not has_comments:
                            demo = disp
                            break

                    display = ScoreDisplay()
                    display = display.copy_from(
                        display=demo,
                        title=request.POST.get('name'),
                        owner=request.user,
                        functions=functions)
                    result['newRecord'] = True
                else:
                    result['message'] = _(
                        'Each user is limited to %(limit)d '
                        'statistics sets. Please delete one or edit '
                        'an existing set.') % {
                            'limit': limit
                        }
                    result['error'] = 'limit'
                    return HttpResponse(
                        json.dumps(result), content_type='application/json')

            result['set'] = {
                'name': force_escape(display.__unicode__()),
                'id': display.id,
                'functions': functions,
                'mine': display.owner == request.user
            }
            result['success'] = True

        else:
            result['message'] = _("Didn't get functions in POST parameter")

    return HttpResponse(json.dumps(result), content_type='application/json')


#
# Comment views
#
def purge_plan_clear_cache(district, version):
    """
    This is a helper method that purges a plan after a version, and clears
    any pre-computed scores at the specified version.
    """
    district.plan.purge(after=version)

    district.plan.version = version
    district.plan.save()

    cache = district.computeddistrictscore_set.filter(
        function__calculator__endswith='.Comments')
    cache.delete()


@unique_session_or_json_redirect
def district_info(request, planid, district_id):
    """
    Get the comments that are attached to a district.

    Parameters:
        request -- An HttpRequest
        planid -- The plan ID
        district_id -- The district ID, this is the district number in a plan, and NOT the id of a district.
    """
    status = {'success': False}
    plan = Plan.objects.filter(id=planid)
    if plan.count() == 0:
        status['message'] = _('No plan with that ID was found.')
    else:
        plan = plan[0]

        version = plan.version
        if 'version' in request.GET:
            try:
                version = int(request.GET['version'])
                version = min(plan.version, int(version))
            except:
                pass

        district_id = int(district_id)
        district = plan.get_districts_at_version(version, include_geom=False)
        district = filter(lambda d: d.district_id == district_id, district)

        if request.method == 'POST':
            district = plan.district_set.get(id=request.POST['object_pk'])
            district.short_label = request.POST['district_short'][0:10]
            district.long_label = request.POST['district_long'][0:256]

            if district.version < version:
                # The district version may lag behind the cursor
                # version if there were no edits for a while. If this
                # is the case the district must be copied to the
                # currently edited version.
                district_copy = copy.copy(district)
                district_copy.id = None
                district_copy.version = version

                district_copy.save()

                # clone the characteristics, comments, and tags from
                # the original district to the copy
                district_copy.clone_relations_from(district)
                district = district_copy
            else:
                # save the changes to the district -- maybe name change
                district.save()

            has_comment = 'comment' in request.POST and request.POST['comment'] != ''
            if has_comment:
                # Don't thread comments, keep only the latest and greatest
                ct = ContentType.objects.get(
                    app_label='redistricting', model='district')
                Comment.objects.filter(
                    object_pk=district.id, content_type=ct).delete()
                comment = Comment(
                    object_pk=district.id,
                    content_type=ct,
                    site_id=Site.objects.get_current().id,
                    user_name=request.user.username,
                    user_email=request.user.email,
                    comment=request.POST['comment'])
                comment.save()
            else:
                # save this if the label changed
                district.save()

            # Get the tags on this object of this type.
            tset = Tag.objects.get_for_object(district).filter(
                name__startswith='type')

            # Purge the tags of this same type off the object
            TaggedItem.objects.filter(
                tag__in=tset, object_id=district.id).delete()

            purge_plan_clear_cache(district, version)

            if len(request.POST.getlist('type[]')) > 0:
                strtags = request.POST.getlist('type[]')
                for strtag in strtags:
                    if strtag == '':
                        continue
                    if strtag.count(' ') > 0:
                        strtag = '"type=%s"' % strtag
                    else:
                        strtag = 'type=%s' % strtag
                    Tag.objects.add_tag(district, strtag)

            status['version'] = version
            status['success'] = True

    return HttpResponse(json.dumps(status), content_type='application/json')


def plan_feed(request):
    feed = loader.get_template('plan_feed.xml')
    # MAP_SERVER = ''
    # MAP_SERVER_NS = 'pmp'
    plans = Plan.objects.all().order_by('-edited')[0:10]
    geolevel = plans[0].legislative_body.get_geolevels()[0]
    extent = geolevel.geounit_set.aggregate(
        Collect('geom'))['geom__collect'].extent
    if extent[2] - extent[0] > extent[3] - extent[1]:
        # wider maps
        width = 500
        height = int(500 * (extent[3] - extent[1]) / (extent[2] - extent[0]))
    else:
        # taller maps
        width = int(500 * (extent[2] - extent[0]) / (extent[3] - extent[1]))
        height = 500
    mapserver = settings.MAP_SERVER if settings.MAP_SERVER != '' else request.META[
        'SERVER_NAME']
    context = {
        'plans': plans,
        'mapserver': mapserver,
        'mapserver_ns': settings.MAP_SERVER_NS,
        'extent': extent,
        'width': width,
        'height': height
    }
    xml = feed.render(context)

    return HttpResponse(xml, content_type='application/atom+xml')


def share_feed(request):
    feed = loader.get_template('shared_feed.xml')
    # MAP_SERVER = ''
    # MAP_SERVER_NS = 'pmp'
    plans = Plan.objects.filter(is_shared=True).order_by('-edited')[0:10]
    if plans.count() < 0:
        geolevel = plans[0].legislative_body.get_geolevels()[0]
        extent = geolevel.geounit_set.aggregate(
            Collect('geom'))['geom__collect'].extent
        if extent[2] - extent[0] > extent[3] - extent[1]:
            # wider maps
            width = 500
            height = int(500 * (extent[3] - extent[1]) /
                         (extent[2] - extent[0]))
        else:
            # taller maps
            width = int(500 * (extent[2] - extent[0]) /
                        (extent[3] - extent[1]))
            height = 500
    else:
        extent = (
            0,
            0,
            0,
            0,
        )
        width = 1
        height = 1
    mapserver = settings.MAP_SERVER if settings.MAP_SERVER != '' else request.META[
        'SERVER_NAME']
    context = {
        'plans': plans,
        'mapserver': mapserver,
        'mapserver_ns': settings.MAP_SERVER_NS,
        'extent': extent,
        'width': width,
        'height': height
    }
    xml = feed.render(context)

    return HttpResponse(xml, content_type='application/atom+xml')
