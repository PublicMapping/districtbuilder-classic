"""
Configuration module for DistrictBuilder

This file handles many common operations that operate on the application
configuration and setup.

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

import base64
import hashlib
import json
import logging
import os
import re
import traceback
import types
from datetime import datetime, timedelta, tzinfo

import httplib
import polib
import sld
import sld_generator as generator
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Avg, Model
from django.utils.translation import ugettext as _
from redistricting.models import (
    ContiguityOverride,
    Geolevel,
    Geounit,
    LegislativeBody,
    LegislativeLevel,
    Region,
    ScoreArgument,
    ScoreDisplay,
    ScoreFunction,
    ScorePanel,
    Subject,
    ValidationCriteria,
    get_featuretype_name,
)

import requests

logger = logging.getLogger(__name__)


def check_and_update(a_model,
                     unique_id_field='name',
                     overwrite=False,
                     **kwargs):
    """
    Check whether an object exists with the given name in the database. If the
    object exists and "overwrite" is True, overwrite the object.  If "overwrite"
    is false, don't overwrite.  If the object doesn't exist, it is always created.

    @param a_model: A model class.
    @param unique_id_field: The field name that is unique.
    @keyword overwrite: Should the new object be overwritten?
    @returns: tuple - the object in the DB after any changes are made,
        whether the object had to be created,
        whether the given attributes were consistent with what was in the database,
        a message to return indicating any changes.
    """
    name = kwargs[unique_id_field]
    object_name = '%s %s' % (a_model.__name__, name)
    # Get the model if it exists
    try:
        id_args = {unique_id_field: name}
        current_object = a_model.objects.get(**id_args)
    # If it doesn't exist, just save it and return
    except ObjectDoesNotExist:
        new = a_model(**kwargs)
        new.save()
        return new, True, False, '%s created' % object_name
    # If it exists, track any changes and overwrite if requested
    different = []
    changed = False
    message = '%s matches database - no changes%s'
    for key in kwargs:
        current_value = current_object.__getattribute__(key)
        config_value = kwargs[key]
        if not (isinstance(current_value, types.StringTypes)
                or isinstance(current_value, Model)):
            config_value = type(current_value)(config_value)
        if current_value != config_value:
            if overwrite:
                current_object.__setattr__(key, config_value)
                changed = True
                message = 'UPDATED %s; CHANGED attribute(s) "%s"'
            else:
                message = (
                    'Didn\'t change %s; attribute(s) "%s" differ(s) from database configuration.\n'
                    '\tWARNING: Sync your config file to your app configuration or use the -f '
                    'switch with setup to force changes')
            different.append(key)
    if overwrite and changed:
        current_object.save()
    return current_object, False, len(different) > 0, message % (
        object_name, ', '.join(different))


class Utils:
    """
    A class of utility functions that aid in the configuration
    steps for DistrictBuilder.
    """

    @staticmethod
    def purge_sessions():
        """
        Delete any sessions that exist in the django database.

        @returns: A flag indicating if the sessions were deleted successfully.
        """
        qset = Session.objects.all()

        logger.debug('Purging %d sessions from the database.', qset.count())

        try:
            qset.delete()
        except Exception:
            logger.info('Could not delete sessions.')
            return False

        return True


class ConfigImporter:
    """
    An importer of configured objects.
    """

    def __init__(self, store):
        """
        Create a new config importer, based on the stored config.

        @param store: The data store for the configuration.
        """
        self.store = store

        # store the utils for all the po file processing
        self.poutils = {}
        for locale in [l[0] for l in settings.LANGUAGES]:
            self.poutils[locale] = PoUtils(locale)

    def save(self):
        """
        Save all modified po files.
        """
        for locale in self.poutils:
            self.poutils[locale].save()

    def import_superuser(self, force):
        """
        Create the django superuser, based on the config.

        @param force: Should the Admin settings be written if the model already exist?
        @returns: A flag indicating if the import was successful.
        """
        try:
            admin_attributes = {
                'first_name': 'Admin',
                'last_name': 'User',
                'is_staff': True,
                'is_active': True,
                'is_superuser': True,
                'username': os.getenv('ADMIN_USER'),
                'email': os.getenv('ADMIN_EMAIL'),
            }

            admin, created, changed, message = check_and_update(
                User,
                unique_id_field='username',
                overwrite=force,
                **admin_attributes)

            if changed and not force:
                logger.info(message)
            else:
                logger.debug(message)

            if created or changed or force:
                m = hashlib.sha1()
                m.update(os.getenv('ADMIN_PASSWORD'))
                admin.set_password(m.hexdigest())
                admin.save()

            return True

        except:
            logger.info('Error when creating superuser.')
            logger.info(traceback.format_exc())

            return False

    def import_regions(self, force):
        """
        Create region models out of the configuration.

        @param force: Should the Region settings be written if the model already exist?
        @returns: A flag indicating if the import was successful.
        """
        regions = self.store.filter_regions()
        for region in regions:
            attributes = {
                'name': region.get('id')[0:256],
                'sort_key': region.get('sort_key')
            }

            obj, created, changed, message = check_and_update(
                Region, overwrite=force, **attributes)

            for locale in [l[0] for l in settings.LANGUAGES]:
                po = self.poutils[locale]
                po.add_or_update(
                    msgid=u'%s short label' % attributes['name'],
                    msgstr=region.get('name') or '',
                    occurs=[(
                        os.path.abspath(self.store.datafile),
                        region.sourceline,
                    )])
                po.add_or_update(
                    msgid=u'%s label' % attributes['name'],
                    msgstr=region.get('label') or '',
                    occurs=[(
                        os.path.abspath(self.store.datafile),
                        region.sourceline,
                    )])
                po.add_or_update(
                    msgid=u'%s long description' % attributes['name'],
                    msgstr=region.get('description') or '',
                    occurs=[(
                        os.path.abspath(self.store.datafile),
                        region.sourceline,
                    )])

            if changed and not force:
                logger.info(message)
            else:
                logger.debug(message)

        return True

    def import_legislative_bodies(self, force):
        """
        Create legislative body models out of the configuration.

        @param force: Should the LegislativeBody settings be written if the model already exist?
        @returns: A flag indicating if the import was successful.
        """
        bodies = self.store.filter_legislative_bodies()
        for body in bodies:
            attributes = {
                'name': body.get('id')[:256],
                'max_districts': body.get('maxdistricts'),
                'sort_key': body.get('sort_key'),
                'is_community': body.get('is_community') == 'true'
            }

            body_by_region = self.store.filter_nodes(
                '/DistrictBuilder/Regions/Region/LegislativeBodies/LegislativeBody[@ref="%s"]'
                % body.get('id'))
            if len(body_by_region) != 1:
                logger.info("Legislative body %s not attributed to any region",
                            attributes['name'])
                continue
            else:
                region_name = body_by_region[0].getparent().getparent().get(
                    'id')
            attributes['region'] = Region.objects.get(name=region_name)

            obj, created, changed, message = check_and_update(
                LegislativeBody, overwrite=force, **attributes)

            for locale in [l[0] for l in settings.LANGUAGES]:
                po = self.poutils[locale]
                po.add_or_update(
                    msgid=u'%s short label' % attributes['name'],
                    msgstr=body.get('short_label') or '%(district_id)s',
                    occurs=[(
                        os.path.abspath(self.store.datafile),
                        body.sourceline,
                    )])
                po.add_or_update(
                    msgid=u'%s label' % attributes['name'],
                    msgstr=body.get('long_label') or '%(district_id)s',
                    occurs=[(
                        os.path.abspath(self.store.datafile),
                        body.sourceline,
                    )])
                po.add_or_update(
                    msgid=u'%s long description' % attributes['name'],
                    msgstr=body.get('name'),
                    occurs=[(
                        os.path.abspath(self.store.datafile),
                        body.sourceline,
                    )])
                po.add_or_update(
                    msgid=u'%s members' % attributes['name'],
                    msgstr=body.get('members'),
                    occurs=[(
                        os.path.abspath(self.store.datafile),
                        body.sourceline,
                    )])

            if changed and not force:
                logger.info(message)
            else:
                logger.debug(message)

            if obj is None:
                continue

            # Add multi-member district configuration
            mmconfig = self.store.get_node(
                '//MultiMemberDistrictConfig[@legislativebodyref="%s"]' %
                body.get('id'))
            if mmconfig:
                obj.multi_members_allowed = True
                obj.multi_district_label_format = mmconfig.get(
                    'multi_district_label_format')[:32]
                obj.min_multi_districts = mmconfig.get('min_multi_districts')
                obj.max_multi_districts = mmconfig.get('max_multi_districts')
                obj.min_multi_district_members = mmconfig.get(
                    'min_multi_district_members')
                obj.max_multi_district_members = mmconfig.get(
                    'max_multi_district_members')
                obj.min_plan_members = mmconfig.get('min_plan_members')
                obj.max_plan_members = mmconfig.get('max_plan_members')
                logger.debug('Multi-member districts enabled for: %s',
                             body.get('name'))
            else:
                obj.multi_members_allowed = False
                obj.multi_district_label_format = ''
                obj.min_multi_districts = 0
                obj.max_multi_districts = 0
                obj.min_multi_district_members = 0
                obj.max_multi_district_members = 0
                obj.min_plan_members = 0
                obj.max_plan_members = 0
                logger.debug('Multi-member districts not configured for: %s',
                             body.get('name'))

            obj.save()

        return True

    def import_subjects(self, force):
        """
        Create subject models out of the configuration.

        @param force: Should the Subject settings be written if the model already exist?
        @returns: A flag indicating if the import was successful.
        """
        subjs = self.store.filter_subjects()
        for subj in subjs:
            if 'aliasfor' in subj.attrib:
                continue

            attributes = {
                'name': subj.get('id').lower()[:50],
                'is_displayed': subj.get('displayed') == 'true',
                'sort_key': subj.get('sortkey')
            }

            obj, created, changed, message = check_and_update(
                Subject, overwrite=force, **attributes)

            for locale in [l[0] for l in settings.LANGUAGES]:
                po = self.poutils[locale]
                po.add_or_update(
                    msgid=u'%s short label' % attributes['name'],
                    msgstr=subj.get('short_name') or '',
                    occurs=[(
                        os.path.abspath(self.store.datafile),
                        subj.sourceline,
                    )])
                po.add_or_update(
                    msgid=u'%s label' % attributes['name'],
                    msgstr=subj.get('name') or '',
                    occurs=[(
                        os.path.abspath(self.store.datafile),
                        subj.sourceline,
                    )])
                po.add_or_update(
                    msgid=u'%s long description' % attributes['name'],
                    msgstr='',
                    occurs=[(
                        os.path.abspath(self.store.datafile),
                        subj.sourceline,
                    )])

            if changed and not force:
                logger.info(message)
            else:
                logger.debug(message)

        for subj in subjs:
            numerator_name = subj.get('id').lower()[:50]
            numerator = Subject.objects.get(name=numerator_name)

            denominator = None
            denominator_name = subj.get('percentage_denominator')
            if denominator_name:
                denominator_name = denominator_name.lower()[:50]
                try:
                    denominator = Subject.objects.get(name=denominator_name)
                except Exception:
                    logger.info('Subject "%s" was not found.',
                                denominator_name)
                    raise

            numerator.percentage_denominator = denominator
            numerator.save()

            logger.debug('Set denominator on "%s" to "%s"', numerator.name,
                         denominator_name)

        return True

    def import_geolevels(self, force):
        """
        Create geolevel models out of the configuration.

        @param force: Should the GeoLevels settings be written if the model already exist?
        @returns: A flag indicating if the import was successful.
        """

        # Note that geolevels may be added in any order, but the geounits
        # themselves need to be imported top-down (smallest area to biggest)
        geolevels = self.store.filter_geolevels()
        for geolevel in geolevels:
            attributes = {
                'name': geolevel.get('id').lower()[:50],
                'min_zoom': geolevel.get('min_zoom'),
                'sort_key': geolevel.get('sort_key'),
                'tolerance': geolevel.get('tolerance')
            }

            glvl, created, changed, message = check_and_update(
                Geolevel, overwrite=force, **attributes)

            for locale in [l[0] for l in settings.LANGUAGES]:
                po = self.poutils[locale]
                po.add_or_update(
                    msgid=u'%s short label' % attributes['name'],
                    msgstr=geolevel.get('name') or '',
                    occurs=[(
                        os.path.abspath(self.store.datafile),
                        geolevel.sourceline,
                    )])
                po.add_or_update(
                    msgid=u'%s label' % attributes['name'],
                    msgstr=geolevel.get('label') or '',
                    occurs=[(
                        os.path.abspath(self.store.datafile),
                        geolevel.sourceline,
                    )])
                po.add_or_update(
                    msgid=u'%s long description' % attributes['name'],
                    msgstr='',
                    occurs=[(
                        os.path.abspath(self.store.datafile),
                        geolevel.sourceline,
                    )])

            if changed and not force:
                logger.info(message)
            else:
                logger.debug(message)

        return True

    def import_regional_geolevels(self, force):
        """
        Map geolevels to regions.

        @param force: Should the Regional GeoLevel settings be written if the model already exist?
        @returns: A flag indicating if the import was successful.
        """
        regions = self.store.filter_regions()
        for region in regions:
            regional_geolevels = self.store.filter_regional_geolevel(region)

            # Get the zoom level of the largest geolevel (last one in the regional_geolevels list)
            zero_geolevel_config = self.store.get_geolevel(
                regional_geolevels[len(regional_geolevels) - 1].get('ref'))
            # store this zoom level, and use it as an offset for the geolevels in this region
            zero_zoom = int(zero_geolevel_config.get('min_zoom'))

            for geolevel in regional_geolevels:
                try:
                    geolevel_obj = Geolevel.objects.get(
                        name=geolevel.get('ref'))
                except Geolevel.DoesNotExist:
                    logger.debug(
                        'Base geolevel %s for %s not found in the database.  Import base geolevels'
                        ' before regional geolevels', region.get('name'))
                    return

                attributes = {
                    'name': '%s_%s' % (region.get('name'),
                                       geolevel.get('ref')),
                    'min_zoom': geolevel_obj.min_zoom - zero_zoom,
                    'tolerance': geolevel_obj.tolerance
                }
                obj, created, changed, message = check_and_update(
                    Geolevel, overwrite=force, **attributes)

                for locale in [l[0] for l in settings.LANGUAGES]:
                    po = self.poutils[locale]
                    po.add_or_update(
                        msgid=u'%s short label' % attributes['name'],
                        msgstr=geolevel.get('name') or '',
                        occurs=[(
                            os.path.abspath(self.store.datafile),
                            geolevel.sourceline,
                        )])
                    po.add_or_update(
                        msgid=u'%s label' % attributes['name'],
                        msgstr=geolevel.get('label') or '',
                        occurs=[(
                            os.path.abspath(self.store.datafile),
                            geolevel.sourceline,
                        )])
                    po.add_or_update(
                        msgid=u'%s long description' % attributes['name'],
                        msgstr=geolevel.get('ref') or '',
                        occurs=[(
                            os.path.abspath(self.store.datafile),
                            geolevel.sourceline,
                        )])

                if changed and not force:
                    logger.info(message)
                else:
                    logger.debug(message)

        # Use the Region nodes to link bodies and geolevels
        for region in regions:

            # Map the imported geolevel to a legislative body
            lbodies = self.store.filter_regional_legislative_bodies(region)
            for lbody in lbodies:
                legislative_body = LegislativeBody.objects.get(
                    name=lbody.get('ref')[:256])

                # Add a mapping for the subjects in this GL/LB combo.
                sconfig = self.store.get_legislative_body_default_subject(
                    lbody)
                if not sconfig.get('aliasfor') is None:
                    # dereference any subject alias
                    sconfig = self.store.get_subject(sconfig.get('aliasfor'))
                subject = Subject.objects.get(
                    name=sconfig.get('id').lower()[:50])

                def add_legislative_level_for_geolevel(node, body, subject,
                                                       parent):
                    """
                    Helper method to recursively add LegislativeLevel mappings from Region configs
                    """
                    geolevel_node = self.store.get_geolevel(node.get('ref'))
                    geolevel_name = "%s_%s" % (region.get('id'),
                                               geolevel_node.get('id'))
                    geolevel = Geolevel.objects.get(name=geolevel_name)
                    obj, created = LegislativeLevel.objects.get_or_create(
                        legislative_body=body,
                        geolevel=geolevel,
                        subject=subject,
                        parent=parent)

                    if created:
                        logger.debug(
                            'Created LegislativeBody/GeoLevel mapping "%s/%s"',
                            legislative_body.name, geolevel.name)
                    else:
                        logger.debug(
                            'LegislativeBody/GeoLevel mapping "%s/%s" already exists',
                            legislative_body.name, geolevel.name)

                    if len(node) > 0:
                        add_legislative_level_for_geolevel(
                            node[0], body, subject, obj)

                parentless = self.store.get_top_regional_geolevel(region)

                if parentless is not None:
                    add_legislative_level_for_geolevel(
                        parentless, legislative_body, subject, None)

        return True

    def import_scoring(self, force):
        """
        Create the Scoring models.

        @param force: Should the Scoring settings be written if the model already exist?
        @returns: A flag indicating if the import was successful.
        """
        result = True
        if not self.store.has_scoring():
            logger.debug('Scoring not configured')

        admin = User.objects.filter(is_superuser=True)
        if admin.count() == 0:
            logger.debug(
                'There was no superuser installed; ScoreDisplays need to be assigned '
                'ownership to a superuser.')
            return False
        else:
            admin = admin[0]

        # Import score displays.
        for sd in self.store.filter_scoredisplays():
            lb = LegislativeBody.objects.get(name=sd.get('legislativebodyref'))

            sd_obj, created = ScoreDisplay.objects.get_or_create(
                name=sd.get('id')[:50],
                title=sd.get('title')[:50],
                legislative_body=lb,
                is_page=sd.get('type') == 'leaderboard',
                cssclass=(sd.get('cssclass') or '')[:50],
                owner=admin)

            for locale in [l[0] for l in settings.LANGUAGES]:
                po = self.poutils[locale]
                po.add_or_update(
                    msgid=u'%s short label' % sd.get('id'),
                    msgstr=sd.get('title') or '',
                    occurs=[(
                        os.path.abspath(self.store.datafile),
                        sd.sourceline,
                    )])
                po.add_or_update(
                    msgid=u'%s label' % sd.get('id'),
                    msgstr=sd.get('title') or '',
                    occurs=[(
                        os.path.abspath(self.store.datafile),
                        sd.sourceline,
                    )])
                po.add_or_update(
                    msgid=u'%s long description' % sd.get('id'),
                    msgstr='',
                    occurs=[(
                        os.path.abspath(self.store.datafile),
                        sd.sourceline,
                    )])

            if created:
                logger.debug('Created ScoreDisplay "%s"', sd.get('title'))
            else:
                logger.debug('ScoreDisplay "%s" already exists',
                             sd.get('title'))

            # Import score panels for this score display.
            for spref in self.store.filter_displayed_score_panels(sd):
                sp = self.store.get_score_panel(spref.get('ref'))
                name = sp.get('id')[:50]
                position = int(sp.get('position'))
                template = sp.get('template')[:500]
                cssclass = (sp.get('cssclass') or '')[:50]
                pnltype = sp.get('type')[:20]

                is_ascending = sp.get('is_ascending')
                if is_ascending is None:
                    is_ascending = True

                ascending = sp.get('is_ascending')
                sp_obj, created = ScorePanel.objects.get_or_create(
                    type=pnltype,
                    position=position,
                    name=name,
                    template=template,
                    cssclass=cssclass,
                    is_ascending=(ascending is None or ascending == 'true'),
                )

                if created:
                    sd_obj.scorepanel_set.add(sp_obj)

                    logger.debug('Created ScorePanel "%s"', name)
                else:
                    attached = sd_obj.scorepanel_set.filter(
                        id=sp_obj.id).count() == 1
                    if not attached:
                        sd_obj.scorepanel_set.add(sp_obj)

                    logger.debug('ScorePanel "%s" already exists', name)

                for locale in [l[0] for l in settings.LANGUAGES]:
                    po = self.poutils[locale]
                    po.add_or_update(
                        msgid=u'%s short label' % sp_obj.name,
                        msgstr=sp.get('title') or '',
                        occurs=[(
                            os.path.abspath(self.store.datafile),
                            sp.sourceline,
                        )])
                    po.add_or_update(
                        msgid=u'%s label' % sp_obj.name,
                        msgstr=sp.get('title') or '',
                        occurs=[(
                            os.path.abspath(self.store.datafile),
                            sp.sourceline,
                        )])
                    po.add_or_update(
                        msgid=u'%s long description' % sp_obj.name,
                        msgstr='',
                        occurs=[(
                            os.path.abspath(self.store.datafile),
                            sp.sourceline,
                        )])

                # Import score functions for this score panel
                for sfref in self.store.filter_paneled_score_functions(sp):
                    sf_node = self.store.get_score_function(sfref.get('ref'))
                    sf_obj = self.import_function(sf_node, force)

                    # Add ScoreFunction reference to ScorePanel
                    sp_obj.score_functions.add(sf_obj)

        # It's possible to define ScoreFunctions that are not part of any ScorePanels, yet
        # still need to be added to allow for user selection. Find and import these functions.
        for sf_node in self.store.filter_score_functions():
            self.import_function(sf_node, force)

        # Import validation criteria.
        if not self.store.has_validation():
            logger.debug('Validation not configured')
            return False

        for vc in self.store.filter_criteria():
            lb = LegislativeBody.objects.get(name=vc.get('legislativebodyref'))

            for crit in self.store.filter_criteria_criterion(vc):
                # Import the score function for this validation criterion
                sfref = self.store.get_criterion_score(crit)
                try:
                    sf = self.store.get_score_function(sfref.get('ref'))
                except:
                    logger.info(
                        "Couldn't import ScoreFunction for Criteria %s",
                        crit.get('name'))
                    result = False

                sf_obj = self.import_function(sf, force)

                # Import this validation criterion
                attributes = {
                    'name': crit.get('id')[0:50],
                    'function': sf_obj,
                    'legislative_body': lb
                }
                crit_obj, created, changed, message = check_and_update(
                    ValidationCriteria, overwrite=force, **attributes)

                for locale in [l[0] for l in settings.LANGUAGES]:
                    po = self.poutils[locale]
                    po.add_or_update(
                        msgid=u'%s short label' % attributes['name'],
                        msgstr=crit.get('name') or '',
                        occurs=[(
                            os.path.abspath(self.store.datafile),
                            crit.sourceline,
                        )])
                    po.add_or_update(
                        msgid=u'%s label' % attributes['name'],
                        msgstr=crit.get('name') or '',
                        occurs=[(
                            os.path.abspath(self.store.datafile),
                            crit.sourceline,
                        )])
                    po.add_or_update(
                        msgid=u'%s long description' % attributes['name'],
                        msgstr=crit.get('description') or '',
                        occurs=[(
                            os.path.abspath(self.store.datafile),
                            crit.sourceline,
                        )])

                if changed and not force:
                    logger.info(message)
                else:
                    logger.debug(message)

        return result

    def import_function(self, node, force):
        """
        Create the ScoreFunction models and child scores.

        @param force: Should the ScoreFunction settings be written if the model already exist?
        @returns: A newly created score function object.
        """
        attributes = {
            'calculator': node.get('calculator')[:500],
            'name': node.get('id')[:50],
            'is_planscore': node.get('type') == 'plan'
        }
        fn_obj, created, changed, message = check_and_update(
            ScoreFunction, overwrite=force, **attributes)

        for locale in [l[0] for l in settings.LANGUAGES]:
            po = self.poutils[locale]
            po.add_or_update(
                msgid=u'%s short label' % attributes['name'],
                msgstr=node.get('label') or '',
                occurs=[(
                    os.path.abspath(self.store.datafile),
                    node.sourceline,
                )])
            po.add_or_update(
                msgid=u'%s label' % attributes['name'],
                msgstr=node.get('label') or '',
                occurs=[(
                    os.path.abspath(self.store.datafile),
                    node.sourceline,
                )])
            po.add_or_update(
                msgid=u'%s long description' % attributes['name'],
                msgstr=node.get('description') or '',
                occurs=[(
                    os.path.abspath(self.store.datafile),
                    node.sourceline,
                )])

        lbodies = []
        for lb in self.store.filter_function_legislative_bodies(node):
            lbodies.append(lb.get('ref'))
        lbodies = list(LegislativeBody.objects.filter(name__in=lbodies))
        fn_obj.selectable_bodies.add(*lbodies)

        if changed and not force:
            logger.info(message)
        else:
            logger.debug(message)

        # Recursion if any ScoreArguments!
        self.import_arguments(fn_obj, node, force)

        return fn_obj

    def import_arguments(self, score_function, node, force):
        """
        Create the ScoreArgument models.

        @param force: Should the ScoreArgument settings be written if the model already exist?
        @returns: A flag indicating if the import was successful.
        """
        # Import arguments for this score function
        for arg in self.store.filter_function_arguments(node):
            name = arg.get('name')[:50]
            arg_obj, created = ScoreArgument.objects.get_or_create(
                function=score_function,
                type='literal',
                argument=name,
            )
            config_value = arg.get('value')[:50]
            if created:
                arg_obj.value = config_value
                arg_obj.save()
                logger.debug('Created literal ScoreArgument "%s"', name)
            else:
                if arg_obj.value == config_value:
                    logger.debug('literal ScoreArgument "%s" already exists',
                                 name)
                elif force:
                    arg_obj.value = config_value
                    arg_obj.save()
                    logger.info('literal ScoreArgument "%s" value UPDATED',
                                name)
                else:
                    logger.info(
                        'Didn\'t change ScoreArgument %s; attribute(s) "value" differ(s) from '
                        'database configuration.\n\tWARNING: Sync your config file to your app '
                        'configuration or use the -f switch with setup to force changes',
                        name)

        # Import subject arguments for this score function
        for subarg in self.store.filter_function_subject_arguments(node):
            name = subarg.get('name')[:50]
            config_value = subarg.get('ref')[:50]
            subarg_obj, created = ScoreArgument.objects.get_or_create(
                function=score_function,
                type='subject',
                argument=name,
            )

            if created:
                subarg_obj.value = config_value
                subarg_obj.save()
                logger.debug('Created subject ScoreArgument "%s"', name)
            else:
                if subarg_obj.value == config_value:
                    logger.debug('subject ScoreArgument "%s" already exists',
                                 name)
                elif force:
                    subarg_obj.value = config_value
                    subarg_obj.save()
                    logger.info('subject ScoreArgument "%s" value UPDATED',
                                name)
                else:
                    logger.info(
                        'Didn\'t change ScoreArgument %s; attribute(s) "value" differ(s) from'
                        ' database configuration.\n\tWARNING: Sync your config file to your app '
                        ' configuration or use the -f switch with setup to force changes',
                        name)

        # Import score arguments for this score function
        for scorearg in self.store.filter_function_score_arguments(node):
            argfn = self.store.get_score_function(scorearg.get('ref'))
            if argfn is None:
                logger.info(
                    "ERROR: No such function %s can be found for argument of %s",
                    scorearg.get('ref'), score_function.name)
                continue

            self.import_function(argfn, force)
            config_value = scorearg.get('ref')[:50]
            name = scorearg.get('name')[:50]

            scorearg_obj, created = ScoreArgument.objects.get_or_create(
                function=score_function, type='score', argument=name)

            if created:
                scorearg_obj.value = config_value
                scorearg_obj.save()
                logger.debug('created subject scoreargument "%s"', name)
            else:
                if scorearg_obj.value == config_value:
                    logger.debug('subject scoreargument "%s" already exists',
                                 name)
                elif force:
                    scorearg_obj.value = config_value
                    scorearg_obj.save()
                    logger.info('subject scoreargument "%s" value UPDATED',
                                name)
                else:
                    logger.info(
                        'Didn\'t change scoreargument %s; attribute(s) "value" differ(s) from '
                        'database configuration.\n\twarning: sync your config file to your app'
                        ' configuration or use the -f switch with setup to force changes',
                        name)

        return True

    def import_contiguity_overrides(self):
        """
        Create the ContiguityOverride models. This is optional.

        @returns: A flag indicating if the import was successful.
        """
        # Remove previous contiguity overrides
        ContiguityOverride.objects.all().delete()

        if not self.store.has_contiguity_overrides():
            logger.debug('ContiguityOverrides not configured')

        # Import contiguity overrides.
        for co in self.store.filter_contiguity_overrides():
            portable_id = co.get('id')
            temp = Geounit.objects.filter(portable_id=portable_id)
            if (len(temp) == 0):
                raise Exception('There exists no geounit with portable_id: %s'
                                % portable_id)
            override_geounit = temp[0]

            portable_id = co.get('connect_to')
            temp = Geounit.objects.filter(portable_id=portable_id)
            if (len(temp) == 0):
                raise Exception('There exists no geounit with portable_id: %s'
                                % portable_id)
            connect_to_geounit = temp[0]

            co_obj, created = ContiguityOverride.objects.get_or_create(
                override_geounit=override_geounit,
                connect_to_geounit=connect_to_geounit)

            if created:
                logger.debug('Created ContiguityOverride "%s"', str(co_obj))
            else:
                logger.debug('ContiguityOverride "%s" already exists',
                             str(co_obj))

        return True


class SpatialUtils:
    """
    A utility that aids in the configuration of the spatial components in the
    configuration.
    """

    def __init__(self, store=None, config=None):
        """
        Create a new spatial utility, based on the stored config.

        @keyword store: Optional L{StoredConfig} that contains configuration settings.
        @keyword config: Optional configuration settings.
        """
        self.host = os.getenv('MAP_SERVER_HOST')
        self.port = os.getenv('WEB_APP_PORT')

        if store is not None:
            self.store = store

            mapconfig = self.store.get_mapserver()

            self.ns = mapconfig.get('ns')
            self.nshref = mapconfig.get('nshref')

        elif isinstance(config, dict):
            try:
                self.ns = config['ns']
                self.nshref = config['nshref']
            except:
                logger.error(
                    'SpatialUtils is missing a required key in the settings dictionary.'
                )
                raise

        else:
            logger.error(
                'SpatialUtils requires either a stored config or a dictionary of settings.'
            )
            raise Exception()

        self.origin = 'http://%s:%s/geoserver' % (self.host, self.port)

        # Hardcode the admin user name to the default since the API doesn't
        # provide a way to easily change it.
        admin_user = 'admin'
        admin_password = os.getenv('MAP_SERVER_ADMIN_PASSWORD')
        user_pass = '%s:%s' % (admin_user, admin_password)

        auth = 'Basic %s' % base64.b64encode(user_pass)
        self.headers = {
            'default': {
                'Authorization': auth,
                'Content-Type': 'application/json',
                'Accepts': 'application/json'
            },
            'sld': {
                'Authorization': auth,
                'Content-Type': 'application/vnd.ogc.sld+xml',
                'Accepts': 'application/xml'
            }
        }

    def purge_geoserver(self):
        """
        Remove any configured items in geoserver for the namespace.

        This configuration step prevents conflicts in geowebcache
        when the datastore and featuretype is reconfigured without
        discarding the old featuretype.

        @returns: A flag indicating if the configuration was purged successfully.
        """
        # Delete workspace
        if not self._rest_config(
                'DELETE', '/geoserver/rest/workspaces/%s.json?recurse=true' % self.ns):
            logger.debug("Could not delete workspace %s", self.ns)
            return False

        # Get a list of styles
        sts_cfg = self._read_config('/geoserver/rest/styles.json',
                                    "Could not get styles.")
        if sts_cfg is not None:
            includes = ['^%s:.*' % self.ns]
            for st_cfg in sts_cfg['styles']['style']:
                skip = False
                for inc in includes:
                    skip = skip or re.compile(inc).match(
                        st_cfg['name']) is None
                if skip:
                    # This style doesn't match any style starting with the prefix.
                    continue

                # Delete the style
                if not self._rest_config('DELETE', st_cfg['href']):
                    logger.debug("Could not delete style %s", st_cfg['name'])
                else:
                    logger.debug("Deleted style %s", st_cfg['name'])

        return True

    def configure_geoserver(self):
        """
        Configure all the components in Geoserver. This method configures the
        geoserver workspace, datastore, feature types, and styles. All
        configuration steps get processed through the REST config.

        @returns: A flag indicating if geoserver was configured correctly.
        """
        # Set the Geoserver proxy base url
        # This is necessary for geoserver to know where to look for its internal
        # resources like its copy of openlayers and other things
        settings = requests.get(
            '%s/rest/settings.json' % self.origin,
            headers=self.headers['default']).json()

        settings['global']['proxyBaseUrl'] = self.origin

        resp = requests.put(
            '%s/rest/settings' % self.origin,
            json=settings,
            headers=self.headers['default'])
        resp.raise_for_status()

        # Create our namespace
        namespace_url = '%s/rest/namespaces' % self.origin
        namespace_obj = {'namespace': {'prefix': self.ns, 'uri': self.nshref}}
        if self._check_spatial_resource(namespace_url, self.ns, namespace_obj):
            logger.debug('Created namespace "%s"' % self.ns)
        else:
            logger.warn('Could not create Namespace')
            return False

        # Create our DataStore
        if self.store is None:
            logger.warning(
                'Geoserver cannot be fully configured without a stored config.'
            )
            return False

        data_store_url = '%s/rest/workspaces/%s/datastores' % (self.origin,
                                                               self.ns)
        data_store_name = 'PostGIS'

        data_store_obj = {
            'dataStore': {
                'name': data_store_name,
                'workspace': {
                    'name': self.ns,
                    'link': self.nshref
                },
                'connectionParameters': {
                    'host': os.getenv('DATABASE_HOST', self.host),
                    'port': os.getenv('DATABASE_PORT'),
                    'database': os.getenv('DATABASE_DATABASE'),
                    'user': os.getenv('DATABASE_USER'),
                    'passwd': os.getenv('DATABASE_PASSWORD'),
                    'dbtype': 'postgis',
                    'schema': 'public'
                }
            }
        }

        if self._check_spatial_resource(data_store_url, data_store_name,
                                        data_store_obj):
            logger.debug('Created datastore "%s"' % data_store_name)
        else:
            logger.warn('Could not create Datastore')
            return False

        # Create the feature types and their styles
        subject_attrs = [
            {'name': 'name', 'binding': 'java.lang.String'},
            {'name': 'geom', 'binding': 'com.vividsolutions.jts.geom.MultiPolygon'},
            {'name': 'geolevel_id', 'binding': 'java.lang.Integer'},
            {'name': 'number', 'binding': 'java.lang.Double'},
            {'name': 'percentage', 'binding': 'java.lang.Double'},
        ]

        if self.create_featuretype(
            'identify_geounit',
            attributes=[
                {'name': 'id', 'binding': 'java.lang.Integer'},
                {'name': 'name', 'binding': 'java.lang.String'},
                {'name': 'geolevel_id', 'binding': 'java.lang.Integer'},
                {'name': 'geom', 'binding': 'com.vividsolutions.jts.geom.MultiPolygon'},
                {'name': 'number', 'binding': 'java.lang.Double'},
                {'name': 'percentage', 'binding': 'java.lang.Double'},
                {'name': 'subject_id', 'binding': 'java.lang.Integer'}
            ]
        ):
            logger.debug('Created feature type "identify_geounit"')
        else:
            logger.warn('Could not create "identify_geounit" feature type')

        for geolevel in Geolevel.objects.all():
            if geolevel.legislativelevel_set.all().count() == 0:
                # Skip 'abstract' geolevels if regions are configured
                continue

            if self.create_featuretype(
                'simple_%s' % geolevel.name,
                attributes=[
                    {'name': 'name', 'binding': 'java.lang.String'},
                    {'name': 'geolevel_id', 'binding': 'java.lang.Integer'},
                    {'name': 'geom', 'binding': 'com.vividsolutions.jts.geom.MultiPolygon'}
                ]
            ):
                logger.debug(
                    'Created "simple_%s" feature type' % geolevel.name)
            else:
                logger.warn('Could not create "simple_%s" simple feature type'
                            % geolevel.name)

            simple_district_attrs = [
                {'name': 'district_id', 'binding': 'java.lang.Integer'},
                {'name': 'plan_id', 'binding': 'java.lang.Integer'},
                {'name': 'legislative_body_id', 'binding': 'java.lang.Integer'},
                {'name': 'geom', 'binding': 'com.vividsolutions.jts.geom.MultiPolygon'}
            ]
            if self.create_featuretype('simple_district_%s' % geolevel.name,
                                       attributes=simple_district_attrs):
                logger.debug('Created "simple_district_%s" feature type' %
                             geolevel.name)
            else:
                logger.warn(
                    'Could not create "simple_district_%s" simple district feature type'
                    % geolevel.name)

            all_subjects = Subject.objects.all().order_by('sort_key')
            if all_subjects.count() > 0:
                subject = all_subjects[0]

                # Create NONE demographic layer, based on first subject
                featuretype_name = get_featuretype_name(geolevel.name)
                if self.create_featuretype(
                        featuretype_name,
                        alias=get_featuretype_name(geolevel.name,
                                                   subject.name),
                        attributes=subject_attrs):
                    logger.debug(
                        'Created "%s" feature type' % featuretype_name)
                else:
                    logger.warn('Could not create "%s" feature type' %
                                featuretype_name)

                if self.create_style(featuretype_name):
                    logger.debug('Created "%s" style' % featuretype_name)
                else:
                    logger.warn(
                        'Could not create style for "%s"' % featuretype_name)

                try:
                    sld_content = SpatialUtils.generate_style(
                        geolevel,
                        geolevel.geounit_set.all(),
                        1,
                        layername='none')

                    self.write_style(geolevel.name + '_none', sld_content)
                except Exception:
                    logger.error(traceback.format_exc())
                    # Have to return here, since there's no guarantee sld_content is defined
                    return False

                if self.set_style(featuretype_name, sld_content):
                    logger.debug('Set "%s" style' % featuretype_name)
                else:
                    logger.warn('Could not set "%s" style' % featuretype_name)

                if self.assign_style(featuretype_name, featuretype_name):
                    logger.debug('Assigned style for "%s"' % featuretype_name)
                else:
                    logger.warn(
                        'Could not assign style for "%s"' % featuretype_name)

                # Create boundary layer, based on geographic boundaries
                featuretype_name = '%s_boundaries' % geolevel.name
                if self.create_featuretype(
                        featuretype_name,
                        alias=get_featuretype_name(geolevel.name,
                                                   subject.name),
                        attributes=subject_attrs):
                    logger.debug(
                        'Created "%s" feature type' % featuretype_name)
                else:
                    logger.warn('Could not create "%s" feature type' %
                                featuretype_name)

                if self.create_style(featuretype_name):
                    logger.debug('Created "%s" style' % featuretype_name)
                else:
                    logger.warn(
                        'Could not create "%s" style' % featuretype_name)

                try:
                    sld_content = SpatialUtils.generate_style(
                        geolevel,
                        geolevel.geounit_set.all(),
                        1,
                        layername='boundary')

                    self.write_style(geolevel.name + '_boundaries',
                                     sld_content)
                except Exception:
                    logger.error(traceback.format_exc())

                if self.set_style(featuretype_name, sld_content):
                    logger.debug('Set "%s" style' % featuretype_name)
                else:
                    logger.warn('Could not set "%s" style' % featuretype_name)

                if self.assign_style(featuretype_name, featuretype_name):
                    logger.debug('Assigned style for "%s"' % featuretype_name)
                else:
                    logger.warn(
                        'Could not assign style for "%s"' % featuretype_name)

            for subject in all_subjects:
                featuretype_name = get_featuretype_name(
                    geolevel.name, subject.name)

                if self.create_featuretype(
                        featuretype_name, attributes=subject_attrs):
                    logger.debug(
                        'Created "%s" feature type' % featuretype_name)
                else:
                    logger.warn('Could not create "%s" subject feature type' %
                                featuretype_name)

                if self.create_style(featuretype_name):
                    logger.debug('Created "%s" style' % featuretype_name)
                else:
                    logger.warn(
                        'Could not create "%s" style' % featuretype_name)

                try:
                    sld_content = SpatialUtils.generate_style(
                        geolevel,
                        geolevel.geounit_set.all(),
                        5,
                        subject=subject)

                    self.write_style(geolevel.name + '_' + subject.name,
                                     sld_content)
                except Exception:
                    logger.error(traceback.format_exc())

                if self.set_style(featuretype_name, sld_content):
                    logger.debug('Set "%s" style' % featuretype_name)
                else:
                    logger.warn('Could not set "%s" style' % featuretype_name)

                if self.assign_style(featuretype_name, featuretype_name):
                    logger.debug('Assigned "%s" style' % featuretype_name)
                else:
                    logger.warn(
                        'Could not assign "%s" style' % featuretype_name)

        # map all the legislative body / geolevels combos
        ngeolevels_map = []
        for lbody in LegislativeBody.objects.all():
            geolevels = lbody.get_geolevels()
            # list by # of geolevels, and the first geolevel
            ngeolevels_map.append((
                len(geolevels),
                lbody,
                geolevels[0],
            ))
        # sort descending by the # of geolevels
        ngeolevels_map.sort(key=lambda x: -x[0])

        # get the first geolevel from the legislative body with the most geolevels
        geolevel = ngeolevels_map[0][2]

        # create simple_district as an alias to the largest geolevel (e.g. counties)
        if self.create_featuretype(
                'simple_district',
                alias='simple_district_%s' % geolevel.name,
                attributes=simple_district_attrs):
            logger.debug('Created "simple_district" feature type')
        else:
            logger.warn('Could not create "simple_district" feature type')

        if self.assign_style('simple_district', 'polygon'):
            logger.debug('Assigned style "polygon" to feature type')
        else:
            logger.warn('Could not assign "polygon" style to simple_district')

        try:
            # add the district intervals
            intervals = self.store.filter_nodes(
                '//ScoreFunction[@calculator="redistricting.calculators.Interval"]'
            )
            for interval in intervals:
                subject_name = interval.xpath('SubjectArgument')[0].get('ref')
                lbody_name = interval.xpath('LegislativeBody')[0].get('ref')
                interval_avg = float(
                    interval.xpath('Argument[@name="target"]')[0].get('value'))
                interval_bnd1 = float(
                    interval.xpath('Argument[@name="bound1"]')[0].get('value'))
                interval_bnd2 = float(
                    interval.xpath('Argument[@name="bound2"]')[0].get('value'))

                intervals = [(interval_avg + interval_avg * interval_bnd2,
                              None, _('Far Over Target'), {
                                  'fill': '#ebb95e',
                                  'fill-opacity': '0.3'
                              }), (interval_avg + interval_avg * interval_bnd1,
                                   interval_avg + interval_avg * interval_bnd2,
                                   _('Over Target'), {
                                       'fill': '#ead3a7',
                                       'fill-opacity': '0.3'
                                   }),
                             (interval_avg - interval_avg * interval_bnd1,
                              interval_avg + interval_avg * interval_bnd1,
                              _('Meets Target'), {
                                  'fill': '#eeeeee',
                                  'fill-opacity': '0.1'
                              }), (interval_avg - interval_avg * interval_bnd2,
                                   interval_avg - interval_avg * interval_bnd1,
                                   _('Under Target'), {
                                       'fill': '#a2d5d0',
                                       'fill-opacity': '0.3'
                                   }),
                             (None,
                              interval_avg - interval_avg * interval_bnd2,
                              _('Far Under Target'), {
                                  'fill': '#0aac98',
                                  'fill-opacity': '0.3'
                              })]

                doc = sld.StyledLayerDescriptor()
                fts = doc.create_namedlayer(
                    subject_name).create_userstyle().create_featuretypestyle()

                for interval in intervals:
                    imin, imax, ititle, ifill = interval
                    rule = fts.create_rule(ititle, sld.PolygonSymbolizer)
                    if imin is None:
                        rule.create_filter('number', '<', str(
                            int(round(imax))))
                    elif imax is None:
                        rule.create_filter('number', '>=', str(
                            int(round(imin))))
                    else:
                        f1 = sld.Filter(rule)
                        f1.PropertyIsGreaterThanOrEqualTo = sld.PropertyCriterion(
                            f1, 'PropertyIsGreaterThanOrEqualTo')
                        f1.PropertyIsGreaterThanOrEqualTo.PropertyName = 'number'
                        f1.PropertyIsGreaterThanOrEqualTo.Literal = str(
                            int(round(imin)))

                        f2 = sld.Filter(rule)
                        f2.PropertyIsLessThan = sld.PropertyCriterion(
                            f2, 'PropertyIsLessThan')
                        f2.PropertyIsLessThan.PropertyName = 'number'
                        f2.PropertyIsLessThan.Literal = str(int(round(imax)))

                        rule.Filter = f1 + f2

                    ps = rule.PolygonSymbolizer
                    ps.Fill.CssParameters[0].Value = ifill['fill']
                    ps.Fill.create_cssparameter('fill-opacity',
                                                ifill['fill-opacity'])
                    ps.Stroke.CssParameters[0].Value = '#fdb913'
                    ps.Stroke.CssParameters[1].Value = '2'
                    ps.Stroke.create_cssparameter('stroke-opacity', '1')

                self.write_style(
                    lbody_name + '_' + subject_name,
                    doc.as_sld(pretty_print=True))

        except Exception:
            logger.warn(traceback.format_exc())
            logger.warn('LegislativeBody intervals are not configured.')

        logger.info("Geoserver configuration complete.")

        # finished configure_geoserver
        return True

    def create_featuretype(self,
                           feature_type_name,
                           data_store_name='PostGIS',
                           alias=None,
                           attributes=[]):
        """
        Create a featuretype.

        @param feature_type_name: The name of the feature type.
        @keyword data_store_name: Optional. The name of the datastore. Defaults to 'PostGIS'
        @keyword alias: Optional. The new feature type is an alias for this names feature type.
        @returns: A flag indicating if the feature type was successfully created.
        """
        feature_type_url = '%s/rest/workspaces/%s/datastores/%s/featuretypes' % (
            self.origin, self.ns, data_store_name)

        feature_type_obj = SpatialUtils.feature_template(
            feature_type_name, alias=alias, attributes=attributes)
        return self._check_spatial_resource(
            feature_type_url, feature_type_name, feature_type_obj)

    def _check_spatial_resource(self, url, name, dictionary, update=False):
        """
        This method will check geoserver for the existence of an object.
        It will create the object if it doesn't exist.

        @param url: The URL of the resource.
        @param name: The name of the resource.
        @param dictionary: A dictionary of settings to the resource.
        @keyword type_name: Optional. Name of the type, if different from the name.
        @keyword update: Optional. Update the featuretype if it exists?
        @returns: A flag indicating if the configuration call completed successfully.
        """
        # TODO: this throws a 404 from geoserver every time it can't find something,
        # and we expect it not to be able to find something pretty often. While I wouldn't
        # expect this to run frequently on a deployed instance, it's a _ton_ of error message
        # noise for local development, especially given that nothing is actually going wrong
        if self._rest_check('%s/%s.json' % (url, name)):
            if update:
                if not self._rest_config(
                        'PUT', url, data=json.dumps(dictionary)):
                    return False

        else:
            if not self._rest_config('POST', url, data=json.dumps(dictionary)):
                return False

        return True

    @staticmethod
    def feature_template(name, title=None, alias=None, attributes=[]):
        """
        Return a common format for feature types.

        @param name: The name of the feature type.
        @keyword title: Optional. The title of the featuretype, defaults to name.
        @keyword alias: Optional. The nativeName of the featuretype, defaults to name.
        @returns: A dictionary of settings for all feature types.
        """
        nativeName = alias if alias is not None else name
        return {
            'featureType': {
                'name': name,
                'nativeName': nativeName,
                'namespace': {
                    'name': 'pmpPublic',
                    'href': 'https://github.com/publicmapping/districtbuilder'
                },
                'title': name if title is None else title,
                'abstract': 'a feature',
                'keywords': [],
                'metadataLinks': [],
                'dataLinks': [],
                'nativeCRS': 'EPSG:900913',
                'srs': 'EPSG:900913',
                # Set the bounding box to the maximum spherical mercator extent
                # in order to avoid all issues with geowebcache tile offsets
                'nativeBoundingBox': {
                    'minx': '%0.1f' % -20037508.342789244,
                    'miny': '%0.1f' % -20048966.1040146,
                    'maxx': '%0.1f' % 20037508.342789244,
                    'maxy': '%0.1f' % 20048966.104014594,
                },
                'latLonBoundingBox': {
                    'minx': -180,
                    'miny': -85.1,
                    'maxx': 180,
                    'maxy': 85.1,
                    'crs': 'EPSG:4326'
                },
                'maxFeatures': settings.FEATURE_LIMIT + 1,
                'attributes': {
                    'attribute': attributes
                }
            }
        }

    @staticmethod
    def get_binding(field):
        """Return a java class for this field type"""

        return {
            'AutoField': 'java.lang.Integer',
            'BooleanField': 'java.lang.Boolean',
            'CharField': 'java.lang.String',
            'PositiveIntegerField': 'java.lang.Integer',
            'FloatField': 'java.lang.Double',
            'MultiPolygonField': 'com.vividsolutions.jts.geom.MultiPolygon',
            'PointField': 'com.vividsolutions.jts.geom.Point'
        }[field.get_internal_type()]

    def _rest_check(self, url):
        """
        Attempt to get a REST resource. If the resource exists, and can
        be retrieved successfully, it will pass the check.

        @returns: True if the resource exists and is readable.
        """
        try:
            resp = requests.get(
                url,
                headers=self.headers['default'],
                params={
                    'quietOnNotFound': True
                })
            resp.raise_for_status()
            return resp.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def _rest_config(self, method, url, data=None, headers=None):
        """
        Configure a REST resource. This issues an HTTP POST or PUT request
        to configure or update the specified resource.

        @param method: The HTTP verb to use (GET, PUT, POST)
        @param url: The URL to access.
        @param data: The serialized data to send.
        @param msg: The error message to report if something goes wrong.
        @keyword headers: Optional. HTTP headers to include in the transaction.
        @returns: True if the configuration succeeded.
        """
        if headers is None:
            headers = self.headers['default']
        try:
            conn = httplib.HTTPConnection(self.host, self.port)
            conn.request(method, url, data, headers)
            rsp = conn.getresponse()
            rsp.read()  # and discard
            conn.close()
            if rsp.status != 201 and rsp.status != 200:
                logger.debug('HTTP Status: %d, %s %s' % (
                    rsp.status,
                    method,
                    url,
                ))
                logger.debug(data)
                return False
        except Exception as ex:
            logger.debug(ex)
            return False

        return True

    def _read_config(self, url, msg, headers=None):
        """
        Read a configured REST resource.

        @param url: The URL to access.
        @param msg: An error message to print if something goes wrong.
        @keyword headers: Optional. HTTP headers to send with the request.
        @returns: A dictionary loaded from a JSON response.
        """
        if headers is None:
            headers = self.headers['default']
        try:
            conn = httplib.HTTPConnection(self.host, self.port)
            conn.request('GET', url, None, headers)
            rsp = conn.getresponse()
            response = rsp.read()  # and discard
            conn.close()
            if rsp.status != 201 and rsp.status != 200:
                return None

            return json.loads(response)
        except Exception:
            return None

    def create_style(self, featuretype):
        """
        Check Geoserver to see if a named style exists. Creates the style if not.

        @returns: True if the object exists or was created. False on error.
        """
        nsfeaturetype = '%s:%s' % (
            self.ns,
            featuretype,
        )
        style_obj = {
            'style': {
                'name': nsfeaturetype,
                'filename': '%s.sld' % nsfeaturetype
            }
        }

        # Create the styles for the demographic layers
        style_url = '%s/rest/styles' % self.origin

        # Get or create the spatial style
        return self._check_spatial_resource(style_url, nsfeaturetype,
                                            style_obj)

    @staticmethod
    def generate_style(geolevel, qset, nclasses, subject=None, layername=None):
        """
        Generate SLD content for a queryset. This uses quantile classification
        for nclasses classes, using the 'Greys' colorbrewer palette, on an inverted
        gradient. The queryset is assumed to be all the geounits in a geolevel.
        The subject is an instance of the Subject model.
        """
        if subject:
            qset = qset.filter(characteristic__subject=subject)
            us_title = subject.get_short_label()
        else:
            us_title = layername

        qset = qset.annotate(Avg('characteristic__number'))

        doc = generator.as_quantiles(
            qset,
            'characteristic__number__avg',
            nclasses,
            propertyname='number',
            userstyletitle=us_title,
            colorbrewername='Greys',
            invertgradient=False)

        # set the width of the borders to 0.25 by default
        strokes = doc._node.xpath('//sld:Stroke', namespaces=doc._nsmap)
        for stroke in strokes:
            node = stroke.xpath(
                'sld:CssParameter[@name="stroke-width"]',
                namespaces=doc._nsmap)[0]
            node.text = '0.25'

        if subject:
            # set the name of the layer
            node = doc._node.xpath(
                '//sld:NamedLayer/sld:Name', namespaces=doc._nsmap)[0]
            node.text = subject.name

        elif nclasses == 1:
            # remove any fill if subject is missing
            fill = doc._node.xpath('//sld:Fill', namespaces=doc._nsmap)[0]
            fill.getparent().remove(fill)

            if layername:
                # set the name of the layer
                name = doc._node.xpath('//sld:Name', namespaces=doc._nsmap)[0]
                name.text = layername

                # set the title of the user style
                name = doc._node.xpath(
                    '//sld:UserStyle/sld:Title', namespaces=doc._nsmap)[0]
                name.text = geolevel.get_long_description()

                # set the title of the rule
                name = doc._node.xpath(
                    '//sld:Rule/sld:Title', namespaces=doc._nsmap)[0]
                name.text = _('Boundary')

                if layername == 'boundary':
                    stroke = doc._node.xpath(
                        '//sld:Stroke', namespaces=doc._nsmap)[0]
                    node = stroke.xpath(
                        'sld:CssParameter[@name="stroke-width"]',
                        namespaces=doc._nsmap)[0]
                    node.text = '3'

                    node = stroke.xpath(
                        'sld:CssParameter[@name="stroke"]',
                        namespaces=doc._nsmap)[0]
                    node.text = '#2BB673'

                    strokeopacity = {'name': 'stroke-opacity'}
                    node = stroke.makeelement(
                        '{%s}CssParameter' % doc._nsmap['sld'],
                        attrib=strokeopacity,
                        nsmap=doc._nsmap)
                    node.text = '0.45'

                    stroke.append(node)

        return doc.as_sld()

    def set_style(self, featuretype, sld_content):
        """
        Assign SLD content to a style already in Geoserver.

        @returns: True if the named style was configured properly
        """
        # Configure the named style
        return self._rest_config(
            'PUT',
            '/geoserver/rest/styles/%s:%s' % (
                self.ns,
                featuretype,
            ),
            data=sld_content,
            headers=self.headers['sld'])

    def assign_style(self, featuretype, style_name):
        """
        Assign a configured style to a configured layer.

        @keyword featuretype: The type of the feature.
        @keyword style_name: The name of the style.
        """
        if not style_name == 'polygon':
            style_name = '%s:%s' % (self.ns, style_name)

        # Apply the uploaded style to the demographic layers
        layer = {
            'layer': {
                'defaultStyle': {
                    'name': style_name
                },
                'enabled': True
            }
        }

        if self._rest_config(
                'PUT',
                '/geoserver/rest/layers/%s:%s' % (
                    self.ns,
                    featuretype,
                ),
                data=json.dumps(layer)):
            return True

        return False

    def write_style(self, name, body):
        """
        Write the contents of an SLD to the file system in the location
        specified by the SLD_ROOT setting.
        """
        dest = '%s%s:%s.sld' % (
            settings.SLD_ROOT,
            self.ns,
            name,
        )
        try:
            sld = open(dest, 'w')
            sld.write(body)
            sld.close()

            logger.info('Saved "%s" style file' % dest)

            return True
        except Exception:
            logger.warn('Could not save "%s" style' % dest)
            return False

    def renest_geolevel(self, glconf, subject=None):
        """
        Perform a re-nesting of the geography in the geographic levels.

        Renesting the geometry works with Census Geography only that
        has treecodes.

        @param glconf: The configuration geolevel
        @keyword subject: Optional. The subject to aggregate, default aggregates everything.
        @returns: True when geolevel is completely renested.
        """
        parent = None

        # For each region in the stored config
        for region in self.store.filter_regions():
            # Get the specific geolevel from the region
            llevel = self.store.get_regional_geolevel(region, glconf.get('id'))

            # If this geolevel doesn't exist in this region, try the next region
            if llevel is None:
                continue

            # Get the parent node
            parent = llevel.getparent()
            while parent.getparent() is not None and parent.getparent(
            ).tag != 'GeoLevels':
                # Find the parent node (the geographic THIS geolevel should
                # match after renesting) by traveling up the nested GeoLevel
                # nodes until we get to the top.
                parent = parent.getparent()

            # Don't check any other regions if we've found a parent
            break

        parent_geolevel = self.store.get_geolevel(parent.get('ref'))
        if parent_geolevel is not None:
            parent = Geolevel.objects.get(
                name=parent_geolevel.get('name').lower()[:50])
        else:
            return False

        geolevel = Geolevel.objects.get(name=glconf.get('name').lower()[:50])
        return geolevel.renest(parent, subject=None, spatial=True)


class PoUtils:
    """
    Utility class to manage translation strings in xmlconfig files.
    """

    def __init__(self, locale):
        """
        Create a new utility object for a specific locale.
        """

        self.popath = 'locale/%(locale)s/LC_MESSAGES/xmlconfig.po' % {
            'locale': locale
        }
        self.mopath = 'locale/%(locale)s/LC_MESSAGES/xmlconfig.mo' % {
            'locale': locale
        }
        if os.path.exists(self.popath):
            logger.debug('Using existing xmlconfig message catalog.')
            self.pofile = polib.pofile(self.popath, check_for_duplicates=True)
        else:
            logger.debug('Creating new xmlconfig message catalog.')
            now = datetime.utcnow()
            now = now.replace(tzinfo=UTC())

            self.pofile = polib.POFile(check_for_duplicates=True)
            self.pofile.metadata = {
                'Project-Id-Version': '1.0',
                'Report-Msgid-Bugs-To': 'districtbuilder-dev@googlegroups.com',
                'POT-Creation-Date': now.strftime('%Y-%m-%d %H:%M%z'),
                'PO-Revision-Date': now.strftime('%Y-%m-%d %H:%M%z'),
                'Language': locale,
                'MIME-Version': '1.0',
                'Content-Type': 'text/plain; charset=UTF-8',
                'Content-Transfer-Encoding': '8bit'
            }
            if settings.ADMINS:
                self.pofile.metadata.update({
                    'Last-Translator':
                    '%s <%s>' % (settings.ADMINS[0][0], settings.ADMINS[0][1]),
                    'Language-Team':
                    '%s <%s>' % (settings.ADMINS[0][0], settings.ADMINS[0][1]),
                })

    def add_or_update(self, msgid='', msgstr='', occurs=[]):
        """
        Add a POEntry to the .po file, or update it if it already exists.

        @keyword msgid: The .po msgid
        @keyword msgstr: The .po msgstr
        """
        entry = self.pofile.find(msgid)
        if entry is None:
            entry = polib.POEntry(
                msgid=msgid, msgstr=msgstr, occurrences=occurs)
            self.pofile.append(entry)
        else:
            entry.msgstr = msgstr
            entry.occurences = occurs

    def save(self):
        """
        Save the .po file, and compile the .mo file.
        """
        logger.debug('Saving file %(po)s.', {'po': self.popath})
        self.pofile.save(self.popath)

        logger.debug('Saving file %(mo)s.', {'mo': self.mopath})
        self.pofile.save_as_mofile(self.mopath)


class UTC(tzinfo):
    """UTC"""

    def utcoffset(self, dt):
        return timedelta(0)

    def tzname(self, dt):
        return 'UTC'

    def dst(self, dt):
        return timedelta(0)
