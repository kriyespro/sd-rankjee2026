import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_http_methods, require_POST

from .forms import (
    LmsAssignmentForm,
    LmsBatchForm,
    LmsBatchMemberForm,
    LmsCommentForm,
    LmsReviewForm,
    LmsSubmissionForm,
    LmsTopicForm,
)
from .models import LmsAssignment, LmsBatch, LmsBatchMembership, LmsReaction, LmsSubmission, LmsTopic
from . import services


def _require_lms_access(user):
    if not services.is_lms_student(user) and not services.is_lms_staff(user):
        return False
    return True


@login_required
def home(request):
    if not _require_lms_access(request.user):
        messages.error(request, 'LMS is for students and staff.')
        return redirect('dashboard:index')

    if services.is_lms_staff(request.user):
        services.attach_orphan_assignments_to_general()

    assignments = list(services.assignments_for_user(request.user)[:50])
    topics = services.topics_for_user(request.user)
    recent = (
        LmsSubmission.objects.filter(assignment__in=[a.pk for a in assignments] or [0])
        .select_related('student', 'assignment')
        .order_by('-is_pinned', '-updated_at')[:12]
    )
    return render(
        request,
        'lms/home.jinja',
        {
            'topics': topics,
            'recent_submissions': recent,
            'is_staff_lms': services.is_lms_staff(request.user),
        },
    )


@login_required
@require_http_methods(['GET', 'POST'])
def assignment_create(request):
    if not services.is_lms_staff(request.user):
        return HttpResponseForbidden('Staff only.')
    if request.method == 'POST':
        form = LmsAssignmentForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.created_by = request.user
            if not obj.topic_id:
                obj.topic = services.ensure_general_topic()
            obj.save()
            if obj.is_published:
                services.notify_new_assignment(obj)
            messages.success(request, f'Assignment “{obj.title}” created.')
            return redirect('lms:assignment_detail', pk=obj.pk)
    else:
        initial = {}
        topic_id = request.GET.get('topic')
        if topic_id and LmsTopic.objects.filter(pk=topic_id).exists():
            initial['topic'] = topic_id
        form = LmsAssignmentForm(initial=initial)
    return render(
        request,
        'lms/assignment_form.jinja',
        {'form': form, 'is_staff_lms': True, 'is_edit': False},
    )


@login_required
@require_http_methods(['GET', 'POST'])
def assignment_edit(request, pk):
    if not services.is_lms_staff(request.user):
        return HttpResponseForbidden('Staff only.')
    assignment = get_object_or_404(LmsAssignment, pk=pk)
    if request.method == 'POST':
        form = LmsAssignmentForm(request.POST, instance=assignment)
        if form.is_valid():
            was_published = assignment.is_published
            obj = form.save(commit=False)
            if not obj.topic_id:
                obj.topic = services.ensure_general_topic()
            obj.save()
            if obj.is_published and not was_published:
                services.notify_new_assignment(obj)
            messages.success(request, f'Assignment “{obj.title}” updated.')
            return redirect('lms:assignment_detail', pk=obj.pk)
    else:
        form = LmsAssignmentForm(instance=assignment)
    return render(
        request,
        'lms/assignment_form.jinja',
        {
            'form': form,
            'is_staff_lms': True,
            'is_edit': True,
            'assignment': assignment,
        },
    )


@login_required
@require_http_methods(['GET', 'POST'])
def topic_create(request):
    if not services.is_lms_staff(request.user):
        return HttpResponseForbidden('Staff only.')
    form = LmsTopicForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        topic = form.save()
        messages.success(request, f'Topic “{topic.title}” created.')
        return redirect('lms:topic_detail', pk=topic.pk)
    return render(
        request,
        'lms/topic_form.jinja',
        {'form': form, 'is_staff_lms': True, 'is_edit': False},
    )


