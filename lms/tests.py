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
        """Office is enrollment-only, not fully read-only (fix: "assign student to faculty"
        is the one action Office needs, so they can now add/remove course members)."""
        self.client.force_login(self.city_admin)
        res = self.client.get(reverse('lms:courses'))
        self.assertEqual(res.status_code, 200)
        body = res.content.decode()
        self.assertIn('Office Oversight Batch', body)
        self.assertIn('enrollment only', body)
        self.assertIn('Assign student', body)
        self.assertIn('name="action" value="remove_member"', body)
        # But never course creation — that stays admin/faculty-only.
        self.assertNotIn('name="action" value="create_course"', body)

    def test_office_cannot_post_create_course(self):
        self.client.force_login(self.city_admin)
        res = self.client.post(
            reverse('lms:courses'),
            {'action': 'create_course', 'name': 'Sneaky office course', 'is_active': 'on'},
        )
        self.assertEqual(res.status_code, 403)
        self.assertFalse(LmsCourse.objects.filter(name='Sneaky office course').exists())

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
