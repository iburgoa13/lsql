# Generated by Django 3.0.7 on 2020-07-20 13:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('judge', '0013_collection_zipfile'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='collection',
            name='zipfile',
        ),
        migrations.AlterField(
            model_name='problem',
            name='create_sql',
            field=models.CharField(blank=True, default=None, max_length=20000),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='problem',
            name='insert_sql',
            field=models.CharField(blank=True, default='', max_length=20000),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='problem',
            name='text_html',
            field=models.CharField(max_length=10000),
        ),
        migrations.AlterField(
            model_name='problem',
            name='title_html',
            field=models.CharField(max_length=200),
        ),
    ]
