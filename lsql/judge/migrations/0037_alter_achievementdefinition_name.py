# Generated by Django 3.2 on 2021-05-06 19:12

import django.core.serializers.json
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('judge', '0036_auto_20210506_2109'),
    ]

    operations = [
        migrations.AlterField(
            model_name='achievementdefinition',
            name='name',
            field=models.JSONField(blank=True, encoder=django.core.serializers.json.DjangoJSONEncoder, null=True),
        ),
    ]
