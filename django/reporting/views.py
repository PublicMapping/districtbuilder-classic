"""
Django views used by the redistricting application.

The methods in redistricting.views define the views used to interact with
the models in the redistricting application. Each method relates to one 
type of output url. There are views that return GeoJSON, JSON, and HTML.

This file is part of The Public Mapping Project
http://sourceforge.net/projects/publicmapping/

License:
    Copyright 2010 Micah Altman, Michael McDonald

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
from django.utils import simplejson as json
from django.views.decorators.csrf import csrf_exempt
from django.core.cache import cache
from rpy2 import robjects
from rpy2.robjects import r, rinterface
from rpy2.rlike import container as rpc
from decimal import *
import settings, threading, traceback, os, sys, time

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
        r.library('rgeos')
        r.library('gpclib')
        r.library('BARD')
        r.library('R2HTML')
        r.gpclibPermit()

        global bardmap
        bardmap = r.readBardMap(settings.BARD_BASESHAPE)

        global bardWorkSpaceLoaded
        bardWorkSpaceLoaded = True

        if settings.DEBUG:
            print 'Workspace loaded: %s' % bardWorkSpaceLoaded
            r('trace(PMPreport, at=1, tracer=function()print(sys.calls()))')

    except Exception as e:
        sys.stderr.write('BARD Could not be loaded.  Check your configuration and available memory')
        return

# A flag that indicates that the workspace was loaded
bardWorkSpaceLoaded = False
# An object that holds the bardmap for later analysis
bardmap = {}
# The loading thread for the BARD setup
bardLoadingThread = threading.Thread(target=load_bard_workspace, name='loading_bard')

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
        msg += 'mod_wsgi.application_group = "%s"' % request.META['mod_wsgi.application_group']
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
    elif threaded and not bardWorkSpaceLoaded and settings.REPORTS_ENABLED:
        bardLoadingThread.daemon = True
        bardLoadingThread.start()
        msg = 'Building bard workspace now\n%s' % msg
    else:
        msg = 'Bard will not be loaded - wrong server config or reports off.\n%s' % msg

    return HttpResponse(msg, mimetype='text/plain')


def get_named_vector(parameter_string, tag = None):
    """
    Helper method to break up the strings that represents lists of 
    variables.
    
    Parameters:
        parameter_string -- A string of parameters
        
    Returns:
        A StrVector with names, suitable for rpy2 use.
    """
    vec = robjects.StrVector(())
    extras = parameter_string.split('^')
    for extra in extras:
        pair = extra.split('|')
        vec += r('list("%s"="%s")' % (pair[0], pair[1]))
    return vec

def drop_error(tempdir, basename, msg):
    """
    Drop an error .html output file and clean up the .pending file.
    """
    output = os.open('%s/%s.html' % (tempdir, basename,), 'w')
    output.write("""<html>
<h1>Error Generating Report</h1>
<p>Your report could not be generated. Please try again.</p>
<!-- Exception message:

%s

