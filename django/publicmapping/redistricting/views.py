"""
Define the views used by the redistricting app.

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
    David Zwarg, Andrew Jennings
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
from publicmapping import settings
from publicmapping.redistricting.models import *
from datetime import datetime
import random, string, types, copy, time, threading, traceback

@login_required
def copyplan(request, planid):
    p = Plan.objects.get(pk=planid)
    status = { 'success': False }
    if not can_copy(request.user, p):
        status['message'] = "User %s doesn't have permission to copy this model" % request.user.username
        return HttpResponse(json.dumps(status),mimetype='application/json')

    newname = p.name + " " + str(random.random()) 
    if (request.method == "POST" ):
        newname = request.POST["name"]
        shared = request.POST.get("shared", False)

    plan_copy = Plan.objects.filter(name__exact=newname, owner=request.user)
    if len(plan_copy) > 0:
        status['message'] = "You already have a plan named that. Please pick a unique name."
        return HttpResponse(json.dumps(status),mimetype='application/json')

    plan_copy = Plan(name = newname, owner=request.user, is_shared = shared)
    plan_copy.save()

    districts = p.get_districts_at_version(p.version)
    for district in districts:
        # Skip Unassigned, we already have that
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

    data = serializers.serialize("json", [ plan_copy ])

    return HttpResponse(data, mimetype='application/json')

def commonplan(request, planid):
    """A common method that gets the same data structures for viewing
    and editing. This method is called by the viewplan and editplan 
    views."""
    try:
        plan = Plan.objects.get(pk=planid)
        districts = plan.get_districts_at_version(plan.version)
        editable = can_edit(request.user, plan)
        if not editable and not can_view(request.user, plan):
            plan = {}
    except:
        plan = {}
        districts = {}
        editable = False
    levels = Geolevel.objects.values_list("id", "name")
    demos = Subject.objects.values_list("id","name", "short_display","is_displayed")
    default_demo = getdefaultsubject()
    layers = []
    snaplayers = []
    rules = []
    targets = Target.objects.all()
    for level in levels:
        snaplayers.append( {'geolevel':level[0],'layer':level[1],'name':level[1].capitalize()} )
    for demo in demos:
        layers.append( {'id':demo[0],'text':demo[2],'value':demo[1].lower(), 'isdefault':str(demo[0] == default_demo.id).lower(), 'isdisplayed':str(demo[3]).lower()} )
    for target in targets:
        # The "in there" range
        range1 = target.lower * settings.POPTARGET_RANGE1  
        # The "out of there" range
        range2 = target.lower * settings.POPTARGET_RANGE2
        rules.append( {'subject_id':target.subject_id,'lowest': target.lower - range2,'lower':target.lower - range1,'upper':target.lower + range1,'highest': target.lower + range2} )

    unassigned_id = 0
    if type(plan) != types.DictType:
        unassigned_id = plan.district_set.filter(name='Unassigned').values_list('district_id',flat=True)[0]

    return {
        'plan': plan,
        'districts': districts,
        'mapserver': settings.MAP_SERVER,
        'namespace': settings.MAP_SERVER_NS,
        'ns_href': settings.MAP_SERVER_NSHREF,
        'demographics': layers,
        'snaplayers': snaplayers,
        'rules': rules,
        'unassigned_id': unassigned_id,
        'is_anonymous': request.user.username == 'anonymous',
        'is_editable': editable,
        'max_dists': settings.MAX_DISTRICTS + 1
    }


@login_required
def viewplan(request, planid):
    "View a plan"
    return render_to_response('viewplan.html', commonplan(request, planid)) 
    
@login_required
def editplan(request, planid):
    "Edit a plan. This template enables editing tools and functionality."
    plan = commonplan(request, planid)
    plan['dists_maxed'] = len(plan['districts']) > settings.MAX_DISTRICTS
    return render_to_response('editplan.html', plan)

@login_required
def createplan(request):
    status = { 'success': False, 'message': 'Unspecified Error' }
    if request.method == "POST":
        name = request.POST['name']
        plan = Plan(name = name, owner = request.user)
        try:
            plan.save()
            data = serializers.serialize("json", [ plan ])
            return HttpResponse(data)    
        except:
            status = { 'success': False, 'message': 'Couldn\'t save new plan' }
            return HttpResponse(json.dumps(status),mimetype='application/json')
    status['message'] = 'Didn\'t submit name through POST'
    return HttpResponse(json.dumps(status),mimetype='application/json')

def load_bard_workspace():
    try:
        r.library('BARD')
        r.library('R2HTML')
        r.gpclibPermit()

        global bardmap
        bardmap = r.readBardMap(settings.BARD_BASESHAPE)

        global bardWorkSpaceLoaded
        bardWorkSpaceLoaded = True
    except:
        sys.stderr.write('BARD Could not be loaded.  Check your configuration and available memory')
        return
 
bardWorkSpaceLoaded = False
bardmap = {}
bardLoadingThread = threading.Thread(target=load_bard_workspace, name='loading_bard') 

def loadbard(request):
    if type(request) == bool:
       threaded = True
    elif type(request) == HttpRequest:
       threaded = request.META['mod_wsgi.application_group'] == 'bard-reports'
    else:
        threaded = False

    if bardWorkSpaceLoaded:
        return HttpResponse('Bard is already loaded')
    elif bardLoadingThread.is_alive():
        return HttpResponse( 'Bard is already building')
    elif threaded and not bardWorkSpaceLoaded and settings.REPORTS_ENABLED:
        bardLoadingThread.daemon = True
        bardLoadingThread.start()
        return HttpResponse( 'Building bard workspace now ')
    return HttpResponse('Bard will not be loaded - wrong server config or reports off')


def getreport(request, planid):
    """ This method takes a request with given variables and a plan id.  It will write out an 
    HTML-formatted BARD report to the directory given in the settings, and return that same
    HTML for use as a preview in the web application, along with the web address of the 
    BARD report.
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
        #       ...)  {
        #...
        #}

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

    def get_tagged_list(parameter_string):
        """ Helper method to break up the strings that represents lists of variables
        Give it a string and get a TaggedList suitable for rpy2 use
        """
        tl = rpc.TaggedList(list())
        extras = parameter_string.split('^')
        for extra in extras:
            pair = extra.split('|')
            tl.append(pair[1], pair[0])
        return tl
    
    district_list = dict()
    district_names = { None: 'Unassigned' }
    geolevel = settings.BASE_GEOLEVEL
    geounits = Geounit.objects.filter(geolevel = settings.BASE_GEOLEVEL)
    # For each district, add to the district_list a dictionary of district_ids using the geounit_ids as keys
    for district in districts:
        if district.simple:
            intersecting = geounits.filter(center__bboverlaps=district.simple).values_list('id', flat=True)
            intersecting = dict.fromkeys(intersecting, district.district_id)
            district_list.update(intersecting)
            district_names[district.district_id] = district.name

    # Get the min and max ids of the geounits in this level
    max_and_min = geounits.aggregate(Min('id'), Max('id'))
    min_id = int(max_and_min['id__min'])
    max_id = int(max_and_min['id__max'])

    sorted_district_list = list()
    names = list()
    # Sort the geounit_id list and add them to the district_list in order.
    # This ordering depends on the geounits in the shapefile matching the order of the imported geounits.
    # If this ordering is the same, the geounits' ids don't have to match their fids in the shapefile
    for i in range(min_id, max_id + 1):
        if i in district_list:
            district_id = district_list[i]
        else:
            district_id = None
        sorted_district_list.append(district_id)
        # Add the names for the districts so we can display them later
        names.append(district_names[district_id])
    # Now we need an R Vector
    block_ids = robjects.IntVector(sorted_district_list)
    block_ids.names = robjects.StrVector(names)

    # Get the other report varialbes from the POST request.  We'll only add them to the report if they're in the request
    popVar = request.POST.get('popVar', None)
    if popVar:
        pop_var = get_tagged_list(popVar)
        pop_var.append(.1, 'tolerance')

    popVarExtra = request.POST.get('popVarExtra', None)
    if popVarExtra:
        pop_var_extra = get_tagged_list(popVarExtra)
    else:
        pop_var_extra = r('as.null()')
    
    racialComp = request.POST.get('ratioVars', None)
    partyControl = request.POST.get('partyControl', None)
    if racialComp or partyControl:
        ratioVars = rpc.TaggedList(list())
        if racialComp:
            mmd = rpc.TaggedList(list())
            mmd.append(pop_var, 'denominator')
            mmd.append(.6, 'threshhold')
            mmdappend( get_tagged_list(racialComp), 'numerators')
            ratioVars.append(mmd, 'Majority Minority Districts')

        if partyControl:
            pc = rpc.TaggedList(list())
            pc.append(pop_var, 'denominator')
            pc.append(.55, 'threshhold')
            pc.append(get_tagged_list(partyControl), 'numerators')
            ratioVars.append(pc, 'Party-controlled Districts')
        ratio_vars = ratioVars
    else:
        ratio_vars = r('as.null()')

    splitVars = request.POST.get('splitVars', None)
    if splitVars:
        split_vars = get_tagged_list(splitVars)
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
        r.PMPreport( bardmap, block_ids, file = report, popVar = pop_var, popVarExtra = pop_var_extra, ratioVars = ratio_vars, splitVars = split_vars, repCompactness = rep_compactness, repCompactnessExtra = rep_compactness_extra, repSpatial = rep_spatial, repSpatialExtra = rep_spatial_extra)
        r.HTMLEndFile()

        # BARD has written the report to file - read it and put it in as the preview
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
    """Create a new district.  Optionally, add the given geounits to the 
    district to start.  Returns the new District's name and district_id.
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
                status['edited'] = plan.edited.isoformat()
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
    """ This method, when called, required a "geolevel" and a "geounits"
    parameter. The geolevel must be a valid geolevel name and the geounits 
    parameters should be a pipe-separated list of geounit ids
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
            status['edited'] = plan.edited.isoformat()
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
    if request.method == "POST":
        return HttpResponse("looking for the requested plan")
        # plan has been chosen.  Open it up
    else:
        templates = Plan.objects.filter(is_template=True, owner__is_staff = True)
        shared = Plan.objects.filter(is_shared=True)
        mine = Plan.objects.filter(is_template=False, is_shared=False, owner=request.user)

        return render_to_response('chooseplan.html', {
            'templates': templates,
            'shared': shared,
            'mine': mine,
            'user': request.user,
            'is_anonymous': request.user.username == 'anonymous'
        })

