"""
Configuration module for DistrictBuilder

This file handles many common operations that operate on the application
configuration and setup.

This file is part of The Public Mapping Project
https://github.com/PublicMapping/

License:
    Copyright 2010-2011 Micah Altman, Michael McDonald

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

import hashlib, logging, httplib, string, base64, pprint, json, traceback, types
from django.db.models import Model
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.sessions.models import Session
from django.contrib.auth.models import User
from models import *

logger = logging.getLogger(__name__)

class ModelHelper:
    @staticmethod
    def check_and_update(a_model, unique_id_field='name', overwrite=False, **kwargs):
        """
        Check whether an object exists with the given name in the database. If the 
        object exists and "overwrite" is True, overwrite the object.  If "overwrite"
        is false, don't overwrite.  If the object doesn't exist, it is always created.

        This method returns a tuple - the object in the DB after any changes are made,
        whether the object had to be created, whether the given attributes were consistent
        with what was in the database, and a message to return indicating any changes.
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

        Returns:
            A flag indicating if the sessions were deleted successfully.
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
        Create a new config imported, based on the stored config.
        """
        self.store = store

    def import_superuser(self, force):
        """
        Create the django superuser, based on the config.

        Returns:
            A flag indicating if the import was successful.
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

            admin, created, changed, message = ModelHelper.check_and_update(User, unique_id_field='username', overwrite=force, **admin_attributes)

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

        Returns:
            A flag indicating if the import was successful.
        """
        regions = self.store.filter_regions()
        for region in regions:
            attributes = {
                'name': region.get('name'),
                'label': region.get('label'),
                'description': region.get('description'),
                'sort_key': region.get('sort_key')
            }
            obj, created, changed, message = ModelHelper.check_and_update(Region, overwrite=force, **attributes)
            if changed and not force:
                logger.info(message)
            else:
                logger.debug(message)

        return True

    def import_legislative_bodies(self, force):
        """
        Create legislative body models out of the configuration.

        Returns:
            A flag indicating if the import was successful.
        """
        bodies = self.store.filter_legislative_bodies()
        for body in bodies:
            attributes = {
                'name': body.get('name')[:256],
                'short_label': body.get('short_label')[:10], 
                'long_label': body.get('long_label')[:256],
                'max_districts': body.get('maxdistricts'),
                'sort_key': body.get('sort_key'),
                'is_community': body.get('is_community')=='true'
            }

            body_by_region = self.store.filter_nodes('/DistrictBuilder/Regions/Region/LegislativeBodies/LegislativeBody[@ref="%s"]' % body.get('id'))
            if len(body_by_region) != 1:
                logger.info( "Legislative body %s not attributed to any region", attributes['name'])
                continue
            else:
                region_name = body_by_region[0].getparent().getparent().get('name')
            attributes['region'] = Region.objects.get(name=region_name)

            obj, created, changed, message = ModelHelper.check_and_update(LegislativeBody, overwrite=force, **attributes)

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

        Returns:
            A flag indicating if the import was successful.
        """
        subjs = self.store.filter_subjects()
        for subj in subjs:
            if 'aliasfor' in subj.attrib:
                continue

            attributes = {
                'name': subj.get('id').lower()[:50],
                'display': subj.get('name')[:200],
                'short_display': subj.get('short_name')[:25],
                'is_displayed': subj.get('displayed')=='true',
                'sort_key': subj.get('sortkey')
            }
                
            obj, created, changed, message = ModelHelper.check_and_update(Subject, overwrite=force, **attributes)

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

        Returns:
            A flag indicating if the import was successful.
        """

        # Note that geolevels may be added in any order, but the geounits
        # themselves need to be imported top-down (smallest area to biggest)
        geolevels = self.store.filter_geolevels()
        for geolevel in geolevels:
            attributes = {
                'name': geolevel.get('name').lower()[:50],
                'min_zoom': geolevel.get('min_zoom'),
                'sort_key': geolevel.get('sort_key'),
                'tolerance': geolevel.get('tolerance')
            }
            
            glvl, created, changed, message = ModelHelper.check_and_update(Geolevel, overwrite=force, **attributes)
    
            if changed and not force:
                logger.info(message)
            else:
                logger.debug(message)

        return True

    def import_regional_geolevels(self, force):
        """
        Map geolevels to regions.

        Returns:
            A flag indicating if the import was successful.
        """
        regions = self.store.filter_regions()
        for region in regions:
            regional_geolevels = self.store.filter_regional_geolevel(region)

            # Get the zoom level of the largest geolevel (last one in the regional_geolevels list)
            zero_geolevel_config = self.store.get_geolevel(regional_geolevels[len(regional_geolevels)-1].get('ref'))
            # store this zoom level, and use it as an offset for the geolevels in this region
            zero_zoom = int(zero_geolevel_config.get('min_zoom'))

            for geolevel in regional_geolevels:
                geolevel_config = self.store.get_geolevel(geolevel.get('ref'))
                if geolevel_config is not None:
                    name = geolevel_config.get('name')
                try:
                    geolevel = Geolevel.objects.get(name=name)
                except:
                    logger.debug("Base geolevel %s for %s not found in the database.  Import base geolevels before regional geolevels", name, region.get('name'))
                    return

                attributes = {
                    'name': '%s_%s' % (region.get('name'), name),
                    'min_zoom': geolevel.min_zoom - zero_zoom,
                    'tolerance': geolevel.tolerance
                }
                obj, created, changed, message = ModelHelper.check_and_update(Geolevel, overwrite=force, **attributes)
                if changed and not self.force:
                    logger.info(message)
                else:
                    logger.debug(message)


        # Use the Region nodes to link bodies and geolevels
        for region in regions:

            # Map the imported geolevel to a legislative body
            lbodies = self.store.filter_regional_legislative_bodies(region)
            for lbody in lbodies:
                # de-reference
                lbconfig = self.store.get_legislative_body(lbody.get('ref'))
                legislative_body = LegislativeBody.objects.get(name=lbconfig.get('name')[:256])
                
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
                    geolevel_name = "%s_%s" % (region.get('name'), geolevel_node.get('name'))
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

        Scoring is currently optional. Import sections only if they are present.

        Returns:
            A flag indicating if the import was successful.
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
            lbconfig = self.store.get_legislative_body(sd.get('legislativebodyref'))
            lb = LegislativeBody.objects.get(name=lbconfig.get('name'))
            title = sd.get('title')[:50]
             
            sd_obj, created = ScoreDisplay.objects.get_or_create(
                title=title, 
                legislative_body=lb,
                is_page=sd.get('type') == 'leaderboard',
                cssclass=(sd.get('cssclass') or '')[:50],
                owner=admin
            )

            if created:
                logger.debug('Created ScoreDisplay "%s"', title)
            else:
                logger.debug('ScoreDisplay "%s" already exists', title)

            # Import score panels for this score display.
            for spref in self.store.filter_displayed_score_panels(sd):
                sp = self.store.get_score_panel(spref.get('ref'))
                title = sp.get('title')[:50]
                position = int(sp.get('position'))
                template = sp.get('template')[:500]
                cssclass = (sp.get('cssclass') or '')[:50]
                pnltype = sp.get('type')[:20]

                is_ascending = sp.get('is_ascending')
                if is_ascending is None:
                    is_ascending = True
                
                ascending = sp.get('is_ascending')
                sp_obj = ScorePanel.objects.filter(
                    type=pnltype,
                    position=position,
                    title=title,
                    template=template,
                    cssclass=cssclass,
                    is_ascending=(ascending is None or ascending=='true'), 
                )

                if len(sp_obj) == 0:
                    sp_obj = ScorePanel(
                        type=pnltype,
                        position=position,
                        title=title,
                        template=template,
                        cssclass=cssclass,
                        is_ascending=(ascending is None or ascending=='true'), 
                    )
                    sp_obj.save()
                    sd_obj.scorepanel_set.add(sp_obj)

                    logger.debug('Created ScorePanel "%s"', title)
                else:
                    sp_obj = sp_obj[0]
                    attached = sd_obj.scorepanel_set.filter(id=sp_obj.id).count() == 1
                    if not attached:
                        sd_obj.scorepanel_set.add(sp_obj)

                    logger.debug('ScorePanel "%s" already exists', title)

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
            lbconfig = self.store.get_legislative_body(vc.get('legislativebodyref'))
            lb = LegislativeBody.objects.get(name=lbconfig.get('name'))

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
                    'name': crit.get('name'),
                    'function': sf_obj,
                    'description': crit.get('description') or '',
                    'legislative_body': lb
                }
                crit_obj, created, changed, message = ModelHelper.check_and_update(ValidationCriteria, overwrite=force, **attributes)

                if changed and not force:
                    logger.info(message)
                else:
                    logger.debug(message)

        return result

    def import_function(self, node, force):
        """
        Create the ScoreFunction models and child scores.

        Returns:
            A newly created score function object.
        """
        attributes = {
            'calculator': node.get('calculator')[:500],
            'name': node.get('id')[:50],
            'label': (node.get('label') or '')[:100],
            'description': node.get('description') or '',
            'is_planscore': node.get('type') == 'plan'
        }
        fn_obj, created, changed, message = ModelHelper.check_and_update(ScoreFunction, overwrite=force, **attributes)

        lbodies = []
        for lbitem in self.store.filter_function_legislative_bodies(node):
            lb = self.store.get_legislative_body(lbitem.get('ref'))
            lbodies.append(lb.get('name')[:256])
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

        Returns:
            A flag indicating if the import was successful.
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

        Returns:
            A flag indicating if the import was successful.
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

        This prevents conflicts in geowebcache when the datastore and
        featuretype is reconfigured without discarding the old featuretype.
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

        Returns:
            A flag indicating if geoserver was configured correctly.
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
                featuretype_name = '%s_boundaries' % geolevel.name,
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
        Create a featuretype. Assuming the datastore name is always 'PostGIS'.
        """
        feature_type_url = '/geoserver/rest/workspaces/%s/datastores/%s/featuretypes' % (self.ns, data_store_name)

        feature_type_obj = SpatialUtils.feature_template(feature_type_name, alias=alias)
        self._check_spatial_resource(feature_type_url, feature_type_name, feature_type_obj, 'Feature Type')

    def _check_spatial_resource(self, url, name, dictionary, type_name=None, update=False):
        """ 
        This method will check geoserver for the existence of an object.
        It will create the object if it doesn't exist and log messages
        to the configured logger.
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

        Please chece the configuration settings, and try again.
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

        Parameters:
            glconf - The configuration geolevel
            subject - The subject to aggregate, default aggregates everything.
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
            while parent.getparent().tag != 'GeoLevels':
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


