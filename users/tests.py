from django.test import TestCase
from django.urls import reverse

from hometutor.models import TutorProfile
from .forms import CustomUserCreationForm
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

    def test_dashboard_redirects_to_onboarding_when_incomplete(self):
        self.client.force_login(self.user)
        res = self.client.get(reverse('dashboard:index'))
        self.assertRedirects(res, reverse('users:onboarding_role'))

    def test_student_profile_onboarding_marks_complete(self):
        self.client.force_login(self.user)
        res = self.client.post(
            reverse('users:onboarding_profile'),
            data={'first_name': 'Demo', 'last_name': 'Student', 'state': 'GJ'},
        )
        self.user.refresh_from_db()
        self.assertTrue(self.user.onboarding_completed)
        self.assertRedirects(res, reverse('dashboard:index'))

    def test_tutor_profile_onboarding_creates_pending_tutor_profile(self):
        self.user.role = CustomUser.Role.TUTOR
        self.user.save(update_fields=['role'])
        self.client.force_login(self.user)
        res = self.client.post(
            reverse('users:onboarding_profile'),
            data={
                'display_name': 'Tutor One',
                'city': 'Ahmedabad',
                'area': 'Satellite',
                'subjects': 'Math, Science',
                'languages': 'English, Hindi',
                'teaching_mode': TutorProfile.TeachingMode.ONLINE,
                'teaches_from': 6,
                'teaches_to': 10,
                'fee_label': 'from ₹5000/mo',
                'bio': 'Result-driven tutor.',
            },
        )
        self.user.refresh_from_db()
        profile = TutorProfile.objects.filter(user=self.user).first()
        self.assertIsNotNone(profile)
        self.assertEqual(profile.verification_status, TutorProfile.VerificationStatus.PENDING)
        self.assertTrue(self.user.onboarding_completed)
        self.assertRedirects(res, reverse('hometutor:my_profile'), fetch_redirect_response=False)
