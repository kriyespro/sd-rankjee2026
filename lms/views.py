import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from .forms import (
    LmsAssignmentForm,
    LmsCommentForm,
    LmsCourseForm,
    LmsCourseMemberForm,
    LmsReviewForm,
    LmsSubmissionForm,
    LmsTopicForm,
)
from .models import LmsAssignment, LmsCourse, LmsCourseEnrollment, LmsReaction, LmsSubmission, LmsTopic
from . import services


def _require_lms_access(user):
    if not services.is_lms_student(user) and not services.is_lms_staff(user) and not services.is_lms_office(user):
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
    recent_qs = LmsSubmission.objects.filter(assignment__in=[a.pk for a in assignments] or [0])
    _scope = services.faculty_student_scope(request.user)
    if _scope is not None:
        recent_qs = recent_qs.filter(_scope)
    recent = recent_qs.select_related('student', 'assignment').order_by('-is_pinned', '-updated_at')[:12]
    recent_assignments = sorted(
        assignments,
        key=lambda a: a.created_at,
        reverse=True,
    )[:12]
    sidebar = services.home_sidebar_data(request.user)
    is_staff = services.is_lms_staff(request.user)
    is_admin = services.is_lms_admin(request.user)
    is_office = services.is_lms_office(request.user)
    admin_stats = services.admin_home_stats(request.user) if (is_staff or is_office) else None
    lms_notify = services.lms_notifications_for_user(request.user) if not is_staff and not is_office else None
    ticker_items = (
        services.student_assignment_ticker(request.user) if not is_staff and not is_office else []
    )
    return render(
        request,
        'lms/home.jinja',
        {
            'topics': topics,
            'recent_submissions': recent,
            'recent_assignments': recent_assignments,
            'top_scores': sidebar['top_scores'],
            'best_likes': sidebar['best_likes'],
            'latest_comments': sidebar['latest_comments'],
            'is_staff_lms': is_staff,
            'is_admin_lms': is_admin,
            'is_office_lms': is_office,
            'admin_stats': admin_stats,
            'lms_notify': lms_notify,
            'ticker_items': ticker_items,
        },
    )


@login_required
def notification_read(request, note_id):
    from users.models import Notification

    note = Notification.objects.filter(pk=note_id, user=request.user).first()
    if not note:
        return redirect('lms:home')
    if not note.is_read:
        note.is_read = True
        note.save(update_fields=['is_read'])
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.GET.get('ajax') == '1':
        from django.http import HttpResponse
        return HttpResponse(status=204)
    if note.link:
        return redirect(note.link)
    return redirect('lms:home')


@login_required
@require_http_methods(['GET', 'POST'])
def assignment_create(request):
    if not services.is_lms_staff(request.user):
        return HttpResponseForbidden('Staff only.')
    if request.method == 'POST':
        form = LmsAssignmentForm(request.POST, user=request.user)
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
        form = LmsAssignmentForm(initial=initial, user=request.user)

    topic = None
    if getattr(form, 'is_bound', False) and form.is_valid():
        topic = form.cleaned_data.get('topic')
    if topic is None:
        raw_tid = request.POST.get('topic') if request.method == 'POST' else request.GET.get('topic')
        if raw_tid:
            topic = LmsTopic.objects.filter(pk=raw_tid).first()
    crumb_parts = []
    if topic:
        crumb_parts.append(services.crumb(topic.title, reverse('lms:topic_detail', kwargs={'pk': topic.pk})))
    crumb_parts.append(services.crumb('New assignment'))
    return render(
        request,
        'lms/assignment_form.jinja',
        {
            'form': form,
            'is_staff_lms': True,
            'is_edit': False,
            'crumbs': services.lms_crumbs(*crumb_parts),
        },
    )


