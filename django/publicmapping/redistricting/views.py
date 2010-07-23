from django.http import *
from django.core import serializers
from django.db import IntegrityError
from django.db.models import Sum
from django.shortcuts import render_to_response
from django.contrib.auth.decorators import login_required
from django import forms
from django.utils import simplejson as json
from publicmapping import settings
from publicmapping.redistricting.models import *
import random, string

@login_required
def copyplan(request, planid):
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
        pass

    districts = p.district_set.all()
    for district in districts:
        district_copy = District(name = district.name, plan = copy, version = 0, geom = district.geom, simple = district.simple)
        district_copy.save() 

        # clone all the geounits manually
        from django.db import connection, transaction
        cursor = connection.cursor()

        sql = "insert into redistricting_districtgeounitmapping (plan_id, district_id, geounit_id) select %d, %d, geounit_id from redistricting_districtgeounitmapping where plan_id = %d and district_id = %d;" % (copy.id, district_copy.id, p.id, district.id)
        cursor.execute(sql)
        transaction.commit_unless_managed()

    data = serializers.serialize("json", [ copy ])

    return HttpResponse(data)    
    
@login_required
def editplan(request, planid):
    try:
        plan = Plan.objects.get(pk=planid)
    except:
        plan = {}
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

    return render_to_response('editplan.html', {
        'plan': plan,
        'mapserver': settings.MAP_SERVER,
        'demographics': layers,
        'snaplayers': snaplayers,
        'rules': rules,
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
    status = { 'success': False, 'message': 'Unspecified error.' }
    if len(request.REQUEST.items()) >= 2: 
        geolevel = request.REQUEST["geolevel"];
        geounit_ids = string.split(request.REQUEST["geounits"], "|")
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
        owner = User.objects.get(username=settings.ADMINS[0][0])
        templates = Plan.objects.filter(is_template=True, owner=owner)
        shared = Plan.objects.exclude(owner=owner).exclude(owner=request.user).filter(is_template=True)
        mine = Plan.objects.filter(owner=request.user)
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
            characteristics = ComputedCharacteristic.objects.filter(subject = subject, district = district) 
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

        characteristics = ComputedCharacteristic.objects.filter(district = district, subject = subject)

        if characteristics.count() == 0:
            stats['demo'] = 'n/a'        
            stats['contiguity'] = 'n/a'
            stats['compactness'] = 'n/a'
            stats['css_class'] = 'under'

        for characteristic in characteristics:
            stats['demo'] = "%.0f" % characteristic.number        
            stats['contiguity'] = random.choice( [True, False] )
            stats['compactness'] = str( random.randint(50, 80)) + "%"

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
