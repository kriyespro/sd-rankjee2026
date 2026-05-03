import json
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape
from django.utils.safestring import mark_safe

from users.models import CustomUser

from .forms import AssignmentSubmissionForm, StudyAssignmentForm, StudyMaterialForm
from .models import AssignmentSubmission, StudyAssignment, StudyMaterial, StudyTopic
from .services import (
    build_lms_flat_nav,
    build_lms_topic_page_cards,
    engaged_tutor_user_ids,
    platform_study_assignment_q,
    get_tutor_profile,
    platform_study_material_q,
    student_can_access_study_assignment,
    student_can_access_study_material,
    student_can_access_tutor,
    topic_breadcrumb_labels,
)

STUDY_URLS_STANDALONE = {
    'hub': 'study:student_hub',
    'material': 'study:student_material',
    'assignment': 'study:student_assignment',
    'topic': 'study:student_topic',
    'topic_general': 'study:student_topic_general',
}
STUDY_URLS_DASHBOARD = {
    'hub': 'dashboard:study',
    'material': 'dashboard:study_material',
    'assignment': 'dashboard:study_assignment',
    'topic': 'dashboard:study_topic',
    'topic_general': 'dashboard:study_topic_general',
}


def _format_note_body(text: str):
    if not text:
        return mark_safe('')
    paras = [p.strip() for p in text.split('\n\n') if p.strip()]
    parts = []
    for p in paras:
        inner = escape(p).replace('\n', '<br>')
        parts.append(f'<p class="study-prose">{inner}</p>')
    return mark_safe(''.join(parts))


def _study_seo_ctx(request):
    return {
        'seo_noindex': True,
        'canonical_url': request.build_absolute_uri(request.path),
        'seo_title': 'Study room — RankJee',
        'seo_description': 'Study hub — materials, assignments, and exams by topic.',
    }


def tutor_required(view_fn):
    @wraps(view_fn)
    def _inner(request, *args, **kwargs):
        if request.user.role != CustomUser.Role.TUTOR:
            messages.warning(request, 'That area is for tutors.')
            return redirect('dashboard:study')
        if not get_tutor_profile(request.user):
            messages.warning(request, 'Create your tutor listing first.')
            return redirect('hometutor:my_profile')
        return view_fn(request, *args, **kwargs)

    return _inner


def _student_study_data(request):
    tutors = engaged_tutor_user_ids(request.user)
    materials_visibility = (
        Q(tutor_id__in=tutors) | platform_study_material_q()
        if tutors
        else platform_study_material_q()
    )
    materials = list(
        StudyMaterial.objects.filter(is_published=True)
        .filter(materials_visibility)
        .select_related('tutor', 'study_topic', 'study_topic__parent')
        .distinct()
        .order_by('-updated_at')[:80]
    )
    assign_q = platform_study_assignment_q()
    if tutors:
        assign_q = Q(tutor_id__in=tutors) | platform_study_assignment_q()
    assignments = list(
        StudyAssignment.objects.filter(assign_q)
        .select_related('tutor', 'skill', 'material', 'study_topic', 'study_topic__parent')
        .distinct()
        .order_by('-updated_at')[:80]
    )
    submitted_ids = set()
    if assignments:
        aid = [a.pk for a in assignments]
        submitted_ids = set(
            AssignmentSubmission.objects.filter(
                student=request.user, assignment_id__in=aid
            ).values_list('assignment_id', flat=True)
        )
    return {
        'tutors': tutors,
        'materials': materials,
        'assignments': assignments,
        'submitted_ids': submitted_ids,
    }


def _study_lms_shell(
    request,
    study_urls,
    *,
    active_nav,
    topic_pk=None,
    highlight_topic_pk=None,
    study_data=None,
):
    data = study_data or _student_study_data(request)
    hub_url = reverse(study_urls['hub'])
    study_nav_items = build_lms_flat_nav(
        data['materials'],
        data['assignments'],
        hub_url=hub_url,
        topic_url_name=study_urls['topic'],
        topic_general_url_name=study_urls['topic_general'],
    )
    dashboard_embedded = study_urls['hub'] == 'dashboard:study'
    active_topic_for_nav = topic_pk if active_nav == 'topic' else None
    return {
        'tutors': data['tutors'],
        'materials': data['materials'],
        'assignments': data['assignments'],
        'submitted_ids': data['submitted_ids'],
        'study_nav_items': study_nav_items,
        'lms_active_nav': active_nav,
        'lms_active_topic_pk': active_topic_for_nav,
        'lms_highlight_topic_pk': highlight_topic_pk,
        'study_route_hub': study_urls['hub'],
        'study_route_material': study_urls['material'],
        'study_route_assignment': study_urls['assignment'],
        'study_route_topic': study_urls['topic'],
        'study_route_topic_general': study_urls['topic_general'],
        'dashboard_study_embedded': dashboard_embedded,
        'has_tutors': bool(data['tutors']),
        'engaged_tutor_count': len(data['tutors']),
    }


