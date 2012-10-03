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

import os, hashlib, logging, httplib, string, base64, json, traceback, types
from datetime import datetime, timedelta, tzinfo
from django.conf import settings
from django.db.models import Model
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.sessions.models import Session
from django.contrib.auth.models import User
from models import *
from rosetta import polib

logger = logging.getLogger(__name__)

def check_and_update(a_model, unique_id_field='name', overwrite=False, **kwargs):
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
        id_args = { unique_id_field: name }
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
        if not (isinstance(current_value, types.StringTypes)) and not (isinstance(current_value, Model)):
            config_value = type(current_value)(config_value)
        if current_value != config_value:
            if overwrite:
                current_object.__setattr__(key, config_value)
                changed = True
                message = 'UPDATED %s; CHANGED attribute(s) "%s"'
            else:
                message = 'Didn\'t change %s; attribute(s) "%s" differ(s) from database configuration.\n\tWARNING: Sync your config file to your app configuration or use the -f switch with setup to force changes'
            different.append(key)
    if overwrite and changed:
        current_object.save()
    return current_object, False, len(different) > 0, message % (object_name, ', '.join(different))


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
        except Exception, e:
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
            admcfg = self.store.get_admin()
            admin_attributes = {
                'first_name':'Admin',
                'last_name':'User',
                'is_staff':True,
                'is_active':True,
                'is_superuser':True,
                'username':admcfg.get('user')[:30],
                'email':admcfg.get('email')[:75]
            }

            admin, created, changed, message = check_and_update(User, unique_id_field='username', overwrite=force, **admin_attributes)

            if changed and not force:
                logger.info(message)
            else:
                logger.debug(message)

            if created or changed or force:
                m = hashlib.sha1()
                m.update(admcfg.get('password'))
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

            obj, created, changed, message = check_and_update(Region, overwrite=force, **attributes)

            for locale in [l[0] for l in settings.LANGUAGES]:
                po = self.poutils[locale]
                po.add_or_update(
                    msgid=u'%s short label' % attributes['name'],
                    msgstr=region.get('name') or '',
                    occurs=[(os.path.abspath(self.store.datafile), region.sourceline,)]
                )
                po.add_or_update(
                    msgid=u'%s label' % attributes['name'],
                    msgstr=region.get('label') or '',
                    occurs=[(os.path.abspath(self.store.datafile), region.sourceline,)]
                )
                po.add_or_update(
                    msgid=u'%s long description' % attributes['name'],
                    msgstr=region.get('description') or '',
                    occurs=[(os.path.abspath(self.store.datafile), region.sourceline,)]
                )

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
                'is_community': body.get('is_community')=='true'
            }

            body_by_region = self.store.filter_nodes('/DistrictBuilder/Regions/Region/LegislativeBodies/LegislativeBody[@ref="%s"]' % body.get('id'))
            if len(body_by_region) != 1:
                logger.info( "Legislative body %s not attributed to any region", attributes['name'])
                continue
            else:
                region_name = body_by_region[0].getparent().getparent().get('id')
            attributes['region'] = Region.objects.get(name=region_name)

            obj, created, changed, message = check_and_update(LegislativeBody, overwrite=force, **attributes)

            for locale in [l[0] for l in settings.LANGUAGES]:
                po = self.poutils[locale]
                po.add_or_update(
                    msgid=u'%s short label' % attributes['name'],
                    msgstr=body.get('short_label') or '%(district_id)s',
                    occurs=[(os.path.abspath(self.store.datafile), body.sourceline,)]
                )
                po.add_or_update(
                    msgid=u'%s label' % attributes['name'],
                    msgstr=body.get('long_label') or '%(district_id)s',
                    occurs=[(os.path.abspath(self.store.datafile), body.sourceline,)]
                )
                po.add_or_update(
                    msgid=u'%s long description' % attributes['name'],
                    msgstr=body.get('name'),
                    occurs=[(os.path.abspath(self.store.datafile), body.sourceline,)]
                )
                po.add_or_update(
                    msgid=u'%s members' % attributes['name'],
                    msgstr=body.get('members'),
                    occurs=[(os.path.abspath(self.store.datafile), body.sourceline,)]
                )

            if changed and not force:
                logger.info(message)
            else:
                logger.debug(message)

            if obj is None:
                continue

            # Add multi-member district configuration
            mmconfig = self.store.get_node('//MultiMemberDistrictConfig[@legislativebodyref="%s"]' % body.get('id'))
            if mmconfig:
                obj.multi_members_allowed = True
                obj.multi_district_label_format = mmconfig.get('multi_district_label_format')[:32]
                obj.min_multi_districts = mmconfig.get('min_multi_districts')
                obj.max_multi_districts = mmconfig.get('max_multi_districts')
                obj.min_multi_district_members = mmconfig.get('min_multi_district_members')
                obj.max_multi_district_members = mmconfig.get('max_multi_district_members')
                obj.min_plan_members = mmconfig.get('min_plan_members')
                obj.max_plan_members = mmconfig.get('max_plan_members')
                logger.debug( 'Multi-member districts enabled for: %s', body.get('name') )
            else:
                obj.multi_members_allowed = False
                obj.multi_district_label_format = ''
                obj.min_multi_districts = 0
                obj.max_multi_districts = 0
                obj.min_multi_district_members = 0
                obj.max_multi_district_members = 0
                obj.min_plan_members = 0
                obj.max_plan_members = 0
                logger.debug( 'Multi-member districts not configured for: %s', body.get('name'))

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
                'is_displayed': subj.get('displayed')=='true',
                'sort_key': subj.get('sortkey')
            }
                
            obj, created, changed, message = check_and_update(Subject, overwrite=force, **attributes)

            for locale in [l[0] for l in settings.LANGUAGES]:
                po = self.poutils[locale]
                po.add_or_update(
                    msgid=u'%s short label' % attributes['name'],
                    msgstr=subj.get('short_name') or '',
                    occurs=[(os.path.abspath(self.store.datafile), subj.sourceline,)]
                )
                po.add_or_update(
                    msgid=u'%s label' % attributes['name'],
                    msgstr=subj.get('name') or '',
                    occurs=[(os.path.abspath(self.store.datafile), subj.sourceline,)]
                )
                po.add_or_update(
                    msgid=u'%s long description' % attributes['name'],
                    msgstr='',
                    occurs=[(os.path.abspath(self.store.datafile), subj.sourceline,)]
                )

            if changed and not force:
                logger.info(message)
            else:
                logger.debug(message)

        for subj in subjs:
            numerator_name = name=subj.get('id').lower()[:50]
            try:
                numerator = Subject.objects.get(name=numerator_name)
            except Exception, ex:
                logger.info('Subject "%s" was not found.', numerator_name)
                raise

            denominator = None
            denominator_name = subj.get('percentage_denominator')
            if denominator_name:
                denominator_name = denominator_name.lower()[:50]
                try:
                    denominator = Subject.objects.get(name=denominator_name)
                except Exception, ex:
                    logger.info('Subject "%s" was not found.', denominator_name)
                    raise

            numerator.percentage_denominator = denominator
            numerator.save()

            logger.debug('Set denominator on "%s" to "%s"', numerator.name, denominator_name)

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
            
            glvl, created, changed, message = check_and_update(Geolevel, overwrite=force, **attributes)
    
            for locale in [l[0] for l in settings.LANGUAGES]:
                po = self.poutils[locale]
                po.add_or_update(
                    msgid=u'%s short label' % attributes['name'],
                    msgstr=geolevel.get('name') or '',
                    occurs=[(os.path.abspath(self.store.datafile), geolevel.sourceline,)]
                )
                po.add_or_update(
                    msgid=u'%s label' % attributes['name'],
                    msgstr=geolevel.get('label') or '',
                    occurs=[(os.path.abspath(self.store.datafile), geolevel.sourceline,)]
                )
                po.add_or_update(
                    msgid=u'%s long description' % attributes['name'],
                    msgstr='',
                    occurs=[(os.path.abspath(self.store.datafile), geolevel.sourceline,)]
                )

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
            zero_geolevel_config = self.store.get_geolevel(regional_geolevels[len(regional_geolevels)-1].get('ref'))
            # store this zoom level, and use it as an offset for the geolevels in this region
            zero_zoom = int(zero_geolevel_config.get('min_zoom'))

            for geolevel in regional_geolevels:
                try:
                    geolevel_obj = Geolevel.objects.get(name=geolevel.get('ref'))
                except:
                    logger.debug("Base geolevel %s for %s not found in the database.  Import base geolevels before regional geolevels", name, region.get('name'))
                    return

                attributes = {
                    'name': '%s_%s' % (region.get('name'), geolevel.get('ref')),
                    'min_zoom': geolevel_obj.min_zoom - zero_zoom,
                    'tolerance': geolevel_obj.tolerance
                }
                obj, created, changed, message = check_and_update(Geolevel, overwrite=force, **attributes)

                for locale in [l[0] for l in settings.LANGUAGES]:
                    po = self.poutils[locale]
                    po.add_or_update(
                        msgid=u'%s short label' % attributes['name'],
                        msgstr=geolevel.get('name') or '',
                        occurs=[(os.path.abspath(self.store.datafile), geolevel.sourceline,)]
                    )
                    po.add_or_update(
                        msgid=u'%s label' % attributes['name'],
                        msgstr=geolevel.get('label') or '',
                        occurs=[(os.path.abspath(self.store.datafile), geolevel.sourceline,)]
                    )
                    po.add_or_update(
                        msgid=u'%s long description' % attributes['name'],
                        msgstr='',
                        occurs=[(os.path.abspath(self.store.datafile), geolevel.sourceline,)]
                    )

                if changed and not force:
                    logger.info(message)
                else:
                    logger.debug(message)


        # Use the Region nodes to link bodies and geolevels
        for region in regions:

            # Map the imported geolevel to a legislative body
            lbodies = self.store.filter_regional_legislative_bodies(region)
            for lbody in lbodies:
                legislative_body = LegislativeBody.objects.get(name=lbody.get('ref')[:256])
                
                # Add a mapping for the subjects in this GL/LB combo.
                sconfig = self.store.get_legislative_body_default_subject(lbody)
                if not sconfig.get('aliasfor') is None:
                    # dereference any subject alias
                    sconfig = self.store.get_subject(sconfig.get('aliasfor'))
                subject = Subject.objects.get(name=sconfig.get('id').lower()[:50])

                def add_legislative_level_for_geolevel(node, body, subject, parent):
                    """
                    Helper method to recursively add LegislativeLevel mappings from Region configs
                    """
                    geolevel_node = self.store.get_geolevel(node.get('ref'))
                    geolevel_name = "%s_%s" % (region.get('id'), geolevel_node.get('id'))
                    geolevel = Geolevel.objects.get(name=geolevel_name)
                    obj, created = LegislativeLevel.objects.get_or_create(
                        legislative_body=body,
                        geolevel=geolevel,
                        subject=subject, 
                        parent=parent)

                    if created:
                        logger.debug('Created LegislativeBody/GeoLevel mapping "%s/%s"', legislative_body.name, geolevel.name)
                    else:
                        logger.debug('LegislativeBody/GeoLevel mapping "%s/%s" already exists', legislative_body.name, geolevel.name)

                    if len(node) > 0:
                        add_legislative_level_for_geolevel(node[0], body, subject, obj)

                parentless = self.store.get_top_regional_geolevel(region)
                if parentless is not None:
                    add_legislative_level_for_geolevel(parentless, legislative_body, subject, None)

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
            logger.debug('There was no superuser installed; ScoreDisplays need to be assigned ownership to a superuser.')
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
                owner=admin
            )

            for locale in [l[0] for l in settings.LANGUAGES]:
                po = self.poutils[locale]
                po.add_or_update(
                    msgid=u'%s short label' % sd.get('id'),
                    msgstr=sd.get('title') or '',
                    occurs=[(os.path.abspath(self.store.datafile), sd.sourceline,)]
                )
                po.add_or_update(
                    msgid=u'%s label' % sd.get('id'),
                    msgstr=sd.get('title') or '',
                    occurs=[(os.path.abspath(self.store.datafile), sd.sourceline,)]
                )
                po.add_or_update(
                    msgid=u'%s long description' % sd.get('id'),
                    msgstr='',
                    occurs=[(os.path.abspath(self.store.datafile), sd.sourceline,)]
                )


            if created:
                logger.debug('Created ScoreDisplay "%s"', sd.get('title'))
            else:
                logger.debug('ScoreDisplay "%s" already exists', sd.get('title'))

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
                    is_ascending=(ascending is None or ascending=='true'), 
                )

                if created:
                    sd_obj.scorepanel_set.add(sp_obj)

                    logger.debug('Created ScorePanel "%s"', name)
                else:
                    attached = sd_obj.scorepanel_set.filter(id=sp_obj.id).count() == 1
                    if not attached:
                        sd_obj.scorepanel_set.add(sp_obj)

                    logger.debug('ScorePanel "%s" already exists', name)

                for locale in[l[0] for l in settings.LANGUAGES]:
                    po = self.poutils[locale]
                    po.add_or_update(
                        msgid=u'%s short label' % sp_obj.name,
                        msgstr=sp.get('title') or '',
                        occurs=[(os.path.abspath(self.store.datafile), sp.sourceline,)]
                    )
                    po.add_or_update(
                        msgid=u'%s label' % sp_obj.name,
                        msgstr=sp.get('title') or '',
                        occurs=[(os.path.abspath(self.store.datafile), sp.sourceline,)]
                    )
                    po.add_or_update(
                        msgid=u'%s long description' % sp_obj.name,
                        msgstr='',
                        occurs=[(os.path.abspath(self.store.datafile), sp.sourceline,)]
                    )

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
            return False;

        for vc in self.store.filter_criteria():
            lb = LegislativeBody.objects.get(name=vc.get('legislativebodyref'))

            for crit in self.store.filter_criteria_criterion(vc):
                # Import the score function for this validation criterion
                sfref = self.store.get_criterion_score(crit)
                try:
                    sf = self.store.get_score_function(sfref.get('ref'))
                except:
                    logger.info("Couldn't import ScoreFunction for Criteria %s", crit.get('name'))
                    result = False

                sf_obj = self.import_function(sf, force)

                # Import this validation criterion
                attributes = {
                    'name': crit.get('id')[0:50],
                    'function': sf_obj,
                    'legislative_body': lb
                }
                crit_obj, created, changed, message = check_and_update(ValidationCriteria, overwrite=force, **attributes)

                for locale in [l[0] for l in settings.LANGUAGES]:
                    po = self.poutils[locale]
                    po.add_or_update(
                        msgid=u'%s short label' % attributes['name'],
                        msgstr=crit.get('name') or '',
                        occurs=[(os.path.abspath(self.store.datafile), crit.sourceline,)]
                    )
                    po.add_or_update(
                        msgid=u'%s label' % attributes['name'],
                        msgstr=crit.get('name') or '',
                        occurs=[(os.path.abspath(self.store.datafile), crit.sourceline,)]
                    )
                    po.add_or_update(
                        msgid=u'%s long description' % attributes['name'],
                        msgstr=crit.get('description') or '',
                        occurs=[(os.path.abspath(self.store.datafile), crit.sourceline,)]
                    )

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
        fn_obj, created, changed, message = check_and_update(ScoreFunction, overwrite=force, **attributes)

        for locale in [l[0] for l in settings.LANGUAGES]:
            po = self.poutils[locale]
            po.add_or_update(
                msgid=u'%s short label' % attributes['name'],
                msgstr=node.get('label') or '',
                occurs=[(os.path.abspath(self.store.datafile), node.sourceline,)]
            )
            po.add_or_update(
                msgid=u'%s label' % attributes['name'],
                msgstr=node.get('label') or '',
                occurs=[(os.path.abspath(self.store.datafile), node.sourceline,)]
            )
            po.add_or_update(
                msgid=u'%s long description' % attributes['name'],
                msgstr=node.get('description') or '',
                occurs=[(os.path.abspath(self.store.datafile), node.sourceline,)]
            )

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
                    logger.debug('literal ScoreArgument "%s" already exists', name)
                elif force:
                    arg_obj.value = config_value
                    arg_obj.save()
                    logger.info('literal ScoreArgument "%s" value UPDATED', name)
                else:
                    logger.info('Didn\'t change ScoreArgument %s; attribute(s) "value" differ(s) from database configuration.\n\tWARNING: Sync your config file to your app configuration or use the -f switch with setup to force changes', name)

        # Import subject arguments for this score function
        for subarg in self.store.filter_function_subject_arguments(node):
            name = subarg.get('name')[:50]
            config_value=subarg.get('ref')[:50]
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
                    logger.debug('subject ScoreArgument "%s" already exists', name)
                elif force:
                    subarg_obj.value = config_value
                    subarg_obj.save()
                    logger.info('subject ScoreArgument "%s" value UPDATED', name)
                else:
                    logger.info('Didn\'t change ScoreArgument %s; attribute(s) "value" differ(s) from database configuration.\n\tWARNING: Sync your config file to your app configuration or use the -f switch with setup to force changes', name)
                    
        
        # Import score arguments for this score function
        for scorearg in self.store.filter_function_score_arguments(node):
            argfn = self.store.get_score_function(scorearg.get('ref'))
            if argfn is None:
                logger.info("ERROR: No such function %s can be found for argument of %s", scorearg.get('ref'), score_function.name)
                continue

            self.import_function(argfn, force)
            config_value=scorearg.get('ref')[:50]
            name = scorearg.get('name')[:50]

            scorearg_obj, created = ScoreArgument.objects.get_or_create(
                function=score_function,
                type='score',
                argument=name
                )

            if created:
                scorearg_obj.value = config_value
                scorearg_obj.save()
                logger.debug('created subject scoreargument "%s"', name)
            else:
                if scorearg_obj.value == config_value:
                    logger.debug('subject scoreargument "%s" already exists', name)
                elif force:
                    scorearg_obj.value = config_value
                    scorearg_obj.save()
                    logger.info('subject scoreargument "%s" value UPDATED', name)
                else:
                    logger.info('Didn\'t change scoreargument %s; attribute(s) "value" differ(s) from database configuration.\n\twarning: sync your config file to your app configuration or use the -f switch with setup to force changes', name)

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
                raise Exception('There exists no geounit with portable_id: %s' % portable_id)
            override_geounit = temp[0]

            portable_id = co.get('connect_to')
            temp = Geounit.objects.filter(portable_id=portable_id)
            if (len(temp) == 0):
                raise Exception('There exists no geounit with portable_id: %s' % portable_id)
            connect_to_geounit = temp[0]

            co_obj, created = ContiguityOverride.objects.get_or_create(
                override_geounit=override_geounit, 
                connect_to_geounit=connect_to_geounit 
                )

            if created:
                logger.debug('Created ContiguityOverride "%s"', str(co_obj))
            else:
                logger.debug('ContiguityOverride "%s" already exists', str(co_obj))

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
        if not store is None:
            self.store = store

            mapconfig = self.store.get_mapserver()

            self.host = mapconfig.get('hostname')
            self.port = 8080 # should this be parameterized?

            self.ns = mapconfig.get('ns')
            self.nshref = mapconfig.get('nshref')

            user_pass = '%s:%s' % (mapconfig.get('adminuser'), mapconfig.get('adminpass'))

            self.styledir = mapconfig.get('styles')
        elif isinstance(config, dict):
            try:
                self.host = config['host']
                self.port = 8080

                self.ns = config['ns']
                self.nshref = config['nshref']

                user_pass = '%s:%s' % (config['adminuser'], config['adminpass'])

                self.styledir = config['styles']
            except:
                logger.error('SpatialUtils is missing a required key in the settings dictionary.')
                raise

        else:
            logger.error('SpatialUtils requires either a stored config or a dictionary of settings.')
            raise Exception()

        if self.host == '':
            self.host = 'localhost'

        auth = 'Basic %s' % base64.b64encode(user_pass)
        self.headers = {
                'default': {
                'Authorization': auth, 
                'Content-Type': 'application/json', 
                'Accepts':'application/json'
            },
            'sld': {
                'Authorization': auth,
                'Content-Type': 'application/vnd.ogc.sld+xml',
                'Accepts':'application/xml'
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
        # get the workspace 
        ws_cfg = self._read_config('/geoserver/rest/workspaces/%s.json' % self.ns, 'Could not get workspace %s.' % self.ns)
        if ws_cfg is None:
            logger.debug("%s configuration could not be fetched.", self.ns)
            return True

        # get the data stores in the workspace
        wsds_cfg = self._read_config(ws_cfg['workspace']['dataStores'], 'Could not get data stores in workspace %s' % ws_cfg['workspace']['name'])
        if wsds_cfg is None:
            logger.debug("Workspace '%s' datastore configuration could not be fetched.", self.ns)
            return False

        # get the data source configuration
        ds_cfg = self._read_config(wsds_cfg['dataStores']['dataStore'][0]['href'], "Could not get datastore configuration for '%s'" % wsds_cfg['dataStores']['dataStore'][0]['name'])
        if ds_cfg is None:
            logger.debug("Datastore configuration could not be fetched.")
            return False

        # get all the feature types in the data store
        fts_cfg = self._read_config(ds_cfg['dataStore']['featureTypes'] + '?list=all', "Could not get feature types in datastore '%s'" % wsds_cfg['dataStores']['dataStore'][0]['name'])
        if fts_cfg is None:
            logger.debug("Data store '%s' feature type configuration could not be fetched.", wsds_cfg['dataStores']['dataStore'][0]['name'])
            return False

        if not 'featureType' in fts_cfg['featureTypes']: 
            fts_cfg['featureTypes'] = { 'featureType':[] }

        for ft_cfg in fts_cfg['featureTypes']['featureType']:
            # Delete the layer
            if not self._rest_config('DELETE', '/geoserver/rest/layers/%s.json' % ft_cfg['name'], None, 'Could not delete layer %s' % (ft_cfg['name'],)):
                logger.debug("Could not delete layer %s", ft_cfg['name'])
                continue

            # Delete the feature type
            if not self._rest_config('DELETE', ft_cfg['href'], None, 'Could not delete feature type %s' % (ft_cfg['name'],)):
                logger.debug("Could not delete feature type '%s'", ft_cfg['name'])
            else:
                logger.debug("Deleted feature type '%s'", ft_cfg['name'])

        # now that the data store is empty, delete it
        if not self._rest_config('DELETE', wsds_cfg['dataStores']['dataStore'][0]['href'], None, 'Could not delete datastore %s' % wsds_cfg['dataStores']['dataStore'][0]['name']):
            logger.debug("Could not delete datastore %s", wsds_cfg['dataStores']['dataStore'][0]['name'])
            return False

        # now that the workspace is empty, delete it
        if not self._rest_config('DELETE', '/geoserver/rest/workspaces/%s.json' % self.ns, None, 'Could not delete workspace %s' % self.ns):
            logger.debug("Could not delete workspace %s", self.ns)
            return False

        # Get a list of styles
        sts_cfg = self._read_config('/geoserver/rest/styles.json', "Could not get styles.")
        if not sts_cfg is None:
            includes = ['^%s:.*' % self.ns]
            for st_cfg in sts_cfg['styles']['style']:
                skip = False
                for inc in includes:
                    skip = skip or re.compile(inc).match(st_cfg['name']) is None
                if skip:
                    # This style doesn't match any style starting with the prefix.
                    continue

                # Delete the style
                if not self._rest_config('DELETE', st_cfg['href'], None, 'Could not delete style %s' % st_cfg['name']):
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
        try:
            srid = Geounit.objects.all()[0].geom.srid
        except:
            srid = 0
            logger.debug('Spatial Reference could not be determined, defaulting to %d', srid)

        # Create our namespace
        namespace_url = '/geoserver/rest/namespaces'
        namespace_obj = { 'namespace': { 'prefix': self.ns, 'uri': self.nshref } }
        self._check_spatial_resource(namespace_url, self.ns, namespace_obj, 'Namespace')

        # Create our DataStore
        if self.store is None:
            logger.warning('Geoserver cannot be fully configured without a stored config.')
            return

        dbconfig = self.store.get_database()

        data_store_url = '/geoserver/rest/workspaces/%s/datastores' % self.ns
        data_store_name = 'PostGIS'

        data_store_obj = {
            'dataStore': {
                'name': data_store_name,
                'connectionParameters': {
                    'host': dbconfig.get('host',self.host),
                    'port': 5432,
                    'database': dbconfig.get('name'),
                    'user': dbconfig.get('user'),
                    'passwd': dbconfig.get('password'),
                    'dbtype': 'postgis',
                    'namespace': self.ns,
                    'schema': dbconfig.get('user')
                }
            }
        }

        self._check_spatial_resource(data_store_url, data_store_name, data_store_obj, 'Data Store')

        # Create the feature types and their styles

        self.create_featuretype('identify_geounit')
        self.create_style('simple_district', None, '%s:simple_district' % self.ns, None)

        for geolevel in Geolevel.objects.all():
            if geolevel.legislativelevel_set.all().count() == 0:
                # Skip 'abstract' geolevels if regions are configured
                continue

            self.create_featuretype('simple_%s' % geolevel.name)
            self.create_featuretype('simple_district_%s' % geolevel.name)

            all_subjects = Subject.objects.all().order_by('sort_key') 
            if all_subjects.count() > 0:
                subject = all_subjects[0]

                # Create NONE demographic layer, based on first subject
                featuretype_name = get_featuretype_name(geolevel.name)
                self.create_featuretype(
                    featuretype_name, alias=get_featuretype_name(geolevel.name, subject.name)
                )
                self.create_style(subject.name, geolevel.name, '%s:%s' % (self.ns, featuretype_name,), 'none')

                # Create boundary layer, based on geographic boundaries
                featuretype_name = '%s_boundaries' % geolevel.name
                self.create_featuretype(
                    featuretype_name, alias=get_featuretype_name(geolevel.name, subject.name)
                )
                self.create_style(subject.name, geolevel.name, '%s:%s' % (self.ns, featuretype_name,), 'boundaries')

            for subject in all_subjects:
                self.create_featuretype(get_featuretype_name(geolevel.name, subject.name))
                self.create_style(subject.name, geolevel.name, None, None)

        logger.info("Geoserver configuration complete.")

        # finished configure_geoserver
        return True

    def create_featuretype(self, feature_type_name, data_store_name='PostGIS', alias=None):
        """
        Create a featuretype.

        @param feature_type_name: The name of the feature type.
        @keyword data_store_name: Optional. The name of the datastore. Defaults to 'PostGIS'
        @keyword alias: Optional. The new feature type is an alias for this names feature type.
        @returns: A flag indicating if the feature type was successfully created.
        """
        feature_type_url = '/geoserver/rest/workspaces/%s/datastores/%s/featuretypes' % (self.ns, data_store_name)

        feature_type_obj = SpatialUtils.feature_template(feature_type_name, alias=alias)
        self._check_spatial_resource(feature_type_url, feature_type_name, feature_type_obj, 'Feature Type')

    def _check_spatial_resource(self, url, name, dictionary, type_name=None, update=False):
        """ 
        This method will check geoserver for the existence of an object.
        It will create the object if it doesn't exist and log messages
        to the configured logger.

        @param url: The URL of the resource.
        @param name: The name of the resource.
        @param dictionary: A dictionary of settings to the resource.
        @keyword type_name: Optional. Name of the type, if different from the name.
        @keyword update: Optional. Update the featuretype if it exists?
        @returns: A flag indicating if the configuration call completed successfully.
        """
        verbose_name = '%s:%s' % ('Geoserver object' if type_name is None else type_name, name)
        if self._rest_check('%s/%s.json' % (url, name)):
            logger.debug("%s already exists", verbose_name)
            if update:
                if not self._rest_config( 'PUT', url, json.dumps(dictionary), 'Could not create %s' % (verbose_name,)):
                    logger.info("%s couldn't be updated.", verbose_name)
                    return False
                
        else:
            if not self._rest_config( 'POST', url, json.dumps(dictionary), 'Could not create %s' % (verbose_name,)):
                return False

            logger.debug('Created %s', verbose_name)

        return True


    @staticmethod
    def feature_template(name, title=None, alias=None):
        """
        Return a common format for feature types.

        @param name: The name of the feature type.
        @keyword title: Optional. The title of the featuretype, defaults to name.
        @keyword alias: Optional. The nativeName of the featuretype, defaults to name.
        @returns: A dictionary of settings for all feature types.
        """
        nativeName = name
        if not alias is None:
            nativeName = alias
        return {
            'featureType': {
                'name': name,
                'title': name if title is None else title,

                # Set the bounding box to the maximum spherical mercator extent
                # in order to avoid all issues with geowebcache tile offsets
                'nativeBoundingBox': {
                    'minx': '%0.1f' % -20037508.342789244,
                    'miny': '%0.1f' % -20037508.342789244,
                    'maxx': '%0.1f' % 20037508.342789244,
                    'maxy': '%0.1f' % 20037508.342789244
                },
                'maxFeatures': settings.FEATURE_LIMIT + 1,
                'nativeName': nativeName
            }
        }

    def _rest_check(self, url):
        """
        Attempt to get a REST resource. If the resource exists, and can
        be retrieved successfully, it will pass the check.

        @returns: True if the resource exists and is readable.
        """
        try:
            conn = httplib.HTTPConnection(self.host, self.port)
            conn.request('GET', url, None, self.headers['default'])
            rsp = conn.getresponse()
            rsp.read() # and discard
            conn.close()
            return rsp.status == 200
        except:
            # HTTP 400, 500 errors are also considered exceptions by the httplib
            return False

    def _rest_config(self, method, url, data, msg, headers=None):
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
            rsp.read() # and discard
            conn.close()
            if rsp.status != 201 and rsp.status != 200:
                logger.info("""
ERROR:

        Could not configure geoserver: 

        %s 

        Please check the configuration settings, and try again.
""", msg)
                logger.debug("        HTTP Status: %d", rsp.status)
                return False
        except Exception, ex:
            logger.info("""
ERROR:

        Exception thrown while configuring geoserver.
""", ex)
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
            response = rsp.read() # and discard
            conn.close()
            if rsp.status != 201 and rsp.status != 200:
                logger.info("""
ERROR:

        Could not fetch geoserver configuration:

        %s

        Please check the configuration settings, and try again.
""", msg)
                return None

            return json.loads(response)
        except Exception, ex:
            logger.info("""
ERROR:

        Exception thrown while fetching geoserver configuration.
""")
            logger.debug(traceback.format_exc())
            return None

    def create_style(self, subject_name, geolevel_name, style_name, style_type, sld_content=None):
        """
        Create a style for a layer, defaulting to 'polygon' for a polygon
        layer if the style file is not available.

        @param subject_name: The name of the subject.
        @param geolevel_name: The name of the geolevel.
        @param style_name: The name of the style.
        @param style_type: The type of the style.
        @keyword sld_content: The content of the SLD.
        """

        if not style_type:
            style_type = subject_name

        if not style_name:
            layer_name = '%s:demo_%s_%s' % (self.ns, geolevel_name, subject_name)
            style_name = layer_name
        else:
            layer_name = style_name

        style_obj = { 'style': {
            'name': layer_name,
            'filename': '%s.sld' % layer_name
        } }

        # Get the SLD file
        if sld_content is None:
            sld_content = self._get_style(geolevel_name, style_type)
            if sld_content is None:
                from_file = False
            else:
                from_file = True
        else:
            from_file = False

        if sld_content is None:
            logger.debug('No style file found for %s', layer_name)
            style_name = 'polygon'
        else:
            # Create the styles for the demographic layers
            style_url = '/geoserver/rest/styles'

            # Create the style object on the geoserver
            self._check_spatial_resource(style_url, style_name, style_obj, 'Map Style')

            # Update the style with the sld file contents

            msg = 'Could not upload style %s' % (("file %s.sld" % style_name) if from_file else style_name)
            if self._rest_config( 'PUT', '/geoserver/rest/styles/%s' % style_name, \
                sld_content, msg, headers=self.headers['sld']):
                if from_file:
                    logger.debug("Uploaded '%s.sld' file.", style_name)
                else:
                    logger.debug("Uploaded '%s' style.", style_name)

        # Apply the uploaded style to the demographic layers
        layer = { 'layer' : {
            'defaultStyle': {
                'name': style_name
            },
            'enabled': True
        } }

        
        if self._rest_config( 'PUT', '/geoserver/rest/layers/%s' % layer_name, \
            json.dumps(layer), "Could not assign style to layer '%s'." % layer_name):
            logger.debug("Assigned style '%s' to layer '%s'.", style_name, layer_name)

    def _get_style(self, geolevel, subject):
        """
        Get an SLD file from the file system.

        @param geolevel: The geolevel name.
        @param subject: The subject name.
        @returns: The content of an SLD file on the filesystem.
        """
        if not geolevel:
            path = '%s/%s:%s.sld' % (self.styledir, self.ns, subject)
        else:
            path = '%s/%s:%s_%s.sld' % (self.styledir, self.ns, geolevel, subject) 
        try:
            stylefile = open(path)
            sld = stylefile.read()
            stylefile.close()

            return sld
        except:
            logger.debug("""
WARNING:

        The style file:
        
        %s
        
        could not be loaded. Please confirm that the
        style files are named according to the "geolevel_subject.sld"
        convention, and try again.
""", path)
            return None


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
            while parent.getparent() is not None and parent.getparent().tag != 'GeoLevels':
                # Find the parent node (the geographic THIS geolevel should
                # match after renesting) by traveling up the nested GeoLevel
                # nodes until we get to the top.
                parent = parent.getparent()

            # Don't check any other regions if we've found a parent
            break

        parent_geolevel = self.store.get_geolevel(parent.get('ref'))
        if not parent_geolevel is None:
            parent = Geolevel.objects.get(name=parent_geolevel.get('name').lower()[:50])
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

        self.popath = 'locale/%(locale)s/LC_MESSAGES/xmlconfig.po' % {'locale':locale}
        self.mopath = 'locale/%(locale)s/LC_MESSAGES/xmlconfig.mo' % {'locale':locale}
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
                'Last-Translator': '%s <%s>' % (settings.ADMINS[0][0], settings.ADMINS[0][1]),
                'Language-Team': '%s <%s>' % (settings.ADMINS[0][0], settings.ADMINS[0][1]),
                'Language': locale,
                'MIME-Version': '1.0',
                'Content-Type': 'text/plain; charset=UTF-8',
                'Content-Transfer-Encoding': '8bit'
            }

    def add_or_update(self, msgid='', msgstr='', occurs=[]):
        """
        Add a POEntry to the .po file, or update it if it already exists.

        @keyword msgid: The .po msgid
        @keyword msgstr: The .po msgstr
        """
        entry = self.pofile.find(msgid)
        if entry is None:
            entry = polib.POEntry(msgid=msgid, msgstr=msgstr, occurrences=occurs)
            self.pofile.append(entry)
        else:
            entry.msgstr = msgstr
            entry.occurences = occurs

    def save(self):
        """
        Save the .po file, and compile the .mo file.
        """
        logger.debug('Saving file %(po)s.', {'po':self.popath})
        self.pofile.save(self.popath)

        logger.debug('Saving file %(mo)s.', {'mo':self.mopath})
        self.pofile.save_as_mofile(self.mopath)


class UTC(tzinfo):
    """UTC"""
    def utcoffset(self, dt):
        return timedelta(0)
    def tzname(self, dt):
        return 'UTC'
    def dst(self, dt):
        return timedelta(0)