@login_required
@require_http_methods(['GET', 'POST'])
def topic_edit(request, pk):
    if not services.is_lms_staff(request.user):
        return HttpResponseForbidden('Staff only.')
    topic = get_object_or_404(LmsTopic, pk=pk)
    form = LmsTopicForm(request.POST or None, instance=topic)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Topic “{topic.title}” updated.')
        return redirect('lms:topic_detail', pk=topic.pk)
    return render(
        request,
        'lms/topic_form.jinja',
        {'form': form, 'topic': topic, 'is_staff_lms': True, 'is_edit': True},
    )


@login_required
def topic_detail(request, pk):
    topic = get_object_or_404(LmsTopic, pk=pk)
    assignments = [
        assignment
        for assignment in services.assignments_for_user(request.user)
        if assignment.topic_id == topic.pk
    ]
    if not assignments and not services.is_lms_staff(request.user):
        raise Http404()
    return render(
        request,
        'lms/topic_detail.jinja',
        {
            'topic': topic,
            'assignments': assignments,
            'is_staff_lms': services.is_lms_staff(request.user),
        },
    )


@login_required
@require_http_methods(['GET', 'POST'])
def assignment_detail(request, pk):
    assignment = get_object_or_404(LmsAssignment.objects.select_related('topic', 'batch'), pk=pk)
    if not services.can_view_assignment(request.user, assignment):
        raise Http404()

    is_staff = services.is_lms_staff(request.user)
    my_sub = LmsSubmission.objects.filter(assignment=assignment, student=request.user).first()
    can_submit = (
        getattr(request.user, 'role', None) == 'STUDENT'
        and services.can_view_assignment(request.user, assignment)
    )
    can_edit = bool(my_sub and services.can_edit_submission(request.user, my_sub))
    # New submit allowed if student, no submission yet, and before deadline (or no deadline)
    from django.utils import timezone

    past_due = bool(assignment.due_at and timezone.now() > assignment.due_at)
    can_create = can_submit and not my_sub and not past_due
    show_submit_form = can_create or can_edit

    submit_form = None
    if request.method == 'POST' and request.POST.get('action') == 'submit' and show_submit_form:
        submit_form = LmsSubmissionForm(
            request.POST,
            instance=my_sub,
        )
        if submit_form.is_valid():
            sub = my_sub or LmsSubmission(
                assignment=assignment,
                student=request.user,
                status=LmsSubmission.Status.SUBMITTED,
            )
            services.save_submission_with_urls(
                sub,
                caption=submit_form.cleaned_data.get('caption', ''),
                url_items=submit_form.cleaned_data['url_items'],
            )
            messages.success(request, 'Submission saved — classmates can see it on the feed.')
            return redirect('lms:assignment_detail', pk=pk)
    elif show_submit_form:
        submit_form = LmsSubmissionForm(instance=my_sub)

    if request.method == 'POST' and request.POST.get('action') == 'review' and is_staff:
        sub_id = request.POST.get('submission_id')
        sub = get_object_or_404(LmsSubmission, pk=sub_id, assignment=assignment)
        review_form = LmsReviewForm(request.POST)
        if review_form.is_valid():
            services.review_submission(
                sub,
                marks=review_form.cleaned_data.get('marks'),
                remark=review_form.cleaned_data.get('remark') or '',
                status=review_form.cleaned_data.get('status'),
                is_pinned=review_form.cleaned_data.get('is_pinned'),
            )
            messages.success(request, f'Review saved for {sub.student.get_username()}.')
            return redirect('lms:assignment_detail', pk=pk)

    feed = list(services.submissions_feed(assignment))
    # Attach per-user reaction + review form for staff
    my_reactions = {}
    if request.user.is_authenticated:
        for r in LmsReaction.objects.filter(
            submission_id__in=[s.pk for s in feed],
            user=request.user,
        ):
            my_reactions[r.submission_id] = r.value

    for s in feed:
        s.user_reaction = my_reactions.get(s.pk)
        s.link_rows = services.submission_link_rows(s)
        if is_staff:
            s.review_form = LmsReviewForm(
                initial={
                    'marks': s.marks,
                    'remark': s.remark,
                    'status': s.status,
                    'is_pinned': s.is_pinned,
                }
            )

    return render(
        request,
        'lms/assignment_detail.jinja',
        {
            'assignment': assignment,
            'feed': feed,
            'submit_form': submit_form,
            'show_submit_form': show_submit_form,
            'my_sub': my_sub,
            'past_due': past_due,
            'is_staff_lms': is_staff,
            'comment_form': LmsCommentForm(),
            'url_rows_json': mark_safe(json.dumps(submit_form.url_rows if submit_form else [])),
        },
    )


