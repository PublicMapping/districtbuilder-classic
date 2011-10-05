"""
Utilities for the redistricting application: format conversion,
useful database queries, etc.

This file is part of The Public Mapping Project
https://github.com/PublicMapping/

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
    Andrew Jennings, David Zwarg
"""

from celery.decorators import task
from celery.task.http import HttpDispatchTask
from django.core import management
from django.contrib.comments.models import Comment
from django.contrib.sessions.models import Session
from django.core.mail import send_mail, mail_admins, EmailMessage
from django.template import loader, Context as DjangoContext
from django.db.models import Sum, Min, Max
from redistricting.models import *
from tagging.utils import parse_tag_input
from tagging.models import Tag, TaggedItem
import csv, time, zipfile, tempfile, os, sys, traceback, time
from datetime import datetime
import socket, urllib

# all for shapefile exports
from glob import glob
from django.contrib.gis.gdal import check_err, OGRGeomType, Driver, OGRGeometry, SpatialReference, CoordTransform
from django.contrib.gis.gdal.libgdal import lgdal
from ctypes import c_double


class DistrictFile():
    """
    A utility class that can check exported file status. DistrictIndexFile and
    DistrictShapeFile use this utility class to export block correspondence
    and shape files, respectively.
    """

    @staticmethod
    def get_file_name(plan, shape=False):
        """
        Given a plan, generate a temporary file name.

        Parameters:
            plan - the Plan for which a file has been requested
            shape - a flag indicating if this is to be a shapefile; defaults to False
        """
        basename = "%s/plan%dv%d" % (tempfile.gettempdir(), plan.id, plan.version)
        if shape:
            basename += '-shp'
        return basename

    @staticmethod
    def get_file_status(plan, shape=False):
        """
        Given a plan, this method will check to see whether the district file
        for the given plan exists, is pending, or has not been created.
        
        Parameters:
            plan - the Plan for which a file has been requested
            shape - a flag indicating if this is to be a shapefile; defaults to False

        Returns:
            A string representing the file's status: "none", "pending", "done"
        """
        basename = DistrictFile.get_file_name(plan,shape)
        if os.path.exists(basename + '.zip'):
            return 'done'
        if os.path.exists(basename + '_pending.zip'):
            return 'pending'
        else:
            return 'none'

    @staticmethod
    def get_file(plan, shape=False):
        """
        Given a plan, return the district file for the plan at the current version.
        
        Parameters:
            plan - the Plan for which a file has been requested.
            shape - a flag indicating if this is to be a shapefile; defaults to False

        Returns:
            A file object representing the district file. If the file requested 
            doesn't exist, nothing is returned.
        """
        if (DistrictFile.get_file_status(plan,shape) == 'done'):
            district_file = open(DistrictFile.get_file_name(plan,shape) + '.zip', 'r')
            district_file.close()
            return district_file

