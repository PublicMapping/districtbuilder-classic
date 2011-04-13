"""
Django views used by the redistricting application.

The methods in redistricting.views define the views used to interact with
the models in the redistricting application. Each method relates to one 
type of output url. There are views that return GeoJSON, JSON, and HTML.

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

from django.http import *
from django.core import serializers
from django.core.exceptions import ValidationError, SuspiciousOperation, ObjectDoesNotExist
from django.db import IntegrityError, connection, transaction
from django.db.models import Sum, Min, Max
from django.shortcuts import render_to_response
from django.core.urlresolvers import reverse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.sessions.models import Session
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.gis.geos.collections import MultiPolygon
from django.contrib.gis.geos import GEOSGeometry
from django.contrib.gis.gdal import *
from django.contrib.gis.gdal.libgdal import lgdal
from django.contrib import humanize
from django import forms
from django.utils import simplejson as json
from django.views.decorators.cache import cache_control
from django.template.defaultfilters import slugify
from datetime import datetime, time, timedelta
from decimal import *
from functools import wraps
from redistricting.calculators import *
from redistricting.models import *
from redistricting.utils import *
import settings, random, string, math, types, copy, time, threading, traceback, os, commands, sys, tempfile, csv, hashlib

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
                if 'activity_time' in decoded and decoded['activity_time'] < datetime.now():
                    # delete this session of mine; it is dormant
                    Session.objects.filter(session_key=session.session_key).delete()
                else:
                    count += 1
        except SuspiciousOperation:
            print "SuspiciousOperation caught while checking the number of sessions a user has open. Session key: %s" % session.session_key
            print traceback.format_exc()

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
            print "SuspiciousOperation caught while setting the session count on all user sessions. Session key: %s" % session.session_key

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
    def decorator(request, *args, **kwargs) :
        def return_nonunique_session_result():
            status = { 'success': False }
            status['message'] = "The current user may only have one session open at a time."
            status['redirect'] = '/?msg=logoff'
            return HttpResponse(json.dumps(status),mimetype='application/json')

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
    if req.user.is_superuser:
        return True

    sessions = Session.objects.filter(expire_date__gt=datetime.now())
    count = 0
    for session in sessions:
        try:
            decoded = session.get_decoded()
            if (not req.user.is_anonymous()) and 'activity_time' in decoded and decoded['activity_time'] > datetime.now():
                count += 1
        except SuspiciousOperation:
            print "SuspiciousOperation caught while checking the last activity time in a user's session. Session key: %s" % session.session_key
            print traceback.format_exc()

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
    window = timedelta(0,0,0,0,settings.SESSION_TIMEOUT)
    req.session['activity_time'] = datetime.now() + window


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
    status = { 'success': False }

    p = Plan.objects.get(pk=planid)

    if not can_copy(request.user, p):
        status['message'] = "User %s doesn't have permission to unload this plan" % request.user.username
        return HttpResponse(json.dumps(status),mimetype='application/json')

    # Purge temporary versions
    if settings.MAX_UNDOS_AFTER_EDIT > 0:
        p.purge_beyond_nth_step(settings.MAX_UNDOS_AFTER_EDIT)
    
    status['success'] = True
    return HttpResponse(json.dumps(status),mimetype='application/json')

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

    status = { 'success': False }
    p = Plan.objects.get(pk=planid)
    # Check if this plan is copyable by the current user.
    if not can_copy(request.user, p):
        status['message'] = "User %s doesn't have permission to copy this model" % request.user.username
        return HttpResponse(json.dumps(status),mimetype='application/json')

    # Create a random name if there is no name provided
    newname = p.name + " " + str(random.random()) 
    if (request.method == "POST" ):
        newname = request.POST["name"]
        shared = request.POST.get("shared", False)

    plan_copy = Plan.objects.filter(name__exact=newname, owner=request.user)
    # Check that the copied plan's name doesn't already exist.
    if len(plan_copy) > 0:
        status['message'] = "You already have a plan named that. Please pick a unique name."
        return HttpResponse(json.dumps(status),mimetype='application/json')

    plan_copy = Plan(name=newname, owner=request.user, is_shared=shared, legislative_body=p.legislative_body)
    plan_copy.create_unassigned = False
    plan_copy.save()

    # Get all the districts in the original plan at the most recent version
    # of the original plan.
    districts = p.get_districts_at_version(p.version, include_geom=True)
    for district in districts:
        district_copy = copy.copy(district)

        district_copy.id = None
        district_copy.version = 0
        district_copy.plan = plan_copy

        try:
            district_copy.save() 
        except Exception as inst:
            status["message"] = "Could not save district copies"
            status["exception"] = inst.message
            return HttpResponse(json.dumps(status),mimetype='application/json')

        # clone the characteristics from the original district to the copy 
        district_copy.clone_characteristics_from(district)

    # Serialize the plan object to the response.
    data = serializers.serialize("json", [ plan_copy ])

    return HttpResponse(data, mimetype='application/json')

@login_required
@unique_session_or_json_redirect
def scoreplan(request, planid):
    """
    Validate a plan to allow for it to be shown in the leaaderboard

    Parameters:
        request -- The HttpRequest, which includes the user.
        planid -- The plan to score.

    Returns:
        A JSON HttpResponse which includes a status, and if applicable,
        a reason why the plan couldn't be validated
    """
    note_session_activity(request)
    status = { 'success': False }
    plan = Plan.objects.get(pk=planid)

    # check if the computed char for REP exists yet
    districts = plan.get_districts_at_version(plan.version,include_geom=False)
    subject = Subject.objects.get(name='govrep')
    ccs = ComputedCharacteristic.objects.filter(district__in=districts,subject=subject)
    seemingly_valid = 0
    for cc in ccs:
        if not cc.number is None and float(cc.number) != 0.0:
            seemingly_valid += 1

    if seemingly_valid == 0:
        # reaggregate this plan w/dem rep
        from django.core.management import call_command
        call_command('reaggregate', plan_id=plan.id)

    criterion = ValidationCriteria.objects.filter(legislative_body=plan.legislative_body)
    status['success'] = True
    for criteria in criterion:
        try:
            score = ComputedPlanScore.compute(criteria.function, plan)
        except:
            print traceback.format_exc()

        if not score:
            status['success'] = False
            status['message'] = '<p>%s</p><p>%s</p>' % (criteria.name, criteria.description or criteria.function.description)
            break

    if status['success']:
        status['success'] = True
        status['message'] = "Validation successful"

        # Set is_valid status on the plan
        plan.is_valid = True
        plan.save()

    return HttpResponse(json.dumps(status),mimetype='application/json')


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

    profile = user.get_profile()

    return {
        'username':user.username,
        'email':user.email,
        'password_hint':profile.pass_hint,
        'firstname':user.first_name,
        'lastname':user.last_name,
        'organization':profile.organization,
        'id':user.id
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
        targets = plan.targets()
        levels = plan.legislative_body.get_geolevels()
        districts = plan.get_districts_at_version(plan.version,include_geom=False)
        editable = can_edit(request.user, plan)
        default_demo = plan.legislative_body.get_default_subject()
        max_dists = plan.legislative_body.max_districts
        body_member = plan.legislative_body.member
        reporting_template = 'bard_%s.html' % plan.legislative_body.name.lower()

        index = body_member.find('%')
        if index >= 0:
            body_member = body_member[0:index]
        if not editable and not can_view(request.user, plan):
            plan = {}
    else:
        # If said plan doesn't exist, use an empty plan & district list.
        plan = {}
        targets = list()
        levels = list()
        districts = {}
        editable = False
        default_demo = None
        max_dists = 0
        body_member = 'District '
        reporting_template = None
    demos = Subject.objects.all().order_by('sort_key').values_list("id","name", "short_display","is_displayed")[0:3]
    layers = []
    snaplayers = []
    boundaries = []
    rules = []

    if len(levels) > 0:
        study_area_extent = list(Geounit.objects.filter(geolevel=levels[0]).extent(field_name='simple'))
    else:
        # The geolevels with higher indexes are larger geography
        biglevel = Geolevel.objects.all().order_by('-id')[0]
        study_area_extent = Geounit.objects.filter(geolevel=biglevel).extent(field_name='simple')

    for level in levels:
        snaplayers.append( {'geolevel':level.id,'layer':level.name,'name':level.name.capitalize(),'min_zoom':level.min_zoom} )
        boundaries.append( {'id':'%s_boundaries' % level.name.lower(), 'name':level.name.capitalize()} )
    # Don't display the lowest geolevel because it's never available as a boundary
    if len(boundaries) > 0:
        boundaries.pop()
    default_selected = False
    for demo in demos:
        isdefault = str((not default_demo is None) and (demo[0] == default_demo.id)).lower()
        if isdefault == True:
            default_selected = True
        layers.append( {'id':demo[0],'text':demo[2],'value':demo[1].lower(), 'isdefault':isdefault, 'isdisplayed':str(demo[3]).lower()} )
    # If the default demo was not selected among the first three, we'll still need it for the dropdown menus
    if default_demo and not default_selected:
        layers.insert( 0, {'id':default_demo.id,'text':default_demo.short_display,'value':default_demo.name.lower(), 'isdefault':str(True).lower(), 'isdisplayed':str(default_demo.is_displayed).lower()} )

    for target in targets:
        # The "in there" range
        range1 = target.value * target.range1
        # The "out of there" range
        range2 = target.value * target.range2
        rules.append( {'subject_id':target.subject_id,'lowest': target.value - range2,'lower':target.value - range1,'upper':target.value + range1,'highest': target.value + range2} )

    unassigned_id = 0
    if type(plan) != types.DictType:
        unassigned_id = plan.district_set.filter(name='Unassigned').values_list('district_id',flat=True)[0]

    return {
        'bodies': LegislativeBody.objects.all().order_by('name'),
        'plan': plan,
        'districts': districts,
        'mapserver': settings.MAP_SERVER,
        'basemaps': settings.BASE_MAPS,
        'namespace': settings.MAP_SERVER_NS,
        'ns_href': settings.MAP_SERVER_NSHREF,
        'feature_limit': settings.FEATURE_LIMIT,
        'demographics': layers,
        'snaplayers': snaplayers,
        'boundaries': boundaries,
        'rules': rules,
        'unassigned_id': unassigned_id,
        'is_registered': request.user.username != 'anonymous' and request.user.username != '',
        'debugging_staff': settings.DEBUG and request.user.is_staff,
        'userinfo': get_user_info(request.user),
        'is_editable': editable,
        'max_dists': max_dists + 1,
        'ga_account': settings.GA_ACCOUNT,
        'ga_domain': settings.GA_DOMAIN,
        'body_member': body_member,
        'reporting_template': reporting_template,
        'study_area_extent': study_area_extent,
        'has_leaderboard' : len(ScoreDisplay.objects.filter(is_page=True)) > 0
    }


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

    if not is_session_available(request):
        return HttpResponseRedirect('/')

    # Cleanup old versions for logged in users
    if not request.user.is_anonymous() and (int(planid) == 0) and (settings.MAX_UNDOS_AFTER_EDIT > 0):
        for p in Plan.objects.filter(owner=request.user):
            p.purge_beyond_nth_step(settings.MAX_UNDOS_AFTER_EDIT)

    return render_to_response('viewplan.html', commonplan(request, planid))


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
    if not is_session_available(request):
        return HttpResponseRedirect('/')

    if request.user.is_anonymous():
        return HttpResponseRedirect('/')

    cfg = commonplan(request, planid)
    if cfg['is_editable'] == False:
        return HttpResponseRedirect('/districtmapping/plan/%s/view/' % planid)
    plan = Plan.objects.get(id=planid,owner=request.user)
    cfg['dists_maxed'] = len(cfg['districts']) > plan.legislative_body.max_districts
    cfg['available_districts'] = plan.get_available_districts()

    # Cleanup old versions
    if settings.MAX_UNDOS_AFTER_EDIT > 0:
        plan.purge_beyond_nth_step(settings.MAX_UNDOS_AFTER_EDIT)

    return render_to_response('editplan.html', cfg) 

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

    status = { 'success': False }
    if request.method == "POST":
        name = request.POST['name']
        body = LegislativeBody.objects.get(id=int(request.POST['legislativeBody']))
        plan = Plan(name = name, owner = request.user, legislative_body = body)
        try:
            plan.save()
            status = serializers.serialize("json", [ plan ])
        except:
            status = { 'success': False, 'message': 'Couldn\'t save new plan' }
    return HttpResponse(json.dumps(status),mimetype='application/json')

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

    status = commonplan(request,0)
    status['upload'] = True
    status['upload_status'] = True

    index_file = request.FILES.get('indexFile', False)
    if not index_file:
        status['upload_status'] = False
        return render_to_response('viewplan.html', status)
    else:
        filename = index_file.name

    if index_file.size > settings.MAX_UPLOAD_SIZE:
        sys.stderr.write('File size exceeds allowable size.\n')
        status['upload_status'] = False
        return render_to_response('viewplan.html', status)

    if not filename.endswith(('.csv','.zip')):
        sys.stderr.write('Uploaded file must be ".csv" or ".zip".\n')
        status['upload_status'] = False
    elif request.POST['userEmail'] == '':
        sys.stderr.write('No email provided for user notification.\n')
        status['upload_status'] = False
    else:
        try:
            dest = tempfile.NamedTemporaryFile(mode='wb+', delete=False)
            for chunk in request.FILES['indexFile'].chunks():
                dest.write(chunk)
            dest.close()
            if request.FILES['indexFile'].name.endswith('.zip'):
                os.rename(dest.name, '%s%s' % (dest.name,'.zip'))
                filename = '%s%s' % (dest.name,'.zip')
            else:
                filename = dest.name

        except Exception as ex:
            sys.stderr.write( 'Could not save uploaded file: %s\n' % ex )
            status['upload_status'] = False
            return render_to_response('viewplan.html', status)

        # Put in a celery task to create the plan and email user on completion
        DistrictIndexFile.index2plan.delay(request.POST['txtNewName'], request.POST['legislativeBody'], filename, owner = request.user, template = False, purge = True, email = request.POST['userEmail'])

    return render_to_response('viewplan.html', status) 

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
def getreport(request, planid):
    """
    Get a BARD report.

    This view will write out an HTML-formatted BARD report to the directory
    given in the settings.
    
    Parameters:
        request -- An HttpRequest
        planid -- The plan to be reported.
    
    Returns:
        The HTML for use as a preview in the web application, along with 
        the web address of the BARD report.
    """
    note_session_activity(request)

    status = { 'success': False }

    if not settings.REPORTS_ENABLED:
        status['message'] = 'Reports functionality is turned off.'
        return HttpResponse(json.dumps(status),mimetype='application/json')
              
    # Get the variables from the request
    if request.method != 'POST':
        status['message'] = 'Information for report wasn\'t sent via POST'
        return HttpResponse(json.dumps(status),mimetype='application/json')

    stamp = request.POST.get('stamp', generate_report_hash(request.POST))

    rptstatus = PlanReport.checkreport(planid, stamp)
    if rptstatus == 'ready':
        print 'Report is ready.'
        status = {
            'success': True,
            'url': PlanReport.getreport(planid, stamp),
            'retry': 0,
            'message': 'Plan report is ready.',
            'stamp': stamp
        }
    elif rptstatus == 'busy':
        print 'Report is busy.'
        status = {
            'success': True,
            'url': reverse(getreport, args=[planid]),
            'retry': 10,
            'message': 'Report is building.',
            'stamp': stamp
        }
    elif rptstatus == 'free':
        print 'Starting new report.'
        status = {
            'success': True,
            'url': reverse(getreport, args=[planid]),
            'retry': 10,
            'message': 'Report generation started.',
            'stamp': stamp
        }

        req = {
            'popVar': request.POST.get('popVar', ''),
            'popVarExtra': request.POST.get('popVarExtra', ''),
            'ratioVars[]': request.POST.getlist('ratioVars[]'),
            'splitVars': request.POST.get('splitVars', ''),
            'blockLabelVar': request.POST.get('blockLabelVar', 'CTID'),
            'repComp': request.POST.get('repCompactness', ''),
            'repCompExtra': request.POST.get('repCompactnessExtra', ''),
            'repSpatial': request.POST.get('repSpatial', ''),
            'repSpatialExtra': request.POST.get('repSpatialExtra', '')
        }

        PlanReport.markpending(planid, stamp)
        PlanReport.createreport.delay(planid, stamp, req)
    else:
        print 'Check report status: "%s"' % rptstatus
        status['message'] = 'Unrecognized status when checking report status.'

    return HttpResponse(json.dumps(status),mimetype='application/json')

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

    status = { 'success': False }
    if len(request.REQUEST.items()) >= 3:
        plan = Plan.objects.get(pk=planid, owner=request.user)

        if 'geolevel' in request.REQUEST:
            geolevel = request.REQUEST['geolevel']
        else:
            geolevel = None
        if 'geounits' in request.REQUEST:
            geounit_ids = string.split(request.REQUEST['geounits'], '|')
        else:
            geounit_ids = None

        if 'district_id' in request.REQUEST:
            district_id = int(request.REQUEST['district_id'])
        else:
            district_id = None

        if 'version' in request.REQUEST:
            version = request.REQUEST['version']
        else:
            version = plan.version

        if geolevel and geounit_ids and district_id:
            try: 
                # add the geounits selected to this district -- this will
                # create a new district w/1 version higher
                fixed = plan.add_geounits(district_id, geounit_ids, geolevel, version)

                status['success'] = True
                status['message'] = 'Created 1 new district'
                plan = Plan.objects.get(pk=planid, owner=request.user)
                status['edited'] = getutc(plan.edited).isoformat()
                status['district_id'] = district_id
                status['version'] = plan.version
            except ValidationError:
                status['message'] = 'Reached Max districts already'
            except:
                print traceback.format_exc()
                status['message'] = 'Couldn\'t save new district.'
        else:
            status['message'] = 'Must specify name, geolevel, and geounit ids for new district.'
    return HttpResponse(json.dumps(status),mimetype='application/json')

@login_required
@unique_session_or_json_redirect
@transaction.commit_manually
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

    status = { 'success': False }

    # Make sure we can edit the given plan
    try:
        plan = Plan.objects.get(pk=planid)
    except:
        status['message'] = 'No plan with the given id'
        return HttpResponse(json.dumps(status),mimetype='application/json')

    if not can_edit(request.user, plan):
        status['message'] = 'User can\'t edit the given plan'
        return HttpResponse(json.dumps(status),mimetype='application/json')
    
    # Get the districts we want to merge
    district_list = request.POST.getlist('districts[]')
    if len(district_list) == 0:
        status['message'] = 'No districts selected to add to the given plan'
        return HttpResponse(json.dumps(status),mimetype='application/json')
    else:
        districts = District.objects.filter(id__in=district_list)
        version = int(request.POST.get('version', None))
        status['message'] = 'Going to merge %d districts' % len(districts)
    
    # Check to see if we have enough room to add these districts without
    # going over MAX_DISTRICTS for the legislative_body
    allowed_districts = plan.get_available_districts(version=version)
    
    if len(districts) > allowed_districts:
        status['message'] = 'Tried to merge too many districts; %d slots left' % allowed_districts

    # Everything checks out, let's paste those districts
    try:
        results = plan.paste_districts(districts, version=version)
        transaction.commit()
        status['success'] = True
        status['message'] = 'Merged %d districts' % len(results)
        status['version'] = plan.version
    except Exception as ex:
        transaction.rollback()
        status['message'] = str(ex)
        status['exception'] = traceback.format_exc()

    return HttpResponse(json.dumps(status),mimetype='application/json')

@login_required
@unique_session_or_json_redirect
@transaction.commit_manually
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

    status = { 'success': False }

    # Make sure we can edit the given plan
    try:
        plan = Plan.objects.get(pk=planid)
    except:
        status['message'] = 'No plan with the given id'
        return HttpResponse(json.dumps(status),mimetype='application/json')

    if not can_edit(request.user, plan):
        status['message'] = 'User can\'t edit the given plan'
        return HttpResponse(json.dumps(status),mimetype='application/json')

    # Make sure this district allows multi-member assignment
    leg_bod = plan.legislative_body
    if (not leg_bod.multi_members_allowed):
        status['message'] = 'Multi-members not allowed for this legislative body'
        return HttpResponse(json.dumps(status),mimetype='application/json')
    
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
            district = District.objects.filter(plan=plan,district_id=id,version__lte=version).order_by('version').reverse()[0]

            if district.num_members != count:
                if (changed == 0):
                    # If there is at least one change, update the plan
                    if version != plan.version:
                        plan.purge(after=version)

                    plan.version = plan.version + 1
                    plan.save()

                plan.update_num_members(district, count)
                changed += 1

        transaction.commit()
        status['success'] = True
        status['version'] = plan.version
        status['modified'] = changed
        status['message'] = 'Modified members for %d districts' % changed
    except Exception as ex:
        transaction.rollback()
        status['message'] = str(ex)
        status['exception'] = traceback.format_exc()

    return HttpResponse(json.dumps(status),mimetype='application/json')

@login_required
@unique_session_or_json_redirect
def combine_districts(request, planid):
    """
    Take the contents of one district and add them to another districts
    """
    
    status = { 'success': False }

    # Make sure we can edit the given plan
    try:
        plan = Plan.objects.get(pk=planid)
    except:
        status['message'] = 'No plan with the given id'
        return HttpResponse(json.dumps(status),mimetype='application/json')

    if not can_edit(request.user, plan):
        status['message'] = 'User can\'t edit the given plan'
        return HttpResponse(json.dumps(status),mimetype='application/json')
    
    # Get the districts we want to merge
    version = int(request.POST.get('version', plan.version))
    from_id = int(request.POST.get('from_district_id', -1))
    to_id = int(request.POST.get('to_district_id', None))

    try:
        all_districts = plan.get_districts_at_version(version, include_geom=True)
        
        from_districts = filter(lambda d: True if d.district_id == from_id else False, all_districts)
        to_district = filter(lambda d: True if d.district_id == to_id else False, all_districts)[0]

        locked = to_district.is_locked
        for district in from_districts:
            if district.is_locked:
                locked = True

        if locked:
            status['message'] = 'Can\'t combine locked districts'
            return HttpResponse(json.dumps(status),mimetype='application/json')

        result = plan.combine_districts(to_district, from_districts, version=version)

        if result[0] == True:
            status['success'] = True
            status['message'] = 'Successfully combined districts'
            status['version'] = result[1]
    except:
        status['message'] = 'Could not combine districts'
        status['exception'] = traceback.format_exc()
    return HttpResponse(json.dumps(status),mimetype='application/json')


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

    status = { 'success': False }

    if len(request.REQUEST.items()) >= 2: 
        geolevel = request.REQUEST["geolevel"]
        geounit_ids = string.split(request.REQUEST["geounits"], "|")
        plan = Plan.objects.get(pk=planid,owner=request.user)

        # get the version from the request or the plan
        if 'version' in request.REQUEST:
            version = request.REQUEST['version']
        else:
            version = plan.version

        try:
            fixed = plan.add_geounits(districtid, geounit_ids, geolevel, version)
            status['success'] = True;
            status['message'] = 'Updated %d districts' % fixed
            status['updated'] = fixed
            plan = Plan.objects.get(pk=planid,owner=request.user)
            status['edited'] = getutc(plan.edited).isoformat()
            status['version'] = plan.version
        except: 
            status['exception'] = traceback.format_exc()
            status['message'] = 'Could not add units to district.'

    else:
        status['message'] = 'Geounits weren\'t found in a district.'

    return HttpResponse(json.dumps(status),mimetype='application/json')

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

    status = {'success':False}

    if request.method != 'POST':
        return HttpResponseForbidden()
    
    lock = request.POST.get('lock').lower() == 'true'
    version = request.POST.get('version')
    if lock == None:
        status['message'] = 'Must include lock parameter.'
    elif version == None:
        status['message'] = 'Must include version parameter.'

    try:
        plan = Plan.objects.get(pk=planid)
        district = District.objects.filter(plan=plan,district_id=district_id,version__lte=version).order_by('version').reverse()[0]
    except ObjectDoesNotExist:
        status['message'] = 'Plan or district does not exist.'
        return HttpResponse(json.dumps(status), mimetype='application/json')

    if plan.owner != request.user:
        return HttpResponseForbidden()
    
    district.is_locked = lock
    district.save()
    status['success'] = True
    status['message'] = 'District successfully %s' % ('locked' if lock else 'unlocked')
  
    return HttpResponse(json.dumps(status), mimetype='application/json')
        
            
@cache_control(private=True)
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

    status = {'success':False}

    plan = Plan.objects.filter(id=planid)
    if plan.count() == 1:
        plan = plan[0]

        if 'version' in request.REQUEST:
            version = int(request.REQUEST['version'])
        else:
            version = plan.version

        districts = plan.get_districts_at_version(version,include_geom=False)

        status['districts'] = []

        status['available'] = plan.get_available_districts(version=version)

        # Find the maximum version in the returned districts
        max_version = max([d.version for d in districts])

        # Only allow undo if the max version being returned isn't
        # equal to the minimum stored version
        can_undo = max_version > plan.min_version

        for district in districts:
            if district.has_geom or district.name == 'Unassigned':
                status['districts'].append({
                    'id':district.district_id,
                    'name':district.name,
                    'version':district.version
                })
        status['canUndo'] = can_undo
        status['success'] = True

    else:
        status['message'] = 'No plan exists with that ID.'

    return HttpResponse(json.dumps(status), mimetype='application/json')


@cache_control(private=True)
def simple_district_versioned(request,planid):
    """
    Emulate a WFS service for versioned districts.

    This function retrieves one version of the districts in a plan, with
    the value of the subject attached to the feature. This function is
    necessary because a traditional view could not be used to get the
    districts in a versioned fashion.

    This method accepts 'version__eq' and 'subjects__eq' URL parameters.

    Parameters:
        request -- An HttpRequest, with the current user.
        planid -- The plan ID from which to get the districts.

    Returns:
        A GeoJSON HttpResponse, describing the districts in the plan.
    """
    note_session_activity(request)

    status = {'type':'FeatureCollection'}

    plan = Plan.objects.filter(id=planid)
    if plan.count() == 1:
        plan = plan[0]
        if 'version__eq' in request.REQUEST:
            version = request.REQUEST['version__eq']
        else:
            version = plan.version

        subject_id = None
        if 'subject__eq' in request.REQUEST:
            subject_id = request.REQUEST['subject__eq']
        elif plan.legislative_body.get_default_subject():
            subject_id = plan.legislative_body.get_default_subject().id

        geolevel = plan.legislative_body.get_geolevels()[0].id
        if 'level__eq' in request.REQUEST:
            geolevel = int(request.REQUEST['level__eq'])

        if subject_id:
            bbox = None
            if 'bbox' in request.REQUEST:
                bbox = request.REQUEST['bbox']
                # convert the request string into a tuple full of floats
                bbox = tuple( map( lambda x: float(x), bbox.split(',')))
            else:
                bbox = plan.district_set.all().extent(field_name='simple')

            status['features'] = plan.get_wfs_districts(version, subject_id, bbox, geolevel)
        else:
            status['features'] = []
            status['message'] = 'Subject for districts is required.'
    else:
        status['features'] = []
        status['message'] = 'Query failed.'

    return HttpResponse(json.dumps(status),mimetype='application/json')


@cache_control(private=True)
def get_unlocked_simple_geometries(request,planid):
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

    status = {'type':'FeatureCollection'}

    plan = Plan.objects.filter(id=planid)
    if plan.count() == 1:
        plan = plan[0]
        version = request.POST.get('version__eq', plan.version)
        geolevel = request.POST.get('level__eq', plan.legislative_body.get_geolevels()[0].id)
        geom = request.POST.get('geom__eq', None)
        if geom is not None:
            try:
                wkt = request.POST.get('geom__eq', None)
                geom = GEOSGeometry(wkt)
            # If we can't get a poly, try a linestring
            except GEOSException:
                wkt = request.REQUEST['geom__eq'].replace('POLYGON', 'LINESTRING')
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
            districts = [d.id for d in plan.get_districts_at_version(version, include_geom=True) if d.is_locked]
            locked = District.objects.filter(id__in=districts).collect()

            # Create a simplified locked boundary for fast, but not completely accurate lookups
            # Note: the preserve topology parameter of simplify is needed here
            locked_buffered = locked.simplify(100, True).buffer(100) if locked else None

            # Filter first by geolevel, then selection
            filtered = Geounit.objects.filter(geolevel=geolevel).filter(selection)
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
                        'geolevel_id': feature.geolevel.id,
                        'id': feature.id
                    }
                })
                    
            status['features'] = features
            return HttpResponse(json.dumps(status),mimetype='application/json')
            
        else:
            status['features'] = []
            status['message'] = 'Geometry is required.'
            
    else:
        status['features'] = []
        status['message'] = 'Invalid plan.'

    return HttpResponse(json.dumps(status),mimetype='application/json')


@unique_session_or_json_redirect
def getdemographics(request, planid):
    """
    Get the demographics of a plan.

    This function retrieves the calculated values for the demographic 
    statistics of a plan.

    Parameters:
        request -- An HttpRequest, with the current user
        planid -- The plan ID

    Returns:
        An HTML fragment that contains the demographic information.
    """
    note_session_activity(request)

    status = { 'success':False }
    try:
        plan = Plan.objects.get(pk=planid)
    except:
        status['message'] = "Couldn't get demographic info from the server. Please try again later."
        return HttpResponse( json.dumps(status), mimetype='application/json', status=500 )

    # We only have room for 3 subjects - get the first three by sort_key (default sort in Meta)
    subjects = Subject.objects.all()[:3]
    headers = list(subjects.values_list('short_display', flat=True))

    if 'version' in request.REQUEST:
        version = int(request.REQUEST['version'])
    else:
        version = plan.version

    try:
        districts = plan.get_districts_at_version(version, include_geom=False)
    except:
        status['message'] = "Couldn't get districts at the specified version."
        return HttpResponse( json.dumps(status), mimetype='application/json')

    try:
        district_values = []
        for district in districts:
            dist_name = district.name
            if dist_name == "Unassigned":
                dist_name = '&#216;' 
            else:
                if not district.has_geom:
                    continue;

            prefix = plan.legislative_body.member
            index = prefix.find('%')
            if index >= 0:
                prefix = prefix[0:index]
            else:
                index = 0

            if dist_name.startswith(prefix):
                dist_name = district.name[index:]

            stats = { 'name': dist_name, 'district_id': district.district_id, 'characteristics': [] }

            for subject in subjects:
                subject_name = subject.short_display
                characteristics = district.computedcharacteristic_set.filter(subject = subject) 
                characteristic = { 'name': subject_name }
                if characteristics.count() == 0:
                    characteristic['value'] = "n/a"
                else:
                    characteristic['value'] = "%.0f" % characteristics[0].number       
                    if subject.percentage_denominator:
                        val = characteristics[0].percentage
                        if val:
                            try:
                                characteristic['value'] = "%.2f%%" % (characteristics[0].percentage * 100)
                            except:
                                characteristic['value'] = "n/a"
                
                stats['characteristics'].append(characteristic)            

            district_values.append(stats)
        return render_to_response('demographics.html', {
            'plan': plan,
            'extra_demographics_template' : ('extra_demographics_%s.html' % plan.legislative_body.name.lower()),
            'district_values': district_values,
            'aggregate': getcompliance(plan, version),
            'headers': headers
        })
    except:
        status['exception'] = traceback.format_exc()
        status['message'] = "Couldn't get district demographics."
        return HttpResponse( json.dumps(status), mimetype='application/json', status=500 )

@unique_session_or_json_redirect
def get_demographics(request, planid):
    note_session_activity(request)

    status = { 'success': False }
    try:
        plan = Plan.objects.get(pk=planid)
    except:
        status['message'] = "Couldn't get geography info from the server. No plan with the given id."
        return HttpResponse( json.dumps(status), mimetype='application/json', status=500)

    if 'version' in request.REQUEST:
        version = int(request.REQUEST['version'])
    else:
        version = plan.version

    districts = plan.get_districts_at_version(version,include_geom=True)
    display = ScoreDisplay.objects.get(title='Demographics')
    
    if 'displayId' in request.REQUEST:
        try:
            display = ScoreDisplay.objects.get(pk=request.POST['displayId'])
        except:
            status['message'] = "Unable to get Personalized ScoreDisplay"
            status['exception'] = traceback.format_exc()

    else:
        sys.stderr.write('No displayId in request: %s\n' % request.POST)
        
    try :
        html = display.render(plan, request)
        return HttpResponse(html, mimetype='text/html')
    except:
        status['message'] = "Couldn't render display tab."
        status['exception'] = traceback.format_exc()
        return HttpResponse( json.dumps(status), mimetype='application/json', status=500)

@unique_session_or_json_redirect
def get_basic_information(request, planid):
    note_session_activity(request)

    status = { 'success': False }
    try:
        plan = Plan.objects.get(pk=planid)
    except:
        status['message'] = "Couldn't get geography info from the server. No plan with the given id."
        return HttpResponse( json.dumps(status), mimetype='application/json', status=500)

    if 'version' in request.REQUEST:
        version = int(request.REQUEST['version'])
    else:
        version = plan.version

    districts = plan.get_districts_at_version(version,include_geom=True)
    display = ScoreDisplay.objects.get(title='Basic Information')

    try :
        html = display.render(plan, request)
        return HttpResponse(html, mimetype='text/html')
    except:
        status['message'] = "Couldn't render display tab."
        status['exception'] = traceback.format_exc()
        return HttpResponse( json.dumps(status), mimetype='application/json', status=500)

@unique_session_or_json_redirect
def getgeography(request, planid):
    """
    Get the geography of a plan.

    This function retrieves the calculated values for the geographic 
    statistics of a plan.

    Parameters:
        request -- An HttpRequest, with the current user
        planid -- The plan ID

    Returns:
        An HTML fragment that contains the geographic information.
    """
    note_session_activity(request)

    status = { 'success': False }
    try:
        plan = Plan.objects.get(pk=planid)
    except:
        status['message'] = "Couldn't get geography info from the server. No plan with the given id."
        return HttpResponse( json.dumps(status), mimetype='application/json', status=500)

    try:
        if 'demo' in request.REQUEST: 
            demo = request.REQUEST['demo']
            subject = Subject.objects.get(pk=demo)
        else:
            subject = plan.legislative_body.get_default_subject()
    except:
        status['message'] = "Couldn't get geography info from the server. No Subject exists with the given id and a default subjct is not listed"
        return HttpResponse ( json.dumps(status), mimetype='application/json', status=500)

    if 'version' in request.REQUEST:
        version = int(request.REQUEST['version'])
    else:
        version = plan.version

    try:
        districts = plan.get_districts_at_version(version, include_geom=False)
    except:
        status['message'] = "Couldn't get districts at the specified version."
        return HttpResponse( json.dumps(status), mimetype='application/json', status=500)


    try:
        district_values = []
        for district in districts:
            dist_name = district.name
            if district.district_id == 0:
                dist_name = '&#216;'
            else:
                if not district.has_geom:
                    continue;

            prefix = plan.legislative_body.member
            index = prefix.find('%')
            if index >= 0:
                prefix = prefix[0:index]
            else:
                index = 0

            if dist_name.startswith(prefix):
                dist_name = district.name[index:]

            stats = { 'name': dist_name, 'district_id': district.district_id }

            characteristics = district.computedcharacteristic_set.filter(subject = subject)

            compactness_calculator = Schwartzberg()
            compactness_calculator.compute(district=district)
            compactness_formatted = compactness_calculator.html()

            contiguity_calculator = Contiguity()
            contiguity_calculator.compute(district=district)
            
            if characteristics.count() == 0:
                stats['demo'] = 'n/a'        
                stats['contiguity'] = contiguity_calculator.result is 1
                stats['compactness'] = compactness_formatted
                stats['css_class'] = 'under'

            for characteristic in characteristics:
                stats['demo'] = "%.0f" % characteristic.number        
                stats['contiguity'] = contiguity_calculator.result is 1
                stats['compactness'] = compactness_formatted

                try: 
                    target = plan.targets().get(subject = subject)
                    # The "in there" range
                    range1 = target.value * target.range1
                    # The "out of there" range
                    range2 = target.value * target.range2
                    number = int(characteristic.number)
                    if number < (target.value - range2):
                        css_class = 'farunder'
                    elif number < (target.value - range1):
                        css_class = 'under'
                    elif number <= (target.value + range1):
                        css_class = 'target'
                    elif number <= (target.value + range2):
                        css_class = 'over'
                    elif number > (target.value + range2):
                        css_class = 'farover'
                # No target found - probably not displayed
                except:
                    css_class = 'target'
                
                stats['css_class'] = css_class 

            if district.district_id == 0:
                # Unassigned is never over nor under
                stats['css_class'] = 'target'

            district_values.append(stats)

        return render_to_response('geography.html', {
            'plan': plan,
            'extra_demographics_template' : ('extra_demographics_%s.html' % plan.legislative_body.name.lower()),
            'district_values': district_values,
            'aggregate': getcompliance(plan, version),
            'name': subject.short_display
        })
    except:
        status['exception'] = traceback.format_exc()
        status['message'] = "Couldn't get district geography."
        return HttpResponse( json.dumps(status), mimetype='application/json', status=500)


def getcompliance(plan, version):
    """
    Get compliance information about a set of districts. Compliance
    includes contiguity, population target data, and minority districts.
    
    Parameters:
        districts -- A list of districts
        
    Returns:
        A set of contiguity and data values.
    """
    compliance = []

    # Check each district for contiguity
    contiguity = { 'name': 'Noncontiguous', 'value': 0 }
    noncontiguous = 0
    # Remember to get only the districts at a specific version
    districts = plan.get_districts_at_version(version, include_geom=True)
    contiguity_calculator = Contiguity()
    for district in districts:
        if district.geom is None:
            continue
        contiguity_calculator.compute(district=district)
        if contiguity_calculator.result == 0 and district.name != 'Unassigned':
            noncontiguous += 1
    if noncontiguous > 0:
        if noncontiguous == 1:
            contiguity['value'] = '%d district' % noncontiguous
        else:
            contiguity['value'] = '%d districts' % noncontiguous
    compliance.append(contiguity);

    #Population targets
    for target in plan.targets():
        data = { 'name': 'Target Pop.', 'target': target.value, 'value': 'All meet target' } 
        noncompliant = 0
        for district in districts:
            try:
                characteristic = district.computedcharacteristic_set.get(subject__exact = target.subject) 
                allowance = target.value * target.range1
                number = int(characteristic.number)
                if (number < (target.value - allowance)) or (number > (target.value + allowance)):
                    noncompliant += 1
            except:
                #print "'%s'(%d) is missing computed characteristics for '%s'" % (district.name,district.id,target.subject.name)
                continue
        if noncompliant > 0:
            data['value'] = '%d miss target' % noncompliant
        compliance.append(data)

    #Minority districts
    population = plan.legislative_body.get_default_subject()
    # We only want the subjects that have data attached to districts
    subject_ids = ComputedCharacteristic.objects.values_list('subject', flat=True).distinct()
    minority = Subject.objects.filter(id__in=subject_ids).exclude(name=population.name)
    # minority = Subject.objects.exclude(name=population.name)
    data = {}
    for subject in minority:
        data[subject]  = { 'name': '%s Majority' % subject.short_display, 'value': 0 }

    for district in districts:
        try:
            characteristics = district.computedcharacteristic_set
            population_value = Decimal(characteristics.get(subject = population).number)
            for subject in minority:
                minority_value = Decimal(characteristics.get(subject__exact = subject).number)
                if minority_value / population_value > Decimal('.5'):
                    data[subject]['value'] += 1   
        except:
            #print "'%s'(%d) is missing computed characteristics for '%s'" % (district.name,district.id,population.name)
            continue
            

    for v in data.values():
        compliance.append(v)
        
    return compliance
        

#def getaggregate(districts):
#    """
#    Get the aggregate data for the districts. This will aggregate all
#    available subjects for the given districts.
#    
#    Parameters:
#        districts -- A list of districts
#        
#    Returns:
#        Aggregated data based on the districts given and all available subjects
#    """
#    aggregate = []
#    characteristics = ComputedCharacteristic.objects.filter(district__in=districts) 
#    for target in Target.objects.all():
#        data = { 'name': target.subject.short_display } 
#        try:
#            data['value']= "%.0f" % characteristics.filter(subject = target.subject).aggregate(Sum('number'))['number__sum'] 
#        except:
#            data['value']= "Data unavailable" 
#        aggregate.append(data)
#    return aggregate
#def createShapeFile(planid):
#    """ Given a plan id, this function will create a shape file in the temp folder
#    that contains the district geometry and all available computed characteristics. 
#    This shapefile is suitable for importing to BARD
#    """
#    import os
#    query = 'select %s b.*, b.name as BARDPlanID from ( select district_id, max(version) as version from redistricting_district group by district_id ) as a join redistricting_district as b on a.district_id = b.district_id and a.version = b.version where geom is not null' % getSubjectQueries()
#    shape = settings.TEMP_DIR + str(planid) + '.shp'
#    cmd = 'pgsql2shp -k -u %s -P %s -f %s %s "%s"' % (settings.DATABASE_USER, settings.DATABASE_PASSWORD, shape, settings.DATABASE_NAME, query)
#    try:
#        if os.system(cmd) == 0:
#            return shape
#        else:
#            return None
#    except doh as Exception:
#        print "%s; %s", query, doh.message

