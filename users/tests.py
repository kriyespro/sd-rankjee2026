from django.test import TestCase
from django.urls import reverse

from hometutor.models import TutorProfile
from .forms import CustomUserCreationForm, TutorOnboardingForm
from .models import CustomUser


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