@login_required
@cache_control(private=True)
def simple_district_versioned(request,planid):
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
        elif getdefaultsubject():
            subject_id = getdefaultsubject().id

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
            'aggregate': getcompliance(districts),
            'headers': headers
        })
    except:
        status['exception'] = traceback.format_exc()
        status['message'] = "Couldn't get district demographics."
        return HttpResponse( json.dumps(status), mimetype='application/json', status=500 )


def getgeography(request, planid):
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

                target = Target.objects.get(subject = subject)
                
                # The "in there" range
                range1 = target.lower * settings.POPTARGET_RANGE1  
                # The "out of there" range
                range2 = target.lower * settings.POPTARGET_RANGE2
                number = int(characteristic.number)
                if number < (target.lower - range2):
                    css_class = 'farunder'
                elif number < (target.lower - range1):
                    css_class = 'under'
                elif number <= (target.lower + range1):
                    css_class = 'target'
                elif number <= (target.lower + range2):
                    css_class = 'over'
                elif number > (target.lower + range2):
                    css_class = 'farover'
                stats['css_class'] = css_class 

            district_values.append(stats)

        return render_to_response('geography.html', {
            'plan': plan,
            'district_values': district_values,
            'aggregate': getcompliance(districts),
            'name': subject.short_display
        })
    except:
        status['exception'] = traceback.format_exc()
        status['message'] = "Couldn't get district geography."
        return HttpResponse( json.dumps(status), mimetype='application/json', status=500)


