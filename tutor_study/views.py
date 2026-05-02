from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.html import escape
from django.utils.safestring import mark_safe

from users.models import CustomUser

from .forms import AssignmentSubmissionForm, StudyAssignmentForm, StudyMaterialForm
from .models import AssignmentSubmission, StudyAssignment, StudyMaterial
from .services import engaged_tutor_user_ids, get_tutor_profile, student_can_access_tutor


def _format_note_body(text: str):
    if not text:
        return mark_safe('')
    paras = [p.strip() for p in text.split('\n\n') if p.strip()]
    parts = []
    for p in paras:
        inner = escape(p).replace('\n', '<br>')
        parts.append(f'<p class="mb-4 text-slate-700 leading-relaxed">{inner}</p>')
    return mark_safe(''.join(parts))


def _study_seo_ctx(request):
    return {
        'seo_noindex': True,
        'canonical_url': request.build_absolute_uri(request.path),
        'seo_title': 'Study room — RankJee',
        'seo_description': 'Tutor notes and assignments for your active engagements.',
    }


def tutor_required(view_fn):
    @wraps(view_fn)
    def _inner(request, *args, **kwargs):
        if request.user.role != CustomUser.Role.TUTOR:
            messages.warning(request, 'That area is for tutors.')
            return redirect('study:student_hub')
        if not get_tutor_profile(request.user):
            messages.warning(request, 'Create your tutor listing first.')
            return redirect('hometutor:my_profile')
        return view_fn(request, *args, **kwargs)

    return _inner


@login_required
def student_hub(request):
    if request.user.role == CustomUser.Role.TUTOR:
        return redirect('study:tutor_dashboard')
    tutors = engaged_tutor_user_ids(request.user)
    materials = []
    assignments = []
    if tutors:
        materials = list(
            StudyMaterial.objects.filter(tutor_id__in=tutors, is_published=True).select_related('tutor')[:50]
        )
        assignments = list(
            StudyAssignment.objects.filter(tutor_id__in=tutors).select_related('tutor', 'skill', 'material')[:50]
        )
    ctx = {
        **_study_seo_ctx(request),
        'materials': materials,
        'assignments': assignments,
        'has_tutors': bool(tutors),
    }
    return render(request, 'tutor_study/student_hub.jinja', ctx)


@login_required
def student_material_detail(request, pk):
    if request.user.role == CustomUser.Role.TUTOR:
        return redirect('study:tutor_dashboard')
    material = get_object_or_404(StudyMaterial.objects.select_related('tutor'), pk=pk)
    if not material.is_published or not student_can_access_tutor(request.user, material.tutor_id):
        messages.error(request, 'You do not have access to these notes.')
        return redirect('study:student_hub')
    ctx = {
        **_study_seo_ctx(request),
        'material': material,
        'body_html': _format_note_body(material.body),
        'seo_title': f'{material.title} — Study room',
    }
    return render(request, 'tutor_study/student_material.jinja', ctx)


@login_required
def student_assignment_detail(request, pk):
    if request.user.role == CustomUser.Role.TUTOR:
        return redirect('study:tutor_dashboard')
    assignment = get_object_or_404(
        StudyAssignment.objects.select_related('tutor', 'skill', 'material'), pk=pk
    )
    if not student_can_access_tutor(request.user, assignment.tutor_id):
        messages.error(request, 'You do not have access to this assignment.')
        return redirect('study:student_hub')

    existing = AssignmentSubmission.objects.filter(assignment=assignment, student=request.user).first()
    if request.method == 'POST':
        form = AssignmentSubmissionForm(request.POST, instance=existing)
        if form.is_valid():
            sub = form.save(commit=False)
            sub.assignment = assignment
            sub.student = request.user
            sub.save()
            messages.success(request, 'Your Drive link was submitted.')
            return redirect('study:student_assignment', pk=assignment.pk)
    else:
        form = AssignmentSubmissionForm(instance=existing)

    ctx = {
        **_study_seo_ctx(request),
        'assignment': assignment,
        'form': form,
        'submission': existing,
        'seo_title': f'{assignment.title} — Study room',
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
        form = StudyMaterialForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tutor = request.user
            obj.save()
            messages.success(request, 'Notes saved.')
            return redirect('study:tutor_dashboard')
    else:
        form = StudyMaterialForm()
    ctx = {**_study_seo_ctx(request), 'form': form, 'seo_title': 'New notes — Tutor study'}
    return render(request, 'tutor_study/tutor_material_form.jinja', ctx)


@login_required
@tutor_required
def tutor_material_edit(request, pk):
    material = get_object_or_404(StudyMaterial, pk=pk, tutor=request.user)
    if request.method == 'POST':
        form = StudyMaterialForm(request.POST, request.FILES, instance=material)
        if form.is_valid():
            form.save()
            messages.success(request, 'Notes updated.')
            return redirect('study:tutor_dashboard')
    else:
        form = StudyMaterialForm(instance=material)
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