@login_required
@require_http_methods(['GET', 'POST'])
def assignment_edit(request, pk):
    if not services.is_lms_staff(request.user):
        return HttpResponseForbidden('Staff only.')
    assignment = get_object_or_404(
        LmsAssignment.objects.select_related('topic', 'course'),
        pk=pk,
    )
    if not services.can_manage_assignment(request.user, assignment):
        return HttpResponseForbidden('You can only edit assignments in your own courses.')
    if request.method == 'POST':
        form = LmsAssignmentForm(request.POST, instance=assignment, user=request.user)
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
        form = LmsAssignmentForm(instance=assignment, user=request.user)
    crumb_parts = []
    if assignment.topic_id:
        crumb_parts.append(
            services.crumb(assignment.topic.title, reverse('lms:topic_detail', kwargs={'pk': assignment.topic_id}))
        )
    crumb_parts.append(
        services.crumb(assignment.title, reverse('lms:assignment_detail', kwargs={'pk': assignment.pk}))
    )
    crumb_parts.append(services.crumb('Edit'))
    return render(
        request,
        'lms/assignment_form.jinja',
        {
            'form': form,
            'is_staff_lms': True,
            'is_edit': True,
            'assignment': assignment,
            'crumbs': services.lms_crumbs(*crumb_parts),
        },
    )


@login_required
@require_http_methods(['GET', 'POST'])
def topic_create(request):
    if not services.can_manage_topics(request.user):
        return HttpResponseForbidden('Admin/office only.')
    form = LmsTopicForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        topic = form.save()
        messages.success(request, f'Topic “{topic.title}” created.')
        return redirect('lms:topic_detail', pk=topic.pk)
    return render(
        request,
        'lms/topic_form.jinja',
        {
            'form': form,
            'is_staff_lms': True,
            'is_edit': False,
            'crumbs': services.lms_crumbs(services.crumb('New topic')),
        },
    )


@login_required
@require_http_methods(['GET', 'POST'])
def topic_edit(request, pk):
    if not services.can_manage_topics(request.user):
        return HttpResponseForbidden('Admin/office only.')
    topic = get_object_or_404(LmsTopic, pk=pk)
    form = LmsTopicForm(request.POST or None, instance=topic)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Topic “{topic.title}” updated.')
        return redirect('lms:topic_detail', pk=topic.pk)
    return render(
        request,
        'lms/topic_form.jinja',
        {
            'form': form,
            'topic': topic,
            'is_staff_lms': True,
            'is_edit': True,
            'crumbs': services.lms_crumbs(
                services.crumb(topic.title, reverse('lms:topic_detail', kwargs={'pk': topic.pk})),
                services.crumb('Edit'),
            ),
        },
    )


@login_required
def topic_detail(request, pk):
    topic = get_object_or_404(LmsTopic.objects.select_related('course', 'course__owner'), pk=pk)
    assignments = [
        assignment
        for assignment in services.assignments_for_user(request.user)
        if assignment.topic_id == topic.pk
    ]
    # A topic pre-built for a course (no assignments under it yet — see "add topic per course")
    # is still visible to that course's own enrolled students, not just once the first
    # assignment under it lands.
    can_view_empty_topic = (
        services.is_lms_staff(request.user)
        or services.is_lms_office(request.user)
        or (bool(topic.course_id) and topic.course_id in services.user_course_ids(request.user))
    )
    if not assignments and not can_view_empty_topic:
        raise Http404()
    return render(
        request,
        'lms/topic_detail.jinja',
        {
            'topic': topic,
            'assignments': assignments,
            'is_staff_lms': services.is_lms_staff(request.user),
            'can_manage_topics': services.can_manage_topics(request.user),
            'crumbs': services.lms_crumbs(services.crumb(topic.title)),
        },
    )


