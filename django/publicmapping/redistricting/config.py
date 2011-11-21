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

import hashlib, logging
import django.db.models
from django.contrib.sessions.models import Session
from django.contrib.auth.models import User
from models import *

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
            if not (isinstance(current_value, types.StringTypes)) and not (isinstance(current_value, models.Model)):
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

        logging.debug('Purging %d sessions from the database.', qset.count())

        try:
            qset.delete()
        except Exception, e:
            logging.info('Could not delete sessions.')
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
                logging.info(message)
            else:
                logging.debug(message)

            if created or changed or force:
                m = hashlib.sha1()
                m.update(admcfg.get('password'))
                admin.set_password(m.hexdigest())
                admin.save()

            return True

        except:
            logging.info('Error when creating superuser.')
            logging.info(traceback.format_exc())

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
                logging.info(message)
            else:
                logging.debug(message)

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
                logging.info( "Legislative body %s not attributed to any region", attributes['name'])
                continue
            else:
                region_name = body_by_region[0].getparent().getparent().get('name')
            attributes['region'] = Region.objects.get(name=region_name)

            obj, created, changed, message = ModelHelper.check_and_update(LegislativeBody, overwrite=force, **attributes)

            if changed and not force:
                logging.info(message)
            else:
                logging.debug(message)

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
                logging.debug( 'Multi-member districts enabled for: %s', body.get('name') )
            else:
                obj.multi_members_allowed = False
                obj.multi_district_label_format = ''
                obj.min_multi_districts = 0
                obj.max_multi_districts = 0
                obj.min_multi_district_members = 0
                obj.max_multi_district_members = 0
                obj.min_plan_members = 0
                obj.max_plan_members = 0
                logging.debug( 'Multi-member districts not configured for: %s', body.get('name'))

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
                logging.info(message)
            else:
                logging.debug(message)

        for subj in subjs:
            numerator_name = name=subj.get('id').lower()[:50]
            try:
                numerator = Subject.objects.get(name=numerator_name)
            except Exception, ex:
                logging.info('Subject "%s" was not found.', numerator_name)
                raise

            denominator = None
            denominator_name = subj.get('percentage_denominator')
            if denominator_name:
                denominator_name = denominator_name.lower()[:50]
                try:
                    denominator = Subject.objects.get(name=denominator_name)
                except Exception, ex:
                    logging.info('Subject "%s" was not found.', denominator_name)
                    raise

            numerator.percentage_denominator = denominator
            numerator.save()

            logging.debug('Set denominator on "%s" to "%s"', numerator.name, denominator_name)

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
                logging.info(message)
            else:
                logging.debug(message)

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
                    logging.debug("Base geolevel %s for %s not found in the database.  Import base geolevels before regional geolevels", name, region.get('name'))
                    return

                attributes = {
                    'name': '%s_%s' % (region.get('name'), name),
                    'min_zoom': geolevel.min_zoom - zero_zoom,
                    'tolerance': geolevel.tolerance
                }
                obj, created, changed, message = ModelHelper.check_and_update(Geolevel, overwrite=force, **attributes)
                if changed and not self.force:
                    logging.info(message)
                else:
                    logging.debug(message)


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
                        logging.debug('Created LegislativeBody/GeoLevel mapping "%s/%s"', legislative_body.name, geolevel.name)
                    else:
                        logging.debug('LegislativeBody/GeoLevel mapping "%s/%s" already exists', legislative_body.name, geolevel.name)

                    if len(node) > 0:
                        add_legislative_level_for_geolevel(node[0], body, subject, obj)

                parentless = self.store.get_top_regional_geolevel(region)
                if parentless is not None:
                    add_legislative_level_for_geolevel(parentless, legislative_body, subject, None)

        return True
