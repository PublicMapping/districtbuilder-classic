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
import csv, datetime, zipfile, tempfile, os, smtplib, email, sys


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
    def index2plan(name, district_index_file, owner=None):
        """
        Imports a plan using a district index file in csv format. 
        There should be only two columns: a CODE matching the 
        supplemental ids of geounits and a DISTRICT integer
        representing the district to which the geounit should belong.

        Parameters:
            name - The name of the Plan.
            district_index_file - The path to the district index file.
            owner - Optional. The user who owns this plan. If not 
                specified, defaults to the system admin.

        Returns:
            A new plan.
        """
        plan = Plan.create_default(name, owner)

        if not plan:
            return None
                
        # initialize the dicts we'll use to store the supplemental_ids,
        # keyed on the district_id of this plan
        new_districts = dict()
        
        csv_file = open(district_index_file)
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
                sys.stderr.write( 'Didn\'t import row: %s' % row )
                sys.stderr.write( '\t%s' % ex )
        csv_file.close()

        
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
                sys.stderr.write( 'Created %s at %s' % (new_district.name, datetime.datetime.now()))
            except Exception as ex:
                sys.stderr.write('Wasn\'t able to create district %s: %s' % (district_id, ex))
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
                    sys.stderr.write( 'Wasn\'t able to create ComputedCharacteristic for district %, subject %s: %s' % (district_id, subject.name, ex))

        # Return the plan just created
        return plan

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
        msg = template % (user.username, plan.name)
        Email.send_email(user, msg, 'District index file for %s' % plan.name, archive)

class Email():
    @staticmethod
    def send_email(user, text, subject, zipfile=None):
        """
        Send an email to a user with an optional subject and attached
        district index file 

        Parameters:
            user -- The django user whose password will be changed.
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
        msg['To'] = user.email

        try:
            smtp = smtplib.SMTP( settings.MAIL_SERVER, settings.MAIL_PORT )
            smtp.ehlo()
            if settings.MAIL_PORT == '587':
                smtp.starttls()
            if settings.MAIL_USERNAME != '' and settings.MAIL_PASSWORD != '':
                smtp.login( settings.MAIL_USERNAME, settings.MAIL_PASSWORD )

            smtp.sendmail( sender, [user.email], msg.as_string() )
            smtp.quit()

            if zipfile:
                os.unlink(zipfile.name)

            return True
        except:
            return False
