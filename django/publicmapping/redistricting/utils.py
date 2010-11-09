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

from redistricting.models import *
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import csv, datetime, zipfile, tempfile, os, smtplib, email, sys, traceback


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
    def index2plan(name, filename, owner=None, template=False, purge=False):
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
        """

        usertitle = "Problem importing your uploaded file."
        usertpl = """Hello %s,

We apologize for the inconvenience, but your uploaded file was not converted into a plan. There are a few reasons why this might have happened. As best we can tell, your file failed to upload for the following reason:

- %s

If you correct this issue and upload your file again, we can try again.

Happy Redistricting!
The Public Mapping Team
"""

        successtitle = "Upload and import plan confirmation."
        successtpl = """Hello %s,

Your plan was created successfully. You can view, edit, and share your new plan by logging in to District Builder, and pulling up the plan entitled "%s"

Happy Redistricting!
The Public Mapping Team
"""

        admintitle = "Problem importing user uploaded file."
        admintpl = """Hello Admin,

There was a problem importing a plan file from user '%s'. This user attempted to upload a file containing a plan, but it failed for the following reason:

- %s

If the user continues to have problems with this process, please check the application settings.

Thank you.
"""
        
        # Is this filename a zip archive?
        if filename.endswith('.zip'):
            try:
                archive = zipfile.ZipFile(filename,'r')

                # Does the zip file contain more than one entry?
                if len(archive.namelist()) > 1:
                    archive.close()
                    if purge:
                        os.unlink(filename)
                    # report error to owner and admin
                    txt = usertpl % (owner.username, "The zip file contains too many files.")
                    Email.send_email(owner, txt, usertitle)

                    adm = User.objects.filter(is_staff=True)[0]
                    txt = admintpl % (owner.username, "The zip file contains too many files.")
                    Email.send_email(adm, txt, admintitle)

                    return

                item = archive.namelist()[0]
                # Does the first entry in the zipfile end in ".csv"?
                if not item.endswith('.csv'):
                    archive.close()
                    if purge:
                        os.unlink(filename)
                    # report error to owner and admin
                    txt = usertpl % (owner.username, "The zip file must contain a comma separated value (.csv) file.")
                    Email.send_email(owner, txt, usertitle)
                    adm = User.objects.filter(is_staff=True)[0]
                    txt = admintpl % (owner.username, "The zip file must contain a comma separated value (.csv) file.")
                    Email.send_email(adm, txt, admintitle)
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
                # Some problem opening the zip file, bail now
                # report error to owner and admin
                txt = usertpl % (owner.username, "Unspecified error during zip file processing.")
                Email.send_email(owner, txt, usertitle)
                adm = User.objects.filter(is_staff=True)[0]
                txt = admintpl % (owner.username, traceback.format_exc())
                Email.send_email(adm, txt, admintitle)
                if purge:
                    os.unlink(filename)
                return
       
        else: # filename.endswith('.csv'):
            indexFile = filename

        plan = Plan.create_default(name, owner=owner, template=template)

        if not plan:
            txt = usertpl % (owner.username, "Plan could not be created, please ensure the plan name is unique.")
            Email.send_email(owner, txt, usertitle)
            adm = User.objects.filter(is_staff=True)[0]
            txt = admintpl % (owner.username, "Plan could no:t be created. Probably a duplicate plan name.")
            Email.send_email(adm,txt,admintitle)
            return
                
        # initialize the dicts we'll use to store the supplemental_ids,
        # keyed on the district_id of this plan
        new_districts = dict()
        accum_errors = []
        admin_errors = []
        
        csv_file = open(indexFile)
        reader = DictReader(csv_file, fieldnames = ['code', 'district']) 
        for row in reader:
            try:
                dist_id = int(row['district'])
                # If the district key is present, add this row's code; 
                # else make a new list
                if dist_id in new_districts:
                    new_districts[dist_id].append(row['code'])
                else:
                    new_districts[dist_id] = list()
                    new_districts[dist_id].append(row['code'])
            except Exception as ex:
                accum_errors.append( "Did not import row:\n  '%s'" % row )
                admin_errors.append( "Did not import row:\n  '%s'\nReason:\n  %s" % (row, traceback.format_exc() ) )
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
                new_simple = new_geom.simplify(tolerance = settings.SIMPLE_TOLERANCE, preserve_topology=True)

                # Create a new district and save it
                new_district = District(name='District %s' % district_id, 
                    district_id = district_id + 1, plan=plan, 
                    geom=enforce_multi(new_geom), 
                    simple = enforce_multi(new_simple))
                new_district.save()
            except Exception as ex:
                accum_errors.append('Unable to create district %s.' % district_id)
                admin_errors.append('Unable to create district %s.\nReason:\n%s' % (district_id, traceback.format_exc()))
                continue
        
            # For each district, create the ComputedCharacteristics
            geounit_ids = Geounit.objects.filter(guFilter).values_list('id', flat=True).order_by('id')
            for subject in subjects:
                try:
                    cc_value = Characteristic.objects.filter(geounit__in = geounit_ids, 
                        subject = subject).aggregate(Sum('number'))
                    cc = ComputedCharacteristic(subject = subject, 
                        number = cc_value['number__sum'], 
                        district = new_district)
                    cc.save()
                except Exception as ex:
                    accum_errors.append('Unable to create ComputedCharacteristic for district %s, subject %s' % (district_id, subject.name))
                    admin_errors.append('Unable to create ComputedCharacteristic for district %s, subject %s\nReason:\n%s' % (district_id, subject.name, traceback.format_exc()))

        # Plan operations completed successfully. It's unclear if the
        # accumulated messages are problems or not. Let's assume they are.
        if len(accum_errors) > 0:
            txt = usertpl % (owner.username, '\n'.join(accum_errors))
            Email.send_email(owner, txt, usertitle)
            adm = User.objects.filter(is_staff=True)[0]
            txt = admintpl % (owner.username, '\n'.join(admin_errors))
            Email.send_email(adm, txt, admintitle)
        else:
            txt = successtpl % (owner.username, plan.name)
            Email.send_email(owner, txt, successtitle)


    @staticmethod
    def plan2index (plan, user):
        """
        Gets a zipped copy of the district index file for the
        given plan.

        Parameters:
            plan - The plan for which to get an index file
        
        Returns:
            A file object representing the zipped index file
        """

        # Get the necessary district/geounit map from the db
        cursor = plan.district_mapping_cursor()
        
        f = tempfile.NamedTemporaryFile(delete=False)
        difile = csv.writer(f)
        # The cursor is iterable so just write each row as a row in the csv file
        difile.writerows(cursor)
        cursor.close()
        f.close()

        # Create a temporary file for the archive
        archive = tempfile.NamedTemporaryFile(delete=False)

        # Zip up the file 
        zipwriter = zipfile.ZipFile(archive, 'w')
        zipwriter.write(f.name, plan.name + '.csv')
        zipwriter.close()
        archive.close()
        
        # delete the temporary csv file
        os.unlink(f.name)
        template = """Hello, %s.

