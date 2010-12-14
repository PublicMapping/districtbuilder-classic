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
    Andrew Jennings, David Zwarg
"""

from django.http import *
from django.core import serializers
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection
from django.db.models import Sum, Min, Max
from django.shortcuts import render_to_response
from django.contrib.auth.decorators import login_required
from django.contrib.gis.gdal import *
from django.contrib.gis.gdal.libgdal import lgdal
from django.contrib import humanize
from django import forms
from django.utils import simplejson as json
from django.views.decorators.cache import cache_control
from rpy2 import robjects
from rpy2.robjects import r, rinterface
from rpy2.rlike import container as rpc
from datetime import datetime, time
from operator import attrgetter
from redistricting.models import *
from redistricting.utils import *
import settings, random, string, math, types, copy, time, threading, traceback, os, sys, tempfile

@login_required
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
    p = Plan.objects.get(pk=planid)
    status = { 'success': False }
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

    plan_copy = Plan(name = newname, owner=request.user, is_shared = shared, legislative_body = p.legislative_body)
    plan_copy.save()

    # Get all the districts in the original plan at the most recent version
    # of the original plan.
    districts = p.get_districts_at_version(p.version)
    for district in districts:
        # Skip Unassigned, we already have that -- created automatically
        # when saving a new plan.
        if district.name == "Unassigned":
            continue

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

def get_user_info(user):
    """
    Get extended user information for the current user.

    Parameters:
        user -- The user attached to the HttpRequest

    Returns:
        A dict with user information, including profile information.
    """
    if user.username == 'anonymous':
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
    try:
        # Get the plan and districts in the plan.
        plan = Plan.objects.get(pk=planid)
        plan.edited = getutc(plan.edited)
        districts = plan.get_districts_at_version(plan.version)
        editable = can_edit(request.user, plan)
        default_demo = plan.legislative_body.get_default_subject()
        max_dists = plan.legislative_body.max_districts
        if not editable and not can_view(request.user, plan):
            plan = {}
    except Exception, ex:
        sys.stderr.write(traceback.format_exc())
        # If said plan doesn't exist, use an empty plan & district list.
        plan = {}
        districts = {}
        editable = False
        default_demo = None
        max_dists = 0
    levels = Geolevel.objects.all()
    demos = Subject.objects.values_list("id","name", "short_display","is_displayed")
    layers = []
    snaplayers = []
    boundaries = []
    rules = []
    targets = Target.objects.all()
    for level in levels:
        snaplayers.append( {'geolevel':level.id,'layer':level.name,'name':level.name.capitalize(),'min_zoom':level.min_zoom} )
        boundaries.append( {'id':'%s_boundaries' % level.name.lower(), 'name':level.name.capitalize()} )
    for demo in demos:
        isdefault = str((not default_demo is None) and (demo[0] == default_demo.id)).lower()
        layers.append( {'id':demo[0],'text':demo[2],'value':demo[1].lower(), 'isdefault':isdefault, 'isdisplayed':str(demo[3]).lower()} )
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
        'bodies': LegislativeBody.objects.all(),
        'plan': plan,
        'districts': districts,
        'mapserver': settings.MAP_SERVER,
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
        'ga_domain': settings.GA_DOMAIN
    }


@login_required
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
    return render_to_response('viewplan.html', commonplan(request, planid)) 
    
@login_required
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
    cfg = commonplan(request, planid)
    if cfg['is_editable'] == False:
        return HttpResponseRedirect('/districtmapping/plan/%s/view/' % planid)
    plan = Plan.objects.get(id=planid)
    cfg['dists_maxed'] = len(cfg['districts']) > plan.legislative_body.max_districts
    return render_to_response('editplan.html', cfg) 

@login_required
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
    status = { 'success': False, 'message': 'Unspecified Error' }
    if request.method == "POST":
        name = request.POST['name']
        body = LegislativeBody.objects.get(id=int(request.POST['legislativeBody']))
        plan = Plan(name = name, owner = request.user, legislative_body = body)
        try:
            plan.save()
            data = serializers.serialize("json", [ plan ])
            return HttpResponse(data)    
        except:
            status = { 'success': False, 'message': 'Couldn\'t save new plan' }
            return HttpResponse(json.dumps(status),mimetype='application/json')
    status['message'] = 'Didn\'t submit name through POST'
    return HttpResponse(json.dumps(status),mimetype='application/json')

@login_required
def uploadfile(request):
    """
    Accept a block equivalency file, and create a plan based on that
    file.

    Parameters:
        request -- An HttpRequest, with a file upload and plan name.

    Returns:
        A plan view, with additional information about the upload status.
    """

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


def load_bard_workspace():
    """
    Load the workspace and setup R.

    This function is called by the thread loading function. The workspace
    setup incurs a significant amount of overhead and processing time to
    load the basemaps into BARD. This method starts up these processes in
    a separate process & thread, in order to keep the web application 
    responsive during R initialization.
    """
    try:
        r.library('rgeos')
        r.library('gpclib')
        r.library('BARD')
        r.library('R2HTML')
        r.gpclibPermit()

        global bardmap
        bardmap = r.readBardMap(settings.BARD_BASESHAPE)

        global bardWorkSpaceLoaded
        bardWorkSpaceLoaded = True

	if settings.DEBUG:
	        r('trace(PMPreport, at=1, tracer=function()print(sys.calls()))')
    except:
        sys.stderr.write('BARD Could not be loaded.  Check your configuration and available memory')
        return

# A flag that indicates that the workspace was loaded
bardWorkSpaceLoaded = False
# An object that holds the bardmap for later analysis
bardmap = {}
# The loading thread for the BARD setup
bardLoadingThread = threading.Thread(target=load_bard_workspace, name='loading_bard') 

def loadbard(request):
    """
    Load BARD and it's workspace.

    BARD is loaded in a separate thread in order to free resources for
    the web processing thread. This method is called by the wsgi application
    setup file, 'reports.wsgi'.

    Parameters:
        request -- An HttpRequest OR True

    Returns:
        A simple text response informing the client what BARD is up to.
    """
    msg = ""

    if type(request) == bool:
        threaded = True
    elif type(request) == HttpRequest:
        threaded = request.META['mod_wsgi.application_group'] == 'bard-reports'
        msg += 'mod_wsg.application_group = "%s"' % request.META['mod_wsgi.application_group']
    else:
        msg += 'Unknown request type.'
        threaded = False

    if bardWorkSpaceLoaded:
        return HttpResponse('Bard is already loaded')
    elif bardLoadingThread.is_alive():
        return HttpResponse( 'Bard is already building')
    elif threaded and not bardWorkSpaceLoaded and settings.REPORTS_ENABLED:
        bardLoadingThread.daemon = True
        bardLoadingThread.start()
        return HttpResponse( 'Building bard workspace now ')
    
    return HttpResponse('Bard will not be loaded - wrong server config or reports off\nThreaded: %s\nMessage: %s' % (threaded, msg), mimetype='text/plain')


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

    status = { 'success': False, 'message': 'Unspecified Error' }
    if not bardWorkSpaceLoaded:
        if not settings.REPORTS_ENABLED:
            status['message'] = 'Reports functionality is turned off.'
        else:
            status['message'] = 'Reports functionality is not ready. Please try again later.'
        return HttpResponse(json.dumps(status),mimetype='application/json')
              
        #  PMP reporrt interface
        #    PMPreport<-function(
        #       bardMap,
        #       blockAssignmentID="BARDPlanID",
        #       popVar=list("Total Population"="POPTOT",tolerance=.01),
        #       popVarExtra=list("Voting Age Population"="VAPTOT","Voting Age
        #Population Black"="VAPHWHT"),
        #       ratioVars=list(
        #               "Majority Minority Districts"=list(
        #                       denominator=list("Total Population"="POPTOT"),
        #                       threshold=.6,
        #                       numerators=list("Black Population"="POPBLK", "Hispanic Population"="POPHISP")
        #                  ),
        #               "Party-Controlled Districts"=list(
        #                       threshold=.55,
        #                       numerators=list("Democratic Votes"="PRES_DEM", "Republican Votes"="PRES_REP")
        #                  )
        #       ),
        #       splitVars = list("County"="COUNTY", "Tract"="TRACT"),
        #       blockLabelVar="CTID",
        #       repCompactness=TRUE,
        #       repCompactnessExtra=FALSE,
        #       repSpatial=TRUE,
        #       repSpatialExtra=FALSE,
        #       useHTML=TRUE,
        #       ...)  

    try:
        plan = Plan.objects.get(pk=planid)
        districts = plan.get_districts_at_version(plan.version)
    except:
        status['message'] = 'Couldn\'t retrieve plan information'
        return HttpResponse(json.dumps(status),mimetype='application/json')
    #Get the variables from the request
    if request.method != 'POST':
        status['message'] = 'Information for report wasn\'t sent via POST'
        return HttpResponse(json.dumps(status),mimetype='application/json')

    def get_named_vector(parameter_string, tag = None):
        """
        Helper method to break up the strings that represents lists of 
        variables.
        
        Parameters:
            parameter_string -- A string of parameters
            
        Returns:
            A StrVector with names, suitable for rpy2 use.
        """
        vec = robjects.StrVector(())
        extras = parameter_string.split('^')
        for extra in extras:
            pair = extra.split('|')
            vec += r('list("%s"="%s")' % (pair[0], pair[1]))
        return vec
    
    # Use the utility query to get the district mapping for geounit ids
    cursor = plan.district_mapping_cursor(geounit_id_field='id')

    # Get the geounit ids we'll be iterating through
    geolevel = plan.legislative_body.get_base_geolevel()
    geounits = Geounit.objects.filter(geolevel=geolevel)
    max_and_min = geounits.aggregate(Min('id'), Max('id'))
    min_id = int(max_and_min['id__min'])
    max_id = int(max_and_min['id__max'])

    # Iterate through the query results to create the district_id list
    # This ordering depends on the geounits in the shapefile matching the 
    # order of the imported geounits. If this ordering is the same, the 
    # geounits' ids don't have to match their fids in the shapefile
    sorted_district_list = list()
    row = cursor.fetchone()
    for i in range(min_id, max_id + 1):
        if row and row[0] == i:
            district_id = row[1]
            row = cursor.fetchone()
        else:
            district_id = 'NA'
        sorted_district_list.append(district_id)
    cursor.close()

    # Now we need an R Vector
    block_ids = robjects.IntVector(sorted_district_list)
    bardplan = r.createAssignedPlan(bardmap, block_ids)

    # assign names to the districts
    names = sorted(districts, key=attrgetter('district_id'))
    sorted_name_list = robjects.StrVector(())
    for district in names:
       if district.name != "Unassigned":
            sorted_name_list += district.name 
    bardplan.do_slot_assign('levels', sorted_name_list)

    # Get the other report variables from the POST request.  We'll only add
    # them to the report if they're in the request
    popVar = request.POST.get('popVar', None)
    if popVar:
        pop_var = get_named_vector(popVar)
        pop_var += r('list("tolerance"=.01)')

    popVarExtra = request.POST.get('popVarExtra', None)
    if popVarExtra:
        pop_var_extra = get_named_vector(popVarExtra)
    else:
        pop_var_extra = r('as.null()')
    
    racialComp = request.POST.get('racialComp', None)
    partyControl = request.POST.get('partyControl', None)
    if racialComp or partyControl:
        ratioVars = robjects.StrVector(())
        if racialComp:
            mmd = robjects.StrVector(())
            mmd += r('list("denominator"=%s)' % get_named_vector(popVar).r_repr())
            mmd += r('list("threshold"=.6)')
            mmd += r('list("numerators"=%s)' % get_named_vector(racialComp).r_repr())
            ratioVars += r('list("Majority Minority Districts"=%s)' % mmd.r_repr())

        if partyControl:
            pc = robjects.StrVector(())
            pc += r('list("denominator"=%s)' % get_named_vector(popVar).r_repr())
            pc += r('list("threshold"=.6)')
            pc += r('list("numerators"=%s)' % get_named_vector(partyControl).r_repr())
            ratioVars += r('list("Party-controlled Districts"=%s)' % pc.r_repr())
        ratio_vars = ratioVars
    else:
        ratio_vars = r('as.null()')

    splitVars = request.POST.get('splitVars', None)
    if splitVars:
        split_vars = get_named_vector(splitVars)
    else:
        split_vars = r('as.null()')
    
    blockLabelVar = request.POST.get('blockLabelVar', 'CTID')

    repCompactness = request.POST.get('repCompactness', None)
    if 'true' == repCompactness:
        rep_compactness = r(True)
    else:
        rep_compactness = r(False)

    repCompactnessExtra = request.POST.get('repCompactnessExtra', None)
    if 'true' == repCompactnessExtra:
        rep_compactness_extra = r(True)
    else:
        rep_compactness_extra = r(False)

    repSpatial = request.POST.get('repSpatial', None)
    if 'true' == repSpatial:
        rep_spatial = r(True)
    else:
        rep_spatial = r(False)

    repSpatialExtra = request.POST.get('repSpatialExtra', None)
    if 'true' == repSpatialExtra:
        rep_spatial_extra = r(True)
    else:
        rep_spatial_extra = r(False)

    try:
        # set up the temp dir and filename
        tempdir = settings.BARD_TEMP
        filename = '%s_%s_%s' % (plan.owner.username, plan.name, datetime.now().strftime('%y%m%d_%H%M'))
        r.copyR2HTMLfiles(tempdir)
        report = r.HTMLInitFile(tempdir, filename=filename, BackGroundColor="#BBBBEE", Title="Plan Analysis")
        title = r['HTML.title']
        r['HTML.title']("Plan Analysis", HR=2, file=report)
        # Now write the report to the temp dir
        r.PMPreport( bardplan, block_ids, file = report, popVar = pop_var, popVarExtra = pop_var_extra, ratioVars = ratio_vars, splitVars = split_vars, repCompactness = rep_compactness, repCompactnessExtra = rep_compactness_extra, repSpatial = rep_spatial, repSpatialExtra = rep_spatial_extra)
        r.HTMLEndFile()

        # BARD has written the report to file - read it and put it in as
        # the preview
        f = open(report[0], 'r')
        status['preview'] = f.read()
        status['file'] = '/reports/%s.html' % filename
        status['message'] = 'Report successful'
        f.close()

        status['success'] = True
    except Exception as ex:
        status['message'] = '<div class="error" title="error">Sorry, there was an error with the report: %s' % ex    
    return HttpResponse(json.dumps(status),mimetype='application/json')

@login_required
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
    status = { 'success': False, 'message': 'Unspecified error.' }
    plan = Plan.objects.get(pk=planid)

    if len(request.REQUEST.items()) >= 3:
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
                # create a temporary district
                district = District(name='District %d' % (district_id - 1), plan=plan, district_id=district_id, version=plan.version)
                district.save()

                # save the district_id generated during save
                district_id = district.district_id

                # add the geounits selected to this district -- this will
                # create a new district w/1 version higher
                fixed = plan.add_geounits(district.district_id, geounit_ids, geolevel, version)

                status['success'] = True
                status['message'] = 'Created %d new district' % fixed
                plan = Plan.objects.get(pk=planid)
                status['edited'] = getutc(plan.edited).isoformat()
                status['district_id'] = district_id
                status['district_name'] = district.name
                status['version'] = plan.version
            except ValidationError:
                status['message'] = 'Reached Max districts already'
            except:
                status['message'] = 'Couldn\'t save new district.'
        else:
            status['message'] = 'Must specify name, geolevel, and geounit ids for new district.'
    return HttpResponse(json.dumps(status),mimetype='application/json')

@login_required
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
    status = { 'success': False, 'message': 'Unspecified error.' }
    if len(request.REQUEST.items()) >= 2: 
        geolevel = request.REQUEST["geolevel"]
        geounit_ids = string.split(request.REQUEST["geounits"], "|")
        plan = Plan.objects.get(pk=planid)

        # get the version from the request or the plan
        if 'version' in request.REQUEST:
            version = request.REQUEST['version']
        else:
            version = plan.version

        try:
            fixed = plan.add_geounits(districtid, geounit_ids, geolevel, version)
            status['success'] = True;
            status['message'] = 'Updated %d districts' % fixed
            plan = Plan.objects.get(pk=planid)
            status['edited'] = getutc(plan.edited).isoformat()
            status['version'] = plan.version
        except: 
            status['exception'] = traceback.format_exc()
            status['message'] = 'Could not add units to district.'

    else:
        status['message'] = 'Geounits weren\'t found in a district.'

    return HttpResponse(json.dumps(status),mimetype='application/json')


@login_required
@cache_control(no_cache=True)
def chooseplan(request):
    """
    Generate an HTML fragment that lists the plans available to the
    current user.

    Parameters:
        request -- An HttpRequest, with the current user.
        
    Returns:
        A rendered HTML fragment that contains available plans.
    """
    templates = Plan.objects.filter(is_template=True, owner__is_staff = True, is_pending=False)
    shared = Plan.objects.filter(is_shared=True, is_pending=False)
    mine = Plan.objects.filter(is_template=False, is_shared=False, owner=request.user, is_pending=False)
    bodies = LegislativeBody.objects.all()

    upload = False
    upload_status = False
    if 'upload' in request.POST:
        upload = True
        upload_status = request.POST['upload_status'] == 'true';

    return render_to_response('chooseplan.html', {
        'templates': templates,
        'shared': shared,
        'mine': mine,
        'user': request.user,
        'is_registered': request.user.username != 'anonymous' and request.user.username != '',
        'upload': upload,
        'upload_status': upload_status,
        'bodies': bodies
    })

@login_required
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
    status = {'success':False,'type':'FeatureCollection'}
    try:
        plan = Plan.objects.get(id=planid)
        if 'version__eq' in request.REQUEST:
            version = request.REQUEST['version__eq']
        else:
            version = plan.version

        subject_id = None
        if 'subject__eq' in request.REQUEST:
            subject_id = request.REQUEST['subject__eq']
        elif plan.legislative_body.get_default_subject():
            subject_id = plan.legislative_body.get_default_subject().id

        if subject_id:
            status['features'] = plan.get_wfs_districts(version, subject_id)
            status['success'] = True
        else:
            status['features'] = []
            status['message'] = 'Subject for districts is required.'
    except:
        status['features'] = []
        status['message'] = 'Query failed.'

    return HttpResponse(json.dumps(status),mimetype='application/json')
    

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
    status = { 'success':False }
    try:
        plan = Plan.objects.get(pk = planid)
    except:
        status['message'] = "Couldn't get demographic info from the server. Please try again later."
        return HttpResponse( json.dumps(status), mimetype='application/json', status=500 )

    subjects = Subject.objects.all()
    headers = list(Subject.objects.all().values_list('short_display', flat=True))

    if 'version' in request.REQUEST:
        version = int(request.REQUEST['version'])
    else:
        version = plan.version

    try:
        districts = plan.get_districts_at_version(version)
    except:
        status['message'] = "Couldn't get districts at the specified version."
        return HttpResponse( json.dumps(status), mimetype='applicatio/json')

    try:
        district_values = []
        for district in districts:
            dist_name = district.name
            if dist_name == "Unassigned":
                dist_name = '&#216;' 
            else:
                try:
                    if not district.geom:
                        # skip any districts with null geom that are not the 
                        # special 'Unassigned' district
                        continue
                except:
                    # Sometimes a GEOSException happens here. Can't explain why.
                    # Sometimes it's a ParseException. Dunno about that either.
                    continue

            if dist_name.startswith('District '):
                dist_name = district.name.rsplit(' ', 1)[1]

            stats = { 'name': dist_name, 'district_id': district.district_id, 'characteristics': [] }
            for subject in subjects:
                subject_name = subject.short_display
                characteristics = district.computedcharacteristic_set.filter(subject = subject) 
                characteristic = { 'name': subject_name }
                if characteristics.count() == 0:
                    characteristic['value'] = "n/a"
                else:
                    characteristic['value'] = "%.0f" % characteristics[0].number       
                stats['characteristics'].append(characteristic)            

            district_values.append(stats)
        return render_to_response('demographics.html', {
            'plan': plan,
            'district_values': district_values,
            'aggregate': getcompliance(districts,plan.legislative_body),
            'headers': headers
        })
    except:
        status['exception'] = traceback.format_exc()
        status['message'] = "Couldn't get district demographics."
        return HttpResponse( json.dumps(status), mimetype='application/json', status=500 )


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
    status = { 'success': False }
    try:
        plan = Plan.objects.get(pk = planid)
    except:
        status['message'] = "Couldn't get geography info from the server. No plan with the given id."
        return HttpResponse( json.dumps(status), mimetype='application/json', status=500)

    if 'demo' in request.REQUEST: 
        demo = request.REQUEST['demo']
    else:
        status['message'] = "Couldn't get geography info from the server. Please use the 'demo' parameter with a Subject id."
        return HttpResponse( json.dumps(status), mimetype='application/json', status=500)

    if 'version' in request.REQUEST:
        version = int(request.REQUEST['version'])
    else:
        version = plan.version

    try:
        districts = plan.get_districts_at_version(version)
    except:
        status['message'] = "Couldn't get districts at the specified version."
        return HttpResponse( json.dumps(status), mimetype='applicatio/json', status=500)

    try:
        subject = Subject.objects.get(pk=demo)
    except:
        status['message'] = "Couldn't get geography info from the server. No Subject exists with the given id."
        return HttpResponse ( json.dumps(status), mimetype='application/json', status=500)

    try:
        district_values = []
        for district in districts:
            dist_name = district.name
            if dist_name == "Unassigned":
                dist_name = '&#216;'
            else:
                try:
                    if not district.geom:
                        # skip any districts with null geom that are not the 
                        # special 'Unassigned' district
                        continue
                except:
                    # Sometimes a GEOSException happens here. Can't explain why.
                    # Sometimes it's a ParseException. Dunno about that either.
                    continue

            if dist_name.startswith('District '):
                dist_name = district.name.rsplit(' ', 1)[1]

            stats = { 'name': dist_name, 'district_id': district.district_id }
            characteristics = district.computedcharacteristic_set.filter(subject = subject)

            if characteristics.count() == 0:
                stats['demo'] = 'n/a'        
                stats['contiguity'] = district.is_contiguous()
                stats['compactness'] = district.get_schwartzberg()
                stats['css_class'] = 'under'

            for characteristic in characteristics:
                stats['demo'] = "%.0f" % characteristic.number        
                stats['contiguity'] = district.is_contiguous()
                stats['compactness'] = district.get_schwartzberg()

                try: 
                    target = Target.objects.get(subject = subject)
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

            district_values.append(stats)

        return render_to_response('geography.html', {
            'plan': plan,
            'district_values': district_values,
            'aggregate': getcompliance(districts,plan.legislative_body),
            'name': subject.short_display
        })
    except:
        status['exception'] = traceback.format_exc()
        status['message'] = "Couldn't get district geography."
        sys.stderr.write(traceback.format_exc())
        return HttpResponse( json.dumps(status), mimetype='application/json', status=500)


def getcompliance(districts,legislative_body):
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
    for district in districts:
        if not district.is_contiguous() and district.name != 'Unassigned':
            noncontiguous += 1
    if noncontiguous > 0:
        if noncontiguous == 1:
            contiguity['value'] = '%d district' % noncontiguous
        else:
            contiguity['value'] = '%d districts' % noncontiguous
    compliance.append(contiguity);

    #Population targets
    displayed = Subject.objects.filter(is_displayed__exact = True)
    targets = Target.objects.filter(subject__in = displayed)
    for target in targets:
        data = { 'name': 'Target Pop. %s' % target.value, 'value': 'All meet target' } 
        noncompliant = 0
        for district in districts:
            try:
                characteristic = district.computedcharacteristic_set.get(subject__exact = target.subject) 
                allowance = target.value * target.range1
                number = int(characteristic.number)
                if (number < (target.value - allowance)) or (number > (target.value + allowance)):
                    noncompliant += 1
            except:
                # District has no characteristics - unassigned
                continue
        if noncompliant > 0:
            data['value'] = '%d miss target' % noncompliant
        compliance.append(data)

    #Minority districts
    population = legislative_body.get_default_subject()
    minority = Subject.objects.exclude(name=population.name)
    data = {}
    for subject in minority:
        data[subject]  = { 'name': '%s Majority' % subject.short_display, 'value': 0 }

    for district in districts:
        try:
            characteristics = district.computedcharacteristic_set
            population_value = characteristics.get(subject = population).number
            for subject in minority:
                minority_value = characteristics.get(subject__exact = minority).number
                if minority_value / population_value > .5:
                    data[subject]['value'] += 1   
        except:
            # District has no characteristics - unassigned
            continue
            

    for v in data.values():
        compliance.append(v)
        
    return compliance
        

def getaggregate(districts):
    """
    Get the aggregate data for the districts. This will aggregate all
    available subjects for the given districts.
    
    Parameters:
        districts -- A list of districts
        
    Returns:
        Aggregated data based on the districts given and all available subjects
    """
    aggregate = []
    characteristics = ComputedCharacteristic.objects.filter(district__in=districts) 
    for target in Target.objects.all():
        data = { 'name': target.subject.short_display } 
        try:
            data['value']= "%.0f" % characteristics.filter(subject = target.subject).aggregate(Sum('number'))['number__sum'] 
        except:
            data['value']= "Data unavailable" 
        aggregate.append(data)
    return aggregate

def getcompactness(district):
    """
    Get the Schwartzberg measure of compactness. Schwartzberg is the 
    measure of the perimeter of the district to the circumference of the 
    circle whose area is equal to the area of the district.
    
    NOTE: This function is empty.
    
    Parameters:
        district -- A list of districts
        
    Returns:
        Nothing
    """
    pass

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

@login_required
def getdistrictindexfilestatus(request, planid):
    """
    Given a plan id, return the status of the district index file
    """    
    plan = Plan.objects.get(pk=planid)
    if not can_copy(request.user, plan):
        return HttpResponseForbidden()
    status = { 'success':False }
    try:
        file_status = DistrictIndexFile.get_index_file_status(plan)
        status['success'] = True
        status['status'] = file_status 
    except Exception as ex:
        status['message'] = 'Failed to get file status'
        status['exception'] = ex 
    return HttpResponse(json.dumps(status),mimetype='application/json')
        
@login_required
def getdistrictindexfile(request, planid):
    """
    Given a plan id, email the user a zipped copy of 
    the district index file
    """
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

@login_required
def getplans(request):
    """
    Get the plans for the given user and return the data in a format readable
    by the jqgrid
    """
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
        available = Q(owner__exact=request.user)
    else:
        return HttpResponseBadRequest()
        
       
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
        plans_list.append( { 'pk': plan.id, 'fields': { 'name': plan.name, 'description': plan.description, 'edited': str(plan.edited), 'is_template': plan.is_template, 'is_shared': plan.is_shared, 'owner': plan.owner.username, 'districtCount': len(plan.get_districts_at_version(plan.version)) - 1, 'can_edit': can_edit(request.user, plan) }})
    json_response = "{ \"total\":\"%d\", \"page\":\"%d\", \"records\":\"%d\", \"rows\":%s }" % (total_pages, page, len(plans), json.dumps(plans_list))
    return HttpResponse(json_response,mimetype='application/json') 

@login_required
def editplanattributes(request, planid):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    new_name = request.POST.get('name', None)
    new_description = request.POST.get('description', None)

    if not planid or not (new_name or new_description):
        return HttpResponseBadRequest('Must declare planId, name and description')

    status = { 'success': False }
    try:
        plan = Plan.objects.get(pk=planid)
        if new_name: 
            plan.name = new_name
        if new_description:
            plan.description = new_description
        plan.save()
    except Exception as ex:
        status['message'] = 'Failed to save the changes to your plan'
        status['exception'] = ex
    else:
        status['success'] = True
        status['message'] = 'Updated plan attributes'
    return HttpResponse(json.dumps(status), mimetype='application/json')