class DistrictIndexFile():
    """
    The publicmapping projects supports users importing and exporting
    their plans to district index files.  These two-column, csv-formatted
    files list all of the base geounits in a plan and to which district they
    belong.  

    These files may be uploaded or downloaded in .zip format. The files
    should not contain a header row - rows which do not contain a 
    portable id from the database will be ignored.
    """

    @staticmethod
    @task
    def index2plan(name, body, filename, owner=None, template=False, purge=False, email=None):
        """
        Imports a plan using a district index file in csv format. 
        There should be only two columns: a CODE matching the 
        portable ids of geounits and a DISTRICT integer
        representing the district to which the geounit should belong.

        Parameters:
            name - The name of the Plan.
            filename - The path to the district index file.
            owner - Optional. The user who owns this plan. If not 
                specified, defaults to the system admin.
            template - Optional. A flag indicating that this new plan
                is a template that other users can instantiate.
            purge - Optional. A flag indicating that the index file that
                was converted should be disposed.
            email - Optional. If provided, feedback should be directed
                through email, otherwise, output to the console.
        """

        if email:
            error_subject = "Problem importing your uploaded file."
            success_subject = "Upload and import plan confirmation."
            admin_subject = "Problem importing user uploaded file."
            
            context = DjangoContext({
                'user': owner,
                'errors': list()
            })
        
        # Is this filename a zip archive?
        if filename.endswith('.zip'):
            try:
                archive = zipfile.ZipFile(filename,'r')

                # Does the zip file contain more than one entry?
                if len(archive.namelist()) > 1:
                    archive.close()
                    if purge:
                        os.unlink(filename)

                    if email:
                        context['errors'].append({'message': 'The zip file contains too many files', 'traceback': None})
                        # report error to owner
                        email_template = loader.get_template('error.email')
                        send_mail(error_subject, email_template.render(context), settings.EMAIL_HOST_USER, [email], fail_silently=False)
                        # report error to admin
                        email_template = loader.get_template('admin.email')
                        mail_admins(admin_subject, email_template.render(context))
                    else:
                        sys.stderr.write('District Index .zip file contains too many files.\n')
                    return

                item = archive.namelist()[0]
                # Does the first entry in the zipfile end in ".csv"?
                if not item.endswith('.csv'):
                    archive.close()
                    if purge:
                        os.unlink(filename)

                    if email:
                        context['errors'].append({'message': 'The zip file must contain a comma separated value (.csv) file.', 'traceback': None})

                        # report error to owner
                        email_template = loader.get_template('error.email')
                        send_mail(error_subject, email_template.render(context), settings.EMAIL_HOST_USER, [email], fail_silently=False)
                        # report error to admin
                        email_template = loader.get_template('admin.email')
                        mail_admins(admin_subject, email_template.render(context))
                    else:
                        sys.stderr.write('District Index .zip file does not contain a .csv file.\n')

                    return

                # Now extract entry
                dest = tempfile.NamedTemporaryFile(mode='w+b+', delete=False)

                # Open the item in the archive
                indexItem = archive.open(item)
                for line in indexItem:
                    # Write the archive data to the filesystem
                    dest.write(line)
                # Close the item in the archive
                indexItem.close()
                # Close the filesystem (extracted) item
                dest.close()
                # Close the archive
                archive.close()

                if purge:
                    os.unlink(filename)

                indexFile = dest.name

            except Exception as ex:
                if email:
                    context['errors'].append({'message': 'Unexpected error during zip file processing', 'traceback': traceback.format_exc()}) 
                    # report error to owner
                    email_template = loader.get_template('error.email')
                    send_mail(error_subject, email_template.render(context), settings.EMAIL_HOST_USER, [email], fail_silently=False)
                    # report error to admin
                    email_template = loader.get_template('admin.email')
                    mail_admins(admin_subject, email_template.render(context))
                else:
                    sys.stderr.write('The .zip file could not be imported:\n%s\n' % traceback.format_exc())

                if purge:
                    # Some problem opening the zip file, bail now
                    os.unlink(filename)
                return
       
        else: # filename.endswith('.csv'):
            indexFile = filename

        try:
            legislative_body = LegislativeBody.objects.get(id=int(body))
        except:
            raise Exception('body parameter could not be cast to an integer. Type: %s, %s' % (type(body), body))
        
        plan = Plan.create_default(name, legislative_body, owner=owner, template=template, is_pending=True, create_unassigned=False)

        if not plan:
            if email:
                context['errors'].append({'message': 'Plan couldn\'t be created. Be sure the plan name is unique.', 'tracback': None })
                template = loader.get_template('error.email')
                send_mail(error_subject, template.render(context), settings.EMAIL_HOST_USER, [email], fail_silently=False)
                template = loader.get_template('admin.email')
                mail_admins(error_subject, template.render(context))
            else:
                sys.stderr.write('The plan "%s" could not be created:\n%s\n' % (name, traceback.format_exc()))
            return
                
        # initialize the dicts we'll use to store the portable_ids,
        # keyed on the district_id of this plan
        new_districts = dict()
        num_members = dict()
        community_labels = dict()
        community_types = dict()
        community_comments = dict()
        csv_file = open(indexFile)
        reader = csv.DictReader(csv_file, fieldnames = ['code', 'district', 'num_members', 'label', 'types', 'comments'])
        for row in reader:
            try:
                dist_id = int(row['district'])
                # If the district key is present, add this row's code; 
                # else make a new list
                if dist_id in new_districts:
                    new_districts[dist_id].append(str(row['code']))
                else:
                    new_districts[dist_id] = list()
                    new_districts[dist_id].append(str(row['code']))

                    # num_members may not exist in files exported before the column was added
                    num_members[dist_id] = int(row['num_members']) if row['num_members'] else 1

                    # community components are only present on community plans
                    if row['label']:
                        community_labels[dist_id] = row['label']
                    if row['types']:
                        community_types[dist_id] = row['types']
                    if row['comments']:
                        community_comments[dist_id] = row['comments']
                    
            except Exception as ex:
                if email:
                    context['errors'].append({
                        'message': 'Did not import row:\n  "%s, %s"\n' % (row['code'], row['district']),
                        'traceback': traceback.format_exc()
                    })
                else:
                    sys.stderr.write("Did not import row:\n  '%s'\nReason:\n  %s\n" % (row, traceback.format_exc()))
        csv_file.close()

        if purge:
            os.unlink(indexFile)
        # Get all subjects - those without denominators first to save a calculation
        subjects = Subject.objects.order_by('-percentage_denominator').all()

        # Determine if this is a community plan
        is_community = bool(community_labels)
        ct = ContentType.objects.get(app_label='redistricting',model='district')        

        # Create the district geometry from the lists of geounits
        for district_id in new_districts.keys():
            # Get a filter using portable_id
            code_list = new_districts[district_id]
            guFilter = Q(portable_id__in = code_list)

            try:
                # Build our new geometry from the union of our geounit geometries
                new_geom = Geounit.objects.filter(guFilter).unionagg()
                
                # Create a new district and save it
                name = community_labels[district_id] if is_community else legislative_body.member % district_id 
                new_district = District(name=name,
                    district_id = district_id, plan=plan, num_members=num_members[district_id],
                    geom=enforce_multi(new_geom))
                new_district.simplify() # implicit save

                # Add community fields if this is a community plan
                if is_community:
                    # Add comments
                    if district_id in community_comments:
                        comments_str = community_comments[district_id]
                    if comments_str:
                        comment = Comment(object_pk=new_district.id, content_type=ct, site_id=1, user_name=owner, user_email=email, comment=comments_str)
                        comment.save()

                    # Add types
                    if district_id in community_types:
                        types_str = community_types[district_id]
                    if types_str:
                        for strtag in types_str.split('|'):
                            if strtag:
                                Tag.objects.add_tag(new_district, 'type=%s' % strtag)
                
            except Exception as ex:
                if email:
                    context['errors'].append({
                        'message': 'Unable to create district %s.' % district_id,
                        'traceback': traceback.format_exc()
                    })
                else:
                    sys.stderr.write('Unable to create district %s.\nReason:\n  %s\n' % (district_id, traceback.format_exc()))
                continue
        
            # For each district, create the ComputedCharacteristics
            geounit_ids = Geounit.objects.filter(guFilter).values_list('id', flat=True).order_by('id')
            for subject in subjects:
                try:
                    cc_value = Characteristic.objects.filter(
                        geounit__in = geounit_ids, 
                        subject = subject).aggregate(Sum('number'))
                    value = cc_value['number__sum']
                    percentage = '0000.00000000'

                    if value is not None:
                        if subject.percentage_denominator:
                            # The denominator's CC should've already been saved
                            denominator_value = ComputedCharacteristic.objects.get(
                                subject = subject.percentage_denominator,
                                district = new_district).number
                            percentage = value / denominator_value

                        # sys.stderr.write('Aggregating value for %s: %s' % (subject, cc_value))
                        cc = ComputedCharacteristic(subject = subject, 
                            number = value, 
                            percentage = percentage,
                            district = new_district)
                        cc.save()
                    else:
                        sys.stderr.write('Unable to create ComputedCharacteristic for Subject: %s. Skipping subject\n' % subject.name)
                        continue
                except Exception as ex:
                    if email:
                        context['errors'].append({
                            'message': 'Unable to create ComputedCharacteristic for district %s, subject %s' % (district_id, subject.name),
                            'traceback': None
                        })
                    else:
                        sys.stderr.write('Unable to create ComputedCharacteristic for district %s, subject %s\nReason:\n  %s\n' % (district_id, subject.name, traceback.format_exc()))

        # Now that all of our other districts exist, create an unassigned district
        plan.create_unassigned = True
        create_unassigned_district(plan, instance=plan, created=True)
        # this plan is complete, and no longer pending
        plan.is_pending = False
        plan.save()

        if email:
            context['plan'] = plan
            # Plan operations completed successfully. It's unclear if the
            # accumulated messages are problems or not. Let's assume they are.

            if len(context['errors']) > 0:
                template = loader.get_template('admin.email')
                mail_admins(admin_subject, template.render(context))

            template = loader.get_template('importedplan.email')
            send_mail(success_subject, template.render(context), settings.EMAIL_HOST_USER, [email], fail_silently=False)

    @staticmethod
    @task
    def plan2index (plan):
        """
        Gets a zipped copy of the district index file for the
        given plan.

        Parameters:
            plan - The plan for which to get an index file
        
        Returns:
            A file object representing the zipped index file
        """
        status = DistrictFile.get_file_status(plan)
        while status == 'pending':
            time.sleep(15)
            status = DistrictFile.get_file_status(plan)
        if status == 'none':
            pending = DistrictFile.get_file_name() + '_pending.zip'
            archive = open(pending, 'w')
            f = tempfile.NamedTemporaryFile(delete=False)
            try:
                units = plan.get_base_geounits()

                # csv layout: portable id, district id, num members, label, types, comments
                # the final three are only written when the plan is a community
                if not plan.is_community():
                    mapping = [(pid, did, members) for (gid, pid, did, members) in units]
                else:
                    # create a map of district_id -> tuple of community details
                    dm = {}
                    ct = ContentType.objects.get(app_label='redistricting',model='district')
                    for district in plan.get_districts_at_version(plan.version, include_geom=False):
                        if district.district_id > 0:
                            types = Tag.objects.get_for_object(district).filter(name__startswith='type=')
                            types = '|'.join([t.name[5:] for t in types])
                            comments = Comment.objects.filter(object_pk__in=[str(district.id)],content_type=ct)
                            comments = comments[0].comment if len(comments) > 0 else ''
                            dm[district.district_id] = (district.name, types, comments)
                    mapping = [(pid, did, members, dm[did][0], dm[did][1], dm[did][2]) for (gid, pid, did, members) in units]
                
                difile = csv.writer(f)
                difile.writerows(mapping)
                f.close()

                # Zip up the file 
                zipwriter = zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED)
                zipwriter.write(f.name, plan.get_friendly_name() + '.csv')
                zipwriter.close()
                archive.close()
                os.rename(archive.name, DistrictFile.get_file_name(plan) + '.zip')
            except Exception as ex:
                sys.stderr.write('The plan "%s" could not be serialized to a district index file:\n%s\n' % (plan.name, traceback.format_exc()))
                os.unlink(archive.name)
            # delete the temporary csv file
            finally:
                os.unlink(f.name)

        return DistrictFile.get_index_file(plan)

    @staticmethod
    @task
    def emailfile(plan, user, post):
        # Create the file (or grab it if it already exists)
        archive = DistrictIndexFile.plan2index(plan)

        # Add it as an attachment and send the email
        template = loader.get_template('submission.email')
        context = DjangoContext({ 'user': user, 'plan': plan, 'post': post })
        email = EmailMessage()
        email.subject = 'Competition submission (user: %s, planid: %d)' % (user.username, plan.pk)
        email.body = template.render(context)
        email.from_email = settings.EMAIL_HOST_USER
        email.to = [settings.EMAIL_SUBMISSION]
        email.attach_file(archive.name)
        email.send()

        # Send a confirmation email to the user
        subject = "Plan submitted successfully"
        user_email = post['email']
        template = loader.get_template('submitted.email')
        context = DjangoContext({ 'user': user, 'plan': plan })
        send_mail(subject, template.render(context), settings.EMAIL_HOST_USER, [user_email], fail_silently=False)


