from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from django.urls import reverse

from hometutor.models import TutorProfile
from . import services
from .forms import CustomUserCreationForm
from .models import CustomUser, ParentStudentLink
from .onboarding import SESSION_PENDING_SIGNUP_ROLE, apply_social_signup_onboarding


class PublicRoleSignupTests(TestCase):
    def test_signup_form_hides_admin_roles(self):
        form = CustomUserCreationForm()
        role_values = {value for value, _ in form.fields['role'].choices}
        self.assertIn(CustomUser.Role.STUDENT, role_values)
        self.assertIn(CustomUser.Role.PARENT, role_values)
        self.assertIn(CustomUser.Role.TUTOR, role_values)
        self.assertNotIn(CustomUser.Role.CITY_ADMIN, role_values)
        self.assertNotIn(CustomUser.Role.GLOBAL_ADMIN, role_values)


class OnboardingFlowTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='oauth_user',
            email='oauth@example.com',
            password='StrongPass!123',
            onboarding_completed=False,
            role=CustomUser.Role.STUDENT,
        )

    def test_dashboard_redirects_social_user_to_role_picker(self):
        self.client.force_login(self.user)
        session = self.client.session
        session['needs_role_picker'] = True
        session.save()
        res = self.client.get(reverse('dashboard:index'))
        self.assertRedirects(res, reverse('users:onboarding_role'))

    def test_dashboard_redirects_email_user_to_profile(self):
        self.client.force_login(self.user)
        res = self.client.get(reverse('dashboard:index'))
        self.assertRedirects(res, reverse('users:onboarding_profile'))

    def test_hometutor_redirects_incomplete_onboarding(self):
        self.client.force_login(self.user)
        res = self.client.get(reverse('hometutor:my_demo_requests'))
        self.assertRedirects(res, reverse('users:onboarding_profile'))

    def test_onboarding_pages_remain_accessible(self):
        self.client.force_login(self.user)
        res = self.client.get(reverse('users:onboarding_profile'))
        self.assertEqual(res.status_code, 200)

    def test_student_profile_onboarding_marks_complete(self):
        self.client.force_login(self.user)
        res = self.client.post(
            reverse('users:onboarding_profile'),
            data={'first_name': 'Demo', 'last_name': '', 'state': '',
                  'phone': '9876543210', 'city': 'Ahmedabad',
                  'class_level': 9, 'subjects': 'Maths'},
        )
        self.user.refresh_from_db()
        self.assertTrue(self.user.onboarding_completed)
        self.assertRedirects(res, reverse('dashboard:index'))

    def test_student_can_skip_profile_onboarding_only_with_contact_info(self):
        # Skip only bypasses the optional name/state fields — phone+city are mandatory,
        # so a user without them on file stays in onboarding.
        self.client.force_login(self.user)
        res = self.client.post(
            reverse('users:onboarding_profile'),
            data={'action': 'skip'},
        )
        self.user.refresh_from_db()
        self.assertFalse(self.user.onboarding_completed)

        self.user.phone = '9876543210'
        self.user.city = 'Ahmedabad'
        self.user.class_level = 9
        self.user.subjects = 'Maths'
        self.user.save(update_fields=['phone', 'city', 'class_level', 'subjects'])
        res = self.client.post(
            reverse('users:onboarding_profile'),
            data={'action': 'skip'},
        )
        self.user.refresh_from_db()
        self.assertTrue(self.user.onboarding_completed)
        self.assertRedirects(res, reverse('dashboard:index'))

    def test_email_signup_goes_to_profile_not_role(self):
        res = self.client.post(
            reverse('users:signup'),
            data={
                'username': 'newstudent',
                'email': 'new@example.com',
                'phone': '9876543210',
                'city': 'Ahmedabad',
                'password1': 'StrongPass!123',
                'password2': 'StrongPass!123',
                'role': CustomUser.Role.STUDENT,
            },
        )
        user = CustomUser.objects.get(username='newstudent')
        self.assertFalse(user.onboarding_completed)
        self.assertRedirects(res, reverse('users:onboarding_profile'))

    def test_signup_role_query_preselects_role(self):
        res = self.client.get(reverse('users:signup'), {'role': 'TUTOR'})
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'value="TUTOR"')
        self.assertContains(res, 'checked')

    def test_tutor_profile_onboarding_minimal_fields(self):
        self.user.role = CustomUser.Role.TUTOR
        self.user.save(update_fields=['role'])
        self.client.force_login(self.user)
        res = self.client.post(
            reverse('users:onboarding_profile'),
            data={
                'display_name': 'Tutor One',
                'phone': '9876543210',
                'city': 'Ahmedabad',
                'subjects': 'Math, Science',
                'teaching_mode': TutorProfile.TeachingMode.ONLINE,
            },
        )
        self.user.refresh_from_db()
        profile = TutorProfile.objects.filter(user=self.user).first()
        self.assertIsNotNone(profile)
        self.assertEqual(profile.verification_status, TutorProfile.VerificationStatus.PENDING)
        self.assertTrue(self.user.onboarding_completed)
        self.assertRedirects(res, reverse('hometutor:my_profile'), fetch_redirect_response=False)

    def test_email_user_onboarding_role_redirects_to_profile(self):
        self.client.force_login(self.user)
        res = self.client.get(reverse('users:onboarding_role'))
        self.assertRedirects(res, reverse('users:onboarding_profile'))

    def test_google_signup_start_stores_role(self):
        res = self.client.get(reverse('users:google_signup_start'), {'role': 'TUTOR'})
        self.assertEqual(res.status_code, 302)
        self.assertEqual(self.client.session.get(SESSION_PENDING_SIGNUP_ROLE), 'TUTOR')

    def test_social_signup_with_pending_role_skips_role_picker(self):
        session = self.client.session
        session[SESSION_PENDING_SIGNUP_ROLE] = CustomUser.Role.TUTOR
        session.save()
        request = RequestFactory().get('/')
        request.session = session
        apply_social_signup_onboarding(request, self.user)
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, CustomUser.Role.TUTOR)
        self.assertFalse(self.user.onboarding_completed)
        self.assertNotIn('needs_role_picker', session)

    def test_role_picker_clears_social_session_flag(self):
        self.client.force_login(self.user)
        session = self.client.session
        session['needs_role_picker'] = True
        session.save()
        res = self.client.post(
            reverse('users:onboarding_role'),
            data={'role': CustomUser.Role.PARENT},
        )
        self.assertRedirects(res, reverse('users:onboarding_profile'))
        self.assertNotIn('needs_role_picker', self.client.session)


