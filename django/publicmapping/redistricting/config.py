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

import hashlib
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
            (success, messages,) -- A tuple that contains a flag indicating if the
            sessions were deleted successfully, and any messages related to the 
            success or failure of the operation.
        """
        qset = Session.objects.all()

        msgs = ['Purging %d sessions from the database.' % qset.count()]

        try:
            qset.delete()
        except Exception, e:
            return (False, ['Could not delete sessions.'],)

        return (True, msgs,)


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
            (success, messages,) -- A tuple which contains a flag indicating
            if the import was successful, and any messages regarding the 
            import transaction.
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

            if created or changed or force:
                m = hashlib.sha1()
                m.update(admcfg.get('password'))
                admin.set_password(m.hexdigest())
                admin.save()

            return (True, [message],)

        except:
            messages = ['Error when creating superuser:\n%s' % traceback.format_exc()]
            return (False, messages,)

    def import_regions(self, force):
        """
        Create region models out of the configuration.

        Returns:
            (success, messages,) -- A tuple which contains a flag indicating
            if the import was successful, and any messages regarding the 
            import transaction.
        """
        regions = self.store.filter_regions()
        messages = []
        for region in regions:
            attributes = {
                'name': region.get('name'),
                'label': region.get('label'),
                'description': region.get('description'),
                'sort_key': region.get('sort_key')
            }
            obj, created, changed, message = ModelHelper.check_and_update(Region, overwrite=force, **attributes)
            messages.append(message)

        return (True, messages,)

    def import_legislative_bodies(self, force):
        """
        Create legislative body models out of the configuration.

        Returns:
            (success, messages,) -- A tuple which contains a flag indicating
            if the import was successful, and any messages regarding the 
            import transaction.
        """
        messages = []
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
                messages.append( "Legislative body %s not attributed to any region" % attributes['name'])
                continue
            else:
                region_name = body_by_region[0].getparent().getparent().get('name')
            attributes['region'] = Region.objects.get(name=region_name)

            obj, created, changed, message = ModelHelper.check_and_update(LegislativeBody, overwrite=force, **attributes)
            messages.append(message)

            if obj is None:
                continue

            # Add multi-member district configuration
            mmconfig = store.get_node('//MultiMemberDistrictConfig[@legislativebodyref="%s"]' % body.get('id'))
            if mmconfig:
                obj.multi_members_allowed = True
                obj.multi_district_label_format = mmconfig.get('multi_district_label_format')[:32]
                obj.min_multi_districts = mmconfig.get('min_multi_districts')
                obj.max_multi_districts = mmconfig.get('max_multi_districts')
                obj.min_multi_district_members = mmconfig.get('min_multi_district_members')
                obj.max_multi_district_members = mmconfig.get('max_multi_district_members')
                obj.min_plan_members = mmconfig.get('min_plan_members')
                obj.max_plan_members = mmconfig.get('max_plan_members')
                messages.append( 'Multi-member districts enabled for: %s' % body.get('name') )
            else:
                obj.multi_members_allowed = False
                obj.multi_district_label_format = ''
                obj.min_multi_districts = 0
                obj.max_multi_districts = 0
                obj.min_multi_district_members = 0
                obj.max_multi_district_members = 0
                obj.min_plan_members = 0
                obj.max_plan_members = 0
                messages.append( 'Multi-member districts not configured for: %s' % body.get('name') )

            obj.save()

        return (True, messages,)