@login_required
def student_hub(request, study_urls=None):
    if request.user.role == CustomUser.Role.TUTOR:
        return redirect('study:tutor_dashboard')
    urls = study_urls or STUDY_URLS_STANDALONE
    if study_urls is None and request.user.role in (
        CustomUser.Role.STUDENT,
        CustomUser.Role.PARENT,
    ):
        return redirect('dashboard:study')
    bundle = _student_study_data(request)
    show_study_empty = not bundle['materials'] and not bundle['assignments']
    seen_skill = set()
    n_exams = 0
    for a in bundle['assignments']:
        if a.skill_id and a.skill_id not in seen_skill:
            seen_skill.add(a.skill_id)
            n_exams += 1
    shell = _study_lms_shell(
        request,
        urls,
        active_nav='hub',
        study_data=bundle,
    )
    ctx = {
        **_study_seo_ctx(request),
        **shell,
        'show_study_empty': show_study_empty,
        'study_summary_materials': len(bundle['materials']),
        'study_summary_assignments': len(bundle['assignments']),
        'study_summary_exams': n_exams,
    }
    return render(request, 'tutor_study/student_hub.jinja', ctx)


def _render_student_topic_page(request, topic_pk, urls):
    if request.user.role == CustomUser.Role.TUTOR:
        return redirect('study:tutor_dashboard')
    merged_urls = urls or STUDY_URLS_STANDALONE
    if urls is None and request.user.role in (
        CustomUser.Role.STUDENT,
        CustomUser.Role.PARENT,
    ):
        if topic_pk is None:
            return redirect(STUDY_URLS_DASHBOARD['topic_general'])
        return redirect(STUDY_URLS_DASHBOARD['topic'], topic_pk=topic_pk)

    bundle = _student_study_data(request)
    topic_obj = None
    if topic_pk is not None:
        topic_obj = get_object_or_404(StudyTopic, pk=topic_pk)

    cards = build_lms_topic_page_cards(
        bundle['materials'],
        bundle['assignments'],
        bundle['submitted_ids'],
        now=timezone.now(),
        root_topic_pk=topic_pk,
        material_url_name=merged_urls['material'],
        assignment_url_name=merged_urls['assignment'],
    )
    labels = topic_breadcrumb_labels(topic_obj)
    shell = _study_lms_shell(
        request,
        merged_urls,
        active_nav='topic',
        topic_pk=topic_pk,
        highlight_topic_pk=topic_pk,
        study_data=bundle,
    )
    ctx = {
        **_study_seo_ctx(request),
        **shell,
        'lms_topic_pk': topic_pk,
        'lms_topic_title': labels[-1] if labels else 'Topic',
        'lms_topic_trail': labels,
        'topic_cards': cards,
        'seo_title': f'{labels[-1]} — Study',
        'seo_description': 'Materials, assignments, and practice for this topic.',
    }
    return render(request, 'tutor_study/student_topic.jinja', ctx)


@login_required
def student_topic_workspace_general(request, study_urls=None):
    return _render_student_topic_page(request, None, study_urls)


@login_required
def student_topic_workspace(request, topic_pk, study_urls=None):
    return _render_student_topic_page(request, topic_pk, study_urls)


@login_required
def student_material_detail(request, pk, study_urls=None):
    urls = study_urls or STUDY_URLS_STANDALONE
    if request.user.role == CustomUser.Role.TUTOR:
        return redirect('study:tutor_dashboard')
    material = get_object_or_404(
        StudyMaterial.objects.select_related('tutor', 'study_topic', 'study_topic__parent'), pk=pk
    )
    if not student_can_access_study_material(request.user, material):
        messages.error(request, 'You do not have access to these notes.')
        return redirect(reverse(urls['hub']))
    bundle = _student_study_data(request)
    shell = _study_lms_shell(
        request,
        urls,
        active_nav='material',
        highlight_topic_pk=material.study_topic_id,
        study_data=bundle,
    )
    ctx = {
        **_study_seo_ctx(request),
        **shell,
        'material': material,
        'body_html': _format_note_body(material.body),
        'material_plain_json': json.dumps(material.body or ''),
        'seo_title': f'{material.title} — Study room',
    }
    return render(request, 'tutor_study/student_material.jinja', ctx)