class DistrictShapeFile():
    """
    The publicmapping projects supports users exporting their plans to 
    shape files.  These files list all of the districts, their geometries,
    and the computed characteristics of the plan's districts.

    These files may be downloaded in .zip format.
    """

    @staticmethod
    @task
    def plan2shape(plan):
        """
        Gets a zipped copy of the plan shape file.

        Parameters:
            plan - The plan for which to get a shape file
        
        Returns:
            A file object representing the zipped shape file
        """
        exportFile = None
        status = DistrictFile.get_file_status(plan,True)
        while status == 'pending':
            time.sleep(15)
            status = DistrictFile.get_file_status(plan,True)
        if status == 'none':
            pending = DistrictFile.get_file_name(plan, True) + '_pending.zip'
            archive = open(pending, 'w')
            try:
                qset = District.objects.filter(plan=plan,version__lte=plan.version)
                qset = qset.values('district_id')
                qset = qset.annotate(latest=Max('version'),max_id=Max('id'))
                qset = qset.values_list('max_id',flat=True)

                # Create a named temporary file
                exportFile = tempfile.NamedTemporaryFile(suffix='.shp', mode='w+b')
                exportFile.close()

                # Get the districts in the plan
                districts = District.objects.filter(id__in=qset)

                # Open a driver, and create a data source
                driver = Driver('ESRI Shapefile')
                datasource = lgdal.OGR_Dr_CreateDataSource(driver._ptr, exportFile.name, None)

                # Get the geometry field
                geo_field = filter(lambda x: x.name=='geom', District._meta.fields)[0]

                # Determine the geometry type from the field
                ogr_type = OGRGeomType(geo_field.geom_type).num
                # Get the spatial reference
                native_srs = SpatialReference(geo_field.srid)
                #Create a layer
                layer = lgdal.OGR_DS_CreateLayer(datasource, 'District', native_srs._ptr, ogr_type, None)

                # Set up mappings of field names for export, as well as shapefile
                # column aliases (only 8 characters!)
                (OGRInteger,OGRReal,OGRString,) = (0,2,4,)
                dfieldnames = ['id', 'district_id', 'name', 'version', 'num_members']
                sfieldnames = list(Subject.objects.all().values_list('name',flat=True))
                aliases = {'district_id':'dist_num', 'num_members':'nmembers'}
                ftypes = {'id':OGRInteger, 'district_id':OGRInteger, 'name':OGRString, 'version':OGRInteger, 'num_members':OGRInteger}

                # set the district attributes
                for fieldname in dfieldnames + sfieldnames:
                    # default to double data types, unless the field type is defined
                    ftype = OGRReal
                    if fieldname in ftypes:
                        ftype = ftypes[fieldname]

                    # customize truncated field names
                    if fieldname in aliases:
                        fieldname = aliases[fieldname]

                    # create the field definition
                    fld = lgdal.OGR_Fld_Create(str(fieldname), ftype)
                    # add the field definition to the layer
                    added = lgdal.OGR_L_CreateField(layer, fld, 0)
                    check_err(added)

                # get all the field definitions for the new layer
                feature_definition = lgdal.OGR_L_GetLayerDefn(layer)

                # begin exporting districts
                for district in districts:
                    # create a feature
                    feature = lgdal.OGR_F_Create(feature_definition)

                    # attach each field from the district model
                    for idx, field in enumerate(dfieldnames):
                        value = getattr(district,field)
                        ftype = ftypes[field]
                        if ftype == OGRInteger:
                            lgdal.OGR_F_SetFieldInteger(feature, idx, int(value))
                        elif ftype == OGRString:
                            lgdal.OGR_F_SetFieldString(feature, idx, str(value))

                    # attach each field for the subjects that relate to this model
                    for idx, sname in enumerate(sfieldnames):
                        try:
                            subject = district.computedcharacteristic_set.get(subject__name=sname)
                        except:
                            subject = 0.0
                        lgdal.OGR_F_SetFieldDouble(feature, idx+len(dfieldnames), c_double(subject.number))

                    # convert the geos geometry to an ogr geometry
                    geometry = OGRGeometry(district.geom.wkt, native_srs)
                    # save the geometry to the feature
                    added = lgdal.OGR_F_SetGeometry(feature, geometry._ptr)
                    check_err(added)

                    # add the feature to the layer
                    added = lgdal.OGR_L_SetFeature(layer, feature)
                    check_err(added)

                # clean up ogr
                lgdal.OGR_L_SyncToDisk(layer)
                lgdal.OGR_DS_Destroy(datasource)
                lgdal.OGRCleanupAll()

                # Zip up the file 
                zipwriter = zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED)
                exportedFiles = glob(exportFile.name[:-4] + '*')
                for exp in exportedFiles:
                    zipwriter.write(exp, '%sv%d%s' % (plan.get_friendly_name(), plan.version, exp[-4:]))
                zipwriter.close()
                archive.close()
                os.rename(archive.name, DistrictFile.get_file_name(plan,True) + '.zip')
            except Exception as ex:
                sys.stderr.write('The plan "%s" could not be saved to a shape file:\n%s\n' % (plan.name, traceback.format_exc()))
                os.unlink(archive.name)
            # delete the temporary csv file
            finally:
                if not exportFile is None:
                    exportedFiles = glob(exportFile.name[:-4] + '*')
                    for exp in exportedFiles:
                        os.remove(exp)

        return DistrictFile.get_file(plan,True)

