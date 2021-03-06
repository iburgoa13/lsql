# Generated by Django 3.0.7 on 2020-06-17 18:21

import django.contrib.postgres.fields.jsonb
import django.core.serializers.json
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('judge', '0002_auto_20200617_2010'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProcProblem',
            fields=[
                ('problem_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='judge.Problem')),
                ('check_order', models.BooleanField(default=False)),
                ('solution', models.CharField(max_length=5000, validators=[django.core.validators.MinLengthValidator(1)])),
                ('proc_call', models.CharField(max_length=1000, validators=[django.core.validators.MinLengthValidator(1)])),
                ('expected_result', django.contrib.postgres.fields.jsonb.JSONField(encoder=django.core.serializers.json.DjangoJSONEncoder)),
            ],
            bases=('judge.problem',),
        ),
        migrations.RemoveField(
            model_name='functionproblem',
            name='proc_call',
        ),
        migrations.AlterField(
            model_name='collection',
            name='description_html',
            field=models.CharField(blank=True, default='', max_length=10000),
        ),
        migrations.AlterField(
            model_name='collection',
            name='name_html',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
        migrations.AlterField(
            model_name='problem',
            name='max_stmt',
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AlterField(
            model_name='problem',
            name='min_stmt',
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AlterField(
            model_name='problem',
            name='text_html',
            field=models.CharField(blank=True, default='', max_length=10000),
        ),
        migrations.AlterField(
            model_name='problem',
            name='title_html',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
    ]
