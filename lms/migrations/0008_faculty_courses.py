"""Faculty ownership: rename LmsBatch -> LmsCourse (+ owner), LmsBatchMembership -> LmsCourseEnrollment."""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('lms', '0007_assignment_study_topic'),
    ]

    operations = [
        migrations.RenameModel(old_name='LmsBatch', new_name='LmsCourse'),
        migrations.RenameModel(old_name='LmsBatchMembership', new_name='LmsCourseEnrollment'),
        # Constraint referencing the old field name must be dropped before the rename (SQLite
        # rebuilds the table on RenameField and would otherwise try to recreate a constraint
        # against a field name that no longer exists).
        migrations.RemoveConstraint(
            model_name='lmscourseenrollment',
            name='unique_lms_batch_member',
        ),
        migrations.RenameField(model_name='lmsassignment', old_name='batch', new_name='course'),
        migrations.RenameField(model_name='lmscourseenrollment', old_name='batch', new_name='course'),
        migrations.AlterModelOptions(
            name='lmscourse',
            options={
                'ordering': ['name'],
                'verbose_name': 'LMS course',
                'verbose_name_plural': 'LMS courses',
            },
        ),
        migrations.AlterField(
            model_name='lmscourseenrollment',
            name='user',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='lms_course_enrollments',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name='lmscourseenrollment',
            name='course',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='enrollments',
                to='lms.lmscourse',
            ),
        ),
        migrations.AddConstraint(
            model_name='lmscourseenrollment',
            constraint=models.UniqueConstraint(fields=('course', 'user'), name='unique_lms_course_member'),
        ),
        migrations.AlterField(
            model_name='lmsassignment',
            name='course',
            field=models.ForeignKey(
                blank=True,
                help_text='Empty = platform-wide (superuser only). Otherwise scoped to this faculty course.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='assignments',
                to='lms.lmscourse',
            ),
        ),
        migrations.AddField(
            model_name='lmscourse',
            name='owner',
            field=models.ForeignKey(
                blank=True,
                help_text='Faculty who owns this course. Empty = platform-wide course (superuser managed).',
                limit_choices_to={'is_staff': True},
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='lms_courses_owned',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
