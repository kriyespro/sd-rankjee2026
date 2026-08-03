from django.db import migrations


def _ordinal(n):
    if 11 <= n % 100 <= 13:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return f'{n}{suffix}'


def seed_and_backfill(apps, schema_editor):
    SkillPath = apps.get_model('assessment', 'SkillPath')
    CustomUser = apps.get_model('users', 'CustomUser')

    # Existing non-class paths sort after all 12 school classes (was level_order 1-3,
    # colliding with the class paths added below).
    SkillPath.objects.filter(name='SSC & Govt Exams').update(level_order=13)
    SkillPath.objects.filter(name='Finance & Banking').update(level_order=14)
    SkillPath.objects.filter(name='Digital Skills Mastery').update(level_order=15)

    class_path_by_number = {}
    for n in range(1, 13):
        name = f'Class {_ordinal(n)}'
        path, _ = SkillPath.objects.get_or_create(
            name=name,
            defaults={'level_order': n, 'is_active': True},
        )
        if path.level_order != n or not path.is_active:
            path.level_order = n
            path.is_active = True
            path.save(update_fields=['level_order', 'is_active'])
        class_path_by_number[n] = path

    # Give existing students the new `level` FK for free from their old class_level number,
    # so nobody has to redo onboarding just because this field now exists.
    for user in CustomUser.objects.filter(role='STUDENT', level__isnull=True, class_level__isnull=False):
        path = class_path_by_number.get(user.class_level)
        if path:
            user.level_id = path.id
            user.save(update_fields=['level'])


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0021_customuser_level'),
    ]

    operations = [
        migrations.RunPython(seed_and_backfill, migrations.RunPython.noop),
    ]
