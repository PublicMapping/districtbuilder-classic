"""
Django views used by the reporting application.

The methods in views define the views used to interact with
the reports in the redistricting application. 

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
    Andrew Jennings, David Zwarg, Kenny Shepard
"""

from django.http import *
from django.utils import simplejson as json, translation
from django.views.decorators.csrf import csrf_exempt
from django.core.cache import cache
from rpy2 import robjects
from decimal import *
import settings, threading, traceback, os, sys, time, tempfile, shutil


def load_bard_workspace():
    """
    Load the workspace and setup R.

    This function is called by the thread loading function. The workspace
    setup incurs a significant amount of overhead and processing time to
    load the basemaps into BARD. This method starts up these processes in
    a separate process & thread, in order to keep the web application 
    responsive during R initialization.
    """
    try:
        robjects.r('library("rgeos")')
        robjects.r('library("gpclib")')
        robjects.r('library("BARD")')
        robjects.r('library("R2HTML")')
        robjects.r('gpclibPermit()')

        robjects.r.assign('bardBasemap', settings.BARD_BASESHAPE)
        robjects.r('bardmap = readBardMap(bardBasemap)')

        global bardWorkSpaceLoaded
        bardWorkSpaceLoaded = True

        if settings.DEBUG:
            print 'Workspace loaded: %s' % bardWorkSpaceLoaded
            robjects.r(
                'trace(PMPreport, at=1, tracer=function()print(sys.calls()))')

    except Exception as e:
        sys.stderr.write(
            'BARD Could not be loaded.  Check your configuration and available memory'
        )
        return


# A flag that indicates that the workspace was loaded
bardWorkSpaceLoaded = False
# The loading thread for the BARD setup
bardLoadingThread = threading.Thread(
    target=load_bard_workspace, name='loading_bard')


@csrf_exempt
def loadbard(request):
    """
    Load BARD and it's workspace.

    BARD is loaded in a separate thread in order to free resources for
    the web processing thread. This method is called by the wsgi application
    setup file, 'reports.wsgi'.

    Parameters:
        request -- An HttpRequest OR True

    Returns:
        A simple text response informing the client what BARD is up to.
    """
    msg = ""

    if type(request) == bool:
        threaded = True
        if settings.DEBUG:
            print 'Boolean request!'
    elif isinstance(request, HttpRequest):
        threaded = request.META['mod_wsgi.application_group'] == 'bard-reports'
        msg += 'mod_wsgi.application_group = "%s"' % request.META[
            'mod_wsgi.application_group']
        if settings.DEBUG:
            print 'HttpRequest request!'
    else:
        msg += 'Unknown request type. %s' % type(request)
        threaded = False

    global bardWorkSpaceLoaded
    if settings.DEBUG:
        print 'Is BARD loaded? %s' % bardWorkSpaceLoaded

    global bardLoadingThread
    if bardWorkSpaceLoaded:
        msg = 'Bard is already loaded\n%s' % msg
    elif bardLoadingThread.is_alive():
        msg = 'Bard is already building\n%s' % msg
    elif threaded and not bardWorkSpaceLoaded and settings.REPORTS_ENABLED == 'BARD':
        bardLoadingThread.daemon = True
        bardLoadingThread.start()
        msg = 'Building bard workspace now\n%s' % msg
    else:
        msg = 'Bard will not be loaded - wrong server config or reports off.\n%s' % msg

    return HttpResponse(msg, content_type='text/plain')


def get_named_vector(parameter_string, rname, tag=None):
    """
    Helper method to break up the strings that represents lists of 
    variables.
    
    Parameters:
        parameter_string -- A string of parameters
        
    Returns:
        A StrVector with names, suitable for rpy2 use.
    """
    if not parameter_string:
        robjects.r('%s = NULL' % rname)
        return

    robjects.r('%s = vector()' % rname)

    extras = parameter_string.split('^')
    for extra in extras:
        pair = extra.split('|')
        if re.match('^[\d\.]+$', pair[1]):
            robjects.r('%s = c(%s, list("%s"=%s))' % (rname, rname, pair[0],
                                                      Decimal(pair[1])))
        else:
            robjects.r('%s = c(%s, list("%s"="%s"))' % (rname, rname, pair[0],
                                                        pair[1]))


