"""
Define asynchronous tasks used by the redistricting app.

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

from celery.task import task
from django.db.models import Max,Avg
from django.db import connection, transaction
from django.conf import settings
import re, csv, inflect, os, logging
from models import *
from config import *
from djsld import generator

logger = logging.getLogger(__name__)

@task
@transaction.commit_manually
def verify_count(upload_id, localstore):
    """
    Initialize the verification process by counting the number of geounits
    in the uploaded file. After this step completes, the verify_preload
    method is called.

    Parameters:
        upload_id - The id of the SubjectUpload record.
        localstore - a temporary file that will get deleted when it is closed
    """
    reader = csv.DictReader(open(localstore,'r'))
    upload = SubjectUpload.objects.get(id=upload_id)
    upload.subject_name = reader.fieldnames[1][0:50]
    upload.save()
    transaction.commit()

    logger.debug('Created new SubjectUpload transaction record for "%s".', upload.subject_name)

    # do this in bulk!
    # insert upload_id, portable_id, number
    sql = 'INSERT INTO "%s" ("%s","%s","%s") VALUES (%%(upload_id)s, %%(geoid)s, %%(number)s)' % (SubjectStage._meta.db_table, SubjectStage._meta.fields[1].attname, SubjectStage._meta.fields[2].attname, SubjectStage._meta.fields[3].attname)
    args = []
    for row in reader:
        args.append( {'upload_id':upload.id, 'geoid':row[reader.fieldnames[0]].strip(), 'number':row[reader.fieldnames[1]].strip()} )
        # django ORM takes about 320s for 280K geounits
        #SubjectStage(upload=upload, portable_id=row[reader.fieldnames[0]],number=row[reader.fieldnames[1]]).save()

    # direct access to db-api takes about 60s for 280K geounits
    cursor = connection.cursor()
    cursor.executemany(sql, tuple(args))

    os.remove(localstore)

    logger.debug('Bulk loaded CSV records into the staging area.')

    nlines = upload.subjectstage_set.all().count()
    geolevel, nunits = LegislativeLevel.get_basest_geolevel_and_count()

    # Validation #1: if the number of geounits in the uploaded file
    # don't match the geounits in the database, the content is not valid
    if nlines != nunits:
        # The number of geounits in the uploaded file do not match the base geolevel geounits
        p = inflect.engine()
        msg = 'There are an incorrect number of geounits in the uploaded Subject file. '
        if nlines < nunits:
            missing = nunits - nlines
            msg += 'There %s %d %s missing.' % (p.plural('is', missing), missing, p.plural('geounit', missing))
        else:
            extra = nlines - nunits
            msg += 'There %s %d extra %s.' % (p.plural('is', extra), extra, p.plural('geounit', extra))

        # since the transaction was never committed after all the inserts, this nullifies
        # all the insert statements, so there should be no quarantine to clean up
        transaction.rollback()

        logger.debug(msg)

        upload.status = 'ER'
        upload.save()
        transaction.commit()

        return {'task_id':None, 'success':False, 'messages':[msg]}

    # The next task will preload the units into the quarintine table
    task = verify_preload.delay(upload_id).task_id

    transaction.commit()

    return {'task_id':task, 'success':True, 'messages':['Verifying consistency of uploaded geounits ...']}


@task
def verify_preload(upload_id):
    """
    Continue the verification process by counting the number of geounits
    in the uploaded file and compare it to the number of geounits in the
    basest geolevel. After this step completes, the copy_to_characteristics
    method is called.

    Parameters:
        upload_id - The id of the SubjectUpload record.
    """
    upload = SubjectUpload.objects.get(id=upload_id)
    geolevel, nunits = LegislativeLevel.get_basest_geolevel_and_count()

    # This seizes postgres -- probably small memory limits.
    #aligned_units = upload.subjectstage_set.filter(portable_id__in=permanent_units).count()

    permanent_units = geolevel.geounit_set.all().order_by('portable_id').values_list('portable_id',flat=True)
    temp_units = upload.subjectstage_set.all().order_by('portable_id').values_list('portable_id',flat=True)

    # quick check: make sure the first and last items are aligned
    ends_match = permanent_units[0] == temp_units[0] and \
        permanent_units[permanent_units.count()-1] == temp_units[temp_units.count()-1]
    msg = 'There are a correct number of geounits in the uploaded Subject file, '
    if not ends_match:
        p = inflect.engine()
        msg += 'but the geounits do not have the same portable ids as those in the database.'

    # python foo here: count the number of zipped items in the 
    # permanent_units and temp_units lists that do not have the same portable_id
    # thus counting the portable_ids that are not mutually shared
    aligned_units = len(filter(lambda x:x[0] == x[1], zip(permanent_units, temp_units)))

    if nunits != aligned_units:
        # The number of geounits in the uploaded file match, but there are some mismatches.
        p = inflect.engine()
        mismatched = nunits - aligned_units
        msg += 'but %d %s %s not match ' % (mismatched, p.plural('geounit', mismatched), p.plural('do', mismatched))
        msg += 'the geounits in the database.'

    if not ends_match or nunits != aligned_units:
        logger.debug(msg)

        upload.status = 'ER'
        upload.save()
        upload.subjectstage_set.all().delete()

        return {'task_id':None, 'success':False, 'messages':[msg]}

    # The next task will load the units into the characteristic table
    task = copy_to_characteristics.delay(upload_id).task_id

    return {'task_id':task, 'success':True, 'messages':['Copying records to characteristic table ...']}


@task
@transaction.commit_manually
def copy_to_characteristics(upload_id):
    """
    Continue the verification process by copying the holding records for
    the subject into the characteristic table. This is the last step before
    user intervention for Subject metadata input.

    Parameters:
        upload_id - The id of the SubjectUpload record.
    """
    upload = SubjectUpload.objects.get(id=upload_id)
    geolevel, nunits = LegislativeLevel.get_basest_geolevel_and_count()

    # these two lists have the same number of items, and no items are extra or missing.
    # therefore, ordering by the same field will create two collections aligned by
    # the 'portable_id' field
    quarantined = upload.subjectstage_set.all().order_by('portable_id')
    geounits = geolevel.geounit_set.all().order_by('portable_id').values_list('id','portable_id')

    geo_quar = zip(geounits, quarantined)

    # create a subject to hold these new values
    new_sort_key = Subject.objects.all().aggregate(Max('sort_key'))['sort_key__max'] + 1
    clean_name = ''
    try:
        cmp1 = re.match(r'.+?([a-zA-Z_]+)', upload.subject_name).groups()[0]
        cmp2 = re.findall(r'[\w]+', upload.subject_name)
        clean_name = '_'.join([cmp1] + cmp2[1:]).lower()
    except:
        msg = 'The subject name contains invalid characters.'

        logger.debug(msg)

        upload.status = 'ER'
        upload.save()
        transaction.commit()

        return {'task_id':None, 'success':False, 'messages':[msg, 'Please correct the error and try again.']}

    defaults = {
        'name':clean_name,
        'display':upload.subject_name, # wider than upload.subject_name
        'short_display':upload.subject_name[0:25], # truncate to field max length
        'description':upload.subject_name, # wider than upload.subject_name
        'is_displayed':False,
        'sort_key':new_sort_key,
        'format_string':'',
        'version':1
    }
    the_subject, created = Subject.objects.get_or_create(name=clean_name, defaults=defaults)

    logger.debug('Using %ssubject "%s" for new Characteristic values.', 'new ' if created else '', the_subject.name)

    upload.subject_name = clean_name
    upload.save()
    transaction.commit()

    args = []
    for geo_char in geo_quar:
        args.append({'subject':the_subject.id, 'geounit':geo_char[0][0], 'number':geo_char[1].number})

    # Prepare bulk loading into the characteristic table.
    if not created:
        # delete then recreate is a more stable technique than updating all the 
        # related characteristic items one at a time
        the_subject.characteristic_set.all().delete()

        logger.debug('Removed old characteristics related to old subject.')

        # increment the subject version, since it's being modified
        the_subject.version += 1
        the_subject.save()

        logger.debug('Incremented subject version to %d', the_subject.version)

    sql = 'INSERT INTO "%s" ("%s", "%s", "%s") VALUES (%%(subject)s, %%(geounit)s, %%(number)s)' % (
        Characteristic._meta.db_table,           # redistricting_characteristic
        Characteristic._meta.fields[1].attname,  # subject_id (foreign key)
        Characteristic._meta.fields[2].attname,  # geounit_id (foreign key)
        Characteristic._meta.fields[3].attname,  # number
    )

    # Insert or update all the records into the characteristic table
    cursor = connection.cursor()
    cursor.executemany(sql, tuple(args))

    logger.debug('Loaded new Characteristic values for subject "%s"', the_subject.name)

    task = update_vacant_characteristics.delay(upload_id, created).task_id

    transaction.commit()

    return {'task_id':task, 'success':True, 'messages':['Created characteristics, resetting computed characteristics...'] }


@task
def update_vacant_characteristics(upload_id, new_subj):
    """
    Update the values for the ComputedCharacteristics. This method
    does not precompute them, just adds dummy values for new subjects.
    For existing subjects, the current ComputedCharacteristics are
    untouched. For new and existing subjects, all plans are marked
    as needing reaggregation.
    """
    upload = SubjectUpload.objects.get(id=upload_id)
    subject = Subject.objects.get(name=upload.subject_name)

    if new_subj:
        sql = 'INSERT INTO "%s" ("%s", "%s", "%s") VALUES (%%(subject)s, %%(district)s, %%(number)s)' % (
            ComputedCharacteristic._meta.db_table,           # redistricting_computedcharacteristic
            ComputedCharacteristic._meta.fields[1].attname,  # subject_id (foreign key)
            ComputedCharacteristic._meta.fields[2].attname,  # district_id (foreign key)
            ComputedCharacteristic._meta.fields[3].attname,  # number
        )
        args = []

        for district in District.objects.all():
            args.append({'subject':subject.id, 'district':district.id, 'number':'0.0'})

        # Insert all the records into the characteristic table
        cursor = connection.cursor()
        cursor.executemany(sql, tuple(args))

        logger.debug('Created initial zero values for district characteristics for subject "%s"', subject.name)
    else:
        # reset the computed characteristics for all districts in one fell swoop
        ComputedCharacteristic.objects.filter(subject=subject).update(number=Decimal('0.0'))

        logger.debug('Cleared existing district characteristics for subject "%s"', subject.name)

        dependents = Subject.objects.filter(percentage_denominator=subject)
        for dependent in dependents:
            ComputedCharacteristic.objects.filter(subject=dependent).update(number=Decimal('0.0'))
            logger.debug('Cleared existing district characteristics for dependent subject "%s"', dependent.name)


    task = renest_uploaded_subject.delay(upload_id).task_id

    return {'task_id':task, 'success':True, 'messages':['Reset computed characteristics, renesting foundation geographies...'] }


@task
def renest_uploaded_subject(upload_id):
    """
    Renest all higher level geographies for the uploaded subject.
    """
    upload = SubjectUpload.objects.get(id=upload_id)
    subject = Subject.objects.get(name=upload.subject_name)

    renested = {}
    lbodies = LegislativeBody.objects.all()
    for lbody in lbodies:
        geolevels = lbody.get_geolevels()
        geolevels.reverse() # get the geolevels smallest to largest
        for i,geolevel in enumerate(geolevels):
            # the 0th level is the smallest level -- never renested
            if i == 0:
                continue

            # get the basename of the geolevel
            basename = geolevel.name[len(lbody.region.name)+1:]
            if basename in renested and renested[basename]:
                logger.debug('Geolevel "%s" already renested.', basename)
                continue

            renested[basename] = geolevel.renest(geolevels[i-1], subject=subject, spatial=False)

            logger.debug('Renesting of "%s" %s', basename, 'succeeded' if renested[basename] else 'failed')

    # reset the processing state for all plans in one fell swoop
    Plan.objects.all().update(processing_state=ProcessingState.NEEDS_REAGG)

    logger.debug('Marked all plans as needing reaggregation.')

    task = create_views_and_styles.delay(upload_id).task_id

    return {'task_id':task, 'success':True, 'messages':['Renested foundation geographies, creating spatial views and styles...'] }


@task
def create_views_and_styles(upload_id):
    """
    Create the spatial views required for visualizing the subject data on the map.
    """

    # Configure ALL views. This will replace view definitions with identical
    # view defintions as well as create the new view definitions.
    configure_views()

    logger.debug('Created spatial views for subject data values.')

    # Get the spatial configuration settings.
    geoutil = SpatialUtils(config={
        'host':settings.MAP_SERVER,
        'ns':settings.MAP_SERVER_NS,
        'nshref':settings.MAP_SERVER_NSHREF,
        'adminuser':settings.MAP_SERVER_USER,
        'adminpass':settings.MAP_SERVER_PASS,
        'styles':settings.SLD_ROOT
    })

    upload = SubjectUpload.objects.get(id=upload_id)
    subject = Subject.objects.get(name=upload.subject_name)

    for geolevel in Geolevel.objects.all():
        if geolevel.legislativelevel_set.all().count() == 0:
            # Skip 'abstract' geolevels if regions are configured
            continue

        logger.debug('Creating queryset and SLD content for %s, %s', geolevel.name, subject.name)

        qset = Geounit.objects.filter(characteristic__subject=subject, geolevel=geolevel).annotate(Avg('characteristic__number'))
        sld_body = generator.as_quantiles(qset, 'characteristic__number__avg', 5, 
            propertyname='number', userstyletitle=subject.short_display)

        logger.debug('Generated SLD content, creating featuretype.')

        geoutil.create_featuretype(get_featuretype_name(geolevel.name, subject.name))
        geoutil.create_style(subject.name, geolevel.name, None, None, sld_content=sld_body.as_sld(pretty_print=True))

        logger.debug('Created featuretype and style for %s, %s', geolevel.name, subject.name)

    task = clean_quarantined.delay(upload_id).task_id

    return {'task_id':task, 'success':True, 'messages':['Created spatial views and styles, cleaning quarantined data...'] }


@task
def clean_quarantined(upload_id):
    """
    Remove all temporary characteristics in the quarantine area for
    the given upload.

    Parameters:
        upload_id - The ID of the uploaded subject data.
    """
    upload = SubjectUpload.objects.get(id=upload_id)
    quarantined = upload.subjectstage_set.all()

    # The upload succeeded
    upload.status = 'OK'
    upload.save()

    logger.debug('Set upload status for SubjectUpload %d to "complete".', upload_id)

    # delete the quarantined items out of the quarantine table
    quarantined.delete()

    logger.debug('Removed quarantined subject data.')

    return {'task_id':None, 'success':True, 'messages':['Upload complete. Subject "%s" added.' % upload.subject_name], 'subject':Subject.objects.get(name=upload.subject_name).id}
