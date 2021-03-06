# Generated by Django 3.2 on 2021-04-20 09:11

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('judge', '0029_numsolvedtypeachievementdefinition'),
    ]

    operations = [
        migrations.CreateModel(
            name='NumSubmissionsProblemsAchievementDefinition',
            fields=[
                ('achievementdefinition_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='judge.achievementdefinition')),
                ('num_submissions', models.PositiveIntegerField(default=1)),
                ('num_problems', models.PositiveIntegerField(default=1)),
            ],
            bases=('judge.achievementdefinition', models.Model),
        ),
    ]
