"""
Define the forms used by the redistricting app.

The forms in redistricting.forms define the UI forms used in the 
application. Each class relates to a form used to capture user input
in the application.

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

from models import *
from tasks import verify_count
from django import forms
from django.core.files.uploadedfile import UploadedFile
from django.utils.translation import ugettext as _, get_language
import os, tempfile, csv, re


class SubjectUploadForm(forms.Form):
    """
    A form that accepts a subject file for upload that contains new Subject data.
    """

    # An uploaded CSV file that contains the subject data
    subject_upload = forms.FileField(required=False)

    # A field that contains the name of the uploaded file for verification
    uploaded_file = forms.CharField(required=False, widget=forms.HiddenInput)

    # A field that contains the name of the processing temp file for verification
    processing_file = forms.CharField(required=False, widget=forms.HiddenInput)

    # The name of the Subject, only used if subject names collide.
    subject_name = forms.CharField(required=False, widget=forms.HiddenInput)

    # Overwrite checkbox to force an upload to win if subject names collide.
    force_overwrite = forms.BooleanField(
        required=False, widget=forms.HiddenInput)

    # The ID of the task that is currently running the verification.
    task_uuid = forms.CharField(required=False, widget=forms.HiddenInput)

    # These members are used locally, and are not bound to the form as fields
    ul_file = None
    ps_file = None
    temp_subject_name = ''

    # These regular expressions are used together to verify that a processing file
    # is stored in the /tmp/ directory, and that it contains no '..' elements in the path
    temp_path_re = re.compile('^\/tmp\/.*$')
    dotdot_path_re = re.compile('.*\.\..*')

    def clean(self):
        """
        Check the validity of the form. If all immediate fields are present,
        this method kicks off a celery task to verify the counts of elements
        in the uploaded file.
        """

        subject_upload = self.cleaned_data['subject_upload']
        if not subject_upload is None and isinstance(subject_upload,
                                                     UploadedFile):
            self.ul_file = subject_upload.name
            task_id = ''

            # Create a new record of uploaded subjects
            sup = SubjectUpload(
                upload_filename=subject_upload.name, status='UL')
            sup.save()

            # try saving the uploaded file via stream to the file system
            try:
                localstore = tempfile.NamedTemporaryFile(
                    mode='w+', delete=False)
                for chunk in subject_upload.chunks():
                    localstore.write(chunk)
            except Exception, ex:
                sup.status = 'ER'
                sup.save()

                raise forms.ValidationError(
                    _('Could not store uploaded Subject template.'))

            sup.processing_filename = self.ps_file = localstore.name
            sup.save()

            # Check if the subject exists.
            localstore.seek(0)

            reader = csv.DictReader(localstore)

            if len(reader.fieldnames) < 2:
                localstore.close()

                sup.status = 'ER'
                sup.save()

                raise forms.ValidationError(
                    _('The uploaded file is missing subject data.'))

            try:
                clean_name = self._clean_name(reader.fieldnames[1][0:50])
                sup.subject_name = self.temp_subject_name = clean_name
                sup.save()
            except Exception, ex:
                raise forms.ValidationError(
                    _('The new subject name could not be determined.'))
            finally:
                localstore.close()

        # If the subject_upload is not a file, it was probably already uploaded.
        # Check the processing_file field to see if that file exists on the file system.
        elif self.cleaned_data['processing_file'] != '':
            self.ps_file = self.cleaned_data['processing_file']
            self.ul_file = self.cleaned_data['uploaded_file']
            self.temp_subject_name = self._clean_name(
                self.cleaned_data['subject_name'])

            sup = SubjectUpload.objects.get(
                upload_filename=self.ul_file, processing_filename=self.ps_file)

            # the processing file must be in the /tmp/ folder, and may not contain any ".."
            if not self.temp_path_re.match(self.ps_file) or \
                self.dotdot_path_re.match(self.ps_file) or \
                not os.path.exists(self.ps_file):
                raise forms.ValidationError(
                    _('Uploaded file cannot be found.'))
        else:
            self._errors['subject_upload'] = self.error_class(
                [_('Uploaded file is required.')])
            return self.cleaned_data

        # path for data dir is adjacent to the web_temp setting
        pathspec = settings.WEB_TEMP.split('/')
        pathspec[-1] = 'data'
        pathspec = '/'.join(pathspec)

        saved_ul = '%s/%s' % (pathspec, self.temp_subject_name)

        collisions = Subject.objects.filter(name=self.temp_subject_name)
        if collisions.count() > 0:
            if not self.cleaned_data['force_overwrite']:
                self.temp_subject_name = sup.subject_name
                self._errors = {}
                self._errors['subject_name'] = self.error_class(
                    [_('Please specify a unique subject name.')])
                self._errors['force_overwrite'] = self.error_class([
                    _('Check this box to overwrite the existing subject with the same name.'
                      )
                ])
                return self.cleaned_data
            saved_ul = '%s_%s.csv' % (saved_ul, str(collisions[0].version))
        else:
            saved_ul = '%s_1.csv' % saved_ul

        # move the uploaded subject file to the data directory
        os.rename(self.ps_file, saved_ul)

        # update the location of the processing_file
        sup.processing_filename = self.ps_file = saved_ul

        sup.subject_name = self.temp_subject_name
        sup.status = 'CH'
        sup.save()

        # verify_count begins a cascade of validation operations
        task = verify_count.delay(
            sup.id, self.ps_file, language=get_language())
        sup.task_id = task.task_id

        sup.save()

        self.cleaned_data['task_uuid'] = sup.task_id
        self.cleaned_data['processing_file'] = sup.upload_filename

        return self.cleaned_data

    def _clean_name(self, inputname):
        try:
            cmp1 = re.match(r'[^a-zA-Z_]+?([a-zA-Z_]+)', inputname)
            cmp2 = re.findall(r'[\w]+', inputname)
            if cmp1 is None:
                if cmp2[0] == inputname:
                    return inputname
                else:
                    return '_'.join(cmp2).lower()
            else:
                cmp1 = cmp1.groups()[0]

            return '_'.join([cmp1] + cmp2[1:]).lower()
        except Exception, ex:
            raise forms.ValidationError(
                _('Uploaded file contains an invalid subject name.'))