@task
def cleanup():
    """
    Clean out all the old sessions.

    Old sessions are sessions whose expiration date is in the past.
    """
    management.call_command('cleanup') 

class PlanReport:
    """
    A collection of static methods that assist in asynchronous report
    generation.
    """

    @staticmethod
    @task
    def createreport(planid, stamp, request):
        """
        Create the data structures required for a BARD report, and call
        the django reporting apache process to create the report.
        """
        if settings.DEBUG:
            sys.stderr.write('Starting task to create a report.\n')
        try:
            plan = Plan.objects.get(pk=planid)
        except:
            sys.stderr.write("Couldn't retrieve plan information.\n")
            return 

        tempdir = settings.BARD_TEMP
        filename = '%s_p%d_v%d_%s' % (plan.owner.username, plan.id, plan.version, stamp)

        if settings.DEBUG:
            sys.stderr.write('Getting base geounits.\n')

        # Get the district mapping and order by geounit id
        mapping = plan.get_base_geounits()
        mapping.sort(key=lambda unit: unit[0])

        # Get the geounit ids we'll be iterating through
        geolevel = plan.legislative_body.get_base_geolevel()
        geounits = Geounit.objects.filter(geolevel=geolevel)
        max_and_min = geounits.aggregate(Min('id'), Max('id'))
        min_id = int(max_and_min['id__min'])
        max_id = int(max_and_min['id__max'])

        if settings.DEBUG:
            sys.stderr.write('Getting district mapping.\n')

        # Iterate through the query results to create the district_id list
        # This ordering depends on the geounits in the shapefile matching the 
        # order of the imported geounits. If this ordering is the same, the 
        # geounits' ids don't have to match their fids in the shapefile
        sorted_district_list = list()
        row = None
        if len(mapping) > 0:
             row = mapping.pop(0)
        for i in range(min_id, max_id + 1):
            if row and row[0] == i:
                district_id = row[2]
                row = None
                if len(mapping) > 0:
                    row = mapping.pop(0)
            else:
                district_id = 'NA'
            sorted_district_list.append(str(district_id))

        if settings.DEBUG:
            sys.stderr.write('Getting POST variables and settings.')
        
        info = plan.get_district_info()
        names = map(lambda i:i[0], info)
        nseats = map(lambda i:i[1], info) # can't do it in the lambda
        nseats = reduce(lambda x,y: x+y, nseats, 0)
        # needs to be a str because of join() below
        magnitude = map(lambda i:str(i[1]), info)

        if settings.DEBUG:
            sys.stderr.write('Firing web worker task.')

        dispatcher = HttpDispatchTask()

        # Callbacks do not fire for HttpDispatchTask -- why not?
        #
        #def failure(self, exc, task_id, args, kwargs, einfo=None):
        #    self.log.get_default_logger().info('  CALLBACK: Failure!')
        #def success(self, retval, task_id, args, kwargs):
        #    self.log.get_default_logger().info('  CALLBACK: Success!')
        #
        #dispatcher.on_failure = failure
        #dispatcher.on_success = success

        # Increase the default timeout, just in case
        socket.setdefaulttimeout(600)

        result = dispatcher.delay(
            url = settings.BARD_SERVER + '/getreport/',
            method='POST',
            plan_id=planid,
            plan_owner=plan.owner.username,
            plan_version=plan.version,
            district_list=';'.join(sorted_district_list),
            district_names=';'.join(names),
            district_mags=';'.join(magnitude),
            nseats=nseats,
            pop_var=request['popVar'],
            pop_var_extra=request['popVarExtra'],
            ratio_vars=';'.join(request['ratioVars[]']),
            split_vars=request['splitVars'],
            block_label_var=request['blockLabelVar'],
            rep_comp=request['repComp'],
            rep_comp_extra=request['repCompExtra'],
            rep_spatial=request['repSpatial'],
            rep_spatial_extra=request['repSpatialExtra'],
            stamp=stamp)
        return

    @staticmethod
    def checkreport(planid, stamp):
        """
        Check on the status of a BARD report.
        """
        try:
            plan = Plan.objects.get(pk=planid)
        except:
            return 'error'

        tempdir = settings.BARD_TEMP
        filename = '%s_p%d_v%d_%s' % (plan.owner.username, plan.id, plan.version, stamp)

        pending_file = '%s/%s.pending' % (tempdir, filename)
        if os.path.exists(pending_file):
            # If the reports server is on another machine
            if not 'localhost'  in settings.BARD_SERVER:
                path = '%s/reports/%s.html' % (settings.BARD_SERVER,filename)
                try:
                    result = urllib.urlopen(path)
                    if result.getcode() == 200:
                        os.unlink(pending_file)
                        return 'ready'
                except:
                    return 'busy'
            return 'busy'
        elif os.path.exists('%s/%s.html' % (tempdir, filename)):
            return 'ready'
        else:
            return 'free'

    @staticmethod
    def markpending(planid, stamp):
        """
        Create a pending file, to indicate that a report is in the works.
        """
        try:
            plan = Plan.objects.get(pk=planid)
        except:
            return 'error'

        tempdir = settings.BARD_TEMP
        filename = '%s_p%d_v%d_%s' % (plan.owner.username, plan.id, plan.version, stamp)

        pending = open('%s/%s.pending' % (tempdir, filename,),'w')
        pending.close()


    @staticmethod
    def getreport(planid, stamp):
        """
        Fetch a previously generated BARD report.
        """
        try:
            plan = Plan.objects.get(pk=planid)
        except:
            return 'error'

        filename = '%s_p%d_v%d_%s' % (plan.owner.username, plan.id, plan.version, stamp)

        return '/reports/%s.html' % filename

