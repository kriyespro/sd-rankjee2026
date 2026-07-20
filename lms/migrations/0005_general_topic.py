from django.db import migrations


def create_general_topic(apps, schema_editor):
    LmsTopic = apps.get_model('lms', 'LmsTopic')
    LmsAssignment = apps.get_model('lms', 'LmsAssignment')
    topic, _ = LmsTopic.objects.get_or_create(
        slug='general',
        defaults={
            'title': 'General',
            'description': 'Default topic for assignments without a specific category.',
        },
    )
    LmsAssignment.objects.filter(topic__isnull=True).update(topic=topic)


class Migration(migrations.Migration):

    dependencies = [
        ('lms', '0004_lmstopic_alter_lmsassignment_options_and_more'),
    ]

    operations = [
        migrations.RunPython(create_general_topic, migrations.RunPython.noop),
    ]
