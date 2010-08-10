from django.http import *
from django.core import serializers
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection
from django.db.models import Sum
from django.shortcuts import render_to_response
from django.contrib.auth.decorators import login_required
from django.contrib import humanize
from django import forms
from django.utils import simplejson as json
from publicmapping import settings
from publicmapping.redistricting.models import *
import random, string, types, copy

"""The view for a plan. This is a data endpoint, and will be used
to return the geometries of plans as they are dynamically constructed."""
@login_required
def plan(request, planid):
    return render_to_response('plan.json', {});


@login_required
def copyplan(request, planid):
    p = Plan.objects.get(pk=planid)
    status = { 'success': False }
    if not can_copy(request.user, p):
        status['success'] = False;
        status['message'] = "User %s doesn't have permission to copy this model" % request.user.username
        return HttpResponse(json.dumps(status),mimetype='application/json')
    newname = p.name + " " + str(random.random()) 
    if (request.method == "POST" ):
        newname = request.POST["name"]
    plan_copy = Plan(
        name = newname, owner=request.user
    )
    plan_copy.save()

    districts = p.district_set.all()
    for district in districts:
        # Skip Unassigned, we already have that
        if district.name == "Unassigned":
            continue
#        district_copy = District(name = district.name, plan = copy, version = 0, geom = district.geom, simple = district.simple)
        district_copy = copy.copy(district)

        district_copy.id = None
        district_copy.version = 0
        district_copy.plan = plan_copy

        try:
            district_copy.save() 
        except Exception as inst:
            status["success"] = False
            status["message"] = "Could not save district copies"
            status["exception"] = inst.message
            return HttpResponse(json.dumps(status),mimetype='application/json')

        district_geounits = DistrictGeounitMapping.objects.filter(plan = p, district = district)
        DistrictGeounitMapping.objects.filter(plan = plan_copy, geounit__in=district_geounits).update(district = district_copy)

        stats = ComputedCharacteristic.objects.filter(district = district)
        for stat in stats:
            stat.district = district_copy
            stat.id = None
            stat.save()
    data = serializers.serialize("json", [ plan_copy ])

    return HttpResponse(data)    
    
@login_required
def editplan(request, planid):
    try:
        plan = Plan.objects.get(pk=planid)
        districts = plan.district_set.all()
        districts = sorted(list(districts), key = lambda district: district.sortKey())
        if not can_edit(request.user, plan):
            plan = {}
    except:
        plan = {}
        districts = {}
    levels = Geolevel.objects.values_list("id", "name")
    demos = Subject.objects.values_list("id","name", "short_display")
    default_demo = getdefaultsubject()
    layers = []
    snaplayers = []
    rules = []
    targets = Target.objects.all()
    for level in levels:
        snaplayers.append( {'geolevel':level[0],'layer':level[1],'name':level[1].capitalize()} )
    for demo in demos:
        layers.append( {'id':demo[0],'text':demo[2],'value':demo[1].lower(), 'isdefault':str(demo[0] == default_demo.id).lower()} )
    for target in targets:
        rules.append( {'subject_id':target.subject_id,'lower':target.lower,'upper':target.upper} )

    unassigned_id = 0
    if type(plan) != types.DictType:
        unassigned_id = plan.district_set.filter(name='Unassigned').values_list('district_id',flat=True)[0]

    return render_to_response('editplan.html', {
        'plan': plan,
        'districts': districts,
        'mapserver': settings.MAP_SERVER,
        'demographics': layers,
        'snaplayers': snaplayers,
        'rules': rules,
        'unassigned_id': unassigned_id,
    })

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

@login_required
def publishplan(request, planid):
    status = { 'success': False, 'message': 'Unspecified Error' }
    try:
        plan = Plan.objects.get(pk=planid)
    except:
        status['message'] = 'No plan with the given ID exists'
        return HttpResponse(json.dumps(status),mimetype='application/json')
    return render_to_response('publishplan.html', {
        'plan': plan,
    })


