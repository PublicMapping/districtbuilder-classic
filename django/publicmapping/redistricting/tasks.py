"""
Utilities for the redistricting application: format conversion,
useful database queries, etc.

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

import csv
import json
import logging
import os
import re
import tempfile
import time
import traceback
import zipfile
from codecs import open
from datetime import datetime
from decimal import Decimal
from glob import glob

from dict2xml import dict2xml
import fiona
from fiona import crs

import sld_generator as generator
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.geos import GeometryCollection
from django.contrib.sites.models import Site
from django.core import management
from django.core.mail import EmailMessage, mail_admins, send_mail
from django.db import connection, transaction
from django.db.models import Avg, Max, Q, Sum
from django.template import loader
from django.utils.translation import ugettext as _
from django.utils.translation import ungettext as _n
from django.utils.translation import activate, get_language
from django_comments.models import Comment
from lxml import etree, objectify
from publicmapping.celery import app
from redistricting.config import PoUtils, SpatialUtils
from redistricting.models import (
    Characteristic, ComputedCharacteristic, ComputedPlanScore, District,
    Geolevel, Geounit, LegislativeBody, LegislativeLevel, Plan,
    ProcessingState, ScoreDisplay, Subject, SubjectStage, SubjectUpload,
    ValidationCriteria, configure_views, create_unassigned_district,
    enforce_multi, get_featuretype_name)
from tagging.models import Tag

logger = logging.getLogger(__name__)


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
        basename = "%s/plan%dv%d" % (settings.REPORTS_ROOT, plan.id,
                                     plan.version)
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
        basename = DistrictFile.get_file_name(plan, shape)
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
        if (DistrictFile.get_file_status(plan, shape) == 'done'):
            file_name = DistrictFile.get_file_name(plan, shape) + '.zip'
            return file_name


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
    @app.task
    def index2plan(name,
                   body,
                   filename,
                   owner_id=None,
                   template=False,
                   purge=False,
                   email=None,
                   language=None):
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
            language - Optional. If provided, the task output will be
                translated to this language (provided message files have
                been completed).
        """
        owner = User.objects.get(pk=owner_id)
        prev_lang = None
        if not language is None:
            prev_lang = get_language()
            activate(language)

        if email:
            error_subject = _("Problem importing your uploaded file.")
            success_subject = _("Upload and import plan confirmation.")
            admin_subject = _("Problem importing user uploaded file.")
            context = {'user': owner, 'errors': list()}
        # Is this filename a zip archive?
        if filename.endswith('.zip'):
            try:
                archive = zipfile.ZipFile(filename, 'r')

                # Does the zip file contain more than one entry?
                if len(archive.namelist()) > 1:
                    archive.close()
                    if purge:
                        os.unlink(filename)

                    if email:
                        context['errors'].append({
                            'message':
                            _('The zip file contains too many files'),
                            'traceback':
                            None
                        })
                        # report error to owner
                        email_template = loader.get_template('error.email')
                        send_mail(
                            error_subject,
                            email_template.render(context),
                            settings.EMAIL_HOST_USER, [email],
                            fail_silently=False)
                        # report error to admin
                        email_template = loader.get_template('admin.email')
                        mail_admins(admin_subject,
                                    email_template.render(context))
                    else:
                        logger.warn(
                            'District Index .zip file contains too many files.'
                        )

                    # reset translation to default
                    if not prev_lang is None:
                        activate(prev_lang)

                    return

                item = archive.namelist()[0]
                # Does the first entry in the zipfile end in ".csv"?
                if not item.endswith('.csv'):
                    archive.close()
                    if purge:
                        os.unlink(filename)

                    if email:
                        context['errors'].append({
                            'message':
                            _('The zip file must contain a comma separated value (.csv) file.'
                              ),
                            'traceback':
                            None
                        })

                        # report error to owner
                        email_template = loader.get_template('error.email')
                        send_mail(
                            error_subject,
                            email_template.render(context),
                            settings.EMAIL_HOST_USER, [email],
                            fail_silently=False)
                        # report error to admin
                        email_template = loader.get_template('admin.email')
                        mail_admins(admin_subject,
                                    email_template.render(context))
                    else:
                        logger.warn(
                            'District Index .zip file does not contain a .csv file.\n'
                        )

                    # reset translation to default
                    if not prev_lang is None:
                        activate(prev_lang)

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
                        logger.info('Could not unlink file: "%s"', filename)

                indexFile = dest.name

            except Exception, ex:
                if email:
                    context['errors'].append({
                        'message':
                        _('Unexpected error during zip file processing'),
                        'traceback':
                        traceback.format_exc()
                    })
                    # report error to owner
                    email_template = loader.get_template('error.email')
                    send_mail(
                        error_subject,
                        email_template.render(context),
                        settings.EMAIL_HOST_USER, [email],
                        fail_silently=False)
                    # report error to admin
                    email_template = loader.get_template('admin.email')
                    mail_admins(admin_subject, email_template.render(context))
                else:
                    logger.info('The .zip file could not be imported')
                    logger.debug('Reason:', ex)

                if purge:
                    # Some problem opening the zip file, bail now
                    os.unlink(filename)

                # reset translation to default
                if not prev_lang is None:
                    activate(prev_lang)

                return

        else:  # filename.endswith('.csv'):
            indexFile = filename

            if not os.path.exists(indexFile):
                logger.warn(
                    'The .csv file could not be found, plan "%s" was not created.',
                    name)
                return

        legislative_body = LegislativeBody.objects.get(id=int(body))

        plan = Plan.create_default(
            name,
            legislative_body,
            owner=owner,
            template=template,
            processing_state=ProcessingState.CREATING,
            create_unassigned=False)

        if not plan:
            if email:
                context['errors'].append({
                    'message':
                    _("Plan couldn't be created. Be sure the plan name is unique."
                      ),
                    'tracback':
                    None
                })
                template = loader.get_template('error.email')
                send_mail(
                    error_subject,
                    template.render(context),
                    settings.EMAIL_HOST_USER, [email],
                    fail_silently=False)
                template = loader.get_template('admin.email')
                mail_admins(error_subject, template.render(context))
            else:
                logger.warn('The plan "%s" could not be created', name)

            # reset translation to default
            if not prev_lang is None:
                activate(prev_lang)

            return

        # initialize the dicts we'll use to store the portable_ids,
        # keyed on the district_id of this plan
        new_districts = dict()
        num_members = dict()
        community_labels = dict()
        community_types = dict()
        community_comments = dict()
        csv_file = open(indexFile)
        reader = csv.DictReader(
            csv_file,
            fieldnames=[
                'code', 'district', 'num_members', 'label', 'types', 'comments'
            ])
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
                    num_members[dist_id] = int(
                        row['num_members']) if row['num_members'] else 1

                    # community components are only present on community plans
                    if row['label']:
                        community_labels[dist_id] = row['label']
                    if row['types']:
                        community_types[dist_id] = row['types']
                    if row['comments']:
                        community_comments[dist_id] = row['comments']

            except Exception, ex:
                if email:
                    context['errors'].append({
                        'message':
                        '%s\n  "%s, %s"\n' % (_('Did not import row:'),
                                              row['code'], row['district']),
                        'traceback':
                        traceback.format_exc()
                    })
                else:
                    logger.debug("Did not import row: '%s'", row)
                    logger.debug(ex)

        csv_file.close()

        if purge:
            os.unlink(indexFile)
        # Get all subjects - those without denominators first to save a calculation
        subjects = Subject.objects.order_by('-percentage_denominator').all()

        # Determine if this is a community plan
        is_community = bool(community_labels)
        ct = ContentType.objects.get(
            app_label='redistricting', model='district')

        # Create the district geometry from the lists of geounits
        for district_id in new_districts.keys():
            # Get a filter using portable_id
            code_list = new_districts[district_id]
            guFilter = Q(portable_id__in=code_list)

            try:
                # Build our new geometry from the union of our geounit geometries
                new_geom = GeometryCollection([
                    gu.geom for gu in Geounit.objects.filter(guFilter)
                ]).unary_union

                # Create a new district and save it
                short_label = (community_labels[district_id][:10]
                               if is_community else
                               legislative_body.get_short_label() % {
                                   'district_id': district_id
                               })
                long_label = (community_labels[district_id][:256]
                              if is_community else
                              legislative_body.get_label() % {
                                  'district_id': district_id
                              })
                new_district = District(
                    short_label=short_label,
                    long_label=long_label,
                    district_id=district_id,
                    plan=plan,
                    num_members=num_members[district_id],
                    geom=enforce_multi(new_geom))
                new_district.simplify()  # implicit save

                # Add community fields if this is a community plan
                if is_community:
                    # Add comments
                    if district_id in community_comments:
                        comments_str = community_comments[district_id]
                    if comments_str:
                        comment = Comment(
                            object_pk=new_district.id,
                            content_type=ct,
                            site_id=1,
                            user_name=owner,
                            user_email=email,
                            comment=comments_str)
                        comment.save()

                    # Add types
                    if district_id in community_types:
                        types_str = community_types[district_id]
                    if types_str:
                        for strtag in types_str.split('|'):
                            if strtag:
                                Tag.objects.add_tag(new_district,
                                                    'type=%s' % strtag)

            except Exception, ex:
                if email:
                    context['errors'].append({
                        'message':
                        '%s %s' % (_('Unable to create district'),
                                   district_id),
                        'traceback':
                        traceback.format_exc()
                    })
                else:
                    logger.warn('Unable to create district %s.', district_id)
                    logger.warn('Reason: %s', ex)
                continue

            # For each district, create the ComputedCharacteristics
            geounit_ids = Geounit.objects.filter(guFilter).values_list(
                'id', flat=True).order_by('id')
            for subject in subjects:
                try:
                    cc_value = Characteristic.objects.filter(
                        geounit__in=geounit_ids, subject=subject).aggregate(
                            Sum('number'))
                    value = cc_value['number__sum']
                    percentage = '0000.00000000'

                    if value is not None:
                        if subject.percentage_denominator:
                            # The denominator's CC should've already been saved
                            denominator_value = ComputedCharacteristic.objects.get(
                                subject=subject.percentage_denominator,
                                district=new_district).number
                            percentage = value / denominator_value

                        cc = ComputedCharacteristic(
                            subject=subject,
                            number=value,
                            percentage=percentage,
                            district=new_district)
                        cc.save()
                    else:
                        logger.debug(
                            'Unable to create ComputedCharacteristic for Subject: %s. Skipping subject.',
                            subject.name)
                        continue
                except Exception, ex:
                    if email:
                        context['errors'].append({
                            'message':
                            _('Unable to create ComputedCharacteristic for district '
                              '%(district_id)s, subject %(subject_name)s') % {
                                  'district': district_id,
                                  'subject_name': subject.name
                              },
                            'traceback': None
                        })
                    else:
                        logger.debug(
                            'Unable to create ComputedCharacteristic for district %s, subject %s',
                            district_id, subject.name)
                        logger.debug('Reason:', ex)

        # Now that all of our other districts exist, create an unassigned district
        plan.create_unassigned = True
        create_unassigned_district(plan, instance=plan, created=True)
        # this plan is complete, and no longer creating
        plan.processing_state = ProcessingState.READY
        plan.save()

        if email:
            context['plan'] = plan
            # Plan operations completed successfully. It's unclear if the
            # accumulated messages are problems or not. Let's assume they are.

            if len(context['errors']) > 0:
                template = loader.get_template('admin.email')
                mail_admins(admin_subject, template.render(context))

            template = loader.get_template('importedplan.email')
            send_mail(
                success_subject,
                template.render(context),
                settings.EMAIL_HOST_USER, [email],
                fail_silently=False)

        # reset translation back to default
        if not prev_lang is None:
            activate(prev_lang)

    @staticmethod
    @app.task
    def plan2index(plan_id):
        """
        Gets a zipped copy of the district index file for the
        given plan.

        Parameters:
            plan - The plan for which to get an index file

        Returns:
            A file name pointing to the zipped index file
        """
        plan = Plan.objects.get(id=plan_id)
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
                    mapping = [(pid, did, members)
                               for (gid, pid, did, members) in units]
                else:
                    # create a map of district_id -> tuple of community details
                    dm = {}
                    ct = ContentType.objects.get(
                        app_label='redistricting', model='district')
                    for district in plan.get_districts_at_version(
                            plan.version, include_geom=False):
                        if district.district_id > 0:
                            types = Tag.objects.get_for_object(
                                district).filter(name__startswith='type=')
                            types = '|'.join([t.name[5:] for t in types])
                            comments = Comment.objects.filter(
                                object_pk__in=[str(district.id)],
                                content_type=ct)
                            comments = comments[
                                0].comment if len(comments) > 0 else ''
                            dm[district.district_id] = (district.long_label,
                                                        types, comments)
                    mapping = [(pid, did, members, dm[did][0], dm[did][1],
                                dm[did][2])
                               for (gid, pid, did, members) in units]

                difile = csv.writer(f)
                difile.writerows(mapping)
                f.close()

                # Zip up the file
                zipwriter = zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED)
                zipwriter.write(f.name, plan.get_friendly_name() + '.csv')
                zipwriter.close()
                archive.close()
                os.rename(archive.name,
                          DistrictFile.get_file_name(plan) + '.zip')
            except Exception, ex:
                logger.warn(
                    'The plan "%s" could not be serialized to a district index file',
                    plan.name)
                logger.debug('Reason:', ex)
                os.unlink(archive.name)
            # delete the temporary csv file
            finally:
                os.unlink(f.name)

        return DistrictFile.get_file(plan)

    @staticmethod
    @app.task
    def emailfile(plan, user, post, language=None):
        """
        Email an archived district index file to a user.

        Parameters:
            plan - The plan to export and mail.
            user - The user requesting the plan.
            post - The request context.
            language - Optional. If provided, translate the email contents to
                the specified language (if message files are complete).
        """
        prev_lang = None
        if not language is None:
            prev_lang = get_language()
            activate(language)

        # Create the file (or grab it if it already exists)
        archive = DistrictIndexFile.plan2index(plan)

        # Add it as an attachment and send the email
        template = loader.get_template('submission.email')
        context = {'user': user, 'plan': plan, 'post': post}
        email = EmailMessage()
        email.subject = _(
            'Competition submission (user: %(username)s, planid: %(plan_id)d)'
        ) % {
            'username': user.username,
            'plan_id': plan.pk
        }
        email.body = template.render(context)
        email.from_email = settings.EMAIL_HOST_USER
        email.to = [settings.EMAIL_SUBMISSION]
        email.attach_file(archive.name)
        email.send()

        # Send a confirmation email to the user
        subject = _("Plan submitted successfully")
        user_email = post['email']
        template = loader.get_template('submitted.email')
        context = {'user': user, 'plan': plan}
        send_mail(
            subject,
            template.render(context),
            settings.EMAIL_HOST_USER, [user_email],
            fail_silently=False)

        # reset the translation back to default
        if not prev_lang is None:
            activate(prev_lang)