Here's the district index file you requested for the plan %s. Thank you for using the Public Mapping Project.

Happy Redistricting!
The Public Mapping Team"""
        if type(user) == User:
            msg = template % (user.username, plan.name)
        else:
            msg = template % (user, plan.name)
        Email.send_email(user, msg, 'District index file for %s' % plan.name, archive)

class Email():
    @staticmethod
    def send_email(user, text, subject, zipfile=None):
        """
        Send an email to a user with an optional subject and attached
        district index file 

        Parameters:
            user -- The user to whom email should be sent
            subject -- the subject of the message
            text -- the text of the message
            zipfile -- a zip file to attach to the message            
        Returns:
            True if the user was emailed successfully.
        """

        admin = settings.ADMINS[0][0]
        sender = settings.ADMINS[0][1]

        text = MIMEText(text)

        if zipfile:
            msg = MIMEMultipart()
            msg.attach(text)
            tach = MIMEApplication(open(zipfile.name).read(), 'zip')
            tach.add_header('Content-Disposition', 'attachment; filename=DistrictIndexFile.zip')
            msg.attach(tach)
        else:
            msg = text

        if subject:
            msg['Subject'] = subject

        msg['From'] = sender
        
        # If given a user object, use the email address
        if type(user) == User:
            msg['To'] = user.email
        else:
            msg['To'] = user

        try:
            smtp = smtplib.SMTP( settings.MAIL_SERVER, settings.MAIL_PORT )
            smtp.ehlo()
            if settings.MAIL_PORT == '587':
                smtp.starttls()
            if settings.MAIL_USERNAME != '' and settings.MAIL_PASSWORD != '':
                smtp.login( settings.MAIL_USERNAME, settings.MAIL_PASSWORD )

            smtp.sendmail( sender, [msg['To']], msg.as_string() )
            smtp.quit()

            if zipfile:
                os.unlink(zipfile.name)

            return True
        except:
            return False
