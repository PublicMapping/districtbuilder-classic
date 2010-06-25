from django.shortcuts import render_to_response
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponseRedirect
from django.contrib.auth.decorators import login_required

import random

def index(request):
    width = 140024
    height = 42007
    xmin = -9439758
    ymin = 4804742
    xmax = -9017448 - width
    ymax = 5069106 - height

    xmin = random.uniform( xmin, xmax )
    ymin = random.uniform( ymin, ymax )
    xmax = xmin + width
    ymax = ymin + height

    bbox = "%d,%d,%d,%d" % ( xmin, ymin, xmax, ymax )

    return render_to_response('index.html', { 'bbox': bbox })

def userlogout(request):
    logout(request)
    return HttpResponseRedirect('/')

@login_required
def mapping(request):
    return render_to_response('mapping.html', {})
