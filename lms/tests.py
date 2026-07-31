from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from assessment.models import Skill, UserAttempt

from . import services
from .models import LmsAssignment, LmsCourse, LmsCourseEnrollment, LmsTopic

User = get_user_model()


class AssignmentSkillLinkTests(TestCase):
    """fix-rankjee.md Phase 4 — a graded /assessment/ test can be attached to an
    LmsAssignment, with course-scoped results rolling up on the assignment page."""

    def setUp(self):
        self.faculty = User.objects.create_user(
            username='faculty_skill_test', email='faculty_skill_test@example.com',
            password='StrongPass!123',
        )
        self.course = LmsCourse.objects.create(name='Skill Test Batch', owner=self.faculty)
        self.faculty.refresh_from_db()

        self.student_a = User.objects.create_user(
            username='student_a_skill', email='student_a_skill@example.com',
            password='StrongPass!123', role='STUDENT',
        )
        self.student_b = User.objects.create_user(
            username='student_b_skill', email='student_b_skill@example.com',
            password='StrongPass!123', role='STUDENT',
        )
        LmsCourseEnrollment.objects.create(course=self.course, user=self.student_a)
        LmsCourseEnrollment.objects.create(course=self.course, user=self.student_b)

        self.skill = Skill.objects.create(name='SEO Basics', description='SEO fundamentals')
        self.topic = LmsTopic.objects.create(title='Marketing')
        self.assignment = LmsAssignment.objects.create(
            topic=self.topic,
            course=self.course,
            title='SEO module test',
            created_by=self.faculty,
            skill=self.skill,
        )

    def test_owning_faculty_auto_flagged_lms_faculty(self):
        self.assertTrue(self.faculty.is_lms_faculty)

    def test_student_skill_attempt_none_when_not_attempted(self):
        result = services.student_skill_attempt_for_assignment(self.student_a, self.assignment)
        self.assertIsNone(result)

    def test_student_skill_attempt_returns_latest(self):
        UserAttempt.objects.create(user=self.student_a, skill=self.skill, score=40, passed=False)
        latest = UserAttempt.objects.create(user=self.student_a, skill=self.skill, score=90, passed=True)
        result = services.student_skill_attempt_for_assignment(self.student_a, self.assignment)
        self.assertEqual(result.pk, latest.pk)

    def test_roster_lists_all_enrolled_students_including_not_attempted(self):
        UserAttempt.objects.create(user=self.student_a, skill=self.skill, score=85, passed=True)
        roster = services.assignment_skill_roster(self.assignment)
        by_student = {row['student'].id: row['attempt'] for row in roster}
        self.assertEqual(len(roster), 2)
        self.assertIsNotNone(by_student[self.student_a.id])
        self.assertIsNone(by_student[self.student_b.id])

    def test_roster_empty_for_platform_wide_assignment(self):
        platform_assignment = LmsAssignment.objects.create(
            title='Platform-wide test', created_by=self.faculty, skill=self.skill,
        )
        self.assertEqual(services.assignment_skill_roster(platform_assignment), [])

    def test_roster_empty_when_no_skill_linked(self):
        no_skill_assignment = LmsAssignment.objects.create(
            title='No skill', course=self.course, created_by=self.faculty,
        )
        self.assertEqual(services.assignment_skill_roster(no_skill_assignment), [])

    def test_assignment_detail_shows_take_test_cta_for_student(self):
        self.client.force_login(self.student_a)
        res = self.client.get(reverse('lms:assignment_detail', kwargs={'pk': self.assignment.pk}))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Take the test')

    def test_assignment_detail_shows_score_after_attempt(self):
        UserAttempt.objects.create(user=self.student_a, skill=self.skill, score=77, passed=False)
        self.client.force_login(self.student_a)
        res = self.client.get(reverse('lms:assignment_detail', kwargs={'pk': self.assignment.pk}))
        self.assertContains(res, 'Your score: 77%')
        self.assertContains(res, 'Retake test')

    def test_faculty_sees_roster_on_assignment_detail(self):
        UserAttempt.objects.create(user=self.student_a, skill=self.skill, score=60, passed=False)
        self.client.force_login(self.faculty)
        res = self.client.get(reverse('lms:assignment_detail', kwargs={'pk': self.assignment.pk}))
        self.assertContains(res, 'Test results')
        self.assertContains(res, 'student_a_skill')
        self.assertContains(res, 'student_b_skill')
        self.assertContains(res, 'Not attempted')

    def test_office_can_view_roster_but_cannot_manage(self):
        UserAttempt.objects.create(user=self.student_a, skill=self.skill, score=55, passed=False)
        office = User.objects.create_user(
            username='office_ops_skill', email='office_ops_skill@example.com',
            password='StrongPass!123', role='CITY_ADMIN',
        )
        self.client.force_login(office)
        res = self.client.get(reverse('lms:assignment_detail', kwargs={'pk': self.assignment.pk}))
        self.assertEqual(res.status_code, 200)
        body = res.content.decode()
        self.assertIn('Test results', body)
        self.assertIn('read-only', body)
        self.assertNotIn('Edit assignment', body)

    def test_other_faculty_cannot_view_or_manage_someone_elses_course_assignment(self):
        other_faculty = User.objects.create_user(
            username='other_faculty_skill', email='other_faculty_skill@example.com',
            password='StrongPass!123',
        )
        LmsCourse.objects.create(name='Other batch', owner=other_faculty)
        # Course-scoped assignments stay isolated per faculty — existing can_view_assignment
        # rule raises Http404, which the app's custom handler404 turns into a redirect home.
        self.client.force_login(other_faculty)
        res = self.client.get(reverse('lms:assignment_detail', kwargs={'pk': self.assignment.pk}))
        self.assertEqual(res.status_code, 302)