class DistrictShapeFile():
    """
    The publicmapping projects supports users exporting their plans to
    shape files.  These files list all of the districts, their geometries,
    and the computed characteristics of the plan's districts.

    These files may be downloaded in .zip format.
    """

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
            srs = districts[0].geom.srs.wkt
            districts[0].geom.transform(4326)
            (xmin, ymin, xmax, ymax) = districts[0].geom.extent
            for dist in districts:
                transformed = dist.geom.transform(4326, clone=True)
                if transformed:
                    (xmin_, ymin_, xmax_, ymax_) = transformed.extent
                else:
                    continue
                (xmin, ymin, xmax, ymax) = (xmin
                                            if xmin < xmin_ else xmin_, ymin
                                            if ymin < ymin_ else ymin_, xmax
                                            if xmax > xmax_ else xmax_, ymax
                                            if ymax > ymax_ else ymax_)
        else:
            raise ValueError('Refusing to export a shapefile of an empty plan')

        site = Site.objects.get_current()

        dt_now = datetime.now()
        # All references to FGDC below refer to the FGDC-STD-001 June 1998 metadata
        # reference. A graphical guide may be found at the following url:
        # http://www.fgdc.gov/csdgmgraphical/index.html
        meta = {
            'idinfo': {  # FGDC 1
                'citation': {  # FGDC 1.1
                    'citeinfo': {
                        'origin':
                        site.domain,
                        'pubdate':
                        dt_now.date().isoformat(),
                        'pubtime':
                        dt_now.time().isoformat(),
                        'title':
                        'DistrictBuilder software, from the PublicMapping Project, running on %s'
                        % site.domain
                    }
                },
                'descript': {  # FGDC 1.2
                    'abstract':
                    'User-created plan "%s" from DistrictBuilder.' % plan.name,
                    'purpose':
                    'Enable community participation in the redistricting process.'
                },
                'timeperd': {  # FGDC 1.3
                    'timeinfo': {
                        'caldate': dt_now.date().isoformat(),
                        'time': dt_now.time().isoformat()
                    },
                    'current':
                    'Snapshot of user-created data at the time period of content.'
                },
                'status': {  # FGDC 1.4
                    'progress': 'Complete',
                    'update': 'Unknown'
                },
                'spdom': {  # FGDC 1.5
                    'bounding': {
                        'westbc': xmin,
                        'eastbc': xmax,
                        'northbc': ymax,
                        'southbc': ymin
                    }
                },
                'keywords': {  # FGDC 1.6
                    'theme': {
                        # The theme keyword thesaurus was chosen from
                        # http://www.loc.gov/standards/sourcelist/subject-category.html
                        'themekt':
                        'nasasscg',  # NASA scope and subject category guide
                        'themekey': 'law'
                    }
                },
                'accconst': 'None',  # FGDC 1.7
                'useconst': 'None',  # FGDC 1.8
            },
            'spdoinfo': {  # FGDC 3
                'direct': 'Vector',  # FGDC 3.2
                'ptvctinf': {  # FGDC 3.3
                    'sdtstype': 'G-polygon',
                    'ptvctcnt': len(districts)
                }
            },
            'spref': {  # FGDC 4
                'horizsys': {
                    'planar': {  # FGDC 4.1.2
                        'gridsys': {
                            'othergrd': srs
                        }
                    }
                }
            },
            'eainfo': {  # FGDC 5
                'detailed': {
                    'enttype': {
                        'enttypl':
                        'Plan "%s"' % plan.name,
                        'enttypd':
                        'Feature Class',
                        'enttypds':
                        '%s (%s %s)' % (
                            plan.owner.username,
                            plan.owner.first_name,
                            plan.owner.last_name,
                        )
                    },
                    'attr':
                    []  # must be populated later, with entity information
                }
            },
            'metainfo': {  # FGDC 7
                'metd':
                dt_now.date().isoformat(),  # FGDC 7.1
                'metstdn':
                'FGDC Content Standards for Digital Geospatial Metadata',
                'metstdv':
                'FGDC-STD-001 June 1998'
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

        # this is stupid, just use dict2xml
        xml = dict2xml(meta)
        with open(filename, 'w+') as output:
            output.write(xml)

    @staticmethod
    def make_record_properties(fieldnames,
                               default='float',
                               overrides={},
                               aliases={}):
        """Create a fiona shapefile schema from field names and overrides

        Args:
            fieldnames ([str]): the names of the fields
            overrides (dict): specific fieldname -> type mappings to include

        Returns:
            dict
        """
        return [(aliases.get(f, f), overrides.get(f, default))
                for f in fieldnames]

    @staticmethod
    def district_to_record(district, field_names, subject_names, aliases={}):
        """Convert a District into a record

        Args:
            district (District): the district to convert
            field_names ([str]): the fields to extract from this record
            subject_names ([str]): subjects to get characteristics for for this record
            aliases (dict): alternate names for fields

        Returns:
            dict
        """

        properties = {
            aliases.get(field, field): getattr(district, field)
            for field in field_names
        }

        for sname in subject_names:
            subject = Subject.objects.get(name=sname)
            try:
                compchar = district.computedcharacteristic_set.get(
                    subject=subject)
            except (ComputedCharacteristic.DoesNotExist,
                    ComputedCharacteristic.MultipleObjectsReturned):
                compchar = ComputedCharacteristic(
                    subject=subject, district=district, number=0.0)
            properties.update({sname: float(compchar.number)})

        geometry = json.loads(district.geom.geojson)

        return {
            'type': 'Feature',
            'geometry': geometry,
            'id': district.id,
            'properties': properties
        }

    @staticmethod
    @app.task
    def plan2shape(plan_id):
        """
        Gets a zipped copy of the plan shape file.

        Parameters:
            plan - The plan for which to get a shape file

        Returns:
            A file name pointing to the zipped shape file
        """
        exportFile = None
        plan = Plan.objects.get(id=plan_id)
        status = DistrictFile.get_file_status(plan, True)
        while status == 'pending':
            time.sleep(15)
            status = DistrictFile.get_file_status(plan, True)
        if status == 'none':
            pending = DistrictFile.get_file_name(plan, True) + '_pending.zip'
            archive = open(pending, 'w')
            try:
                # Create a named temporary file
                exportFile = tempfile.NamedTemporaryFile(
                    suffix='.shp', mode='w+b')
                exportFile.close()

                # Get the districts in the plan
                districts = plan.district_set.filter(
                    id__in=plan.get_district_ids_at_version(plan.version))

                # Generate metadata
                meta = DistrictShapeFile.generate_metadata(plan, districts)

                # Open a driver, and create a data source
                driver = 'ESRI Shapefile'

                # Set up mappings of field names for export, as well as shapefile
                # column aliases (only 8 characters!)
                district_fieldnames = [
                    'id', 'district_id', 'short_label', 'long_label',
                    'version', 'num_members'
                ]
                subject_names = list(Subject.objects.all().values_list(
                    'name', flat=True))
                aliases = {
                    'district_id': 'dist_num',
                    'num_members': 'nmembers',
                    'short_label': 'label',
                    'long_label': 'descr'
                }
                # Map fields to types where the default is incorrect
                mapped_fields = {
                    'id': 'int',
                    'district_id': 'int',
                    'short_label': 'str:10',
                    'long_label': 'str:254',
                    'version': 'int',
                    'num_members': 'int'
                }

                # set the district attributes
                record_properties = DistrictShapeFile.make_record_properties(
                    district_fieldnames + subject_names,
                    overrides=mapped_fields,
                    aliases=aliases)

                # Add record metadata to meta
                for fieldname in district_fieldnames + subject_names:

                    # default to double data types, unless the field type is defined
                    ftype = mapped_fields.get(fieldname, 'float')

                    # customize truncated field names
                    fieldname = aliases.get(fieldname, fieldname)

                    if fiona.prop_type(ftype) == unicode:
                        domain = {'udom': 'User entered value.'}
                    elif fiona.prop_type(ftype) == int:
                        rdommin = 0
                        rdommax = '+Infinity'
                        if fieldname == 'id':
                            rdommin = 1
                        elif fieldname == 'district_id':
                            rdommax = plan.legislative_body.max_districts
                        elif fieldname == 'num_members':
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
                    elif fiona.prop_type(ftype) == float:
                        # fieldname = Subject.objects.get(
                        #     name=fieldname).get_label()
                        domain = {
                            'rdom': {
                                'rdommin': 0.0,
                                'rdommax': '+Infinity'
                            }
                        }

                    attr = {
                        'attrlabl': fieldname,
                        'attrdef': fieldname,
                        'attrdomv': domain
                    }

                    meta['eainfo']['detailed']['attr'].append(attr)

                # Create the schema for writing out the shapefile
                schema = {
                    'geometry': 'Polygon',
                    'properties': record_properties
                }
                # begin exporting districts
                with fiona.open(
                        exportFile.name,
                        'w',
                        driver=driver,
                        crs=crs.from_string(districts[0].geom.crs.wkt),
                        schema=schema) as sink:
                    for district in districts:
                        # create a feature
                        feature = DistrictShapeFile.district_to_record(
                            district, district_fieldnames, subject_names,
                            aliases)

                        sink.write(feature)

                # write metadata
                DistrictShapeFile.meta2xml(meta, exportFile.name[:-4] + '.xml')

                # Zip up the file
                zipwriter = zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED)
                exportedFiles = glob(exportFile.name[:-4] + '*')
                for exp in exportedFiles:
                    zipwriter.write(exp, '%sv%d%s' % (plan.get_friendly_name(),
                                                      plan.version, exp[-4:]))
                zipwriter.close()
                archive.close()
                os.rename(archive.name,
                          DistrictFile.get_file_name(plan, True) + '.zip')
            except ValueError as e:
                os.unlink(archive.name)
                logger.warn('The plan "%s" was empty, so I bailed out')
            except Exception, ex:
                os.unlink(archive.name)
                logger.warn('The plan "%s" could not be saved to a shape file',
                            plan.name)
                logger.debug('Reason: %s', ex)
            # delete the temporary file
            finally:
                if not exportFile is None:
                    exportedFiles = glob(exportFile.name[:-4] + '*')
                    for exp in exportedFiles:
                        os.remove(exp)

        return DistrictFile.get_file(plan, True)


@app.task
def cleanup():
    """
    Clean out all the old sessions.

    Old sessions are sessions whose expiration date is in the past.
    """
    management.call_command('cleanup')


class CalculatorReport:
    """
    A collection of static methods that assist in asynchronous report
    generation for calculator-based reports.
    """

    @staticmethod
    @app.task
    def createcalculatorreport(planid, stamp, request, language=None):
        """
        Create the report.

        Parameters:
            planid - The plan ID.
            stamp - A unique identifier for this report.
            request - The request context.
            language - Optional. If provided, translate the report output
                into the specified language (if message files are complete).
        """
        logger.debug('Starting task to create a report.')
        try:
            plan = Plan.objects.get(pk=planid)
        except:
            logger.exception(
                "Couldn't retrieve plan information for plan {}".format(
                    planid))
            return

        function_ids = map(lambda s: int(s), request['functionIds'].split(','))

        prev_lang = None
        if not language is None:
            prev_lang = get_language()
            activate(language)

        try:
            # Render the report
            display = ScoreDisplay.objects.get(
                name='%s_reports' % plan.legislative_body.name)
            html = display.render(plan, request, function_ids=function_ids)
        except Exception:
            logger.exception('Error creating calculator report')
            html = _('Error creating calculator report.')

        # Add to report container template
        html = loader.get_template('report_panel_container.html').render({
            'report_panels':
            html
        })

        # Write it to file
        filename = '%s_p%d_v%d_%s' % (plan.owner.username, plan.id,
                                      plan.version, stamp)
        file_path = '%s/%s.html' % (settings.REPORTS_ROOT, filename)
        with open(file_path, mode='w', encoding='utf8') as htmlfile:
            htmlfile.write(html)

        # reset the language back to default
        if not prev_lang is None:
            activate(prev_lang)

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

        tempdir = settings.REPORTS_ROOT
        filename = '%s_p%d_v%d_%s' % (plan.owner.username, plan.id,
                                      plan.version, stamp)
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

        tempdir = settings.REPORTS_ROOT
        filename = '%s_p%d_v%d_%s' % (plan.owner.username, plan.id,
                                      plan.version, stamp)

        pending = open('%s/%s.pending' % (
            tempdir,
            filename,
        ), 'w')
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

        filename = '%s_p%d_v%d_%s' % (plan.owner.username, plan.id,
                                      plan.version, stamp)

        return '/reports/%s.html' % filename


#
# Reaggregation tasks
#
@app.task
def reaggregate_plan(plan_id):
    """
    Asynchronously reaggregate all computed characteristics for each district in the plan.

    @param plan_id: The plan to reaggregate
    @return: An integer count of the number of districts reaggregated
    """
    try:
        plan = Plan.objects.get(id=plan_id)
    except Exception, ex:
        logger.info('Could not retrieve plan %d for reaggregation.' % plan_id)
        logger.debug('Reason:', ex)
        return None

    try:
        count = plan.reaggregate()

        logger.debug('Reaggregated %d districts.', count)

        return count

    except Exception, ex:
        plan.processing_state = ProcessingState.NEEDS_REAGG
        plan.save()

        logger.warn('Could not reaggregate plan %d.' % plan_id)
        logger.debug('Reason:', ex)

        return None


#
# Validation tasks
#
@app.task
def validate_plan(plan_id):
    """
    Asynchronously validate a plan.

    @param plan_id: The plan_id to reaggregate
    @return: A flag indicating if the plan is valid
    """
    try:
        plan = Plan.objects.get(id=plan_id)
    except Exception, ex:
        logger.warn('Could not retrieve plan %d for validation.' % plan_id)
        logger.debug('Reason:', ex)
        return False

    criterion = ValidationCriteria.objects.filter(
        legislative_body=plan.legislative_body)
    is_valid = True
    for criteria in criterion:
        score = None
        try:
            score = ComputedPlanScore.compute(criteria.function, plan)
        except Exception, ex:
            logger.debug(traceback.format_exc())

        if not score or not score['value']:
            is_valid = False
            break

    plan.is_valid = is_valid
    plan.save()

    return is_valid


@app.task
@transaction.atomic
def verify_count(upload_id, localstore, language):
    """
    Initialize the verification process by counting the number of geounits
    in the uploaded file. After this step completes, the verify_preload
    method is called.

    Parameters:
        upload_id - The id of the SubjectUpload record.
        localstore - a new subject file that remains when the task is complete
        language - Optional. If provided, translate the status messages
            into the specified language (if message files are complete).
    """
    reader = csv.DictReader(open(localstore, 'r'))

    if len(reader.fieldnames) < 2:
        msg = _('There are missing columns in the uploaded Subject file')

        return {'task_id': None, 'success': False, 'messages': [msg]}

    upload = SubjectUpload.objects.get(id=upload_id)
    upload.subject_name = reader.fieldnames[1][0:50]
    upload.save()

    logger.debug('Created new SubjectUpload transaction record for "%s".',
                 upload.subject_name)

    # do this in bulk!
    # insert upload_id, portable_id, number
    sql = 'INSERT INTO "%s" ("%s","%s","%s") VALUES (%%(upload_id)s, %%(geoid)s, %%(number)s)' % (
        SubjectStage._meta.db_table, SubjectStage._meta.fields[1].attname,
        SubjectStage._meta.fields[2].attname,
        SubjectStage._meta.fields[3].attname)
    args = []

    try:
        for row in reader:
            args.append({
                'upload_id': upload.id,
                'geoid': row[reader.fieldnames[0]].strip(),
                'number': row[reader.fieldnames[1]].strip()
            })
            # django ORM takes about 320s for 280K geounits
            #SubjectStage(upload=upload, portable_id=row[reader.fieldnames[0]],number=row[reader.fieldnames[1]]).save()

        # direct access to db-api takes about 60s for 280K geounits
        cursor = connection.cursor()
        cursor.executemany(sql, tuple(args))

        logger.debug('Bulk loaded CSV records into the staging area.')
    except AttributeError:
        msg = _('There are an incorrect number of columns in the uploaded '
                'Subject file')

        return {'task_id': None, 'success': False, 'messages': [msg]}
    except Exception:
        msg = _('Invalid data detected in the uploaded Subject file')

        return {'task_id': None, 'success': False, 'messages': [msg]}

    nlines = upload.subjectstage_set.all().count()
    geolevel, nunits = LegislativeLevel.get_basest_geolevel_and_count()

    prev_lang = None
    if not language is None:
        prev_lang = get_language()
        activate(language)

    # Validation #1: if the number of geounits in the uploaded file
    # don't match the geounits in the database, the content is not valid
    if nlines != nunits:
        # The number of geounits in the uploaded file do not match the base geolevel geounits
        msg = _(
            'There are an incorrect number of geounits in the uploaded Subject file. '
        )
        if nlines < nunits:
            missing = nunits - nlines
            msg += _n('There is %(count)d geounit missing.',
                      'There are %(count)d geounits missing.', missing) % {
                          'count': missing
                      }
        else:
            extra = nlines - nunits
            msg += _n('There is %(count)d extra geounit.',
                      'There are %(count)d extra geounits.', extra) % {
                          'count': extra
                      }

        # since the transaction was never committed after all the inserts, this nullifies
        # all the insert statements, so there should be no quarantine to clean up

        logger.debug(msg)

        upload.status = 'ER'
        upload.save()

        status = {'task_id': None, 'success': False, 'messages': [msg]}

    else:
        # The next task will preload the units into the quarintine table
        task = verify_preload.delay(upload_id, language=language).task_id

        status = {
            'task_id': task,
            'success': True,
            'messages': [_('Verifying consistency of uploaded geounits ...')]
        }

    # reset language to default
    if not prev_lang is None:
        activate(prev_lang)

    return status


@app.task
def verify_preload(upload_id, language=None):
    """
    Continue the verification process by counting the number of geounits
    in the uploaded file and compare it to the number of geounits in the
    basest geolevel. After this step completes, the copy_to_characteristics
    method is called.

    Parameters:
        upload_id - The id of the SubjectUpload record.
        language - Optional. If provided, translate the status messages
            into the specified language (if message files are complete).
    """
    prev_lang = None
    if not language is None:
        prev_lang = get_language()
        activate(language)

    upload = SubjectUpload.objects.get(id=upload_id)
    geolevel, nunits = LegislativeLevel.get_basest_geolevel_and_count()

    # This seizes postgres -- probably small memory limits.
    #aligned_units = upload.subjectstage_set.filter(portable_id__in=permanent_units).count()

    permanent_units = geolevel.geounit_set.all().order_by(
        'portable_id').values_list(
            'portable_id', flat=True)
    temp_units = upload.subjectstage_set.all().order_by(
        'portable_id').values_list(
            'portable_id', flat=True)

    # quick check: make sure the first and last items are aligned
    ends_match = (permanent_units[0] == temp_units[0] and
                  permanent_units[permanent_units.count()
                                  - 1] == temp_units[temp_units.count() - 1])
    msg = _(
        'There are a correct number of geounits in the uploaded Subject file, '
    )
    if not ends_match:
        msg += _(
            'but the geounits do not have the same portable ids as those in the database.'
        )

    # python foo here: count the number of zipped items in the
    # permanent_units and temp_units lists that do not have the same portable_id
    # thus counting the portable_ids that are not mutually shared
    aligned_units = len(
        filter(lambda x: x[0] == x[1], zip(permanent_units, temp_units)))

    if ends_match and nunits != aligned_units:
        # The number of geounits in the uploaded file match, but there are some mismatches.
        mismatched = nunits - aligned_units
        msg += _n(
            'but %(count)d geounit does not match the geounits in the database.',
            'but %(count)d geounits do not match the geounits in the database.',
            mismatched) % {
                'count': mismatched
            }

    if not ends_match or nunits != aligned_units:
        logger.debug(msg)

        upload.status = 'ER'
        upload.save()
        upload.subjectstage_set.all().delete()

        status = {'task_id': None, 'success': False, 'messages': [msg]}

    else:
        try:
            # The next task will load the units into the characteristic table
            task = copy_to_characteristics.delay(
                upload_id, language=language).task_id

            status = {
                'task_id': task,
                'success': True,
                'messages': [_('Copying records to characteristic table ...')]
            }

        except:
            logger.error(
                "Couldn't copy characteristics: %s" % traceback.format_exc())
    # reset the language back to the default
    if not prev_lang is None:
        activate(prev_lang)

    return status


@app.task
@transaction.atomic
def copy_to_characteristics(upload_id, language=None):
    """
    Continue the verification process by copying the holding records for
    the subject into the characteristic table. This is the last step before
    user intervention for Subject metadata input.

    Parameters:
        upload_id - The id of the SubjectUpload record.
        language - Optional. If provided, translate the status messages
            into the specified language (if message files are complete).
    """
    prev_lang = None
    if not language is None:
        prev_lang = get_language()
        activate(language)

    upload = SubjectUpload.objects.get(id=upload_id)
    geolevel, nunits = LegislativeLevel.get_basest_geolevel_and_count()

    # these two lists have the same number of items, and no items are extra or missing.
    # therefore, ordering by the same field will create two collections aligned by
    # the 'portable_id' field
    quarantined = upload.subjectstage_set.all().order_by('portable_id')
    geounits = geolevel.geounit_set.all().order_by('portable_id').values_list(
        'id', 'portable_id')

    geo_quar = zip(geounits, quarantined)

    # create a subject to hold these new values
    new_sort_key = Subject.objects.all().aggregate(
        Max('sort_key'))['sort_key__max'] + 1

    # To create a clean name, replace all non-word characters with an
    # underscore
    clean_name = re.sub(r"\W", "_", upload.subject_name).lower()[:50]

    defaults = {
        'name': clean_name,
        'is_displayed': False,
        'sort_key': new_sort_key,
        'format_string': '',
        'version': 1
    }
    the_subject, created = Subject.objects.get_or_create(
        name=clean_name, defaults=defaults)

    # If the subject is newly created, we need catalog entries for each locale
    if created:
        logger.debug('Writing catalog entries for %s' % the_subject.name)
        for locale in [l[0] for l in settings.LANGUAGES]:
            try:
                logger.debug('Writing catalog entry for %s' % locale)
                po = PoUtils(locale)
                po.add_or_update(
                    msgid=u'%s short label' % the_subject.name,
                    msgstr=upload.subject_name[0:25])
                po.add_or_update(
                    msgid=u'%s label' % the_subject.name,
                    msgstr=upload.subject_name)
                po.add_or_update(
                    msgid=u'%s long description' % the_subject.name, msgstr='')
                po.save()
            except:
                logger.error("Couldn't write catalog entries for %s" % locale)

    logger.debug('Using %ssubject "%s" for new Characteristic values.', 'new '
                 if created else '', the_subject.name)

    upload.subject_name = clean_name
    upload.save()

    args = []
    for geo_char in geo_quar:
        args.append({
            'subject': the_subject.id,
            'geounit': geo_char[0][0],
            'number': geo_char[1].number
        })

    # Prepare bulk loading into the characteristic table.
    if not created:
        # delete then recreate is a more stable technique than updating all the
        # related characteristic items one at a time
        the_subject.characteristic_set.all().delete()

        logger.debug('Removed old characteristics related to old subject.')

        # increment the subject version, since it's being modified
        the_subject.version += 1
        the_subject.save()

        logger.debug('Incremented subject version to %d', the_subject.version)

    sql = 'INSERT INTO "%s" ("%s", "%s", "%s") VALUES (%%(subject)s, %%(geounit)s, %%(number)s)' % (
        Characteristic._meta.db_table,  # redistricting_characteristic
        Characteristic._meta.fields[1].attname,  # subject_id (foreign key)
        Characteristic._meta.fields[2].attname,  # geounit_id (foreign key)
        Characteristic._meta.fields[3].attname,  # number
    )

    # Insert or update all the records into the characteristic table
    cursor = connection.cursor()
    cursor.executemany(sql, tuple(args))

    logger.debug('Loaded new Characteristic values for subject "%s"',
                 the_subject.name)

    try:
        task = update_vacant_characteristics.delay(
            upload_id, created, language=language).task_id

        status = {
            'task_id':
            task,
            'success':
            True,
            'messages': [
                _('Created characteristics, resetting computed characteristics...'
                  )
            ]
        }

    except:
        status = {
            'task_id':
            task,
            'success':
            False,
            'messages':
            [_('Not able to create task for update_vacant_characteristics.')]
        }
    # reset the translation to default
    if not prev_lang is None:
        activate(prev_lang)

    return status


@app.task
def update_vacant_characteristics(upload_id, new_subj, language=None):
    """
    Update the values for the ComputedCharacteristics. This method
    does not precompute them, just adds dummy values for new subjects.
    For existing subjects, the current ComputedCharacteristics are
    untouched. For new and existing subjects, all plans are marked
    as needing reaggregation.

    Parameters:
        upload_id - The id of the SubjectUpload record.
        new_subj -
        language - Optional. If provided, translate the status messages
            into the specified language (if message files are complete).
    """
    upload = SubjectUpload.objects.get(id=upload_id)
    subject = Subject.objects.get(name=upload.subject_name)

    if new_subj:
        sql = 'INSERT INTO "%s" ("%s", "%s", "%s") VALUES (%%(subject)s, %%(district)s, %%(number)s)' % (
            ComputedCharacteristic._meta.
            db_table,  # redistricting_computedcharacteristic
            ComputedCharacteristic._meta.fields[
                1].attname,  # subject_id (foreign key)
            ComputedCharacteristic._meta.fields[
                2].attname,  # district_id (foreign key)
            ComputedCharacteristic._meta.fields[3].attname,  # number
        )
        args = []

        for district in District.objects.all():
            args.append({
                'subject': subject.id,
                'district': district.id,
                'number': '0.0'
            })

        # Insert all the records into the characteristic table
        cursor = connection.cursor()
        cursor.executemany(sql, tuple(args))

        logger.debug(
            'Created initial zero values for district characteristics for subject "%s"',
            subject.name)
    else:
        # reset the computed characteristics for all districts in one fell swoop
        ComputedCharacteristic.objects.filter(subject=subject).update(
            number=Decimal('0.0'))

        logger.debug(
            'Cleared existing district characteristics for subject "%s"',
            subject.name)

        dependents = Subject.objects.filter(percentage_denominator=subject)
        for dependent in dependents:
            ComputedCharacteristic.objects.filter(subject=dependent).update(
                number=Decimal('0.0'))
            logger.debug(
                'Cleared existing district characteristics for dependent subject "%s"',
                dependent.name)

    task = renest_uploaded_subject.delay(upload_id, language=language).task_id

    prev_lang = None
    if not language is None:
        prev_lang = get_language()
        activate(language)

    status = {
        'task_id':
        task,
        'success':
        True,
        'messages': [
            _('Reset computed characteristics, renesting foundation geographies...'
              )
        ]
    }

    # reset language back to default
    if not prev_lang is None:
        activate(prev_lang)

    return status


@app.task
def renest_uploaded_subject(upload_id, language=None):
    """
    Renest all higher level geographies for the uploaded subject.

    Parameters:
        upload_id - The id of the SubjectUpload record.
        language - Optional. If provided, translate the status messages
            into the specified language (if message files are complete).
    """
    upload = SubjectUpload.objects.get(id=upload_id)
    subject = Subject.objects.get(name=upload.subject_name)

    renested = {}
    lbodies = LegislativeBody.objects.all()
    for lbody in lbodies:
        geolevels = lbody.get_geolevels()
        geolevels.reverse()  # get the geolevels smallest to largest
        for i, geolevel in enumerate(geolevels):
            # the 0th level is the smallest level -- never renested
            if i == 0:
                continue

            # get the basename of the geolevel
            basename = geolevel.name[len(lbody.region.name) + 1:]
            if basename in renested and renested[basename]:
                logger.debug('Geolevel "%s" already renested.', basename)
                continue

            renested[basename] = geolevel.renest(
                geolevels[i - 1], subject=subject, spatial=False)

            logger.debug('Renesting of "%s" %s', basename, 'succeeded'
                         if renested[basename] else 'failed')

    # reset the processing state for all plans in one fell swoop
    Plan.objects.all().update(processing_state=ProcessingState.NEEDS_REAGG)

    logger.debug('Marked all plans as needing reaggregation.')

    task = create_views_and_styles.delay(upload_id).task_id

    prev_lang = None
    if not language is None:
        prev_lang = get_language()
        activate(language)

    status = {
        'task_id':
        task,
        'success':
        True,
        'messages': [
            _('Renested foundation geographies, creating spatial views and styles...'
              )
        ]
    }

    # reset language back to default
    if not prev_lang is None:
        activate(prev_lang)

    return status


@app.task
def create_views_and_styles(upload_id, language=None):
    """
    Create the spatial views required for visualizing the subject data on the map.

    Parameters:
        upload_id - The id of the SubjectUpload record.
        language - Optional. If provided, translate the status messages
            into the specified language (if message files are complete).
    """

    # Configure ALL views. This will replace view definitions with identical
    # view defintions as well as create the new view definitions.
    configure_views()

    logger.debug('Created spatial views for subject data values.')

    # Get the spatial configuration settings.
    geoutil = SpatialUtils(
        config={
            'host': settings.MAP_SERVER,
            'ns': settings.MAP_SERVER_NS,
            'nshref': settings.MAP_SERVER_NSHREF,
            'adminuser': settings.MAP_SERVER_USER,
            'adminpass': settings.MAP_SERVER_PASS,
            'styles': settings.SLD_ROOT
        })

    upload = SubjectUpload.objects.get(id=upload_id)
    subject = Subject.objects.get(name=upload.subject_name)

    for geolevel in Geolevel.objects.all():
        if geolevel.legislativelevel_set.all().count() == 0:
            # Skip 'abstract' geolevels if regions are configured
            continue

        logger.debug('Creating queryset and SLD content for %s, %s',
                     geolevel.name, subject.name)

        qset = Geounit.objects.filter(
            characteristic__subject=subject, geolevel=geolevel).annotate(
                Avg('characteristic__number'))
        sld_body = generator.as_quantiles(
            qset,
            'characteristic__number__avg',
            5,
            propertyname='number',
            userstyletitle=subject.get_short_label())

        logger.debug('Generated SLD content, creating featuretype.')

        geoutil.create_featuretype(
            get_featuretype_name(geolevel.name, subject.name))
        geoutil.create_style(
            subject_name=subject.name,
            geolevel_name=geolevel.name,
            sld_content=sld_body.as_sld(pretty_print=True))

        logger.debug('Created featuretype and style for %s, %s', geolevel.name,
                     subject.name)

    task = clean_quarantined.delay(upload_id, language=language).task_id

    prev_lang = None
    if not language is None:
        prev_lang = get_language()
        activate(language)

    status = {
        'task_id':
        task,
        'success':
        True,
        'messages':
        [_('Created spatial views and styles, cleaning quarantined data...')]
    }

    # reset language back to default
    if not prev_lang is None:
        activate(prev_lang)

    return status


@app.task
def clean_quarantined(upload_id, language=None):
    """
    Remove all temporary characteristics in the quarantine area for
    the given upload.

    Parameters:
        upload_id - The id of the SubjectUpload record.
        language - Optional. If provided, translate the status messages
            into the specified language (if message files are complete).
    """
    upload = SubjectUpload.objects.get(id=upload_id)
    quarantined = upload.subjectstage_set.all()

    # The upload succeeded
    upload.status = 'OK'
    upload.save()

    logger.debug('Set upload status for SubjectUpload %d to "complete".',
                 upload_id)

    # delete the quarantined items out of the quarantine table
    quarantined.delete()

    logger.debug('Removed quarantined subject data.')

    prev_lang = None
    if not language is None:
        prev_lang = get_language()
        activate(language)

    try:
        Plan.objects.all().update(is_valid=False)
    except Exception:
        logger.warn('Could not reset the is_valid flag on all plans.')

    status = {
        'task_id':
        None,
        'success':
        True,
        'messages': [
            _('Upload complete. Subject "%(subject_name)s" added.') % {
                'subject_name': upload.subject_name
            }
        ],
        'subject':
        Subject.objects.get(name=upload.subject_name).id
    }

    # reset language back to default
    if not prev_lang is None:
        activate(prev_lang)

    return status
