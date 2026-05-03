from collections import defaultdict

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from hometutor.models import TutorEngagement, TutorProfile


def get_tutor_profile(user):
    try:
        return user.tutor_profile
    except TutorProfile.DoesNotExist:
        return None


def engaged_tutor_user_ids(student):
    """User IDs of tutors linked to this student/parent via an open engagement.

    Includes ACTIVE and PENDING_MUTUAL so notes appear once a demo engagement exists,
    not only after both parties fully confirm (CLOSED engagements excluded).
    """
    return set(
        TutorEngagement.objects.filter(
            student=student,
        )
        .exclude(status=TutorEngagement.Status.CLOSED)
        .filter(tutor_profile__user__isnull=False)
        .values_list('tutor_profile__user_id', flat=True)
    )


def student_can_access_tutor(student, tutor_user_id: int) -> bool:
    return tutor_user_id in engaged_tutor_user_ids(student)


def platform_study_material_q():
    """Materials whose owner is Django staff/superuser — shown to every logged-in student."""
    return Q(tutor__is_staff=True) | Q(tutor__is_superuser=True)


def platform_study_assignment_q():
    """Assignments created by staff/superuser tutors — shown to every logged-in student."""
    return Q(tutor__is_staff=True) | Q(tutor__is_superuser=True)


def study_material_visible_to_all_students(material) -> bool:
    t = material.tutor
    return bool(t.is_staff or t.is_superuser)


def student_can_access_study_material(student, material) -> bool:
    if not material.is_published:
        return False
    if study_material_visible_to_all_students(material):
        return True
    return student_can_access_tutor(student, material.tutor_id)


def platform_assignment_visible_to_all_students(assignment) -> bool:
    t = assignment.tutor
    return bool(t.is_staff or t.is_superuser)


def student_can_access_study_assignment(student, assignment) -> bool:
    """Engaged tutor assignments, or platform (staff/superuser) assignments for any logged-in student."""
    if platform_assignment_visible_to_all_students(assignment):
        return True
    return student_can_access_tutor(student, assignment.tutor_id)


def _tutor_display_name(user) -> str:
    name = (user.get_full_name() or '').strip()
    if name:
        return name
    if getattr(user, 'username', None):
        return user.username
    return getattr(user, 'email', None) or str(user.pk)


def _fmt_hub_date(dt) -> str:
    if not dt:
        return '—'
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    dt = timezone.localtime(dt)
    return dt.strftime('%d %b %Y')


def _sort_toc_rows(rows):
    return sorted(rows, key=lambda r: r['date_sort'], reverse=True)


def _subsection_heading(topic):
    if topic is None:
        return 'General'
    if topic.parent_id:
        return f'{topic.parent.title} › {topic.title}'
    return topic.title


def _bucket_into_subsections(main_slug, rows_with_topic_meta):
    """Split rows (each may include ``_topic``: StudyTopic | None) into chapter subsections + TOC tables."""
    groups = defaultdict(list)
    topic_objs_by_id = {}

    for r in rows_with_topic_meta:
        t = r.get('_topic')
        tid = t.pk if t else None
        if t:
            topic_objs_by_id[t.pk] = t
            if t.parent_id:
                topic_objs_by_id[t.parent.pk] = t.parent
        clean = {k: v for k, v in r.items() if k != '_topic'}
        groups[tid].append(clean)

    keys_present = list(groups.keys())
    ordered_ids = []
    if None in keys_present:
        ordered_ids.append(None)
    non_none = [k for k in keys_present if k is not None]
    topics_sorted = sorted(
        [topic_objs_by_id[k] for k in non_none if k in topic_objs_by_id],
        key=lambda t: (
            (t.parent or t).sort_order,
            (t.parent or t).title.lower(),
            1 if t.parent_id else 0,
            t.sort_order,
            t.title.lower(),
        ),
    )
    ordered_ids.extend(t.pk for t in topics_sorted)

    subsections = []
    for tid in ordered_ids:
        topic = topic_objs_by_id.get(tid) if tid is not None else None
        anchor = f'{main_slug}-sub-{tid if tid is not None else "general"}'
        subsections.append(
            {
                'title': _subsection_heading(topic),
                'anchor': anchor,
                'rows': _sort_toc_rows(groups[tid]),
            }
        )
    return subsections


