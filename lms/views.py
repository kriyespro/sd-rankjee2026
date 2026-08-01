import json

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from .forms import (
    LmsAssignmentForm,
    LmsAttendanceDateForm,
    LmsCommentForm,
    LmsCourseForm,
    LmsCourseMemberForm,
    LmsReviewForm,
    LmsSubmissionForm,
    LmsTopicForm,
)
from .models import LmsAssignment, LmsAttendance, LmsCourse, LmsCourseEnrollment, LmsReaction, LmsSubmission, LmsTopic
from . import services

User = get_user_model()


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
            if my_sub is not None and my_sub.status != LmsSubmission.Status.SUBMITTED:
                # Fix: resubmitting after "changes requested" (or editing an already-approved
                # submission) left status untouched forever — it never came back into any
                # pending-review queue for faculty to see the revision.
                sub.status = LmsSubmission.Status.SUBMITTED
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
    # Fix: was `is_lms_staff` (true for admin AND office AND any faculty account, regardless of
    # whether they actually own this submission's course) — the review form's POST silently
    # no-ops for anyone who isn't `can_manage_assignment`, which is confusing UI to show them.
    if services.can_manage_assignment(request.user, sub.assignment):
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
                # Fix: unassigning a course's owner used to give no signal that this leaves the
                # course's existing assignments/students with nobody but a superuser able to
                # manage or grade them going forward (can_manage_course/can_manage_assignment are
                # faculty-owner-only) — warn instead of a plain success toast so it's a deliberate
                # choice, not an accidental click.
                has_data = course.assignments.exists() or course.enrollments.exists()
                if has_data:
                    messages.warning(
                        request,
                        f'{course.name} is now platform-wide (no faculty owner) — it still has '
                        f'assignments and/or enrolled students, and only a superuser can manage or '
                        f'grade them from here on. Reassign to another faculty instead if that '
                        f'wasn\u2019t the intent.',
                    )
                else:
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


# ── Bulk enrollment helpers ───────────────────────────────────────────────────

@login_required
def students_for_course(request, pk):
    """HTMX GET: return a student checkbox list partial for the chosen course.

    Used by the superadmin "Bulk enroll" panel in /admin/. Admin-only.
    """
    if not services.is_lms_admin(request.user):
        return HttpResponseForbidden('Superadmin only.')

    course = get_object_or_404(LmsCourse, pk=pk)
    enrolled_ids = set(
        LmsCourseEnrollment.objects.filter(course=course).values_list('user_id', flat=True)
    )
    # All active student-role users on the platform
    all_students = list(
        User.objects.filter(is_active=True, role='STUDENT')
        .order_by('username')
        .values('id', 'username', 'email', 'first_name', 'last_name')
    )
    for s in all_students:
        s['enrolled'] = s['id'] in enrolled_ids
        s['display'] = f"{s['username']}"
        if s.get('email'):
            s['display'] += f" · {s['email']}"

    return render(
        request,
        'lms/partials/_student_picker.jinja',
        {
            'course': course,
            'students': all_students,
            'enrolled_count': len(enrolled_ids),
        },
    )


@login_required
@require_POST
def bulk_enroll(request):
    """POST: enroll multiple students into a course at once. Admin-only.

    Accepts: course_id (int), user_ids (list of int), remove_ids (list of int).
    """
    if not services.is_lms_admin(request.user):
        return HttpResponseForbidden('Superadmin only.')

    course_id = request.POST.get('course_id', '')
    if not course_id:
        messages.error(request, 'No course selected.')
        return redirect('lms:courses')

    course = get_object_or_404(LmsCourse, pk=course_id)

    enroll_ids = request.POST.getlist('user_ids')
    remove_ids = request.POST.getlist('remove_ids')

    added = 0
    for uid in enroll_ids:
        try:
            user = User.objects.get(pk=int(uid), is_active=True)
            services.add_course_member(course, user)
            added += 1
        except (User.DoesNotExist, ValueError):
            pass

    removed = 0
    for uid in remove_ids:
        try:
            deleted, _ = LmsCourseEnrollment.objects.filter(course=course, user_id=int(uid)).delete()
            removed += deleted
        except (ValueError, LmsCourseEnrollment.DoesNotExist):
            pass

    parts = []
    if added:
        parts.append(f'Enrolled {added} student{"s" if added != 1 else ""}')
    if removed:
        parts.append(f'removed {removed}')
    if parts:
        messages.success(request, f'{" · ".join(parts)} in "{course.name}".')
    else:
        messages.info(request, 'No changes made.')

    # If triggered from the admin dashboard, go back there
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER', '')
    if next_url and '/admin/' in next_url:
        return redirect(next_url)
    return redirect('lms:courses')


