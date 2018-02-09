"""
Configure the appearance of the redistricting admin interface.

The classes in redistricting.admin assist the Django framework's
administrative interface in presenting the models. The classes contained
within change the default behavior of the administrative to make maintenance
of models easier.

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

from models import *
from forms import *
from tasks import *
from django import forms
from django.http import HttpResponse
from django.contrib.gis import admin
from django.shortcuts import render
from django.utils.encoding import force_unicode
from django.contrib.admin import helpers
from django.utils.translation import ugettext_lazy, ugettext as _
from django.core.exceptions import PermissionDenied
from django import template
from django.conf import settings
import inflect
from functools import update_wrapper


class ComputedCharacteristicAdmin(admin.ModelAdmin):
    """
    Administrative settings for ComputedCharacteristics of a District.
    """

    list_display = (
        'subject',
        'district',
        'number',
    )

    # Enable filtering by subject
    list_filter = ('subject', )


class CharacteristicAdmin(admin.ModelAdmin):
    """
    Administrative settings for Characteristics of a Geounit.

    A Geounit's characteristic is a measurement of the Geounit, such as
    'total population', or 'percent with a high school diploma'.
    """

    # When displayed as a list, show these fields in columns.
    list_display = (
        'subject',
        'geounit',
        'number',
    )

    # Don't try to lookup the relationships to geounits, just list their
    # IDs
    raw_id_fields = ('geounit', )


class CharacteristicInline(admin.TabularInline):
    """
    Administrative setting for inline displays of Characteristics.

    Characteristics are displayed inline when viewing Geounits. This class
    defines the model that should be used in the inline display.
    """

    # The model that this inline class is displaying.
    model = Characteristic


class GeounitAdmin(admin.OSMGeoAdmin):
    """
    Administrative setting for Geounits.

    Geounits are the units of geography in the redistricting app. Each
    Geounit can have zero or more Characteristics, with one Characteristic
    per Subject.

    This class controls the display of an OpenStreetMap slippy map for the
    geometry fields in the Geounit model.
    """

    # Display the Characteristics of this Geounit inline.
    inlines = [CharacteristicInline]

    # When displayed as a list, show the name and geolevel
    list_display = ('name', )

    # In admin view, show the name, portable_id, tree_code, geolevel, and geom fields.
    fields = (
        'name',
        'portable_id',
        'tree_code',
        'geom',
    )

    # Order geounits by name by default.
    ordering = ('name', )


class DistrictInline(admin.TabularInline):
    """
    Administrative setting for inline displays of Districts.

    Districts are displayed inline when viewing plans. This class
    defines the model that should be used in the inline display, as well
    as the fields of that model that are editable inline.
    """

    # The fields that are editable inline.
    fields = (
        'district_id',
        'short_label',
        'long_label',
        'version',
    )

    # The model that this inline class is displaying.
    model = District


class DistrictAdmin(admin.OSMGeoAdmin):
    """
    Administrative setting for Districts.

    Districts are composite sets of geometry that are built out of Geounits.
    Each district aggregates the Characteristics of the Geounits that are
    contained within in, and stores those results in ComputedCharacteristic
    models.

    This class controls the display of an OpenStreetMap slippy map for the
    geometry fields in the District model.
    """

    # In admin view, show the district_id, name, plan, version, and geom
    # fields.
    fields = (
        'district_id',
        'short_label',
        'long_label',
        'plan',
        'version',
        'geom',
    )

    # When displayed as a list, show the name, plan, and version.
    list_display = (
        'short_label',
        'long_label',
        'plan',
        'version',
    )

    # Enable filtering by plan, version and district_id in the admin list view.
    list_filter = ('plan', 'version', 'district_id')

    # Order Districts by version and district_id by default.
    ordering = (
        'version',
        'district_id',
    )


class PlanAdmin(admin.ModelAdmin):
    """
    Administrative setting for Plans.

    Plans are collections of Districts. Admin views of plans display all
    the districts that are in the plan.
    """

    # Display the Districts of this Plan inline.
    inlines = [DistrictInline]

    # When displayed as a list, show the name, is_template, is_shared,
    # owner, created, is_valid, processing_state, edited flags.
    list_display = ('name', 'is_template', 'is_shared', 'owner', 'created',
                    'edited', 'is_valid', 'processing_state')

    list_filter = ('is_template', 'is_shared', 'is_valid', 'legislative_body',
                   'owner', 'is_valid', 'processing_state')

    # Order Plans by name by default.
    ordering = ('name', )

    # Add custom actions
    def reaggregate_selected_plans(self, request, queryset):
        for plan in queryset:
            # Set the reaggregating flag
            # (needed for the state to display on immediate refresh)
            plan.processing_state = ProcessingState.REAGGREGATING
            plan.save()

            # Reaggregate asynchronously
            reaggregate_plan.delay(plan.id)

    def validate_selected_plans(self, request, queryset):
        for plan in queryset:
            # Validate asynchronously
            validate_plan.delay(plan.id)

    actions = [reaggregate_selected_plans, validate_selected_plans]


class SubjectAdmin(admin.ModelAdmin):
    """
    Administrative setting for Subjects.

    Subjects are the names of attributes of Geounits. Each Geounit has one
    Characteristic per Subject.
    """

    # When displayed as a list, show the display name, the short display,
    # and a flag indicating if it should be displayed (in the app), and
    # the percentage denominator.
    list_display = (
        'name',
        'sort_key',
        'is_displayed',
        'percentage_denominator',
    )

    fields = (
        'name',
        'percentage_denominator',
        'is_displayed',
        'sort_key',
        'format_string',
        'version',
    )

    # Enable filtering by the displayed flag
    list_filter = ('is_displayed', )

    # Use a custom object deletion mechanism
    actions = ['delete_selected_subject']

    def get_urls(self):
        """
        Get the URLs for the auto-discovered admin pages. The Subject admin pages
        support a GET url for a subject template, an upload endpoint, and an upload/uuid/status
        endpoint to check the status of an upload.
        """

        # This is django wrapper nastiness inherited from the default admin get_url method
        from django.conf.urls import url

        def wrap(view):
            def wrapper(*args, **kwargs):
                return self.admin_site.admin_view(view)(*args, **kwargs)

            return update_wrapper(wrapper, view)

        info = self.model._meta.app_label, self.model._meta.model_name

        # Add patterns special to subject uploading
        urlpatterns = [
            # subject/template GETs a csv template
            url(r'^template/$',
                wrap(self.template_view),
                name='%s_%s_add' % info),
            # subject/upload/ POSTs a user-edited csv template
            url(r'^upload/$',
                wrap(self.upload_view),
                name='%s_%s_upload' % info),
            # subject/upload/<uuid>/status GETs the status of a celery task
            url(r'^upload/(?P<task_uuid>.+)/status/$',
                wrap(self.upload_status_view),
                name='%s_%s_status' % info),
        ] + super(SubjectAdmin, self).get_urls()

        return urlpatterns

    def get_actions(modeladmin, request):
        """
        Get the actions available for administering subject objects.

        This overrides the default get_actions to remove the 'delete' action, and replace
        it with our own.
        """
        actions = super(SubjectAdmin, modeladmin).get_actions(request)
        del actions['delete_selected']
        return actions

    def has_delete_permission(modeladmin, request, obj=None):
        """
        Override the delete permission for the Subject model. A Subject may never be deleted.
        This only affects the admin change form, and not the bulk delete dropdown in the
        Subject list screen.
        """
        return False

    def delete_selected_subject(modeladmin, request, queryset):
        """
        This is invoked from the dropdown menu in the admin as a bulk action.
        This overrides the
        """
        opts = modeladmin.model._meta
        app_label = opts.app_label

        # Check that the user has delete permission for the actual model
        # BUT we can't use modeladmin.has_delete_permission, as it's overridden
        # above to hide the delete button on the change form.
        if not request.user.has_perm(modeladmin.opts.app_label + '.' +
                                     modeladmin.opts.get_delete_permission()):
            raise PermissionDenied

        if request.POST:
            n = queryset.count()
            if n:
                engine = inflect.engine()
                for obj in queryset:
                    obj_display = force_unicode(obj)
                    modeladmin.log_deletion(request, obj, obj_display)
                queryset.delete()
                modeladmin.message_user(
                    request,
                    _('Successfully deleted %(count)d %(item)s') % {
                        'count': n,
                        'item': engine.plural('subject', n)
                    })
            # Return None to display the change list page again.
            return None

        warned = request.POST.get('warned') == 'on'

        context = {
            "object_name": force_unicode(opts.verbose_name),
            "deletable_objects": queryset.all(),
            "queryset": queryset,
            "opts": opts,
            "app_label": app_label,
            "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
            "warned": warned
        }

        # Display the confirmation page
        return render(
            "admin/%s/%s/delete_selected_confirmation.html" %
            (app_label, opts.object_name.lower()),
            context,
            context_instance=template.RequestContext(request))

    # Customize the label of the delete_selected_subject action to look like the normal delete label
    delete_selected_subject.short_description = ugettext_lazy(
        "Delete selected %(verbose_name_plural)s")

    # Use a special add_form template
    add_form_template = 'admin/redistricting/subject/add_form.html'

    def template_view(modeladmin, request, form_url='', extra_context=None):
        """
        A view function that returns a dynamically generated CSV file, based
        on the geounits available in the application.
        """
        opts = modeladmin.model._meta
        app_label = opts.app_label
        geolevel, nunits = LegislativeLevel.get_basest_geolevel_and_count()
        context = {
            # get geounits at the basest of all base geolevels
            'geounits':
            geolevel.geounit_set.all().order_by('portable_id').values_list(
                'portable_id', flat=True)
        }

        resp = render(
            "admin/%s/%s/add_template.csv" % (app_label,
                                              opts.object_name.lower()),
            dictionary=context,
            content_type='text/plain')
        resp['Content-Disposition'] = 'attachement; filename=new_subject.csv'
        return resp

    def upload_view(modeladmin, request, form_url='', extra_context=None):
        """
        A view function that displays an upload form or upload verification
        form input.
        """
        opts = modeladmin.model._meta
        app_label = opts.app_label
        is_processing = False

        if request.method == 'GET':
            form = SubjectUploadForm()
        else:
            form = SubjectUploadForm(request.POST, request.FILES)
            is_processing = form.is_valid()

            if is_processing:
                # form data is immutable, so we must create a new form with the cleaned
                # data if we want to re-use it.
                form = SubjectUploadForm(form.cleaned_data)

                # do not validate this new form, as it replaces one that has already been validated.
                form._errors = {}

                # Switch the form input types, as we're now processing the file in the background
                form.fields['processing_file'].widget = forms.TextInput(
                    attrs={
                        'readOnly': True
                    })
                form.fields['subject_upload'].widget = forms.HiddenInput()
            else:
                errors = form._errors
                if 'subject_upload' in errors:
                    form = SubjectUploadForm()
                    form._errors = errors
                else:

                    form = SubjectUploadForm({
                        'processing_file':
                        form.ps_file,
                        'uploaded_file':
                        form.ul_file,
                        'subject_name':
                        form.temp_subject_name,
                        'subject_upload':
                        form.ul_file
                    })
                    form._errors = errors

                    form.fields['uploaded_file'].widget = forms.TextInput(
                        attrs={
                            'readOnly': True
                        })
                    form.fields[
                        'force_overwrite'].widget = forms.CheckboxInput()
                    form.fields['subject_upload'].widget = forms.HiddenInput()
                    form.fields['subject_name'].widget = forms.TextInput()

        context = {
            'add':
            True,
            'opts':
            opts,
            'app_label':
            app_label,
            'has_change_permission':
            True,
            'upload_form':
            form,
            'user':
            request.user,
            'errors':
            form.errors,
            'form_url':
            '/admin/%s/%s/upload/' % (
                app_label,
                opts.object_name.lower(),
            ),
            'request': {
                'has_upload_template': True
            },
            'is_processing':
            is_processing
        }

        resp = render(
            'admin/redistricting/subject/upload_form.html',
            context,
            context_instance=template.RequestContext(request))
        return resp

    def upload_status_view(modeladmin,
                           request,
                           form_url='',
                           extra_context=None,
                           task_uuid=''):
        """
        Get the status of an uploading task.
        """
        response = {'success': False}
        task = verify_count.AsyncResult(task_uuid)
        if task is None:
            response['message'] = _('No task with that id.')
        else:
            response['success'] = True
            response['state'] = task.state
            response['task_id'] = task.task_id

            if task.state == 'SUCCESS':
                response['info'] = task.result
            else:
                response['message'] = str(task.result)

        return HttpResponse(
            json.dumps(response), content_type='application/json')


class ScorePanelAdmin(admin.ModelAdmin):
    """
    Administrative settings for ScorePanels.
    """

    fields = (
        'name',
        'title',
        'displays',
        'type',
        'template',
        'position',
        'is_ascending',
        'cssclass',
        'score_functions',
    )

    list_display = (
        'name',
        'title',
        'type',
        'template',
        'cssclass',
    )

    list_filter = (
        'type',
        'cssclass',
    )

    ordering = ['name', 'title']


class ScoreArgumentInline(admin.TabularInline):
    model = ScoreArgument


class ScoreFunctionAdmin(admin.ModelAdmin):
    """
    Administrative settings for ScoreFunctions.
    """
    fields = (
        'name',
        'calculator',
        'selectable_bodies',
        'is_planscore',
    )

    list_display = (
        'name',
        'is_planscore',
    )

    list_filter = (
        'is_planscore',
        'calculator',
    )

    ordering = ['name']

    inlines = [ScoreArgumentInline]


class ScoreArgumentAdmin(admin.ModelAdmin):
    """
    Administrative settings for ScoreArguments
    """
    fields = (
        'argument',
        'type',
        'value',
        'function',
    )

    list_display = (
        'argument',
        'type',
        'value',
        'function',
    )

    ordering = ['function', 'argument']


class ScoreDisplayAdmin(admin.ModelAdmin):
    """
    Administrative settings for ScoreDisplay
    """
    list_filter = ('is_page', )


class ValidationCriteriaAdmin(admin.ModelAdmin):
    """
    Administrative settings for ValidationCriteria.
    """
    fields = (
        'name',
        'legislative_body',
        'function',
    )


# Register these classes with the admin interface.
admin.site.register(Geounit, GeounitAdmin)
admin.site.register(Region)
admin.site.register(ComputedCharacteristic, ComputedCharacteristicAdmin)
admin.site.register(Characteristic, CharacteristicAdmin)
admin.site.register(Subject, SubjectAdmin)
admin.site.register(Geolevel)
admin.site.register(LegislativeBody)
admin.site.register(LegislativeLevel)
admin.site.register(Plan, PlanAdmin)
admin.site.register(District, DistrictAdmin)
admin.site.register(Profile)
admin.site.register(ScoreArgument, ScoreArgumentAdmin)
admin.site.register(ScoreDisplay, ScoreDisplayAdmin)
admin.site.register(ScoreFunction, ScoreFunctionAdmin)
admin.site.register(ScorePanel, ScorePanelAdmin)
admin.site.register(ValidationCriteria, ValidationCriteriaAdmin)
admin.site.register(ComputedDistrictScore)
admin.site.register(ComputedPlanScore)
admin.site.register(ContiguityOverride)
