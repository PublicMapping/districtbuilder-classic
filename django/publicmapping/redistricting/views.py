from django.http import *
from django.core import serializers
from django.db import IntegrityError
from django.db.models import Sum
from django.shortcuts import render_to_response
from django.contrib.auth.decorators import login_required
from django import forms
from publicmapping.redistricting.models import *
import random, string

@login_required
def copyplan(request, planid):
   #  return HttpResponse("You are copying plan %s" % planid)
    p = Plan.objects.get(pk=planid)
    newname = p.name + " " + str(random.random()) 
    if (request.method == "POST" ):
        newname = request.POST["name"]
    copy = Plan(
        name = newname, owner=request.user
    )
    try:
        copy.save()
    except IntegrityError:
        return HttpResponse("[{ \"success\" : false, \"message\" : \"Can't create a plan with a duplicate name\" }]")
    districts = p.district_set.all()
    for district in districts:
        district_copy = District(name = district.name, plan = copy, version = 0)
        district_copy.save() 
        district_copy.geounits = district.geounits.all()
    data = serializers.serialize("json", [ copy ])
    return HttpResponse(data)    
    
@login_required
def editplan(request, planid):
    try:
        plan = Plan.objects.get(pk=planid)
    except:
        plan = {}
    levels = Geolevel.objects.values_list("name", flat=True)
    demos = Subject.objects.values_list("name", "short_display")
    layers = []
    snaplayers = []
    for level in levels:
        snaplayers.append( {'layer':level,'name':level.capitalize()} )
    for demo in demos:
        layers.append( {'text':demo[1],'value':demo[0].lower()} )
    return render_to_response('editplan.html', {
        'plan': plan,
        'mapserver': settings.MAP_SERVER,
        'demographics': layers,
        'snaplayers': snaplayers,
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
def addtodistrict(request, planid, districtid):
    """ This method, when called, required a "geolevel" and a "geounits" parameter.  
    The geolevel must be a valid geolevel name and the geounits parameters should be a pipe-separated list of geounit ids
    """
    if len(request.REQUEST.items()) >= 2: 
        geolevel = request.REQUEST["geolevel"];
        geounit_ids = string.split(request.REQUEST["geounits"], "|")
        plan = Plan.objects.get(pk=planid)
        fixed = plan.add_geounits(districtid, geounit_ids, geolevel)
        return HttpResponse("{\"success\": true, \"message\":\"Updated " + str(fixed) + " districts\"}")
    else:
        return HttpResponse("Geounits weren't found in a district")

#@login_required
#def deletefromplan(request, planid, geounit_ids):
#    """ This method, when called, requires "geolevel" and a "geounits" parameter. The requested geounits will be removed from all districts in the given plan. 
#    The geolevel must be a valid geolevel name and the geounits parameters should be a pipe-separated list of geounit ids
#    """
#    if len(request.REQUEST.items()) >= 2: 
#        geolevel = request.REQUEST["geolevel"];
#        geounit_ids = string.split(request.REQUEST["geounits"], "|")
#        plan = Plan.objects.get(pk=planid)
#        fixed = plan.delete_geounits(districtid, geounit_ids, geolevel)
#        return HttpResponse("{\"success\": true, \"message\":\"Updated " + str(fixed) + " districts\"}")
#    else:
#        return HttpResponse("{ \"success\:: false, \"message\": \"Geounits weren't found in the given plan\" }")

@login_required
def chooseplan(request):
    if request.method == "POST":
        return HttpResponse("looking for the requested plan")
        # plan has been chosen.  Open it up
    else:
        templates = Plan.objects.filter(is_template=True, owner = 1)
        shared = Plan.objects.exclude(owner = 1).exclude(owner=request.user).filter(is_template=True)
        mine = Plan.objects.filter(owner=request.user)
        return render_to_response('chooseplan.html', {
            'templates': templates,
            'shared': shared,
            'mine': mine,
            'user': request.user,
        })

def getdemographics(request, planid):
    plan = Plan.objects.get(pk = planid)
    if plan == None:
        return HttpResponse ( "{ \"success\": false, \"message\":\"Couldn't get demographic info from the server. Please try again later.\" }" )
    targets = {}
    aggregate = {}
    district_values = {}

    district_ids = plan.district_set.values_list('id')
    characteristics = ComputedCharacteristic.objects.filter(id__in=district_ids) 
    for characteristic in characteristics:
        if not characteristic.district.name in district_values: 
            district_values[characteristic.district.name] = {}
        district_values[characteristic.district.name][characteristic.subject.name] = characteristic.number        

    for target in Target.objects.all():
        targets[target.subject.display] = target.value
        aggregate[target.subject.display] = characteristics.filter(subject = target.subject).aggregate(Sum('number'))['number__sum']
    return render_to_response('demographics.html', {
        'plan': plan,
        'district_values': district_values,
        'aggregate': aggregate,
        'characteristics': characteristics,
        'targets': targets,
    })


def getgeography(request, planid):
    plan = Plan.objects.get(pk = planid)
    if plan == None:
        return HttpResponse ( "{ \"success\": false, \"message\":\"Couldn't get geography info from the server. Please try again later.\" }" )
    
    targets = {}
    aggregate = {}
    district_values = {}

    district_ids = plan.district_set.values_list('id')
    characteristics = ComputedCharacteristic.objects.filter(id__in=district_ids, subject__exact=3) 
    for characteristic in characteristics:
        if not characteristic.district.name in district_values: 
            district_values[characteristic.district.name] = {}
        district_values[characteristic.district.name][characteristic.subject.name] = characteristic.number        
        district_values[characteristic.district.name]['contiguity'] = random.choice( [True, False] )
        district_values[characteristic.district.name]['compactness'] = 'N/A'

    for target in Target.objects.all():
        targets[target.subject.name] = target.value
        aggregate[target.subject.name] = characteristics.filter(subject = target.subject).aggregate(Sum('number')) 
    return render_to_response('geography.html', {
        'plan': plan,
        'district_values': district_values,
        'characteristics': characteristics,
        'targets': targets,
    })