def drop_error(tempdir, basename, msg):
    """
    Drop an error .html output file and clean up the .pending file.
    """
    output = open('%s/%s.html' % (
        tempdir,
        basename,
    ), 'w')
    output.write("""<html>
<h1>Error Generating Report</h1>
<p>Your report could not be generated. Please try again.</p>
<!-- Exception message:

%s

-->
""" % msg)
    output.close()
    try:
        os.unlink('%s/%s.pending' % (
            tempdir,
            basename,
        ))
    except:
        return


@csrf_exempt
def getreport(request):
    """
    Get a BARD report.

    This view will write out an HTML-formatted BARD report to the directory
    given in the settings.
    
    Parameters:
        request -- An HttpRequest
    
    Returns:
        The HTML for use as a preview in the web application, along with 
        the web address of the BARD report.
    """
    global bardWorkSpaceLoaded
    if settings.DEBUG:
        print "Generating report. Is BARD loaded? %s" % bardWorkSpaceLoaded

    status = {'status': 'failure'}
    stamp = request.POST.get('stamp', '')

    # set up the temp dir and filename
    tempdir = settings.WEB_TEMP
    basename = '%s_p%d_v%d_%s' % (request.POST['plan_owner'],
                                  int(request.POST['plan_id']),
                                  int(request.POST['plan_version']), stamp)

    if not bardWorkSpaceLoaded:
        if settings.REPORTS_ENABLED != 'BARD':
            status['reason'] = 'Reports functionality is turned off.'

            if settings.DEBUG:
                print "Quitting request, because BARD is not ready."

            drop_error(tempdir, basename, 'BARD is not enabled.')
            return HttpResponse(
                json.dumps(status), content_type='application/json')
        else:
            status[
                'reason'] = 'Reports functionality is not ready. Please try again later.'
            loadbard(True)

            maxwait = 300
            while not bardWorkSpaceLoaded and maxwait > 0:
                if settings.DEBUG:
                    print 'Waiting for BARD to load...'
                maxwait -= 5
                time.sleep(5)

            if maxwait <= 0:
                status['reason'] = 'Waiting for BARD to load timed out.'
                drop_error(tempdir, basename, 'BARD load timed out.')
                return HttpResponse(
                    json.dumps(status), content_type='application/json')
    #Get the variables from the request
    if request.method != 'POST':
        status['reason'] = 'Information for report wasn\'t sent via POST'
        if settings.DEBUG:
            print "Quitting request, because the request wasn't POSTed."
        drop_error(tempdir, basename,
                   'Requested items were not delivered via POST.')
        return HttpResponse(
            json.dumps(status), content_type='application/json')

    sorted_district_list = request.POST.get('district_list').split(';')
    nseat_param = request.POST.get('nseats')
    mag_param = request.POST.get('district_mags').split(';')

    if settings.DEBUG:
        print "Got district list, getting other POSTed stuff."

    try:
        # Now we need an R Vector
        robjects.r.assign('block_ids', sorted_district_list)
        robjects.r.assign('num_seats', int(nseat_param))
        robjects.r.assign('magnitude', mag_param)
        robjects.r(
            'bardplan = createAssignedPlan(bardmap, block_ids, nseats=num_seats, magnitude=magnitude)'
        )
    except Exception as ex:
        status['reason'] = 'Could not create BARD plan from map.'
        if settings.DEBUG:
            print traceback.format_exc()
        drop_error(tempdir, basename, 'Could not create BARD plan from map.')
        return HttpResponse(
            json.dumps(status), content_type='application/json')

    if settings.DEBUG:
        print "Created assigned plan."

    try:
        # assign names to the districts
        robjects.r('sorted_name_list = vector()')
        names = request.POST.get('district_names').split(';')
        for district in names:
            robjects.r(
                'sorted_name_list = c(sorted_name_list,"%s")' % district)
        robjects.r('levels(bardplan) <- sorted_name_list')

        # Get the other report variables from the POST request.  We'll only add
        # them to the report if they're in the request
        popVar = request.POST.get('pop_var', None)
        if settings.DEBUG:
            print 'popVar', popVar
        get_named_vector(popVar, 'popVar')

        popVarExtra = request.POST.get('pop_var_extra', None)
        if settings.DEBUG:
            print 'popVarExtra', popVarExtra
        get_named_vector(popVarExtra, 'popVarExtra')

        post_list = request.POST.get('ratio_vars').split(';')
        if settings.DEBUG:
            print 'post_list', post_list
        if len(post_list) > 0 and post_list[0] != '':
            robjects.r('ratioVars = vector()')
            # Each of the ratioVars should have been posted as a list of items separated by
            # double pipes
            for i, ratioVar in enumerate(post_list):
                ratioAttributes = ratioVar.split('||')
                get_named_vector(ratioAttributes[0], 'rden%d' % i)
                get_named_vector(ratioAttributes[2], 'rnum%d' % i)
                robjects.r("""
ratioVars = 
    c(ratioVars, 
      list("%s"=list(
        "denominator"=rden%d,
        "threshold"=%s,
        "numerators"=rnum%d)
      )
    )
""" % (ratioAttributes[3], i, ratioAttributes[1], i))
        else:
            robjects.r('ratioVars = NULL')

        splitVars = request.POST.get('split_vars', None)
        if settings.DEBUG:
            print 'splitVars', splitVars
        get_named_vector(splitVars, 'splitVars')

        repCompactness = request.POST.get('rep_comp', None)
        if settings.DEBUG:
            print 'repCompactness', repCompactness
        if 'true' == repCompactness:
            robjects.r('repCompactness = TRUE')
        else:
            robjects.r('repCompactness = FALSE')

        repCompactnessExtra = request.POST.get('rep_comp_extra', None)
        if settings.DEBUG:
            print 'repCompactnessExtra', repCompactnessExtra
        if 'true' == repCompactnessExtra:
            robjects.r('repCompactnessExtra = TRUE')
        else:
            robjects.r('repCompactnessExtra = FALSE')

        repSpatial = request.POST.get('rep_spatial', None)
        if settings.DEBUG:
            print 'repSpatial', repSpatial
        if 'true' == repSpatial:
            robjects.r('repSpatial = TRUE')
        else:
            robjects.r('repSpatial = FALSE')

        repSpatialExtra = request.POST.get('rep_spatial_extra', None)
        if settings.DEBUG:
            print 'repSpatialExtra', repSpatialExtra
        if 'true' == repSpatialExtra:
            robjects.r('repSpatialExtra = TRUE')
        else:
            robjects.r('repSpatialExtra = FALSE')
    except Exception as ex:
        if settings.DEBUG:
            print traceback.format_exc()
        status['reason'] = 'Exception: %s' % traceback.format_exc()
        drop_error(tempdir, basename, traceback.format_exc())
        return HttpResponse(
            json.dumps(status), content_type='application/json')

    if settings.DEBUG:
        print "Variables loaded, starting BARD."

    try:
        robjects.r.assign('tempdir', tempdir)
        robjects.r('copyR2HTMLfiles(tempdir)')
        # Write to a temp file so that the reports-checker doesn't see it early
        robjects.r.assign('tempfiledir', tempfile.gettempdir())
        robjects.r.assign('filename', basename)
        robjects.r.assign('locale', translation.get_language())
        robjects.r(
            'report = HTMLInitFile(tempfiledir, filename=filename, BackGroundColor="#BBBBEE", Title="Plan Analysis")'
        )
        robjects.r('HTML.title("Plan Analysis", HR=2, file=report)')
        robjects.r("""PMPreport( bardplan, file=report, 
            popVar=popVar, 
            popVarExtra=popVarExtra, 
            ratioVars=ratioVars, 
            splitVars=splitVars, 
            repCompactness=repCompactness, 
            repCompactnessExtra=repCompactnessExtra,
            repSpatial=repSpatial, 
            repSpatialExtra=repSpatialExtra,
            locale=locale)""")
        robjects.r('HTMLEndFile()')

        # Now move the report back to the reports directory dir
        shutil.move('%s/%s.html' % (tempfile.gettempdir(), basename), tempdir)

        if settings.DEBUG:
            print "Removing pending file."

        try:
            os.unlink('%s/%s.pending' % (tempdir, basename))
        except:
            if settings.DEBUG:
                print "No pending file to remove - report finished"

        status['status'] = 'success'
        status['retval'] = '%s.html' % basename
    except Exception as ex:
        if settings.DEBUG:
            print traceback.format_exc()
        status['reason'] = 'Exception: %s' % ex
        drop_error(tempdir, basename, traceback.format_exc())

    return HttpResponse(json.dumps(status), content_type='application/json')


@csrf_exempt
def index(request):
    global bardWorkSpaceLoaded
    return HttpResponse(
        'Greetings from the BARD Report server.\n(Reporting:%s)' %
        bardWorkSpaceLoaded,
        content_type='text/plain')