@login_required
@require_http_methods(['GET', 'POST'])
def assignment_detail(request, pk):
    assignment = get_object_or_404(
        LmsAssignment.objects.select_related(
            'topic',
            'course',
            'course__owner',
            'concept_video',
            'concept_video__skill',
            'study_topic',
            'study_topic__parent',
            'skill',
        ),
        pk=pk,
    )
    if not services.can_view_assignment(request.user, assignment):
        raise Http404()

    is_staff = services.is_lms_staff(request.user)
    can_manage = services.can_manage_assignment(request.user, assignment)
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

    if request.method == 'POST' and request.POST.get('action') == 'review' and can_manage:
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

    my_skill_attempt = (
        services.student_skill_attempt_for_assignment(request.user, assignment)
        if getattr(request.user, 'role', None) == 'STUDENT'
        else None
    )
    is_office = services.is_lms_office(request.user)
    skill_roster = services.assignment_skill_roster(assignment) if (can_manage or is_office) else []

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
        if can_manage:
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
            'my_skill_attempt': my_skill_attempt,
            'skill_roster': skill_roster,
            'is_office_lms': is_office,
            'is_staff_lms': is_staff,
            'can_manage_lms': can_manage,
            'comment_form': LmsCommentForm(),
            'url_rows_json': json.dumps(submit_form.url_rows if submit_form else []),
            'crumbs': services.lms_crumbs(
                *(
                    [
                        services.crumb(
                            assignment.topic.title,
                            reverse('lms:topic_detail', kwargs={'pk': assignment.topic_id}),
                        )
                    ]
                    if assignment.topic_id
                    else []
                ),
                services.crumb(assignment.title),
            ),
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
def courses(request):
    is_manager = services.is_lms_staff(request.user)
    is_office = services.is_lms_office(request.user)
    if not is_manager and not is_office:
        return HttpResponseForbidden('Staff only.')

    is_admin = services.is_lms_admin(request.user)
    # Office sets up who teaches what: create a course + assign a faculty/tutor as owner, and
    # manage enrollment. Only actual teaching (assignments, grading) stays faculty/admin-only.
    can_create_course = is_manager or is_office
    can_manage_enrollment = is_manager or is_office
    course_form = LmsCourseForm(user=request.user) if can_create_course else None
    member_form = LmsCourseMemberForm() if can_manage_enrollment else None

    def _visible_course_or_404(course_id):
        qs = LmsCourse.objects.all() if (is_admin or is_office) else LmsCourse.objects.filter(owner_id=request.user.id)
        return get_object_or_404(qs, pk=course_id)

    if request.method == 'POST' and not can_manage_enrollment:
        return HttpResponseForbidden('Read-only access.')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create_course':
            if not can_create_course:
                return HttpResponseForbidden('Only faculty/admin/office can create courses.')
            course_form = LmsCourseForm(request.POST, user=request.user)
            if course_form.is_valid():
                course = course_form.save(commit=False)
                # Faculty self-serving their own course always own it; admin/office pick an
                # owner (or leave it platform-wide) via the form's owner field.
                if not (is_admin or is_office):
                    course.owner = request.user
                course.save()
                messages.success(request, 'Course created.')
                return redirect('lms:courses')
        elif action == 'add_member':
            course = _visible_course_or_404(request.POST.get('course_id'))
            member_form = LmsCourseMemberForm(request.POST)
            if member_form.is_valid():
                user = member_form.cleaned_data['username']
                services.add_course_member(course, user)
                messages.success(request, f'Added {user.username} to {course.name}.')
                return redirect('lms:courses')
        elif action == 'remove_member':
            course = _visible_course_or_404(request.POST.get('course_id'))
            mid = request.POST.get('membership_id')
            m = get_object_or_404(LmsCourseEnrollment, pk=mid, course=course)
            m.delete()
            messages.success(request, 'Member removed.')
            return redirect('lms:courses')
        elif action == 'reassign_owner':
            # Fix: previously the only way to assign/change a course's faculty owner was at
            # creation time — there was no way to reassign an *existing* course. Admin/office only.
            if not (is_admin or is_office):
                return HttpResponseForbidden('Admin/office only.')
            course = _visible_course_or_404(request.POST.get('course_id'))
            owner_id = request.POST.get('owner_id') or ''
            if owner_id:
                owner = get_object_or_404(services.lms_owner_queryset(), pk=owner_id)
                course.owner = owner
                messages.success(request, f'{course.name} is now taught by {owner.get_username()}.')
            else:
                course.owner = None
                messages.success(request, f'{course.name} is now platform-wide (no faculty owner).')
            course.save(update_fields=['owner'])
            return redirect('lms:courses')

    course_list = list(services.courses_for_user(request.user))
    unassigned_purchases = services.purchases_missing_lms_enrollment(limit=10) if (is_admin or is_office) else []
    return render(
        request,
        'lms/courses.jinja',
        {
            'courses': course_list,
            'course_form': course_form,
            'member_form': member_form,
            'is_staff_lms': is_manager,
            'is_admin_lms': is_admin,
            'is_office_lms': is_office,
            'can_manage_enrollment': can_manage_enrollment,
            'can_create_course': can_create_course,
            'unassigned_purchases': unassigned_purchases,
            # Faculty never sees another student's email in the assign-student suggestions —
            # only admin/office, who need it to disambiguate students, get the email shown.
            'student_options': services.student_directory_options(include_email=(is_admin or is_office)),
            'owner_options': services.lms_owner_queryset() if (is_admin or is_office) else [],
            'crumbs': services.lms_crumbs(services.crumb('Courses')),
        },
    )
