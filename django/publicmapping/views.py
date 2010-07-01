from django.shortcuts import render_to_response
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.http import HttpResponseRedirect, HttpResponse
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.utils import simplejson

def index(request):
    return render_to_response('index.html', { })

def userregister(request):
    username = request.POST['newusername']
    password = request.POST['newpassword1']
    anonymous = False
    if username != '':
        anonymous = (username == 'anonymous' and password == 'anonymous')

        exists = User.objects.filter(username__exact=username)

        if len(exists) == 0 or anonymous:
            if not anonymous:
                email = request.POST['email']
                User.objects.create_user(username, email, password)

            user = authenticate(username=username, password=password)
            login( request, user )
            return HttpResponse(simplejson.dumps({
                    'success':True,
                    'redirect':'/districtmapping/'
                }), 
                mimetype='application/json')
        else:
            msg = 'User with that name already exists.'
    else:
        msg = 'Username cannot be empty.'

    return HttpResponse(simplejson.dumps({
            'success':False,
            'message':msg
        }), 
        mimetype='application/json')

def userlogout(request):
    logout(request)
    return HttpResponseRedirect('/')

@login_required
def mapping(request):
    return render_to_response('mapping.html', 
        { 'mapserver': settings.MAP_SERVER })

@login_required
def plan(request, planid):
    return render_to_response('plan.json', {});