# ── Attendance views ──────────────────────────────────────────────────────────

@login_required
def attendance_mark(request, pk):
    """Faculty marks attendance for all enrolled students in a course session."""
    course = get_object_or_404(LmsCourse, pk=pk)

    # Only course owner (faculty/tutor) or LMS admin can mark attendance
    is_admin = services.is_lms_admin(request.user)
    is_owner = course.owner_id == request.user.pk
    if not (is_admin or is_owner):
        messages.error(request, 'Only the course faculty or admin can mark attendance.')
        return redirect('lms:courses')

    # Get enrolled students
    enrolled = list(
        LmsCourseEnrollment.objects.filter(course=course)
        .select_related('user')
        .order_by('user__username')
    )

    date_form = LmsAttendanceDateForm(request.GET or None)
    selected_date = None
    if date_form.is_valid():
        selected_date = date_form.cleaned_data['date']
    else:
        from django.utils import timezone as _tz
        selected_date = _tz.localdate()

    # Existing attendance for this date
    existing = {
        a.student_id: a.status
        for a in LmsAttendance.objects.filter(course=course, date=selected_date)
    }

    if request.method == 'POST':
        post_date_str = request.POST.get('date')
        from datetime import date as _date
        try:
            session_date = _date.fromisoformat(post_date_str)
        except (TypeError, ValueError):
            from django.utils import timezone as _tz
            session_date = _tz.localdate()

        status_map = {}
        for enr in enrolled:
            key = f'status_{enr.user_id}'
            val = request.POST.get(key, 'ABSENT')
            if val in LmsAttendance.Status.values:
                status_map[enr.user_id] = val

        count = services.attendance_mark_session(course, session_date, request.user, status_map)
        messages.success(request, f'Attendance saved for {count} student(s) on {session_date}.')
        return redirect(f"{request.path}?date={session_date}")

    crumbs = services.lms_crumbs(
        services.crumb(course.name, None),
        services.crumb('Mark attendance'),
    )
    return render(request, 'lms/attendance_mark.jinja', {
        'course': course,
        'enrolled': enrolled,
        'selected_date': selected_date,
        'existing': existing,
        'date_form': date_form,
        'statuses': LmsAttendance.Status.choices,
        'breadcrumbs': crumbs,
    })