def build_student_study_topics(
    materials,
    assignments,
    *,
    submitted_assignment_ids: set,
    now=None,
    material_url_name='study:student_material',
    assignment_url_name='study:student_assignment',
):
    """RankJee bucket + one bucket per tutor; each bucket has chapter subsections with TOC rows."""
    now = now or timezone.now()

    platform_rows = []
    by_tutor = defaultdict(list)
    tutor_users = {}

    for m in materials:
        tutor_users[m.tutor_id] = m.tutor
        row_date = m.updated_at
        row = {
            'name': m.title,
            'date_sort': row_date,
            'date_label': _fmt_hub_date(row_date),
            'type_label': 'Material',
            'href': reverse(material_url_name, kwargs={'pk': m.pk}),
            '_topic': m.study_topic,
        }
        if study_material_visible_to_all_students(m):
            platform_rows.append(row)
        else:
            by_tutor[m.tutor_id].append(row)

    for a in assignments:
        tutor_users[a.tutor_id] = a.tutor
        is_submitted = a.pk in submitted_assignment_ids
        due = a.due_at
        overdue = False
        if due and not is_submitted:
            due_cmp = due
            if timezone.is_naive(due_cmp):
                due_cmp = timezone.make_aware(due_cmp, timezone.get_current_timezone())
            overdue = now > due_cmp
        assign_date = due or a.created_at
        type_label = 'Assignment'
        if is_submitted:
            type_label = 'Assignment · submitted'
        elif overdue:
            type_label = 'Assignment · overdue'

        by_tutor[a.tutor_id].append(
            {
                'name': a.title,
                'date_sort': assign_date,
                'date_label': ('Due ' + _fmt_hub_date(due)) if due else ('Assigned ' + _fmt_hub_date(a.created_at)),
                'type_label': type_label,
                'href': reverse(assignment_url_name, kwargs={'pk': a.pk}),
                '_topic': a.study_topic,
            }
        )
        if a.skill_id:
            skill_name = (a.skill.name if a.skill else '') or 'Quiz'
            by_tutor[a.tutor_id].append(
                {
                    'name': f'{a.title} · {skill_name}',
                    'date_sort': a.updated_at or assign_date,
                    'date_label': _fmt_hub_date(a.updated_at or assign_date),
                    'type_label': 'Exam',
                    'href': reverse('assessment:take_test', kwargs={'skill_id': a.skill_id}),
                    '_topic': a.study_topic,
                }
            )

    topics = []
    if platform_rows:
        topics.append(
            {
                'title': 'RankJee',
                'slug': 'rankjee',
                'subsections': _bucket_into_subsections('rankjee', platform_rows),
            }
        )

    for tid in sorted(by_tutor.keys(), key=lambda i: _tutor_display_name(tutor_users[i]).lower()):
        bucket = by_tutor[tid]
        if not bucket:
            continue
        slug = f'tutor-{tid}'
        topics.append(
            {
                'title': _tutor_display_name(tutor_users[tid]),
                'slug': slug,
                'subsections': _bucket_into_subsections(slug, bucket),
            }
        )

    return topics


def topic_in_subtree(item_topic, root_pk):
    """True if content topic matches subtree rooted at root_pk.

    root_pk ``None`` means uncategorized (no ``study_topic``).
    """
    if root_pk is None:
        return item_topic is None
    if item_topic is None:
        return False
    cur = item_topic
    while cur is not None:
        if cur.pk == root_pk:
            return True
        cur = cur.parent
    return False


def collect_topics_from_items(materials, assignments):
    topics_by_id = {}
    has_general = False

    def add_chain(t):
        while t is not None:
            topics_by_id[t.pk] = t
            t = t.parent

    for m in materials:
        if m.study_topic_id:
            add_chain(m.study_topic)
        else:
            has_general = True
    for a in assignments:
        if a.study_topic_id:
            add_chain(a.study_topic)
        else:
            has_general = True
    return topics_by_id, has_general


def roots_for_nav(topics_by_id):
    ids = set(topics_by_id.keys())
    roots = []
    seen = set()
    for t in topics_by_id.values():
        if t.parent_id is None or t.parent_id not in ids:
            if t.pk not in seen:
                seen.add(t.pk)
                roots.append(t)
    return sorted(roots, key=lambda t: (t.sort_order, t.title.lower()))


def count_items_in_topic(materials, assignments, root_pk):
    """Returns (n_materials, n_assignments, n_exams_unique_skill)."""
    nm = sum(1 for m in materials if topic_in_subtree(m.study_topic, root_pk))
    na = sum(1 for a in assignments if topic_in_subtree(a.study_topic, root_pk))
    seen_skill = set()
    ne = 0
    for a in assignments:
        if not topic_in_subtree(a.study_topic, root_pk):
            continue
        if a.skill_id and a.skill_id not in seen_skill:
            seen_skill.add(a.skill_id)
            ne += 1
    return nm, na, ne