@login_required
@require_POST
def react(request, pk):
    sub = get_object_or_404(LmsSubmission.objects.select_related('assignment'), pk=pk)
    if not services.can_view_assignment(request.user, sub.assignment):
        raise Http404()
    value = (request.POST.get('value') or '').upper()
    if value not in LmsReaction.Value.values:
        return HttpResponseForbidden('Invalid reaction.')
    services.set_reaction(sub, request.user, value)
    # Refresh annotated counts
    sub = services.submissions_feed(sub.assignment).filter(pk=pk).first() or sub
    user_reaction = (
        LmsReaction.objects.filter(submission=sub, user=request.user).values_list('value', flat=True).first()
    )
    sub.user_reaction = user_reaction
    return render(
        request,
        'lms/partials/_reactions.jinja',
        {'s': sub, 'assignment': sub.assignment},
    )


@login_required
@require_POST
def comment(request, pk):
    sub = get_object_or_404(LmsSubmission.objects.select_related('assignment', 'student'), pk=pk)
    if not services.can_view_assignment(request.user, sub.assignment):
        raise Http404()
    form = LmsCommentForm(request.POST)
    if form.is_valid():
        try:
            services.add_comment(sub, request.user, form.cleaned_data['body'])
        except ValueError as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, 'Could not post comment.')
    # Re-fetch with comments
    sub = services.submissions_feed(sub.assignment).filter(pk=pk).first() or sub
    user_reaction = (
        LmsReaction.objects.filter(submission_id=pk, user=request.user)
        .values_list('value', flat=True)
        .first()
    )
    sub.user_reaction = user_reaction
    sub.link_rows = services.submission_link_rows(sub)
    if services.is_lms_staff(request.user):
        sub.review_form = LmsReviewForm(
            initial={
                'marks': sub.marks,
                'remark': sub.remark,
                'status': sub.status,
                'is_pinned': sub.is_pinned,
            }
        )
    return render(
        request,
        'lms/partials/_submission_card.jinja',
        {
            's': sub,
            'assignment': sub.assignment,
            'is_staff_lms': services.is_lms_staff(request.user),
            'comment_form': LmsCommentForm(),
        },
    )


@login_required
@require_http_methods(['GET', 'POST'])
def batches(request):
    if not services.is_lms_staff(request.user):
        return HttpResponseForbidden('Staff only.')

    batch_form = LmsBatchForm()
    member_form = LmsBatchMemberForm()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create_batch':
            batch_form = LmsBatchForm(request.POST)
            if batch_form.is_valid():
                batch_form.save()
                messages.success(request, 'Batch created.')
                return redirect('lms:batches')
        elif action == 'add_member':
            batch = get_object_or_404(LmsBatch, pk=request.POST.get('batch_id'))
            member_form = LmsBatchMemberForm(request.POST)
            if member_form.is_valid():
                user = member_form.cleaned_data['username']
                services.add_batch_member(batch, user)
                messages.success(request, f'Added {user.username} to {batch.name}.')
                return redirect('lms:batches')
        elif action == 'remove_member':
            batch = get_object_or_404(LmsBatch, pk=request.POST.get('batch_id'))
            mid = request.POST.get('membership_id')
            m = get_object_or_404(LmsBatchMembership, pk=mid, batch=batch)
            m.delete()
            messages.success(request, 'Member removed.')
            return redirect('lms:batches')

    batch_list = list(
        LmsBatch.objects.prefetch_related('memberships__user').order_by('name')
    )
    return render(
        request,
        'lms/batches.jinja',
        {
            'batches': batch_list,
            'batch_form': batch_form,
            'member_form': member_form,
            'is_staff_lms': True,
        },
    )