class ParentStudentLinkTests(TestCase):
    """fix-rankjee.md Phase 2 — parent<->student linking must be opt-in (student approves)
    and must never leak visibility before approval."""

    def setUp(self):
        self.parent = CustomUser.objects.create_user(
            username='parent1', email='parent1@example.com', password='StrongPass!123',
            role=CustomUser.Role.PARENT,
        )
        self.student = CustomUser.objects.create_user(
            username='student1link', email='student1link@example.com', password='StrongPass!123',
            role=CustomUser.Role.STUDENT,
        )
        self.other_parent = CustomUser.objects.create_user(
            username='parent2', email='parent2@example.com', password='StrongPass!123',
            role=CustomUser.Role.PARENT,
        )

    def test_request_link_creates_pending_unverified_link(self):
        link = services.request_parent_link(self.parent, self.student.username)
        self.assertFalse(link.is_verified)
        self.assertFalse(services.can_parent_view_student(self.parent, self.student))

    def test_request_link_is_idempotent(self):
        link1 = services.request_parent_link(self.parent, self.student.username)
        link2 = services.request_parent_link(self.parent, self.student.username)
        self.assertEqual(link1.pk, link2.pk)
        self.assertEqual(ParentStudentLink.objects.filter(parent=self.parent, student=self.student).count(), 1)

    def test_request_link_by_email_works(self):
        link = services.request_parent_link(self.parent, self.student.email)
        self.assertEqual(link.student_id, self.student.id)

    def test_non_parent_cannot_request_link(self):
        with self.assertRaises(ValidationError):
            services.request_parent_link(self.student, self.other_parent.username)

    def test_cannot_link_to_non_student(self):
        with self.assertRaises(ValidationError):
            services.request_parent_link(self.parent, self.other_parent.username)

    def test_cannot_link_to_unknown_identifier(self):
        with self.assertRaises(ValidationError):
            services.request_parent_link(self.parent, 'no-such-user')

    def test_approve_grants_visibility_only_after_student_approves(self):
        link = services.request_parent_link(self.parent, self.student.username)
        self.assertFalse(services.can_parent_view_student(self.parent, self.student))
        services.approve_parent_link(self.student, link.pk)
        self.assertTrue(services.can_parent_view_student(self.parent, self.student))

    def test_other_student_cannot_approve_someone_elses_link(self):
        link = services.request_parent_link(self.parent, self.student.username)
        intruder = CustomUser.objects.create_user(
            username='intruder', email='intruder@example.com', password='StrongPass!123',
            role=CustomUser.Role.STUDENT,
        )
        with self.assertRaises(ValidationError):
            services.approve_parent_link(intruder, link.pk)
        link.refresh_from_db()
        self.assertFalse(link.is_verified)

    def test_remove_link_only_by_participant(self):
        link = services.request_parent_link(self.parent, self.student.username)
        removed_by_stranger = services.remove_parent_link(self.other_parent, link.pk)
        self.assertFalse(removed_by_stranger)
        self.assertTrue(ParentStudentLink.objects.filter(pk=link.pk).exists())

        removed_by_student = services.remove_parent_link(self.student, link.pk)
        self.assertTrue(removed_by_student)
        self.assertFalse(ParentStudentLink.objects.filter(pk=link.pk).exists())

    def test_family_hub_view_requires_login(self):
        res = self.client.get(reverse('users:family_hub'))
        self.assertEqual(res.status_code, 302)

    def test_parent_can_request_link_via_view(self):
        self.client.force_login(self.parent)
        res = self.client.post(
            reverse('users:family_hub'),
            data={'action': 'request_link', 'identifier': self.student.username},
        )
        self.assertRedirects(res, reverse('users:family_hub'))
        self.assertTrue(ParentStudentLink.objects.filter(parent=self.parent, student=self.student).exists())

    def test_student_can_approve_link_via_view(self):
        link = services.request_parent_link(self.parent, self.student.username)
        self.client.force_login(self.student)
        res = self.client.post(
            reverse('users:family_hub'),
            data={'action': 'approve', 'link_id': link.pk},
        )
        self.assertRedirects(res, reverse('users:family_hub'))
        link.refresh_from_db()
        self.assertTrue(link.is_verified)

    def test_student_progress_summary_shape(self):
        summary = services.student_progress_summary(self.student)
        self.assertIn('total_attempts', summary)
        self.assertIn('lms_enrollments', summary)
        self.assertEqual(summary['total_attempts'], 0)