def build_lms_flat_nav(
    materials,
    assignments,
    *,
    hub_url,
    topic_url_name,
    topic_general_url_name,
):
    topics_by_id, has_general = collect_topics_from_items(materials, assignments)
    rows = [
        {
            'kind': 'overview',
            'label': 'Overview',
            'href': hub_url,
            'depth': 0,
        }
    ]
    if has_general:
        rows.append(
            {
                'kind': 'topic',
                'label': 'General',
                'href': reverse(topic_general_url_name),
                'topic_pk': None,
                'depth': 0,
            }
        )

    def ordered_children(parent_id):
        return sorted(
            [t for t in topics_by_id.values() if t.parent_id == parent_id],
            key=lambda t: (t.sort_order, t.title.lower()),
        )

    def walk(parent_id, depth):
        for ch in ordered_children(parent_id):
            rows.append(
                {
                    'kind': 'topic',
                    'label': ch.title,
                    'href': reverse(topic_url_name, kwargs={'topic_pk': ch.pk}),
                    'topic_pk': ch.pk,
                    'depth': depth,
                }
            )
            walk(ch.pk, depth + 1)

    for r in roots_for_nav(topics_by_id):
        rows.append(
            {
                'kind': 'topic',
                'label': r.title,
                'href': reverse(topic_url_name, kwargs={'topic_pk': r.pk}),
                'topic_pk': r.pk,
                'depth': 0,
            }
        )
        walk(r.pk, 1)

    for row in rows:
        if row['kind'] == 'topic':
            nm, na, ne = count_items_in_topic(materials, assignments, row['topic_pk'])
            row['count_materials'] = nm
            row['count_assignments'] = na
            row['count_exams'] = ne

    return rows


def format_assignment_card_labels(a, submitted_ids, now):
    now = now or timezone.now()
    is_submitted = a.pk in submitted_ids
    due = a.due_at
    overdue = False
    if due and not is_submitted:
        due_cmp = due
        if timezone.is_naive(due_cmp):
            due_cmp = timezone.make_aware(due_cmp, timezone.get_current_timezone())
        overdue = now > due_cmp
    subtitle = ('Due ' + _fmt_hub_date(due)) if due else ('Assigned ' + _fmt_hub_date(a.created_at))
    badge = 'Assignment'
    if is_submitted:
        badge = 'Submitted'
    elif overdue:
        badge = 'Overdue'
    return subtitle, badge


def build_lms_topic_page_cards(
    materials,
    assignments,
    submitted_assignment_ids,
    *,
    now,
    root_topic_pk,
    material_url_name,
    assignment_url_name,
):
    """Cards for one topic workspace (materials / assignments / exams)."""
    now = now or timezone.now()
    mats = []
    mat_objs = [m for m in materials if topic_in_subtree(m.study_topic, root_topic_pk)]
    mat_objs.sort(key=lambda m: m.updated_at, reverse=True)
    for m in mat_objs:
        mats.append(
            {
                'kind': 'material',
                'title': m.title,
                'subtitle': _fmt_hub_date(m.updated_at),
                'href': reverse(material_url_name, kwargs={'pk': m.pk}),
                'source': (
                    'RankJee'
                    if study_material_visible_to_all_students(m)
                    else _tutor_display_name(m.tutor)
                ),
                'has_attachment': bool(m.attachment),
            }
        )

    assigns = []
    exams = []
    seen_skill = set()
    assign_objs = [a for a in assignments if topic_in_subtree(a.study_topic, root_topic_pk)]

    def _assign_sort_key(a):
        base = a.due_at or a.created_at
        if base is None:
            return timezone.now()
        if timezone.is_naive(base):
            return timezone.make_aware(base, timezone.get_current_timezone())
        return base

    assign_objs.sort(key=_assign_sort_key)
    for a in assign_objs:
        subtitle, badge = format_assignment_card_labels(
            a, submitted_assignment_ids, now
        )
        assigns.append(
            {
                'kind': 'assignment',
                'title': a.title,
                'subtitle': subtitle,
                'badge': badge,
                'href': reverse(assignment_url_name, kwargs={'pk': a.pk}),
                'source': _tutor_display_name(a.tutor),
            }
        )
        if a.skill_id and a.skill_id not in seen_skill:
            seen_skill.add(a.skill_id)
            skill_title = (a.skill.name if a.skill else '') or 'Practice quiz'
            exams.append(
                {
                    'kind': 'exam',
                    'title': skill_title,
                    'subtitle': f'Practice · {_tutor_display_name(a.tutor)}',
                    'href': reverse('assessment:take_test', kwargs={'skill_id': a.skill_id}),
                    'source': _tutor_display_name(a.tutor),
                }
            )
    exams.sort(key=lambda x: x['title'].lower())
    return {'materials': mats, 'assignments': assigns, 'exams': exams}


def topic_breadcrumb_labels(topic):
    if topic is None:
        return ['General']
    chain = []
    cur = topic
    while cur is not None:
        chain.append(cur.title)
        cur = cur.parent
    return list(reversed(chain))
