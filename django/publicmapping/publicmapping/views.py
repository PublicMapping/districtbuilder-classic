"""
Define project views for this django project.

This file is part of The Public Mapping Project
https://github.com/PublicMapping/

License:
    Copyright 2010-2012 Micah Altman, Michael McDonald

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

         http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

Author:
    Andrew Jennings, David Zwarg
"""

from django.conf import settings
from django.core.mail import send_mail
from django.contrib.sessions.models import Session
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User, AnonymousUser
from django.contrib.sessions.models import Session
from django.contrib.auth.decorators import login_required
from django.contrib.sites.models import Site
from django.db import transaction
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponseRedirect, HttpResponse, HttpResponseNotFound
from django.shortcuts import render
from django.template import loader, RequestContext
from hashlib import sha1
from django.utils.translation import ugettext as _, get_language
import json

# for proxy
import cgi
import os
import sys
import urllib2

# for password reminders
from random import choice

import logging
logger = logging.getLogger(__name__)


def index(request):
    """
    Generate the index page for the application. The
    index template contains a login button, a register
    button, and an anonymous button, all of which interact
    with django's authentication system.

    Parameters:
        request -- An HttpRequest

    Returns:
        An HTML welcome page.
    """

    count = 0
    if 'count' in request.session:
        count = request.session['count']

    avail = True
    if 'avail' in request.session:
        avail = request.session['avail']

    return HttpResponse(
        render(
            request, 'index.html', {
                'is_registered': False,
                'opensessions': count,
                'sessionavail': avail,
                'ga_account': settings.GA_ACCOUNT,
                'ga_domain': settings.GA_DOMAIN,
                'user': request.user,
                'site': Site.objects.get_current(),
                'language_code': get_language(),
                'LANGUAGES': settings.LANGUAGES,
            }))


@transaction.atomic()
def userregister(request):
    """
    A registration form endpoint for registering and logging in.

    This view will permit a user to register if their username is unique,
    their password is not empty, and an email address is provided.
    This view returns JSON, with a 'success' property if registration or
    login was successful.

    If registration was successful, the JSON also contains
    a 'redirect' property.

    If registration was unsuccessful, the JSON also contains
    a 'message' property, describing why the registration failed.

    Parameters:
        request -- An HttpRequest, with the form submitted parameters.

    Returns:
        A JSON object indicating if registration/login was successful.
    """
    username = request.POST.get('newusername', None)
    password = request.POST.get('newpassword1', None)
    email = request.POST.get('email', None)
    fname = request.POST.get('firstname', None)
    lname = request.POST.get('lastname', None)
    hint = request.POST.get('passwordhint', None)
    org = request.POST.get('organization', None)
    anonymous = False
    status = {'success': False}
    if username != '' and password != '':
        if (username == 'anonymous' and password == 'anonymous'):
            user = AnonymousUser()
        else:
            name_exists = User.objects.filter(username__exact=username)
            if name_exists:
                status['message'] = 'name exists'
                return HttpResponse(json.dumps(status))

            email_exists = email != '' and User.objects.filter(
                email__exact=email)
            if email_exists:
                status['message'] = 'email exists'
                return HttpResponse(json.dumps(status))

            try:
                User.objects.create_user(username, email, password)
            except Exception as error:
                status[
                    'message'] = 'Sorry, we weren\'t able to create your account.'
                return HttpResponse(json.dumps(status))

            # authenticate the user, and add additional registration info
            user = authenticate(username=username, password=password)

            user.first_name = fname
            user.last_name = lname
            user.save()

            profile = user.profile
            profile.organization = org
            profile.pass_hint = hint
            profile.save()

            login(request, user)

        status['success'] = True
        status['redirect'] = '/districtmapping/plan/0/view/'
        return HttpResponse(json.dumps(status))
    else:
        status['message'] = 'Username cannot be empty.'
        return HttpResponse(json.dumps(status))


@transaction.atomic()
def userupdate(request):
    """
    Update a user's information.

    This function will update the user's account based on the contents of
    the form, much the same way the register function works.

    Parameters:
        request -- An HttpRequest with parameters for user information.

    Returns:
        JSON indicating success or failure.
    """
    username = request.POST.get('newusername', None)
    password1 = request.POST.get('newpassword1', None)
    password2 = request.POST.get('newpassword2', None)
    email = request.POST.get('email', None)
    fname = request.POST.get('firstname', None)
    lname = request.POST.get('lastname', None)
    hint = request.POST.get('passwordhint', None)
    org = request.POST.get('organization', None)
    id = request.POST.get('userid', None)

    status = {'success': False, 'message': 'Unspecified error.'}

    if username == 'anonymous':
        status['message'] = 'Cannot update anonymous account information.'
    else:
        try:
            user = User.objects.get(id=id)
            if user.username != username:
                status['message'] = 'Cannot change username.'
            elif password1 != password2:
                status['message'] = 'Passwords do not match.'
            else:
                user.email = email
                user.first_name = fname
                user.last_name = lname
                if not (password1 == '' or password1 is None):
                    user.set_password(password1)
                user.save()

                profile = user.profile
                profile.pass_hint = hint
                profile.organization = org
                profile.save()

                status['success'] = True
                status['message'] = 'Information updated.'
        except:
            status['message'] = 'No user for that account.'

    return HttpResponse(json.dumps(status))


