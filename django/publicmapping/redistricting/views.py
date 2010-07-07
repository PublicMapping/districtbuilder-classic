from django.http import *
from django.core import serializers
from django.db import IntegrityError
from django.shortcuts import render_to_response
from django import forms
from publicmapping.redistricting.models import *
import random, string

def copyplan(request, planid):
   #  return HttpResponse("You are copying plan %s" % planid)
    p = Plan.objects.get(pk=planid)
    copy = Plan(
        name = p.name + " " + str(random.random()), owner=request.user
    )
    try:
        copy.save()
    except IntegrityError:
        return HttpResponse("{ success: false; message: 'Can\'t create a plan with a duplicate name' }")
    districts = p.district_set.all()
    for district in districts:
        district_copy = District(name = district.name, plan = copy, version = 0)
        district_copy.save() 
        district_copy.geounits = district.geounits.all()
    data = serializers.serialize("json", [ copy ])
    return HttpResponse(data)    
    
def editplan(request, planid):
    plan = Plan.objects.get(pk=planid)
    layers = Geolevel.objects.values_list("name", flat=True)
    return render_to_response('editplan.html', {
        'plan': plan,
        'mapserver': settings.MAP_SERVER,
        'layers': layers,
    })

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

def addtodistrict(request, planid, districtid):
    if len(request.GET.items()) > 0: 
        geounit_ids = string.split(request.REQUEST["geounits"], "|")
        plan = Plan.objects.get(pk=planid)
        fixed = plan.add_geounits(districtid, geounit_ids)
        return HttpResponse("{ success: true, message:\"Updated " + str(fixed) + " districts\"}")
    else:
        return HttpResponse("Geounits weren't found in a district")

def deletefromdistrict(request, planid, districtid):
    if len(request.GET.items()) > 0:
        geounit_ids = string.split(request.REQUEST["geounits"], "|")
        plan = Plan.objects.get(pk=planid)
        fixed = plan.delete_geounits(districtid, geounit_ids)
        return HttpResponse("{ success: true, message:\"Updated " + str(fixed) + " districts\"}")
    else:
        return HttpResponse("Geounits weren't found in a district")

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
