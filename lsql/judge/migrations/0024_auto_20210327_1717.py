# Generated by Django 3.1.7 on 2021-03-27 16:17

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('judge', '0023_auto_20210327_1203'),
    ]

    operations = [
        migrations.AlterField(
            model_name='obtainedachievement',
            name='obtained_date',
            field=models.DateTimeField(default=datetime.datetime(2021, 3, 27, 17, 17, 7, 733388)),
        ),
    ]
