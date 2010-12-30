"""
Utilities for the redistricting application: format conversion,
useful database queries, etc.

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
    Andrew Jennings, David Zwarg
"""

from celery.decorators import task
from django.core.mail import send_mail, mail_admins
from django.template import loader, Context
from redistricting.models import *
import csv, time, zipfile, tempfile, os, sys, traceback


class DistrictIndexFile():
    """
    The publicmapping projects supports users importing and exporting
    their plans to district index files.  These two-column, csv-formatted
    files list all of the base geounits in a plan and to which district they
    belong.  

    These files may be uploaded or downloaded in .zip format. The files
    should not contain a header row - rows which do not contain a 
    supplemental id from the database will be ignored.
    """

    @staticmethod
    @task
    def index2plan(name, body, filename, owner=None, template=False, purge=False, email=None):
        """
        Imports a plan using a district index file in csv format. 
        There should be only two columns: a CODE matching the 
        supplemental ids of geounits and a DISTRICT integer
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
            
            context = Context({
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
                        template = loader.get_template('error.email')
                        send_mail(error_subject, template.render(context), settings.EMAIL_HOST_USER, [email], fail_silently=False)
                        # report error to admin
                        template = loader.get_template('admin.email')
                        mail_admins(admin_subject, template.render(context))
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
                        template = loader.get_template('error.email')
                        send_mail(error_subject, template.render(context), settings.EMAIL_HOST_USER, [email], fail_silently=False)
                        # report error to admin
                        template = loader.get_template('admin.email')
                        mail_admins(admin_subject, template.render(context))
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
                    template = loader.get_template('error.email')
                    send_mail(error_subject, template.render(context), settings.EMAIL_HOST_USER, [email], fail_silently=False)
                    # report error to admin
                    template = loader.get_template('admin.email')
                    mail_admins(admin_subject, template.render(context))
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
        
        plan = Plan.create_default(name, legislative_body, owner=owner, template=template, is_pending=True)

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
                
        # initialize the dicts we'll use to store the supplemental_ids,
        # keyed on the district_id of this plan
        new_districts = dict()
        csv_file = open(indexFile)
        reader = csv.DictReader(csv_file, fieldnames = ['code', 'district']) 
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
        
        subjects = Subject.objects.all()

        # Create the district geometry from the lists of geounits
        for district_id in new_districts.keys():
            # Get a filter using supplemental_id
            code_list = new_districts[district_id]
            guFilter = Q(supplemental_id__in = code_list)

            try:
                # Build our new geometry from the union of our geounit geometries
                new_geom = Geounit.objects.filter(guFilter).unionagg()

                # Create a new district and save it
                new_district = District(name=legislative_body.member % district_id, 
                    district_id = district_id + 1, plan=plan, 
                    geom=enforce_multi(new_geom))
                new_district.simplify() # implicit save
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
                    cc = ComputedCharacteristic(subject = subject, 
                        number = cc_value['number__sum'], 
                        district = new_district)
                    cc.save()
                except Exception as ex:
                    if email:
                        context['errors'].append({
                            'message': 'Unable to create ComputedCharacteristic for district %s, subject %s' % (district_id, subject.name),
                            'traceback': None
                        })
                    else:
                        sys.stderr.write('Unable to create ComputedCharacteristic for district %s, subject %s\nReason:\n  %s\n' % (district_id, subject.name, traceback.format_exc()))

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
    def plan2index (plan, user=None):
        """
        Gets a zipped copy of the district index file for the
        given plan.

        Parameters:
            plan - The plan for which to get an index file
        
        Returns:
            A file object representing the zipped index file
        """
        status = DistrictIndexFile.get_index_file_status(plan)
        while status == 'pending':
            time.sleep(15)
            status = DistrictIndexFile.get_index_file_status(plan)
        if status == 'none':
            pending = ('%s/plan%dv%d_pending.zip' % (tempfile.gettempdir(), plan.id, plan.version)) 
            archive = open(pending, 'w')
            f = tempfile.NamedTemporaryFile(delete=False)
            try:
                # Get the necessary district/geounit map from the db
                cursor = plan.district_mapping_cursor()
                
                difile = csv.writer(f)
                # The cursor is iterable so just write each row as a row in the csv file
                difile.writerows(cursor)
                cursor.close()
                f.close()

                # Zip up the file 
                zipwriter = zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED)
                zipwriter.write(f.name, plan.name + '.csv')
                zipwriter.close()
                archive.close()
                os.rename(archive.name, '%s/plan%dv%d.zip' % (tempfile.gettempdir(), plan.id, plan.version))
            except Exception as ex:
                sys.stderr.write('The plan "%s" could not be serialized to a district index file:\n%s\n' % (plan.name, traceback.format_exc()))
                os.unlink(archive.name)
            # delete the temporary csv file
            finally:
                os.unlink(f.name)

        return DistrictIndexFile.get_index_file(plan)

    @staticmethod
    def get_index_file_status(plan):
        """
        Given a plan, this method will check to see whether the district index file
        for the given plan exists, is pending, or has not been created.
        
        Parameters:
            plan - the Plan for which an index file has been requested

        Returns:
            A string representing the file's status: "none", "pending", "done"
        """
        basename = "%s/plan%dv%d" % (tempfile.gettempdir(), plan.id, plan.version)
        if os.path.exists('%s.zip' % basename):
            return 'done'
        if os.path.exists('%s_pending.zip' % basename):
            return 'pending'
        else:
            return 'none'        
    @staticmethod
    def get_index_file(plan):
        """
        Given a plan, return the district index file for the plan at the current
        version
        
        Parameters:
            plan - the Plan for which an index file has been requested

        Returns:
            A file object representing the district index file. If the 
            file requested doesn't exist, nothing is returned
        """
        if (DistrictIndexFile.get_index_file_status(plan) == 'done'):
            index_file = open('%s/plan%dv%d.zip' % (tempfile.gettempdir(), plan.id, plan.version), 'r')
            index_file.close()
            return index_file
