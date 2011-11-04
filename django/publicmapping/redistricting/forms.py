from models import *
from django import forms
import os, tempfile, csv, inflect

class SubjectUploadForm(forms.Form):
    """
    A simple form that accepts a single file for upload that contains new Subject data.
    """
    subject_upload = forms.FileField()

    def clean_subject_upload(self):
        """
        After requiring that the field be present, this method checks the
        validity of the 'subject_upload' field.
        """
        subject_upload = self.cleaned_data['subject_upload']

        localstore = tempfile.NamedTemporaryFile(mode='w+',delete=False)
        for chunk in subject_upload.chunks():
            localstore.write(chunk)

        # move to the beginning of the file
        localstore.seek(0)

        nlines = 0
        reader = csv.DictReader(localstore.file)
        for row in reader:
            nlines += 1

        localstore.close()
        os.remove(localstore.name)

        geolevel, nunits = SubjectUploadForm.get_basest_geolevel_and_count()

        if nlines != nunits:
            p = inflect.engine()
            msg = 'There are an incorrect number of geounits in the uploaded Subject file. '
            if nlines < nunits:
                missing = nunits - nlines
                msg += 'There %s %d %s missing.' % (p.plural('is', missing), missing, p.plural('geounit', missing))
            else:
                extra = nlines - nunits
                msg += 'There %s %d extra %s.' % (p.plural('is', extra), extra, p.plural('geounit', extra))

            raise forms.ValidationError(msg)

        raise forms.ValidationError('Incomplete.')

    @staticmethod
    def get_basest_geolevel_and_count():
        base_levels = LegislativeLevel.objects.filter(parent__isnull=True)
        geolevel = None
        nunits = 0
        for base_level in base_levels:
            if base_level.geolevel.geounit_set.all().count() > nunits:
                nunits = base_level.geolevel.geounit_set.all().count()
                geolevel = base_level.geolevel

        return (geolevel, nunits,)


