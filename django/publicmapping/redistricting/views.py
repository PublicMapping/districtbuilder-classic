from django.http import *
from django.core import serializers
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Sum
from django.shortcuts import render_to_response
from django.contrib.auth.decorators import login_required
from django import forms
from django.utils import simplejson as json
from publicmapping import settings
from publicmapping.redistricting.models import *
import random, string, types

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
    copy = Plan(
        name = newname, owner=request.user
    )
    copy.save()

    districts = p.district_set.all()
    for district in districts:
        district_copy = District(name = district.name, plan = copy, version = 0, geom = district.geom, simple = district.simple)
        try:
            district_copy.save() 
        except:
            status["success"] = False
            status["message"] = "Could not save district copies"
            return HttpResponse(json.dumps(status),mimetype='application/json')
        # clone all the geounits manually
        from django.db import connection, transaction
        cursor = connection.cursor()

        sql = "insert into redistricting_districtgeounitmapping (plan_id, district_id, geounit_id) select %d, %d, geounit_id from redistricting_districtgeounitmapping where plan_id = %d and district_id = %d;" % (copy.id, district_copy.id, p.id, district.id)
        cursor.execute(sql)

        sql = 'insert into redistricting_computedcharacteristic (subject_id,district_id,"number",percentage) select subject_id, %d, number, percentage from redistricting_computedcharacteristic where district_id = %d' % (district_copy.id, district.id)
        cursor.execute(sql)
        transaction.commit_unless_managed()

    data = serializers.serialize("json", [ copy ])

    return HttpResponse(data)    
    
@login_required
def editplan(request, planid):
    try:
        plan = Plan.objects.get(pk=planid)
        districts = plan.district_set.all()
        if not can_edit(request.user, plan):
            plan = {}
    except:
        plan = {}
        districts = {}
    levels = Geolevel.objects.values_list("name", flat=True)
    demos = Subject.objects.values_list("id","name", "short_display")
    layers = []
    snaplayers = []
    rules = []
    targets = Target.objects.all()
    for level in levels:
        snaplayers.append( {'layer':level,'name':level.capitalize()} )
    for demo in demos:
        layers.append( {'id':demo[0],'text':demo[2],'value':demo[1].lower()} )
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
    if request.method == "POST":
        form = PlanForm(request.POST)
        if form.is_valid():
            # make a new plan
            model = form.save()
            return HttpResponseRedirect('/districtmapping/plan/%s/edit' % model.id)
    else:
        form = PlanForm()
    return render_to_response('createplan.html', {
        'form': form,
    })

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
        geounit_ids = tuple(string.split(request.REQUEST["geounits"], "|"))
        plan = Plan.objects.get(pk=planid)
        try:
            fixed = plan.add_geounits(districtid, geounit_ids, geolevel)
            status['success'] = True;
            status['message'] = 'Updated %d districts' % fixed
        except: 
            status['message'] = 'Could not add units to district.'
    else:
        status['message'] = 'Geounits weren\'t found in a district.'

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
    targets = {}
    aggregate = {}
    district_values = {}

    subjects = Subject.objects.all()
    districts = plan.district_set.all()
    for district in districts:
        dist_name = district.name
        if dist_name == "Unassigned":
            dist_name = "U"
        if not dist_name in district_values: 
            district_values[dist_name] = {}

        stats = district_values[dist_name]

        for subject in subjects:
            subject_name = subject.short_display
            characteristics = district.computedcharacteristic_set.filter(subject = subject) 
            if characteristics.count() == 0:
                stats[subject_name] = "n/a"
            else:
                stats[subject_name] = "%.0f" % characteristics[0].number       

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
        
    targets = {}
    aggregate = {}
    district_values = {}

    districts = plan.district_set.all()
    try:
        subject = Subject.objects.get(pk=demo)
    except:
        return HttpResponse ( "{ \"success\": false, \"message\":\"Couldn't get geography info from the server. No Subject exists with the given id.\" }" )
    for district in districts:
        dist_name = district.name
        if dist_name == "Unassigned":
            dist_name = "U"
        if not dist_name in district_values: 
            district_values[dist_name] = {}

        stats = district_values[dist_name]

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

    return render_to_response('geography.html', {
        'plan': plan,
        'district_values': district_values,
        'aggregate': getaggregate(districts),
        'name': subject.short_display
    })


def getaggregate(districts):
    aggregate = {}
    characteristics = ComputedCharacteristic.objects.filter(district__in=districts) 
    for target in Target.objects.all():
        try:
            aggregate[target.subject.short_display]= "%.0f" % characteristics.filter(subject = target.subject).aggregate(Sum('number'))['number__sum'] 
        except:
            aggregate[target.subject.short_display]= "Data unavailable" 
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
        