@login_required
def newdistrict(request, planid):
    """Create a new district.  Optionally, add the given geounits to the 
    district to start.  Returns the new District's name and district_id.
    """
    status = { 'success': False, 'message': 'Unspecified error.' }
    plan = Plan.objects.get(pk=planid)
    if not plan:
        status['message'] = 'No plan with that ID'
        return HttpResponse(json.dumps(status),mimetype='application/json')
    if len(request.REQUEST.items()) >= 1:
        if request.REQUEST.__contains__('name'):
            try: 
                district = District(name = request.REQUEST['name'], plan=plan)
                district.save()
                status['success'] = True
                status['message'] = 'Created new district'
                plan = Plan.objects.get(pk=planid)
                status['edited'] = plan.edited.isoformat()
                status['district_id'] = district.district_id
                status['district_name'] = district.name
            except ValidationError:
                status['message'] = 'Reached Max districts already'
            except:
                status['message'] = 'Couldn\'t save new district.'
        else:
            status['message'] = 'Must specify name for district'
    return HttpResponse(json.dumps(status),mimetype='application/json')

@login_required
def addtodistrict(request, planid, districtid):
    """ This method, when called, required a "geolevel" and a "geounits" parameter.  
    The geolevel must be a valid geolevel name and the geounits parameters should be a pipe-separated list of geounit ids
    """
    status = { 'success': False, 'message': 'Unspecified error.' }
    if len(request.REQUEST.items()) >= 2: 
        geolevel = request.REQUEST["geolevel"];
        geounit_ids = string.split(request.REQUEST["geounits"], "|")
        plan = Plan.objects.get(pk=planid)
        try:
            fixed = plan.add_geounits(districtid, geounit_ids, geolevel)
            status['success'] = True;
            status['message'] = 'Updated %d districts' % fixed
            plan = Plan.objects.get(pk=planid)
            status['edited'] = plan.edited.isoformat()
        except: 
            status['message'] = 'Could not add units to district.'
    else:
        status['message'] = 'Geounits weren\'t found in a district.'

    # debug the times used for each query
    #status['queries'] = json.dumps(connection.queries)

    return HttpResponse(json.dumps(status),mimetype='application/json')


@login_required
def chooseplan(request):
    if request.method == "POST":
        return HttpResponse("looking for the requested plan")
        # plan has been chosen.  Open it up
    else:
        templates = Plan.objects.filter(is_template=True, owner__is_staff = True)
        shared = Plan.objects.filter(is_template=True, owner__is_staff = False).exclude(owner = request.user)
        mine = Plan.objects.filter(is_template=False, owner=request.user)
        return render_to_response('chooseplan.html', {
            'templates': templates,
            'shared': shared,
            'mine': mine,
            'user': request.user,
        })

def getdemographics(request, planid):
    try:
        plan = Plan.objects.get(pk = planid)
    except:
        return HttpResponse ( "{ \"success\": false, \"message\":\"Couldn't get demographic info from the server. Please try again later.\" }" )
    subjects = Subject.objects.all()
    districts = plan.district_set.all()
    district_values = []

    for district in districts:
        dist_name = district.name
        if dist_name == "Unassigned":
            dist_name = "U"
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
        'aggregate': getaggregate(districts),
    })


def getgeography(request, planid):
    try:
        plan = Plan.objects.get(pk = planid)
    except:
        return HttpResponse ( "{ \"success\": false, \"message\":\"Couldn't get geography info from the server. No plan with the given id.\" }" )
    
    if 'demo' in request.REQUEST: 
        demo = request.REQUEST['demo']
    else:
        return HttpResponse ( "{ \"success\": false, \"message\":\"Couldn't get geography info from the server. Please use the 'demo' parameter with a Subject id.\" }" )

    districts = plan.district_set.all()
    try:
        subject = Subject.objects.get(pk=demo)
    except:
        return HttpResponse ( "{ \"success\": false, \"message\":\"Couldn't get geography info from the server. No Subject exists with the given id.\" }" )

    district_values = []
    for district in districts:
        dist_name = district.name
        if dist_name == "Unassigned":
            dist_name = "U"
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
            if characteristic.number < target.lower:
                css_class = 'under'
            elif characteristic.number > target.upper:
                css_class = 'over'
            else:
                css_class = 'target'
            stats['css_class'] = css_class

        district_values.append(stats)

    return render_to_response('geography.html', {
        'plan': plan,
        'district_values': district_values,
        'aggregate': getaggregate(districts),
        'name': subject.short_display
    })


def getaggregate(districts):
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

def updatestats(request, planid):
    status = { 'success': False }
    plan = Plan.objects.get(pk=planid)
    try:
        numdistricts = plan.update_stats()
        status['success'] = True
        status['message'] = 'Updated stats for %s; %d districts updated.' % (plan.name, numdistricts)
    except:
        status['message'] = 'Couldn\'t update plan stats.'

    return HttpResponse(json.dumps(status), mimetype='application/json')

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
