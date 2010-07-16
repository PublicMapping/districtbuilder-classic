from django.http import *
from django.core import serializers
from django.db import IntegrityError
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
    demos = Subject.objects.values_list("name", flat=True)
    layers = []
    snaplayers = []
    for level in levels:
        snaplayers.append( {'layer':level,'name':level.capitalize()} )
        for demo in demos:
            layers.append(string.lower('demo_%s_%s' % ( level, demo)) )
    return render_to_response('editplan.html', {
        'plan': plan,
        'mapserver': settings.MAP_SERVER,
        'layers': layers,
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
#def deletefromdistrict(request, planid, districtid):
#    """ This method, when called, required a "geolevel" and a "geounits" parameter.  
#    The geolevel must be a valid geolevel name and the geounits parameters should be a pipe-separated list of geounit ids
#    """
#    if len(request.REQUEST.items()) >= 2: 
#        geolevel = request.REQUEST["geolevel"];
#        geounit_ids = string.split(request.REQUEST["geounits"], "|")
#        plan = Plan.objects.get(pk=planid)
#        fixed = plan.delete_geounits(districtid, geounit_ids, geolevel)
#        return HttpResponse("{\"success\": true, \"message\":\"Updated " + str(fixed) + " districts\"}")
#    else:
#        return HttpResponse("Geounits weren't found in a district")

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