#def get_subject_queries():
#    all = Subject.objects.all()
#    query = '';
#    for subject in all:
#        query += 'getsubjectfordistrict(b.id, \'%s\') as %s, ' % (subject.name, subject.name)
#    return query
     
def getutc(t):
    """Given a datetime object, translate to a datetime object for UTC time.
    """
    t_tuple = t.timetuple()
    t_seconds = time.mktime(t_tuple)
    return t.utcfromtimestamp(t_seconds)

@unique_session_or_json_redirect
def getdistrictindexfilestatus(request, planid):
    """
    Given a plan id, return the status of the district index file
    """    
    note_session_activity(request)

    status = { 'success':False }
    plan = Plan.objects.get(pk=planid)
    if not can_copy(request.user, plan):
        return HttpResponseForbidden()
    try:
        file_status = DistrictIndexFile.get_index_file_status(plan)
        status['success'] = True
        status['status'] = file_status 
    except Exception as ex:
        status['message'] = 'Failed to get file status'
        status['exception'] = ex 
    return HttpResponse(json.dumps(status),mimetype='application/json')
        
@unique_session_or_json_redirect
def getdistrictindexfile(request, planid):
    """
    Given a plan id, email the user a zipped copy of 
    the district index file
    """
    note_session_activity(request)

    # Get the districtindexfile and create a response
    plan = Plan.objects.get(pk=planid)
    if not can_copy(request.user, plan):
        return HttpResponseForbidden()
    
    file_status = DistrictIndexFile.get_index_file_status(plan)
    if file_status == 'done':
        archive = DistrictIndexFile.plan2index(plan)
        response = HttpResponse(open(archive.name).read(), content_type='application/zip')
        response['Content-Disposition'] = 'attachment; filename="%s.zip"' % plan.name
    else:
        # Put in a celery task to create this file
        DistrictIndexFile.plan2index.delay(plan)
        response = HttpResponse('File is not yet ready. Please try again in a few minutes')
    return response

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
    displays = ScoreDisplay.objects.filter(title='%s Leaderboard - %s' % (leg_body.name, owner_filter.title()))
    return displays[0] if len(displays) > 0 else None