class OfficeOversightTests(TestCase):
    """fix-rankjee.md Phase 1 (remaining slice) — CITY_ADMIN/GLOBAL_ADMIN get platform-wide
    READ-ONLY visibility into LMS courses/assignments, never management rights."""

    def setUp(self):
        self.city_admin = User.objects.create_user(
            username='office_city_admin', email='office_city_admin@example.com',
            password='StrongPass!123', role='CITY_ADMIN',
        )
        self.global_admin = User.objects.create_user(
            username='office_global_admin', email='office_global_admin@example.com',
            password='StrongPass!123', role='GLOBAL_ADMIN',
        )
        self.faculty = User.objects.create_user(
            username='faculty_office_test', email='faculty_office_test@example.com',
            password='StrongPass!123',
        )
        self.course = LmsCourse.objects.create(name='Office Oversight Batch', owner=self.faculty)
        self.student = User.objects.create_user(
            username='student_office_test', email='student_office_test@example.com',
            password='StrongPass!123', role='STUDENT',
        )
        LmsCourseEnrollment.objects.create(course=self.course, user=self.student)
        self.assignment = LmsAssignment.objects.create(
            course=self.course, title='Office visible assignment', created_by=self.faculty,
        )

    def test_is_lms_office_true_for_admin_roles_only(self):
        self.assertTrue(services.is_lms_office(self.city_admin))
        self.assertTrue(services.is_lms_office(self.global_admin))
        self.assertFalse(services.is_lms_office(self.faculty))
        self.assertFalse(services.is_lms_office(self.student))

    def test_office_never_counted_as_manager(self):
        # Critical isolation guarantee: is_lms_staff (manage rights) must stay False for Office.
        self.assertFalse(services.is_lms_staff(self.city_admin))
        self.assertFalse(services.can_manage_course(self.city_admin, self.course))
        self.assertFalse(services.can_manage_assignment(self.city_admin, self.assignment))

    def test_office_sees_all_courses_across_faculty(self):
        other_faculty = User.objects.create_user(
            username='faculty_office_test2', email='faculty_office_test2@example.com',
            password='StrongPass!123',
        )
        LmsCourse.objects.create(name="Other faculty's batch", owner=other_faculty)
        ids = {c.pk for c in services.courses_for_user(self.city_admin)}
        self.assertIn(self.course.pk, ids)

    def test_office_can_view_home_page(self):
        self.client.force_login(self.global_admin)
        res = self.client.get(reverse('lms:home'))
        self.assertEqual(res.status_code, 200)
        # Note: a *different*, unrelated marketing tip elsewhere on the base layout also
        # contains the substring "New assignment" (tutor_study feature hint) — assert against
        # the actual create-assignment link/URL, not the raw substring, to avoid a false positive.
        self.assertNotContains(res, reverse('lms:assignment_create'))

    def test_office_can_view_courses_page_and_assign_students(self):
        """Office sets up who teaches what (fix: "faculty will be assigned to that course" by
        admin/office) — they can create a course, assign a faculty/tutor as owner, and manage
        enrollment. They still never touch assignments/grading."""
        self.client.force_login(self.city_admin)
        res = self.client.get(reverse('lms:courses'))
        self.assertEqual(res.status_code, 200)
        body = res.content.decode()
        self.assertIn('Office Oversight Batch', body)
        self.assertIn('course & student setup', body)
        self.assertIn('Assign student', body)
        self.assertIn('name="action" value="remove_member"', body)
        # Office CAN create courses + assign an owner now.
        self.assertIn('name="action" value="create_course"', body)
        self.assertContains(res, 'Owner (faculty/tutor)')

    def test_office_can_create_course_and_assign_faculty_owner(self):
        """The actual "admin/office assigns faculty to that course" flow."""
        self.client.force_login(self.global_admin)
        other_faculty = User.objects.create_user(
            username='office_assigns_owner', email='office_assigns_owner@example.com',
            password='StrongPass!123', role='FACULTY',
        )
        res = self.client.post(
            reverse('lms:courses'),
            {
                'action': 'create_course',
                'name': 'Office-created batch',
                'owner': other_faculty.pk,
                'is_active': 'on',
            },
        )
        self.assertEqual(res.status_code, 302)
        course = LmsCourse.objects.get(name='Office-created batch')
        self.assertEqual(course.owner_id, other_faculty.pk)

    def test_office_cannot_set_catalog_fields_when_creating_course(self):
        """Monetization-linked catalog fields stay admin-only even though office can now
        create courses — the form simply never exposes those fields to office."""
        self.client.force_login(self.city_admin)
        res = self.client.get(reverse('lms:courses'))
        self.assertNotContains(res, 'Paid course (/courses/)')

    def test_office_can_add_and_remove_course_members(self):
        """The actual "assign student to faculty" flow — Office adds a student to any
        faculty's course, then removes them, without ever being able to create the course."""
        self.client.force_login(self.global_admin)
        other_student = User.objects.create_user(
            username='office_assignable_student', email='office_assignable_student@example.com',
            password='StrongPass!123', role='STUDENT',
        )
        res = self.client.post(
            reverse('lms:courses'),
            {'action': 'add_member', 'course_id': self.course.pk, 'username': other_student.username},
        )
        self.assertEqual(res.status_code, 302)
        membership = LmsCourseEnrollment.objects.get(course=self.course, user=other_student)

        res = self.client.post(
            reverse('lms:courses'),
            {'action': 'remove_member', 'course_id': self.course.pk, 'membership_id': membership.pk},
        )
        self.assertEqual(res.status_code, 302)
        self.assertFalse(LmsCourseEnrollment.objects.filter(pk=membership.pk).exists())

    def test_office_cannot_manage_enrollment_via_email_lookup_of_unrelated_user(self):
        """clean_username's new email fallback still only ever resolves to a real user — an
        office typo/garbage input is rejected, not silently matched to the wrong account."""
        self.client.force_login(self.city_admin)
        res = self.client.post(
            reverse('lms:courses'),
            {'action': 'add_member', 'course_id': self.course.pk, 'username': 'nobody@nowhere.example'},
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn('No student found matching', res.content.decode())

    def test_office_cannot_create_or_edit_assignments(self):
        self.client.force_login(self.city_admin)
        res = self.client.get(reverse('lms:assignment_create'))
        self.assertEqual(res.status_code, 403)
        res = self.client.get(reverse('lms:assignment_edit', kwargs={'pk': self.assignment.pk}))
        self.assertEqual(res.status_code, 403)

    def test_office_sees_assignment_detail_without_edit_link(self):
        self.client.force_login(self.city_admin)
        res = self.client.get(reverse('lms:assignment_detail', kwargs={'pk': self.assignment.pk}))
        self.assertEqual(res.status_code, 200)
        self.assertNotContains(res, 'Edit assignment')


class FacultyOwnStudentScopeTests(TestCase):
    """Fix: a platform-wide (unbatched) assignment is visible to every faculty (shared
    curriculum), but that used to leak every OTHER faculty's students' submissions into a
    faculty's own LMS home page (top scores, best likes, latest comments, recent activity,
    pending-review counts) — `faculty_student_scope` narrows all of that to a faculty's own
    roster, while an admin/office account still sees everything."""

    def setUp(self):
        self.faculty_a = User.objects.create_user(
            username='scope_faculty_a', email='scope_faculty_a@example.com', password='StrongPass!123',
        )
        self.faculty_b = User.objects.create_user(
            username='scope_faculty_b', email='scope_faculty_b@example.com', password='StrongPass!123',
        )
        self.course_a = LmsCourse.objects.create(name='Faculty A batch', owner=self.faculty_a)
        self.course_b = LmsCourse.objects.create(name='Faculty B batch', owner=self.faculty_b)
        # LmsCourse.save() auto-flags the owner is_lms_faculty=True — refresh the in-memory
        # objects so direct service-function calls below see it (force_login already re-fetches
        # from DB, so this only matters for tests calling services.* directly with these objects).
        self.faculty_a.refresh_from_db()
        self.faculty_b.refresh_from_db()

        self.student_a = User.objects.create_user(
            username='scope_student_a', email='scope_student_a@example.com',
            password='StrongPass!123', role='STUDENT',
        )
        self.student_b = User.objects.create_user(
            username='scope_student_b', email='scope_student_b@example.com',
            password='StrongPass!123', role='STUDENT',
        )
        LmsCourseEnrollment.objects.create(course=self.course_a, user=self.student_a)
        LmsCourseEnrollment.objects.create(course=self.course_b, user=self.student_b)

        # A platform-wide assignment (no course) — shared curriculum, both students can submit.
        self.platform_assignment = LmsAssignment.objects.create(
            title='Shared platform-wide quiz', created_by=self.faculty_a,
        )

    def _submit(self, student, assignment):
        from .models import LmsSubmission

        return LmsSubmission.objects.create(
            assignment=assignment, student=student, caption='work',
            status=LmsSubmission.Status.SUBMITTED, marks=90,
        )

    def test_faculty_student_scope_none_for_admin_and_office(self):
        admin = User.objects.create_superuser(
            username='scope_admin', email='scope_admin@example.com', password='StrongPass!123',
        )
        office = User.objects.create_user(
            username='scope_office', email='scope_office@example.com',
            password='StrongPass!123', role='CITY_ADMIN',
        )
        self.assertIsNone(services.faculty_student_scope(admin))
        self.assertIsNone(services.faculty_student_scope(office))

    def test_own_student_ids_scoped_per_faculty(self):
        self.assertEqual(services.own_student_ids(self.faculty_a), {self.student_a.id})
        self.assertEqual(services.own_student_ids(self.faculty_b), {self.student_b.id})

    def test_home_page_hides_other_faculty_students_platform_wide_submission(self):
        self._submit(self.student_a, self.platform_assignment)
        self._submit(self.student_b, self.platform_assignment)

        self.client.force_login(self.faculty_a)
        res = self.client.get(reverse('lms:home'))
        body = res.content.decode()
        self.assertIn('scope_student_a', body)
        self.assertNotIn('scope_student_b', body)

    def test_admin_home_stats_pending_count_scoped_to_own_students(self):
        self._submit(self.student_a, self.platform_assignment)
        self._submit(self.student_b, self.platform_assignment)

        stats_a = services.admin_home_stats(self.faculty_a)
        self.assertEqual(stats_a['pending'], 1)
        self.assertEqual(stats_a['students_submitted'], 1)

    def test_own_course_submission_never_filtered_out(self):
        """Belt-and-suspenders: even if enrollment were ever removed after submission, a
        submission on a faculty's OWN course-owned assignment must still show for that faculty."""
        course_assignment = LmsAssignment.objects.create(
            course=self.course_a, title='Course-scoped hw', created_by=self.faculty_a,
        )
        self._submit(self.student_a, course_assignment)
        LmsCourseEnrollment.objects.filter(course=self.course_a, user=self.student_a).delete()

        stats_a = services.admin_home_stats(self.faculty_a)
        self.assertEqual(stats_a['students_submitted'], 1)


class TopicAndStudentPrivacyPermissionTests(TestCase):
    """Fix: (1) topics are curriculum categories admin/office manage centrally — faculty pick
    from the existing list only, never mint new ones; (2) admin/office can now create a course
    AND assign a faculty/tutor to teach it ("faculty will be assigned to that course"); (3) a
    faculty/tutor never sees another student's email address anywhere in the LMS UI."""

    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='topics_admin', email='topics_admin@example.com', password='StrongPass!123',
        )
        self.office = User.objects.create_user(
            username='topics_office', email='topics_office@example.com',
            password='StrongPass!123', role='CITY_ADMIN',
        )
        self.faculty = User.objects.create_user(
            username='topics_faculty', email='topics_faculty@example.com', password='StrongPass!123',
        )
        self.course = LmsCourse.objects.create(name='Topics test batch', owner=self.faculty)
        self.faculty.refresh_from_db()
        self.student = User.objects.create_user(
            username='topics_student', email='topics_student_secret@example.com',
            password='StrongPass!123', role='STUDENT',
        )
        LmsCourseEnrollment.objects.create(course=self.course, user=self.student)
        self.topic = LmsTopic.objects.create(title='Existing Topic')

    def test_faculty_cannot_create_or_edit_topics(self):
        self.client.force_login(self.faculty)
        res = self.client.get(reverse('lms:topic_create'))
        self.assertEqual(res.status_code, 403)
        res = self.client.get(reverse('lms:topic_edit', kwargs={'pk': self.topic.pk}))
        self.assertEqual(res.status_code, 403)

    def test_office_can_create_and_edit_topics(self):
        self.client.force_login(self.office)
        res = self.client.get(reverse('lms:topic_create'))
        self.assertEqual(res.status_code, 200)
        res = self.client.post(reverse('lms:topic_create'), {'title': 'Office-made topic', 'description': ''})
        self.assertEqual(res.status_code, 302)
        self.assertTrue(LmsTopic.objects.filter(title='Office-made topic').exists())
        res = self.client.get(reverse('lms:topic_edit', kwargs={'pk': self.topic.pk}))
        self.assertEqual(res.status_code, 200)

    def test_admin_can_create_topics(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('lms:topic_create')).status_code, 200)

    def test_faculty_assignment_form_has_no_create_new_topic_option(self):
        self.client.force_login(self.faculty)
        res = self.client.get(reverse('lms:assignment_create'))
        self.assertEqual(res.status_code, 200)
        self.assertNotContains(res, 'name="topic_mode"')
        self.assertNotContains(res, 'name="new_topic_title"')

    def test_admin_assignment_form_has_create_new_topic_option(self):
        self.client.force_login(self.admin)
        res = self.client.get(reverse('lms:assignment_create'))
        self.assertContains(res, 'name="topic_mode"')

    def test_office_can_create_course_and_assign_faculty_owner(self):
        other_faculty = User.objects.create_user(
            username='office_assigns_owner', email='office_assigns_owner@example.com',
            password='StrongPass!123', role='FACULTY',
        )
        self.client.force_login(self.office)
        res = self.client.post(
            reverse('lms:courses'),
            {'action': 'create_course', 'name': 'Office-created batch', 'owner': other_faculty.pk, 'is_active': 'on'},
        )
        self.assertEqual(res.status_code, 302)
        course = LmsCourse.objects.get(name='Office-created batch')
        self.assertEqual(course.owner_id, other_faculty.pk)

    def test_faculty_cannot_see_student_email_in_courses_datalist(self):
        self.client.force_login(self.faculty)
        res = self.client.get(reverse('lms:courses'))
        self.assertEqual(res.status_code, 200)
        self.assertNotContains(res, 'topics_student_secret@example.com')

    def test_admin_and_office_see_student_email_in_courses_datalist(self):
        for user in (self.admin, self.office):
            self.client.force_login(user)
            res = self.client.get(reverse('lms:courses'))
            self.assertContains(res, 'topics_student_secret@example.com')
