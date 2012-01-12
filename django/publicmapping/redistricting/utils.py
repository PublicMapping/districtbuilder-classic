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
from django.contrib.sites.models import Site
from django.core.mail import send_mail, mail_admins, EmailMessage
from django.template import loader, Context as DjangoContext
from django.db.models import Sum, Min, Max
from redistricting.models import *
from tagging.utils import parse_tag_input
from tagging.models import Tag, TaggedItem
import csv, time, zipfile, tempfile, os, sys, traceback, time
from datetime import datetime
import socket, urllib2
from lxml import etree, objectify

# all for shapefile exports
from glob import glob
from django.contrib.gis.gdal import *
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
                    try:
                        os.unlink(filename)
                    except:
                        sys.stderr.write('Could not unlink file: "%s":\n' % filename)

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
                short_label = community_labels[district_id] if is_community else legislative_body.short_label % district_id 
                long_label = community_labels[district_id] if is_community else legislative_body.long_label % district_id
                new_district = District(short_label=short_label,long_label=long_label,
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
            pending = DistrictFile.get_file_name(plan) + '_pending.zip'
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
                            dm[district.district_id] = (district.long_label, types, comments)
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

        return DistrictFile.get_file(plan)

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
    def contact_from_getcapabilities(site):
        """
        Retrieve contact information for metadata from the contact data in geoserver.

        Returns a tuple of information with:
            contact_person
            contact_organization
            contact_position
            address_type
            address
            city
            state
            postal
            country
            voice_phone
            fax_phone
            email
        """
        # get the map server URL for the GetCapabilities doc
        ms_url = settings.MAP_SERVER
        if ms_url == '':
            ms_url = site.domain
        ms_url = 'http://%s/geoserver/ows?service=wms&version=1.1.1&request=GetCapabilities' % ms_url

        stream = urllib2.urlopen(ms_url)
        tree = etree.parse(stream)
        stream.close()

        contact = tree.xpath('/WMT_MS_Capabilities/Service/ContactInformation')[0]

        parsed_contact = (
            contact.xpath('ContactPersonPrimary/ContactPerson')[0].text,
            contact.xpath('ContactPersonPrimary/ContactOrganization')[0].text,
            contact.xpath('ContactPosition')[0].text,
            contact.xpath('ContactAddress/AddressType')[0].text,
            contact.xpath('ContactAddress/Address')[0].text,
            contact.xpath('ContactAddress/City')[0].text,
            contact.xpath('ContactAddress/StateOrProvince')[0].text,
            contact.xpath('ContactAddress/PostCode')[0].text,
            contact.xpath('ContactAddress/Country')[0].text,
            contact.xpath('ContactVoiceTelephone')[0].text,
            contact.xpath('ContactFacsimileTelephone')[0].text,
            contact.xpath('ContactElectronicMailAddress')[0].text,
        )

        return tuple(map(lambda x:x if x is not None else '', parsed_contact))
        

    @staticmethod
    def generate_metadata(plan, districts):
        """
        Generate a base chunk of metadata based on the spatial data in the plan and districts.

        This base chunk does not contain entity or attribute information.

        Parameters:
            plan -- The plan for which metadata should be generated
            districts -- The collection of districts that compose the plan

        Returns:
            A dict of metadata information about this plan.
        """
        if len(districts) > 0:
            srs = SpatialReference(districts[0].geom.srid)
            districts[0].geom.transform(4326)
            e = None
            for i in range(1, len(districts)):
                districts[i].geom.transform(4326)
                if not districts[i].geom.empty:
                    if e is None:
                        e = Envelope(districts[i].geom.extent)
                    else: 
                        e.expand_to_include(districts[i].geom.extent)
        else:
            srs = SpatialReference(4326)
            e = Envelope( (-180.0,-90.0,180.0,90.0,) )

        site = Site.objects.get_current()

        contact = DistrictShapeFile.contact_from_getcapabilities(site)

        dt_now = datetime.now()
        # All references to FGDC below refer to the FGDC-STD-001 June 1998 metadata
        # reference. A graphical guide may be found at the following url:
        # http://www.fgdc.gov/csdgmgraphical/index.html
        meta = {
            'idinfo':{ # FGDC 1
                'citation':{ # FGDC 1.1
                    'citeinfo':{
                        'origin':site.domain,
                        'pubdate':dt_now.date().isoformat(),
                        'pubtime':dt_now.time().isoformat(),
                        'title':'DistrictBuilder software, from the PublicMapping Project, running on %s' % site.domain
                    }
                },
                'descript':{ # FGDC 1.2
                    'abstract':'User-created plan "%s" from DistrictBuilder.' % plan.name,
                    'purpose':'Enable community participation in the redistricting process.'
                },
                'timeperd':{ # FGDC 1.3
                    'timeinfo':{
                        'caldate':dt_now.date().isoformat(),
                        'time':dt_now.time().isoformat()
                    },
                    'current':'Snapshot of user-created data at the time period of content.'
                },
                'status':{ # FGDC 1.4
                    'progress':'Complete',
                    'update':'Unknown'
                },
                'spdom':{ # FGDC 1.5
                    'bounding':{
                        'westbc':e.min_x,
                        'eastbc':e.max_x,
                        'northbc':e.max_y,
                        'southbc':e.min_y
                    }
                },
                'keywords':{ # FGDC 1.6
                    'theme': {
                        # The theme keyword thesaurus was chosen from 
                        # http://www.loc.gov/standards/sourcelist/subject-category.html
                        'themekt':'nasasscg', # NASA scope and subject category guide
                        'themekey': 'law'
                    }
                },
                'accconst': 'None', # FGDC 1.7
                'useconst': 'None', # FGDC 1.8
            },
            'spdoinfo':{ # FGDC 3
                'direct': 'Vector', # FGDC 3.2
                'ptvctinf': { # FGDC 3.3
                    'sdtstype': 'G-polygon',
                    'ptvctcnt': len(districts)
                }
            },
            'spref':{ # FGDC 4
                'horizsys': {
                    'planar': { # FGDC 4.1.2
                        'gridsys':{
                            'othergrd': srs.wkt
                        }
                    }
                }
            },
            'eainfo': { # FGDC 5 
                'detailed': {
                    'enttype': {
                        'enttypl': 'Plan "%s"' % plan.name,
                        'enttypd': 'Feature Class',
                        'enttypds': '%s (%s %s)' % (plan.owner.username, plan.owner.first_name, plan.owner.last_name,)
                    },
                    'attr':[] # must be populated later, with entity information
                }
            }, 
            'metainfo':{ # FGDC 7
                'metd': dt_now.date().isoformat(), # FGDC 7.1
                'metc': { # FGDC 7.4
                    'cntinfo': {
                        'cntperp': contact[0],
                        'cntorgp': contact[1],
                        'cntpos': contact[2],
                        'cntaddr':{
                            'addrtype': contact[3],
                            'address': contact[4],
                            'city': contact[5],
                            'state': contact[6],
                            'postal': contact[7],
                            'country': contact[8]
                        },
                        'cntvoice': contact[9],
                        'cntfax': contact[10],
                        'cntemail': contact[11]
                    }
                },
                'metstdn': 'FGDC Content Standards for Digital Geospatial Metadata',
                'metstdv': 'FGDC-STD-001 June 1998'
            }
        }

        return meta

    @staticmethod
    def meta2xml(meta, filename):
        """
        Serialize a metadata dictionary into XML.

        Parameters:
            meta -- A dictionary of metadata to serialize
            filename -- The destination of the serialized metadata
        """
        def dict2elem(elem, d):
            """
            Recursive dictionary element serializer helper.
            """
            if isinstance(d, dict):
                # the element passed is a dict
                for key in d:
                    if isinstance(d[key], list):
                        # this dict item is a list -- serialize a series of these
                        items = d[key]
                        for item in items:
                            sub = etree.SubElement(elem, key)
                            dict2elem(sub, item)
                    else:
                        # this dict item is a scalar or another dict
                        sub = etree.SubElement(elem, key)
                        dict2elem(sub,d[key])
            else:
                # the element passed is no longer a dict, it's a scalar value
                elem._setText(str(d))

            return elem
                

        elem = objectify.Element('metadata')
        elem = dict2elem(elem, meta)

        # remove some lxml cruft
        objectify.deannotate(elem,pytype=True,xsi=True,xsi_nil=True)
        etree.cleanup_namespaces(elem)

        output = open(filename, 'w+')
        output.write( etree.tostring(elem, pretty_print=True) )
        output.close()


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
                # Create a named temporary file
                exportFile = tempfile.NamedTemporaryFile(suffix='.shp', mode='w+b')
                exportFile.close()

                # Get the districts in the plan
                districts = plan.district_set.filter(id__in=plan.get_district_ids_at_version(plan.version))

                # Generate metadata
                meta = DistrictShapeFile.generate_metadata(plan, districts)

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
                dfieldnames = ['id', 'district_id', 'short_label', 'long_label', 'version', 'num_members']
                sfieldnames = list(Subject.objects.all().values_list('name',flat=True))
                aliases = {'district_id':'dist_num', 'num_members':'nmembers', 'short_label':'label', 'long_label':'descr'}
                ftypes = {'id':OGRInteger, 'district_id':OGRInteger, 'short_label':OGRString, 'long_label':OGRString, 'version':OGRInteger, 'num_members':OGRInteger}

                # set the district attributes
                for fieldname in dfieldnames + sfieldnames:

                    # default to double data types, unless the field type is defined
                    ftype = OGRReal
                    if fieldname in ftypes:
                        ftype = ftypes[fieldname]

                    definition = fieldname
                    # customize truncated field names
                    if fieldname in aliases:
                        fieldname = aliases[fieldname]

                    if ftype == OGRString:
                        domain = { 'udom': 'User entered value.' }
                    elif ftype == OGRInteger:
                        rdommin = 0 
                        rdommax = '+Infinity'
                        if definition == 'id':
                            rdommin = 1
                        elif definition == 'district_id':
                            rdommax = plan.legislative_body.max_districts
                        elif definition == 'num_members':
                            if plan.legislative_body.multi_members_allowed:
                                rdommax = plan.legislative_body.max_multi_district_members
                                rdommin = plan.legislative_body.min_multi_district_members
                            else:
                                rdommin = 1
                                rdommax = 1

                        domain = {
                            'rdom': {
                                'rdommin': rdommin,
                                'rdommax': rdommax
                            }
                        }
                    elif ftype == OGRReal:
                        definition = Subject.objects.get(name=definition).display
                        domain = {
                            'rdom': {
                                'rdommin': 0.0,
                                'rdommax': '+Infinity'
                            }
                        }


                    attr = {
                        'attrlabl': fieldname,
                        'attrdef': definition,
                        'attrdomv': domain
                    }

                    meta['eainfo']['detailed']['attr'].append(attr)

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
                            try:
                                lgdal.OGR_F_SetFieldString(feature, idx, str(value))
                            except UnicodeEncodeError:
                                lgdal.OGR_F_SetFieldString(feature, idx, '')

                    # attach each field for the subjects that relate to this model
                    for idx, sname in enumerate(sfieldnames):
                        subject = Subject.objects.get(name=sname)
                        try:
                            compchar = district.computedcharacteristic_set.get(subject=subject)
                        except:
                            compchar = ComputedCharacteristic(subject=subject, district=district, number=0.0)
                        lgdal.OGR_F_SetFieldDouble(feature, idx+len(dfieldnames), c_double(compchar.number))

                    # convert the geos geometry to an ogr geometry
                    geometry = OGRGeometry(district.geom.ewkt)
                    geometry.transform(native_srs)
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

                # write metadata
                DistrictShapeFile.meta2xml(meta, exportFile.name[:-4] + '.xml')

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

        tempdir = settings.WEB_TEMP
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

        tempdir = settings.WEB_TEMP
        filename = '%s_p%d_v%d_%s' % (plan.owner.username, plan.id, plan.version, stamp)

        pending_file = '%s/%s.pending' % (tempdir, filename)
        if os.path.exists(pending_file):
            # If the reports server is on another machine
            if not 'localhost'  in settings.BARD_SERVER:
                path = '%s/reports/%s.html' % (settings.BARD_SERVER,filename)
                try:
                    result = urllib2.urlopen(path)
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

        tempdir = settings.WEB_TEMP
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
        tempdir = settings.WEB_TEMP
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

        tempdir = settings.WEB_TEMP
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

        tempdir = settings.WEB_TEMP
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
