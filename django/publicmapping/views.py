from django.shortcuts import render_to_response
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.http import HttpResponseRedirect, HttpResponse
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.utils import simplejson

# for proxy
import urllib2
import cgi
import sys, os

"""Generate the index page for the application. The
index template contains a login button, a register
button, and an anonymous button, all of which interact
with django's authentication system."""
def index(request):
    return render_to_response('index.html', { })

"""The view to process when a client attempts to register.
A user can log in if their username is unique, and their
password is not empty. An email address is optional. This
view returns a JSON nugget, with a 'success' property.

If registration was successful, the JSON nugget also contains
a 'redirect' property.

If registration was unsuccessful, the JSON script also contains
a 'message' property, describing why the registration failed.
"""
def userregister(request):
    username = request.POST.get('newusername', None)
    password = request.POST.get('newpassword1', None)
    email = request.POST.get('email', None)
    anonymous = False
    status = { 'success':False }
    if username != '' and password != '':
        anonymous = (username == 'anonymous' and password == 'anonymous')

        name_exists = User.objects.filter(username__exact=username)
        if name_exists:
            status['message'] ='name exists'
            return HttpResponse(simplejson.dumps(status), mimetype='application/json')

        email_exists = email != '' and User.objects.filter(email__exact = email)
        if email_exists:
            status['message'] ='email exists'
            return HttpResponse(simplejson.dumps(status), mimetype='application/json')

        if not anonymous:
            try:
                User.objects.create_user(username, email, password)
            except Exception as error:
                status['message'] = 'Sorry, we weren\'t able to create your account.'
                return HttpResponse(simplejson.dumps(status), mimetype='application/json')

        user = authenticate(username=username, password=password)
        login( request, user )
        status['success'] = True
        status['redirect'] = '/districtmapping/plan/0/view'
        return HttpResponse(simplejson.dumps(status), mimetype='application/json')
    else:
        status['message'] = 'Username cannot be empty.'
        return HttpResponse(simplejson.dumps(status), mimetype='application/json')

"""Log out a client from the application. This uses django's
authentication system to clear the session, etc. The view will
redirect the user to the index page after logging out."""
def userlogout(request):
    logout(request)
    return HttpResponseRedirect('/')

"""The view for the mapping page. The mapping page requires
a valid user, and as such, is decorated with login_required."""
@login_required
def mapping(request):
    return render_to_response('mapping.html', 
        { 'mapserver': settings.MAP_SERVER })

@login_required
def proxy(request):
    url = request.GET['url']

    host = url.split('/')[2]
    if host != settings.MAP_SERVER:
        raise Http404

    if request.method == 'POST':
        rsp = urllib2.urlopen( urllib2.Request(
            url, 
            request.raw_post_data,
            {'Content-Type': request.META['CONTENT_TYPE'] }
        ))
    else:
        rsp = urllib2.urlopen(url)

    httprsp = HttpResponse( rsp.read() )
    if rsp.info().has_key('Content-Type'):
        httprsp['Content-Type'] = rsp.info()['Content-Type']
    else:
        httprsp['Content-Type'] = 'text/plain'

    rsp.close()

    return httprsp