@login_required
def attendance_student(request, pk):
    """Student/parent views monthly attendance calendar for a course."""
    from datetime import date as _date
    import calendar

    course = get_object_or_404(LmsCourse, pk=pk)
    user = request.user
    role = getattr(user, 'role', '')

    # Determine whose attendance to show
    if role == 'STUDENT':
        student = user
    elif role == 'PARENT':
        # Parent: show linked child's attendance
        from users.models import ParentStudentLink
        link = ParentStudentLink.objects.filter(parent=user).select_related('student').first()
        if not link:
            messages.error(request, 'No child linked to your parent account.')
            return redirect('dashboard:index')
        student = link.student
    elif services.is_lms_admin(request.user) or course.owner_id == user.pk:
        # Admin or faculty: let them pick a student via query param
        student_id = request.GET.get('student_id')
        if student_id:
            from django.contrib.auth import get_user_model as _gum
            student = get_object_or_404(_gum(), pk=student_id)
        else:
            # Default: show all enrolled students summary
            return redirect('lms:attendance_course_summary', pk=pk)
    else:
        messages.error(request, 'Access denied.')
        return redirect('dashboard:index')

    # Month/year navigation
    today = _date.today()
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
        if not (1 <= month <= 12):
            month = today.month
    except (TypeError, ValueError):
        year, month = today.year, today.month

    days = services.student_monthly_calendar(course, student, year, month)
    summary = services.attendance_summary(course, student)

    # Prev/next month
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    month_name = _date(year, month, 1).strftime('%B %Y')
    weekday_start = _date(year, month, 1).weekday()  # 0=Mon

    crumbs = services.lms_crumbs(
        services.crumb(course.name, None),
        services.crumb('Attendance'),
    )
    return render(request, 'lms/attendance_student.jinja', {
        'course': course,
        'student': student,
        'days': days,
        'summary': summary,
        'year': year,
        'month': month,
        'month_name': month_name,
        'weekday_start': weekday_start,
        'prev_year': prev_year,
        'prev_month': prev_month,
        'next_year': next_year,
        'next_month': next_month,
        'breadcrumbs': crumbs,
    })


@login_required
def attendance_course_summary(request, pk):
    """Faculty/admin sees all students' attendance for a course — monthly summary table."""
    from datetime import date as _date

    course = get_object_or_404(LmsCourse, pk=pk)
    is_admin = services.is_lms_admin(request.user)
    is_owner = course.owner_id == request.user.pk
    if not (is_admin or is_owner):
        messages.error(request, 'Access denied.')
        return redirect('lms:courses')

    today = _date.today()
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
        if not (1 <= month <= 12):
            month = today.month
    except (TypeError, ValueError):
        year, month = today.year, today.month

    enrolled = list(
        LmsCourseEnrollment.objects.filter(course=course)
        .select_related('user')
        .order_by('user__username')
    )

    # Build per-student summary
    rows = []
    for enr in enrolled:
        summary = services.attendance_summary(course, enr.user)
        month_days = services.student_monthly_calendar(course, enr.user, year, month)
        rows.append({
            'user': enr.user,
            'summary': summary,
            'month_days': month_days,
        })

    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    month_name = _date(year, month, 1).strftime('%B %Y')

    crumbs = services.lms_crumbs(
        services.crumb(course.name, None),
        services.crumb('Attendance summary'),
    )
    return render(request, 'lms/attendance_summary.jinja', {
        'course': course,
        'rows': rows,
        'year': year,
        'month': month,
        'month_name': month_name,
        'prev_year': prev_year,
        'prev_month': prev_month,
        'next_year': next_year,
        'next_month': next_month,
        'breadcrumbs': crumbs,
    })


@login_required
def attendance_admin_all(request):
    """Superadmin sees all attendance records across all courses — monthly."""
    from datetime import date as _date

    if not services.is_lms_admin(request.user):
        messages.error(request, 'Superadmin only.')
        return redirect('dashboard:index')

    today = _date.today()
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
        if not (1 <= month <= 12):
            month = today.month
    except (TypeError, ValueError):
        year, month = today.year, today.month

    records = services.attendance_for_admin(year, month)

    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    month_name = _date(year, month, 1).strftime('%B %Y')

    # Aggregate stats
    total = len(records)
    present = sum(1 for r in records if r.status == LmsAttendance.Status.PRESENT)
    late = sum(1 for r in records if r.status == LmsAttendance.Status.LATE)
    absent = sum(1 for r in records if r.status == LmsAttendance.Status.ABSENT)

    crumbs = [
        services.crumb('LMS Admin', None),
        services.crumb('All Attendance'),
    ]
    return render(request, 'lms/attendance_admin.jinja', {
        'records': records,
        'year': year,
        'month': month,
        'month_name': month_name,
        'prev_year': prev_year,
        'prev_month': prev_month,
        'next_year': next_year,
        'next_month': next_month,
        'total': total,
        'present': present,
        'late': late,
        'absent': absent,
        'breadcrumbs': crumbs,
    })
