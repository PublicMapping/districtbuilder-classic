from models import *
from django import forms
from django.core.files.uploadedfile import UploadedFile
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
    force_overwrite = forms.BooleanField(required=False, widget=forms.HiddenInput)

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
        if not subject_upload is None and isinstance(subject_upload,UploadedFile):
            self.ul_file = subject_upload.name
            task_id = ''

            # Create a new record of uploaded subjects
            sup = SubjectUpload(upload_filename=subject_upload.name, status='UL')
            sup.save()

            # try saving the uploaded file via stream to the file system
            try:
                localstore = tempfile.NamedTemporaryFile(mode='w+', delete=False)
                for chunk in subject_upload.chunks():
                    localstore.write(chunk)
            except Exception, ex:
                sup.status = 'ER'
                sup.save()

                raise forms.ValidationError('Could not store uploaded Subject template.')

            sup.processing_filename = self.ps_file = localstore.name
            sup.save()

            # Check if the subject exists.
            localstore.seek(0)

            reader = csv.DictReader(localstore)
            sup.subject_name = self.temp_subject_name = reader.fieldnames[1][0:50]
            sup.save()

            localstore.close()

        # If the subject_upload is not a file, it was probably already uploaded.
        # Check the processing_file field to see if that file exists on the file system.
        elif 'processing_file' in self.cleaned_data and self.cleaned_data['processing_file'] != '':
            if 'uploaded_subject' in self._errors:
                del self._errors['uploaded_subject']

            self.ps_file = self.cleaned_data['processing_file']
            self.ul_file = self.cleaned_data['uploaded_file']
            self.temp_subject_name = self.cleaned_data['subject_name']

            sup = SubjectUpload.objects.get(upload_filename=self.ul_file,
                processing_filename=self.ps_file)

            # the processing file must be in the /tmp/ folder, and may not contain any ".."
            if not self.temp_path_re.match(self.ps_file) or \
                self.dotdot_path_re.match(self.ps_file) or \
                not os.path.exists(self.ps_file):
                raise forms.ValidationError('Uploaded file cannot be found.')
        else:
            raise forms.ValidationError('Uploaded file is required.')

        collisions = Subject.objects.filter(name=self.temp_subject_name).count()
        if collisions > 0:
            if not self.cleaned_data['force_overwrite']:
                self.temp_subject_name = sup.subject_name
                self._errors = {}
                self._errors['subject_name'] = self.error_class(['Please specify the subject name.'])
                self._errors['force_overwrite'] = self.error_class(['Check this box to overwrite the existing subject with the same name.'])
                return self.cleaned_data

        sup.subject_name = self.temp_subject_name
        sup.status = 'CH'
        sup.save()

        # verify_count begins a cascade of validation operations
        task = SubjectUpload.verify_count.delay(sup.id, self.ps_file)
        sup.task_id = task.task_id

        sup.save()

        self.cleaned_data['task_uuid'] = sup.task_id
        self.cleaned_data['processing_file'] = sup.upload_filename

        return self.cleaned_data