def userlogout(request):
    """
    Log out a client from the application.

    This funtion uses django's authentication system to clear the session,
    etc. The view will redirect the user to the index page after logging
    out.

    Parameters:
        request -- An HttpRequest

    Returns:
        An HttpResponseRedirect to the root url.
    """
    key = request.session.session_key
    logout(request)
    Session.objects.filter(session_key=key).delete()
    if 'next' in request.GET:
        return HttpResponseRedirect(request.GET['next'])
    else:
        return HttpResponseRedirect('/')


def emailpassword(user):
    """
    Send a user an email with a new, auto-generated password.

    We cannot decrypt the current password stored with the user record,
    so create a new one, and send it to the user.

    This method is used within the forgotpassword form endpoint, but not
    as a user facing view.

    Parameters:
        user -- The django user whose password will be changed.

    Returns:
        True if the user was modified and notified successfully.
    """

    newpw = ''.join([
        choice(
            'abcdefghjkmnopqrstuvwxyzABCDEFGHJKMNOPQRSTUVWXYZ023456789!@#$%^&*()-_=+'
        ) for i in range(8)
    ])
    context = {'user': user, 'new_password': newpw}
    template = loader.get_template('forgottenpassword.email')

    try:
        s = sha1()
        s.update(newpw)
        user.set_password(s.hexdigest())
        user.save()
    except:
        return False

    send_mail(
        _('Your Password Reset Request'),
        template.render(context),
        settings.EMAIL_HOST_USER, [user.email],
        fail_silently=False)
    return True


@cache_control(no_cache=True)
def forgotpassword(request):
    """
    A form endpoint to provide a facility for retrieving a forgotten
    password. If someone has forgotten their password, this form will email
    them a replacement password.

    Parameters:
        request -- An HttpRequest

    Returns:
        A JSON object with a password hint or a message indicating that an
        email was sent with their new password.
    """
    status = {'success': False}
    data = request.POST
    username = data.get('username')
    email = data.get('email')
    if username:
        try:
            user = User.objects.get(username__exact=username)
            status['success'] = True
            status['mode'] = 'hinting'
            status['hint'] = user.profile.pass_hint
        except:
            status['field'] = 'username'
            status['message'] = 'Invalid username. Please try again.'
    elif email:
        try:
            user = User.objects.get(email__exact=email)
            status['mode'] = 'sending'
            status['success'] = emailpassword(user)
        except User.DoesNotExist:
            logger.info('Email not found: %s' % email)
            status['field'] = 'email'
            status['message'] = 'Invalid email address. Please try again.'
            status['success'] = False
        except:
            logger.exception('Error sending password reset email')
            status[
                'message'] = 'An error occurred sending password reset email'
            status['success'] = False
    else:
        status['field'] = 'both'
        status['message'] = 'Missing username or email.'

    return HttpResponse(json.dumps(status))


@login_required
@cache_control(no_cache=True)
def proxy(request):
    """
    A proxy for all requests to the map server.

    This proxy is required for WFS requests and queries, since geoserver
    is on a different port, and browser javascript is restricted to
    same origin policies.

    Parameters:
        request -- An HttpRequest, with an URL parameter.

    Returns:
        The content of the URL.
    """
    url = request.GET['url']

    if not url.startswith(settings.MAP_SERVER):
        return HttpResponseNotFound()

    if request.method == 'POST':
        rsp = urllib2.urlopen(
            urllib2.Request(url, request.raw_post_data, {
                'Content-Type': request.META['CONTENT_TYPE']
            }))
    else:
        rsp = urllib2.urlopen(url)

    httprsp = HttpResponse(rsp.read())
    if rsp.info().has_key('Content-Type'):
        httprsp['Content-Type'] = rsp.info()['Content-Type']
    else:
        httprsp['Content-Type'] = 'text/plain'

    rsp.close()

    return httprsp


@csrf_exempt
def session(request):
    status = {'success': False, 'message': 'Unspecified error.'}
    user = request.user

    try:
        user = User.objects.get(username=user)
    except:
        status['message'] = 'No user found.'
        return HttpResponse(json.dumps(status))

    sessions = Session.objects.all()
    count = 0
    for session in sessions:
        decoded = session.get_decoded()
        if '_auth_user_id' in decoded and decoded['_auth_user_id'] == user.id:
            Session.objects.filter(session_key=session.session_key).delete()
            count += 1

    status['success'] = True
    status['message'] = 'Deleted %d sessions.' % count
    return HttpResponse(json.dumps(status))
