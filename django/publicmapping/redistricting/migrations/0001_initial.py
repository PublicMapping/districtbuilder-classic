# -*- coding: utf-8 -*-
# Generated by Django 1.11.5 on 2017-09-27 18:08
from __future__ import unicode_literals

from django.conf import settings
import django.contrib.gis.db.models.fields
import django.contrib.gis.geos.collections
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Characteristic',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('number', models.DecimalField(decimal_places=4, max_digits=12)),
                ('percentage', models.DecimalField(blank=True, decimal_places=8, max_digits=12, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='ComputedCharacteristic',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('number', models.DecimalField(decimal_places=4, max_digits=12)),
                ('percentage', models.DecimalField(blank=True, decimal_places=8, max_digits=12, null=True)),
            ],
            options={
                'ordering': ['subject'],
            },
        ),
        migrations.CreateModel(
            name='ComputedDistrictScore',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('value', models.TextField()),
            ],
        ),
        migrations.CreateModel(
            name='ComputedPlanScore',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version', models.PositiveIntegerField(default=0)),
                ('value', models.TextField()),
            ],
        ),
        migrations.CreateModel(
            name='ContiguityOverride',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ],
        ),
        migrations.CreateModel(
            name='District',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('district_id', models.PositiveIntegerField(default=None)),
                ('short_label', models.CharField(max_length=10)),
                ('long_label', models.CharField(max_length=256)),
                ('geom', django.contrib.gis.db.models.fields.MultiPolygonField(default=django.contrib.gis.geos.collections.MultiPolygon([]), srid=3785)),
                ('simple', django.contrib.gis.db.models.fields.GeometryCollectionField(default=django.contrib.gis.geos.collections.GeometryCollection([]), srid=3785)),
                ('version', models.PositiveIntegerField(default=0)),
                ('is_locked', models.BooleanField(default=False)),
                ('num_members', models.PositiveIntegerField(default=1)),
            ],
            options={
                'ordering': ['short_label'],
            },
        ),
        migrations.CreateModel(
            name='Geolevel',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50)),
                ('min_zoom', models.PositiveIntegerField(default=0)),
                ('sort_key', models.PositiveIntegerField(default=1)),
                ('tolerance', models.FloatField(default=10)),
            ],
            options={
                'ordering': ['sort_key'],
            },
        ),
        migrations.CreateModel(
            name='Geounit',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('portable_id', models.CharField(blank=True, db_index=True, max_length=50, null=True)),
                ('tree_code', models.CharField(blank=True, db_index=True, max_length=50, null=True)),
                ('geom', django.contrib.gis.db.models.fields.MultiPolygonField(srid=3785)),
                ('simple', django.contrib.gis.db.models.fields.MultiPolygonField(srid=3785)),
                ('center', django.contrib.gis.db.models.fields.PointField(srid=3785)),
                ('child', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='redistricting.Geounit')),
                ('geolevel', models.ManyToManyField(to='redistricting.Geolevel')),
            ],
        ),
        migrations.CreateModel(
            name='LegislativeBody',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=256)),
                ('max_districts', models.PositiveIntegerField()),
                ('multi_members_allowed', models.BooleanField(default=False)),
                ('multi_district_label_format', models.CharField(default=b'{label} - [{num_members}]', max_length=32)),
                ('min_multi_districts', models.PositiveIntegerField(default=0)),
                ('max_multi_districts', models.PositiveIntegerField(default=0)),
                ('min_multi_district_members', models.PositiveIntegerField(default=0)),
                ('max_multi_district_members', models.PositiveIntegerField(default=0)),
                ('min_plan_members', models.PositiveIntegerField(default=0)),
                ('max_plan_members', models.PositiveIntegerField(default=0)),
                ('is_community', models.BooleanField(default=False)),
                ('sort_key', models.PositiveIntegerField(default=0)),
            ],
            options={
                'verbose_name_plural': 'Legislative bodies',
            },
        ),
        migrations.CreateModel(
            name='LegislativeLevel',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('geolevel', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='redistricting.Geolevel')),
                ('legislative_body', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='redistricting.LegislativeBody')),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='redistricting.LegislativeLevel')),
            ],
        ),
        migrations.CreateModel(
            name='Plan',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('description', models.CharField(blank=True, db_index=True, max_length=500)),
                ('is_template', models.BooleanField(default=False)),
                ('is_shared', models.BooleanField(default=False)),
                ('processing_state', models.IntegerField(choices=[(-1, b'Unknown'), (0, b'Ready'), (1, b'Creating'), (2, b'Reaggregating'), (3, b'Needs reaggregation')], default=-1)),
                ('is_valid', models.BooleanField(default=False)),
                ('version', models.PositiveIntegerField(default=0)),
                ('min_version', models.PositiveIntegerField(default=0)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('edited', models.DateTimeField(auto_now=True)),
                ('legislative_body', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='redistricting.LegislativeBody')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Profile',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('organization', models.CharField(max_length=256)),
                ('pass_hint', models.CharField(max_length=256)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Region',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=256)),
                ('sort_key', models.PositiveIntegerField(default=0)),
            ],
        ),
        migrations.CreateModel(
            name='ScoreArgument',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('argument', models.CharField(max_length=50)),
                ('value', models.CharField(max_length=50)),
                ('type', models.CharField(max_length=10)),
            ],
        ),
        migrations.CreateModel(
            name='ScoreDisplay',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50)),
                ('title', models.CharField(max_length=50)),
                ('is_page', models.BooleanField(default=False)),
                ('cssclass', models.CharField(blank=True, max_length=50)),
                ('legislative_body', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='redistricting.LegislativeBody')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='ScoreFunction',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('calculator', models.CharField(max_length=500)),
                ('name', models.CharField(max_length=50)),
                ('is_planscore', models.BooleanField(default=False)),
                ('selectable_bodies', models.ManyToManyField(to='redistricting.LegislativeBody')),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='ScorePanel',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50)),
                ('title', models.CharField(max_length=50)),
                ('type', models.CharField(max_length=20)),
                ('position', models.PositiveIntegerField(default=0)),
                ('template', models.CharField(max_length=500)),
                ('cssclass', models.CharField(blank=True, max_length=50)),
                ('is_ascending', models.BooleanField(default=True)),
                ('displays', models.ManyToManyField(to='redistricting.ScoreDisplay')),
                ('score_functions', models.ManyToManyField(to='redistricting.ScoreFunction')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Subject',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50)),
                ('is_displayed', models.BooleanField(default=True)),
                ('sort_key', models.PositiveIntegerField(default=1)),
                ('format_string', models.CharField(blank=True, max_length=50)),
                ('version', models.PositiveIntegerField(default=1)),
                ('percentage_denominator', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='redistricting.Subject')),
            ],
            options={
                'ordering': ['sort_key'],
            },
        ),
        migrations.CreateModel(
            name='SubjectStage',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('portable_id', models.CharField(max_length=50)),
                ('number', models.DecimalField(decimal_places=4, max_digits=12)),
            ],
        ),
        migrations.CreateModel(
            name='SubjectUpload',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('processing_filename', models.CharField(max_length=256)),
                ('upload_filename', models.CharField(max_length=256)),
                ('subject_name', models.CharField(max_length=50)),
                ('status', models.CharField(choices=[(b'CH', b'Checking'), (b'ER', b'Error'), (b'NA', b'Not Available'), (b'OK', b'Done'), (b'UL', b'Uploading')], default=b'NA', max_length=2)),
                ('task_id', models.CharField(max_length=36)),
            ],
        ),
        migrations.CreateModel(
            name='ValidationCriteria',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50)),
                ('function', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='redistricting.ScoreFunction')),
                ('legislative_body', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='redistricting.LegislativeBody')),
            ],
            options={
                'verbose_name_plural': 'Validation criterion',
            },
        ),
        migrations.AddField(
            model_name='subjectstage',
            name='upload',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='redistricting.SubjectUpload'),
        ),
        migrations.AddField(
            model_name='scoreargument',
            name='function',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='redistricting.ScoreFunction'),
        ),
        migrations.AlterUniqueTogether(
            name='region',
            unique_together=set([('name',)]),
        ),
        migrations.AddField(
            model_name='legislativelevel',
            name='subject',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='redistricting.Subject'),
        ),
        migrations.AddField(
            model_name='legislativebody',
            name='region',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='redistricting.Region'),
        ),
        migrations.AlterUniqueTogether(
            name='geolevel',
            unique_together=set([('name',)]),
        ),
        migrations.AddField(
            model_name='district',
            name='plan',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='redistricting.Plan'),
        ),
        migrations.AddField(
            model_name='contiguityoverride',
            name='connect_to_geounit',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='connect_to_geounit', to='redistricting.Geounit'),
        ),
        migrations.AddField(
            model_name='contiguityoverride',
            name='override_geounit',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='override_geounit', to='redistricting.Geounit'),
        ),
        migrations.AddField(
            model_name='computedplanscore',
            name='function',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='redistricting.ScoreFunction'),
        ),
        migrations.AddField(
            model_name='computedplanscore',
            name='plan',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='redistricting.Plan'),
        ),
        migrations.AddField(
            model_name='computeddistrictscore',
            name='district',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='redistricting.District'),
        ),
        migrations.AddField(
            model_name='computeddistrictscore',
            name='function',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='redistricting.ScoreFunction'),
        ),
        migrations.AddField(
            model_name='computedcharacteristic',
            name='district',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='redistricting.District'),
        ),
        migrations.AddField(
            model_name='computedcharacteristic',
            name='subject',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='redistricting.Subject'),
        ),
        migrations.AddField(
            model_name='characteristic',
            name='geounit',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='redistricting.Geounit'),
        ),
        migrations.AddField(
            model_name='characteristic',
            name='subject',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='redistricting.Subject'),
        ),
        migrations.AlterUniqueTogether(
            name='validationcriteria',
            unique_together=set([('name',)]),
        ),
        migrations.AlterUniqueTogether(
            name='subject',
            unique_together=set([('name',)]),
        ),
        migrations.AlterUniqueTogether(
            name='scorefunction',
            unique_together=set([('name',)]),
        ),
        migrations.AlterUniqueTogether(
            name='scoredisplay',
            unique_together=set([('name', 'title', 'owner', 'legislative_body')]),
        ),
        migrations.AlterUniqueTogether(
            name='plan',
            unique_together=set([('name', 'owner', 'legislative_body')]),
        ),
        migrations.AlterUniqueTogether(
            name='legislativelevel',
            unique_together=set([('geolevel', 'legislative_body', 'subject')]),
        ),
        migrations.AlterUniqueTogether(
            name='legislativebody',
            unique_together=set([('name',)]),
        ),
        migrations.AlterUniqueTogether(
            name='computeddistrictscore',
            unique_together=set([('function', 'district')]),
        ),
    ]