-->
""" % msg)
    output.close()
    os.unlink('%s/%s.pending' % (tempdir, basename,))

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

    status = { 'status': 'failure' }
    stamp = request.POST.get('stamp','')

    # set up the temp dir and filename
    tempdir = settings.BARD_TEMP
    basename = '%s_p%d_v%d_%s' % (request.POST['plan_owner'], int(request.POST['plan_id']), int(request.POST['plan_version']), stamp)

    if not bardWorkSpaceLoaded:
        if not settings.REPORTS_ENABLED:
            status['reason'] = 'Reports functionality is turned off.'

            if settings.DEBUG:
                print "Quitting request, because BARD is not ready."

            drop_error(tempdir, basename, 'BARD is not enabled.')
            return HttpResponse(json.dumps(status),mimetype='application/json')
        else:
            status['reason'] = 'Reports functionality is not ready. Please try again later.'
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
                return HttpResponse(json.dumps(status), mimetype='application/json') 
    #Get the variables from the request
    if request.method != 'POST':
        status['reason'] = 'Information for report wasn\'t sent via POST'
        if settings.DEBUG:
            print "Quitting request, because the request wasn't POSTed."
        drop_error(tempdir, basename, 'Requested items were not delivered via POST.')
        return HttpResponse(json.dumps(status),mimetype='application/json')

    sorted_district_list = request.POST.get('district_list').split(';')

    if settings.DEBUG:
        print "Got district list, getting other POSTed stuff."

    global bardmap
    try:
        # Now we need an R Vector
        block_ids = robjects.IntVector(sorted_district_list)
        bardplan = r.createAssignedPlan(bardmap, block_ids)
    except Exception as ex:
        status['reason'] = 'Could not create BARD plan from map.'
        if settings.DEBUG:
            print traceback.format_exc()
        drop_error(tempdir, basename, 'Could not create BARD plan from map.')
        return HttpResponse(json.dumps(status),mimetype='application/json')

    if settings.DEBUG:
        print "Created assigned plan."

    try: 
        # assign names to the districts
        sorted_name_list = robjects.StrVector(())
        names = request.POST.get('district_names').split(';')
        for district in names:
            sorted_name_list += district
        bardplan.do_slot_assign('levels', sorted_name_list)

        # Get the other report variables from the POST request.  We'll only add
        # them to the report if they're in the request
        popVar = request.POST.get('pop_var', None)
        if settings.DEBUG:
            print 'popVar',popVar
        if popVar:
            pop_var = get_named_vector(popVar)
            pop_var += r('list("tolerance"=.01)')
        else:
            pop_var = r('as.null()')

        popVarExtra = request.POST.get('pop_var_extra', None)
        if settings.DEBUG:
            print 'popVarExtra',popVarExtra
        if popVarExtra:
            pop_var_extra = get_named_vector(popVarExtra)
        else:
            pop_var_extra = r('as.null()')
        
        post_list = request.POST.get('ratio_vars').split(';')
        if settings.DEBUG:
            print 'post_list',post_list
        if len(post_list) > 0 and post_list[0] != '':
            ratioVars = robjects.StrVector(())
            # Each of the ratioVars should have been posted as a list of items separated by
            # double pipes
            for ratioVar in post_list:
                ratioAttributes = ratioVar.split('||')
                rVar = robjects.StrVector(())
                rVar += r('list("denominator"=%s)' % get_named_vector(ratioAttributes[0]).r_repr())
                rVar += r('list("threshold"=%s)' % ratioAttributes[1])
                rVar += r('list("numerators"=%s)' % get_named_vector(ratioAttributes[2]).r_repr())
                ratioVars += r('list("%s"=%s)' % (ratioAttributes[3], rVar.r_repr()))

            ratio_vars = ratioVars
        else:
            ratio_vars = r('as.null()')

        splitVars = request.POST.get('split_vars', None)
        if settings.DEBUG:
            print 'splitVars',splitVars
        if splitVars:
            split_vars = get_named_vector(splitVars)
        else:
            split_vars = r('as.null()')
        
        blockLabelVar = request.POST.get('block_label_var', 'CTID')
        if settings.DEBUG:
            print 'blockLabelVar',blockLabelVar

        repCompactness = request.POST.get('rep_comp', None)
        if settings.DEBUG:
            print 'repCompactness',repCompactness
        if 'true' == repCompactness:
            rep_compactness = r(True)
        else:
            rep_compactness = r(False)

        repCompactnessExtra = request.POST.get('rep_comp_extra', None)
        if settings.DEBUG:
            print 'repCompactnessExtra',repCompactnessExtra
        if 'true' == repCompactnessExtra:
            rep_compactness_extra = r(True)
        else:
            rep_compactness_extra = r(False)

        repSpatial = request.POST.get('rep_spatial', None)
        if settings.DEBUG:
            print 'repSpatial',repSpatial
        if 'true' == repSpatial:
            rep_spatial = r(True)
        else:
            rep_spatial = r(False)

        repSpatialExtra = request.POST.get('rep_spatial_extra', None)
        if settings.DEBUG:
            print 'repSpatialExtra',repSpatialExtra
        if 'true' == repSpatialExtra:
            rep_spatial_extra = r(True)
        else:
            rep_spatial_extra = r(False)
    except Exception as ex:
        if settings.DEBUG:
            print traceback.format_exc()
        status['reason'] = 'Exception: %s' % traceback.format_exc()
        drop_error(tempdir, basename, traceback.format_exc())
        return HttpResponse(json.dumps(status),mimetype='application/json')

    if settings.DEBUG:
        print "Variables loaded, starting BARD."

    try:
        r.copyR2HTMLfiles(tempdir)
        report = r.HTMLInitFile(tempdir, filename=basename, BackGroundColor="#BBBBEE", Title="Plan Analysis")
        title = r['HTML.title']
        r['HTML.title']("Plan Analysis", HR=2, file=report)
        # Now write the report to the temp dir
        r.PMPreport( bardplan, block_ids, file = report, popVar = pop_var, popVarExtra = pop_var_extra, ratioVars = ratio_vars, splitVars = split_vars, repCompactness = rep_compactness, repCompactnessExtra = rep_compactness_extra, repSpatial = rep_spatial, repSpatialExtra = rep_spatial_extra)
        r.HTMLEndFile()

        if settings.DEBUG:
            print "Removing pending file."

        os.unlink('%s/%s.pending' % (tempdir, basename))

        status['status'] = 'success'
        status['retval'] = '%s.html' % basename
    except Exception as ex:
        if settings.DEBUG:
            print traceback.format_exc()
        status['reason'] = 'Exception: %s' % ex
        drop_error(tempdir, basename, traceback.format_exc())

    return HttpResponse(json.dumps(status),mimetype='application/json')

@csrf_exempt
def index(request):
    global bardWorkSpaceLoaded
    return HttpResponse('Greetings from the BARD Report server.\n(Reporting:%s)' % bardWorkSpaceLoaded, mimetype='text/plain')