def getleaderboard(request):
    """
    Get the rendered leaderboard
    """
    note_session_activity(request)

    if not using_unique_session(request.user):
        return HttpResponseForbidden()

    owner_filter = request.REQUEST['owner_filter']
    body_pk = int(request.REQUEST['legislative_body']);
    leg_body = LegislativeBody.objects.get(pk=body_pk)
    
    display = getleaderboarddisplay(leg_body, owner_filter)
    if display is None:
        return HttpResponse('No display configured', mimetype='text/plain')
    
    plans = getvalidplans(leg_body, request.user if owner_filter == 'mine' else None)

    try :
        html = display.render(plans, request)
        return HttpResponse(html, mimetype='text/plain')
    except Exception as ex:
        print traceback.format_exc()
        return HttpResponse('%s' % ex, mimetype='text/plain')

def getleaderboardcsv(request):
    """
    Get the leaderboard scores in csv form
    """
    note_session_activity(request)

    if not using_unique_session(request.user):
        return HttpResponseForbidden()

    owner_filter = request.REQUEST['owner_filter']
    body_pk = int(request.REQUEST['legislative_body']);
    leg_body = LegislativeBody.objects.get(pk=body_pk)
    plans = getvalidplans(leg_body, request.user if owner_filter == 'mine' else None)

    display = getleaderboarddisplay(leg_body, owner_filter)
    plans = getvalidplans(leg_body, request.user if owner_filter == 'mine' else None)

    panels = display.scorepanel_set.all().order_by('position')
    
    try :
        # mark the response as csv, and create the csv writer
        response = HttpResponse(mimetype='text/csv')
        response['Content-Disposition'] = 'attachment; filename=leaderboard_scores.csv'
        writer = csv.writer(response)

        # write headers
        writer.writerow(['Plan ID', 'Plan Name', 'User Name'] + [p.title for p in panels])

        # write row for each plan
        for plan in plans:
            row = [plan.id, plan.name, plan.owner.username]

            # add each score
            for panel in panels:
                function = panel.score_functions.all()[0]
                score = ComputedPlanScore.compute(function, plan)
                row.append(score[0] if isinstance(score, (list, tuple)) else score)
                
            # write the row
            writer.writerow(row)
            
        return response    
    except Exception as ex:
        print traceback.format_exc()
        return HttpResponse('%s' % ex, mimetype='text/plain')


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
        owner_filter = request.POST.get('owner_filter');
        body_pk = int(request.POST.get('legislative_body'));
        search = request.POST.get('_search', False);
        search_string = request.POST.get('searchString', '');
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
        available = Q(is_template=True) | Q(is_shared=True) | Q(owner__exact=request.user)
    else:
        return HttpResponseBadRequest("Unknown filter method.")
        
       
    not_pending = Q(is_pending=False)
    body_filter = Q(legislative_body=body_pk)
    
    # Set up the order_by parameter from sidx and sord in the request
    if sidx.startswith('fields.'):
        sidx = sidx[len('fields.'):]
    if sidx == 'owner':
        sidx = 'owner__username'
    if sord == 'desc':
        sidx = '-' + sidx

    if search:
        search_filter = Q(name__icontains = search_string) | Q(description__icontains = search_string) | Q(owner__username__icontains = search_string)
    else:
        search_filter = None

    all_plans = Plan.objects.filter(available, not_pending, body_filter, search_filter).order_by(sidx)

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
                'edited': str(plan.edited), 
                'is_template': plan.is_template, 
                'is_shared': plan.is_shared, 
                'owner': plan.owner.username, 
                'districtCount': len(plan.get_districts_at_version(plan.version, include_geom=False)) - 1, 
                'can_edit': can_edit(request.user, plan)
                }
            })
    json_response = "{ \"total\":\"%d\", \"page\":\"%d\", \"records\":\"%d\", \"rows\":%s }" % (total_pages, page, len(all_plans), json.dumps(plans_list))
    return HttpResponse(json_response,mimetype='application/json') 

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

        all_districts = plan.get_districts_at_version(plan.version, include_geom=False)
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
        if district.has_geom and district.name != 'Unassigned':
            districts_list.append({
                'pk': district.id, 
                'fields': { 
                    'name': district.name, 
                    'district_id': district.district_id,
                }
            })

    json_response = "{ \"total\":\"%d\", \"page\":\"%d\", \"records\":\"%d\", \"rows\":%s }" % (total_pages, page, len(all_districts), json.dumps(districts_list))
    return HttpResponse(json_response,mimetype='application/json') 