@login_required
def student_assignment_detail(request, pk, study_urls=None):
    urls = study_urls or STUDY_URLS_STANDALONE
    if request.user.role == CustomUser.Role.TUTOR:
        return redirect('study:tutor_dashboard')
    assignment = get_object_or_404(
        StudyAssignment.objects.select_related(
            'tutor', 'skill', 'material', 'study_topic', 'study_topic__parent'
        ),
        pk=pk,
    )
    if not student_can_access_study_assignment(request.user, assignment):
        messages.error(request, 'You do not have access to this assignment.')
        return redirect(reverse(urls['hub']))

    existing = AssignmentSubmission.objects.filter(assignment=assignment, student=request.user).first()
    if request.method == 'POST':
        form = AssignmentSubmissionForm(request.POST, instance=existing)
        if form.is_valid():
            sub = form.save(commit=False)
            sub.assignment = assignment
            sub.student = request.user
            sub.save()
            messages.success(request, 'Your Drive link was submitted.')
            return redirect(reverse(urls['assignment'], kwargs={'pk': assignment.pk}))
    else:
        form = AssignmentSubmissionForm(instance=existing)

    bundle = _student_study_data(request)
    shell = _study_lms_shell(
        request,
        urls,
        active_nav='assignment',
        highlight_topic_pk=assignment.study_topic_id,
        study_data=bundle,
    )
    cid = getattr(settings, 'GOOGLE_OAUTH_CLIENT_ID', '').strip()
    pkey = getattr(settings, 'GOOGLE_PICKER_API_KEY', '').strip()
    picker_on = bool(cid and pkey)
    ctx = {
        **_study_seo_ctx(request),
        **shell,
        'assignment': assignment,
        'form': form,
        'submission': existing,
        'seo_title': f'{assignment.title} — Study room',
        'google_drive_picker_enabled': picker_on,
        'google_picker_client_id_json': json.dumps(cid),
        'google_picker_api_key_json': json.dumps(pkey),
    }
    return render(request, 'tutor_study/student_assignment.jinja', ctx)


@login_required
@tutor_required
def tutor_dashboard(request):
    materials = StudyMaterial.objects.filter(tutor=request.user)
    assignments = StudyAssignment.objects.filter(tutor=request.user).annotate(sub_count=Count('submissions'))
    ctx = {
        **_study_seo_ctx(request),
        'materials': materials,
        'assignments': assignments,
        'seo_title': 'Tutor study room — RankJee',
    }
    return render(request, 'tutor_study/tutor_dashboard.jinja', ctx)


@login_required
@tutor_required
def tutor_material_create(request):
    if request.method == 'POST':
        form = StudyMaterialForm(request.POST, request.FILES, tutor_user=request.user)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tutor = request.user
            obj.save()
            messages.success(request, 'Notes saved.')
            return redirect('study:tutor_dashboard')
    else:
        form = StudyMaterialForm(tutor_user=request.user)
    ctx = {**_study_seo_ctx(request), 'form': form, 'seo_title': 'New notes — Tutor study'}
    return render(request, 'tutor_study/tutor_material_form.jinja', ctx)


@login_required
@tutor_required
def tutor_material_edit(request, pk):
    material = get_object_or_404(StudyMaterial, pk=pk, tutor=request.user)
    if request.method == 'POST':
        form = StudyMaterialForm(request.POST, request.FILES, instance=material, tutor_user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Notes updated.')
            return redirect('study:tutor_dashboard')
    else:
        form = StudyMaterialForm(instance=material, tutor_user=request.user)
    ctx = {
        **_study_seo_ctx(request),
        'form': form,
        'material': material,
        'seo_title': f'Edit — {material.title}',
    }
    return render(request, 'tutor_study/tutor_material_form.jinja', ctx)


@login_required
@tutor_required
def tutor_assignment_create(request):
    if request.method == 'POST':
        form = StudyAssignmentForm(request.POST, tutor=request.user)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tutor = request.user
            if obj.material_id and obj.material.tutor_id != request.user.id:
                messages.error(request, 'Invalid material.')
                return redirect('study:tutor_assignment_create')
            obj.save()
            messages.success(request, 'Assignment created.')
            return redirect('study:tutor_dashboard')
    else:
        form = StudyAssignmentForm(tutor=request.user)
    ctx = {**_study_seo_ctx(request), 'form': form, 'seo_title': 'New assignment — Tutor study'}
    return render(request, 'tutor_study/tutor_assignment_form.jinja', ctx)


@login_required
@tutor_required
def tutor_assignment_edit(request, pk):
    assignment = get_object_or_404(StudyAssignment, pk=pk, tutor=request.user)
    if request.method == 'POST':
        form = StudyAssignmentForm(request.POST, tutor=request.user, instance=assignment)
        if form.is_valid():
            obj = form.save(commit=False)
            if obj.material_id and obj.material.tutor_id != request.user.id:
                messages.error(request, 'Invalid material.')
                return redirect('study:tutor_assignment_edit', pk=pk)
            obj.save()
            messages.success(request, 'Assignment updated.')
            return redirect('study:tutor_dashboard')
    else:
        form = StudyAssignmentForm(tutor=request.user, instance=assignment)
    ctx = {
        **_study_seo_ctx(request),
        'form': form,
        'assignment': assignment,
        'seo_title': f'Edit — {assignment.title}',
    }
    return render(request, 'tutor_study/tutor_assignment_form.jinja', ctx)


@login_required
@tutor_required
def tutor_assignment_submissions(request, pk):
    assignment = get_object_or_404(StudyAssignment, pk=pk, tutor=request.user)
    submissions = assignment.submissions.select_related('student').order_by('-submitted_at')
    ctx = {
        **_study_seo_ctx(request),
        'assignment': assignment,
        'submissions': submissions,
        'seo_title': f'Submissions — {assignment.title}',
    }
    return render(request, 'tutor_study/tutor_submissions.jinja', ctx)