def getcompliance(districts):
    """ Returns compliance information about the districts, including contiguity and population 
    target data, and minority districts
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
        data = { 'name': 'Target Pop. %s' % target.lower, 'value': 'All meet target' } 
        noncompliant = 0
        for district in districts:
            try:
                characteristic = district.computedcharacteristic_set.get(subject__exact = target.subject) 
                allowance = target.lower * settings.POPTARGET_RANGE1
                number = int(characteristic.number)
                if (number < (target.lower - allowance)) or (number > (target.lower + allowance)):
                    noncompliant += 1
            except:
                # District has no characteristics - unassigned
                continue
        if noncompliant > 0:
            data['value'] = '%d miss target' % noncompliant
        compliance.append(data)

    #Minority districts
    population = Subject.objects.get(name=settings.DEFAULT_DISTRICT_DISPLAY)
    minority = Subject.objects.exclude(name=settings.DEFAULT_DISTRICT_DISPLAY)
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
    Returns aggregated data based on the districts given and all available subjects
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

def updatedistrict(request, planid, districtid):
    status = { 'success': False }
    plan = Plan.objects.get(pk=planid)
    district = plan.district_set.get(district_id=districtid)
    try:
        status['success'] = True
        status['message'] = 'Updated stats for %s.' % district.name
    except:
        status['message'] = 'Couldn\'t update district stats.'
    
    return HttpResponse(json.dumps(status),mimetype='application/json')

def getcompactness(district):
    """This is the Schwartzberg measure of compactness, which is the measure of the perimeter of the district 
    to the circumference of the circle whose area is equal to the area of the district
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
     
def getdefaultsubject():
    """Get the default subject to display. This reads the settings
    for the value 'DEFAULT_DISTRICT_DISPLAY', which can be the ID of
    a subject, a name of a subject, or the display of a subject.
    """
    key = settings.DEFAULT_DISTRICT_DISPLAY
    try:
        subject = Subject.objects.filter(id__exact=key)
        if len(subject) == 1:
            return subject[0]
    except:
        pass

    try:
        subject = Subject.objects.filter(name__exact=key)
        if len(subject) == 1:
            return subject[0]
    except:
        pass

    try:
        subject = Subject.objects.filter(display__exact=key)
        if len(subject) == 1:
            return subject[0]
    except:
        pass

    try:
        subject = Subject.objects.filter(short_display__exact=key)
        if len(subject) == 1:
            return subject[0]
    except:
        pass

    return None
