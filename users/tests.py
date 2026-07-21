from django.test import RequestFactory, TestCase
from django.urls import reverse

from hometutor.models import TutorProfile
from .forms import CustomUserCreationForm
from .models import CustomUser
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
            data={'first_name': 'Demo', 'last_name': '', 'state': ''},
        )
        self.user.refresh_from_db()
        self.assertTrue(self.user.onboarding_completed)
        self.assertRedirects(res, reverse('dashboard:index'))

    def test_student_can_skip_profile_onboarding(self):
        self.client.force_login(self.user)
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
