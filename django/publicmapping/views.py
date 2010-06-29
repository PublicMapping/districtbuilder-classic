from django.shortcuts import render_to_response
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponseRedirect
from django.contrib.auth.decorators import login_required
from django.conf import settings

import random

def index(request):
    return render_to_response('index.html', { })

def userlogout(request):
    logout(request)
    return HttpResponseRedirect('/')

@login_required
def mapping(request):
    return render_to_response('mapping.html', { 'mapserver': settings.MAP_SERVER })

@login_required
def plan(request, planid):
    return render_to_response('plan.json', {});
