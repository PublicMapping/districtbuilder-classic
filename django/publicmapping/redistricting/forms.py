from models import *
from django import forms
import os, tempfile

class SubjectUploadForm(forms.Form):
    """
    A simple form that accepts a single file for upload that contains new Subject data.
    """
    subject_upload = forms.FileField()

    processing_file = forms.CharField(required=False, widget=forms.HiddenInput)

    task_uuid = forms.CharField(required=False, widget=forms.HiddenInput)

    def clean(self):
        """
        After requiring that the field be present, this method checks the
        validity of the 'subject_upload' field.
        """
        subject_upload = self.cleaned_data['subject_upload']
        task_id = ''

        sup = SubjectUpload(filename=subject_upload.name, status='UL')
        sup.save()

        try:
            localstore = tempfile.NamedTemporaryFile(mode='w+', delete=False)
            for chunk in subject_upload.chunks():
                localstore.write(chunk)
            localstore.close()

            sup.status = 'CH'

            # verify_count begins a cascade of validation operations
            task = SubjectUpload.verify_count.delay(sup.id, localstore.name)
            sup.task_id = task.task_id

            sup.save()
        except:
            sup.status = 'ER'
            sup.save()

            raise forms.ValidationError('Could not store uploaded Subject template.')

        self.cleaned_data['task_uuid'] = sup.task_id
        self.cleaned_data['processing_file'] = sup.filename

        return self.cleaned_data