@login_required
@unique_session_or_json_redirect
def editplanattributes(request, planid):
    """
    Edit the attributes of a plan. Attributes of a plan are the name and/or
    description.
    """
    note_session_activity(request)

    status = { 'success': False }
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    new_name = request.POST.get('name', None)
    new_description = request.POST.get('description', None)

    if not planid or not (new_name or new_description):
        return HttpResponseBadRequest('Must declare planId, name and description')

    plan = Plan.objects.filter(pk=planid,owner=request.user)
    if plan.count() == 1:
        plan = plan[0]
        if new_name: 
            plan.name = new_name
        if new_description:
            plan.description = new_description
        try:
            plan.save()

            status['success'] = True
            status['message'] = 'Updated plan attributes'
        except Exception as ex:
            status['message'] = 'Failed to save the changes to your plan'
            status['exception'] = ex
    else:
        status['message'] = "Cannot edit a plan you don\'t own."
    return HttpResponse(json.dumps(status), mimetype='application/json')

def get_health(request):
    try:
        result = 'Health retrieved at %s\n' % datetime.now()
        result += '%d plans in database\n' % Plan.objects.all().count()
        result += '%d sessions in use out of %s\n' % (Session.objects.all().count(), settings.CONCURRENT_SESSIONS)
        space = os.statvfs('/projects/publicmapping')
        result += '%s MB of disk space free\n' % ((space.f_bsize * space.f_bavail) / (1024*1024))
        result += 'Memory Usage:\n%s\n' % commands.getoutput('free -m')
        return HttpResponse(result, mimetype='text/plain')
    except:
        return HttpResponse('ERROR! Couldn\'t get health:\n%s' % traceback.format_exc())