class CalculatorReport:
    """
    A collection of static methods that assist in asynchronous report
    generation for calculator-based reports.
    """

    @staticmethod
    @task
    def createcalculatorreport(planid, stamp, request):
        """
        Create the report.
        """
        if settings.DEBUG:
            sys.stderr.write('Starting task to create a report.\n')
        try:
            plan = Plan.objects.get(pk=planid)
        except:
            sys.stderr.write("Couldn't retrieve plan information.\n")
            return 

        function_ids = map(lambda s: int(s), request['functionIds'].split(','))

        try:
            # Render the report
            display = ScoreDisplay.objects.filter(title='%s Reports' % plan.legislative_body.name)[0]
            html = display.render(plan, request, function_ids=function_ids)
        except Exception as ex:
            err = 'Error creating calculator report:\n%s\n' % traceback.format_exc()
            sys.stderr.write(err)
            html = err

        # Add to report container template
        html = loader.get_template('report_panel_container.html').render(DjangoContext({'report_panels': html}))
            
        # Write it to file
        tempdir = settings.CALC_REPORTS_DIR
        filename = '%s_p%d_v%d_%s' % (plan.owner.username, plan.id, plan.version, stamp)
        htmlfile = open('%s/%s.html' % (tempdir, filename,),'w')
        htmlfile.write(html)
        htmlfile.close()
            
        return

    @staticmethod
    def checkreport(planid, stamp):
        """
        Check on the status of a calculator report.
        """
        try:
            plan = Plan.objects.get(pk=planid)
        except:
            return 'error'

        tempdir = settings.CALC_REPORTS_DIR
        filename = '%s_p%d_v%d_%s' % (plan.owner.username, plan.id, plan.version, stamp)
        pending_file = '%s/%s.pending' % (tempdir, filename)
        complete_file = '%s/%s.html' % (tempdir, filename)
        
        if os.path.exists(complete_file):
            if os.path.exists(pending_file):
                os.unlink(pending_file)
            return 'ready'

        if os.path.exists(pending_file):
            return 'busy'
        
        return 'free'

    @staticmethod
    def markpending(planid, stamp):
        """
        Create a pending file, to indicate that a report is in the works.
        """
        try:
            plan = Plan.objects.get(pk=planid)
        except:
            return 'error'

        tempdir = settings.CALC_REPORTS_DIR
        filename = '%s_p%d_v%d_%s' % (plan.owner.username, plan.id, plan.version, stamp)

        pending = open('%s/%s.pending' % (tempdir, filename,),'w')
        pending.close()


    @staticmethod
    def getreport(planid, stamp):
        """
        Fetch a previously generated calculator report.
        """
        try:
            plan = Plan.objects.get(pk=planid)
        except:
            return 'error'

        filename = '%s_p%d_v%d_%s' % (plan.owner.username, plan.id, plan.version, stamp)

        return '/reports/%s.html' % filename