def statistics_sets(request, planid):
    result = { 'success': False }
    # If it's a get request, find the user
    # see what's available
    # return names and IDs in JSON to populate the dropdown/stats editor
    if request.method == 'GET':
        sets = []
        scorefunctions = []
            
        allfunctions = ScoreFunction.objects.all()
        for f in allfunctions:
            scorefunctions.append({ 'id': f.id, 'name': f.name })
        result['functions'] = scorefunctions

        try:
            user_displays = ScoreDisplay.objects.filter(owner=request.user)
            result['displays_count'] = len(user_displays)
            for display in user_displays:
                functions = []
                for panel in display.scorepanel_set.all():
                    if panel.type == 'district':
                        functions = map(lambda x: x.id, panel.score_functions.all())
                        if len(functions) == 0:
                            result['message'] = "No functions for %s" % panel
                sets.append({ 'id': display.id, 'name': display.title, 'functions': functions })
        except:
            result['message'] = 'No user displays for %s: %s' % (request.user, traceback.format_exc())

        bi = ScoreDisplay.objects.get(title='Basic Information', owner__is_superuser=True)
        sets.append({ 'id': bi.id, 'name': bi.title, 'functions': [] })
        demo = ScoreDisplay.objects.get(title='Demographics', owner__is_superuser=True)
        sets.append({ 'id': demo.id, 'name': demo.title, 'functions': [] })

        result['sets'] = sets
        result['success'] = True
    # Delete the requested ScoreDisplay to make some room
    elif request.method == 'POST' and 'delete' in request.POST:
        try:
            display = ScoreDisplay.objects.get(pk=request.REQUEST.get('id', -1))
            result['set'] = {'name':display.title, 'id':display.id}
            display.delete()
            result['success'] = True
        except:
            result['message'] = 'Couldn\'t delete personalized scoredisplay'
            result['exception'] = traceback.format_exc()
        
    # If it's a post, edit or create the ScoreDisplay and return 
    # the id and name as usual
    elif request.method == 'POST':
        if 'functions[]' in request.POST:
            functions = request.POST.getlist('functions[]')
            try:
                display = ScoreDisplay.objects.get(title=request.POST.get('name'), owner=request.user)
                display = display.copy_from(display=display, functions=functions)
            except:
                demo = ScoreDisplay.objects.get(title='Demographics', owner__is_superuser=True)
                display = ScoreDisplay()
                display = display.copy_from(display=demo, title=request.POST.get('name'), owner=request.user, functions=functions)
                result['newRecord'] = True

            result['set'] = {'name':display.title, 'id':display.id, 'functions':functions}
            result['success'] = True

        else:
            result['message'] = "Didn't get functions in POST parameter"

    return HttpResponse(json.dumps(result),mimetype='application/json')
