from django.contrib.auth.forms import UserCreationForm
from django import forms

from core.hometutor_data import PILOT_CITY
from hometutor.models import TutorProfile

from .models import CustomUser


class CustomUserCreationForm(UserCreationForm):
    PUBLIC_ROLE_CHOICES = (
        (CustomUser.Role.STUDENT, 'Student'),
        (CustomUser.Role.PARENT, 'Parent'),
        (CustomUser.Role.TUTOR, 'Tutor'),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['role'].choices = self.PUBLIC_ROLE_CHOICES

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'role')
        labels = {
            'role': 'I want to join as',
        }


class RoleSelectionForm(forms.Form):
    role = forms.ChoiceField(
        choices=[
            (CustomUser.Role.STUDENT, 'Student'),
            (CustomUser.Role.PARENT, 'Parent'),
            (CustomUser.Role.TUTOR, 'Tutor'),
        ],
        widget=forms.RadioSelect,
    )


class StudentParentOnboardingForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ('first_name', 'last_name', 'state')
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'w-full rounded-xl border border-slate-200 px-3 py-2 text-sm'}),
            'last_name': forms.TextInput(attrs={'class': 'w-full rounded-xl border border-slate-200 px-3 py-2 text-sm'}),
            'state': forms.Select(attrs={'class': 'w-full rounded-xl border border-slate-200 px-3 py-2 text-sm'}),
        }


class TutorOnboardingForm(forms.ModelForm):
    class Meta:
        model = TutorProfile
        fields = (
            'display_name',
            'city',
            'area',
            'subjects',
            'languages',
            'teaching_mode',
            'teaches_from',
            'teaches_to',
            'fee_label',
            'bio',
        )
        widgets = {
            'display_name': forms.TextInput(attrs={'class': 'w-full rounded-xl border border-slate-200 px-3 py-2 text-sm'}),
            'city': forms.TextInput(attrs={'class': 'w-full rounded-xl border border-slate-200 px-3 py-2 text-sm'}),
            'area': forms.TextInput(attrs={'class': 'w-full rounded-xl border border-slate-200 px-3 py-2 text-sm'}),
            'subjects': forms.TextInput(attrs={'class': 'w-full rounded-xl border border-slate-200 px-3 py-2 text-sm'}),
            'languages': forms.TextInput(attrs={'class': 'w-full rounded-xl border border-slate-200 px-3 py-2 text-sm'}),
            'teaching_mode': forms.Select(attrs={'class': 'w-full rounded-xl border border-slate-200 px-3 py-2 text-sm'}),
            'teaches_from': forms.NumberInput(attrs={'class': 'w-full rounded-xl border border-slate-200 px-3 py-2 text-sm', 'min': 1, 'max': 12}),
            'teaches_to': forms.NumberInput(attrs={'class': 'w-full rounded-xl border border-slate-200 px-3 py-2 text-sm', 'min': 1, 'max': 12}),
            'fee_label': forms.TextInput(attrs={'class': 'w-full rounded-xl border border-slate-200 px-3 py-2 text-sm'}),
            'bio': forms.Textarea(attrs={'class': 'w-full rounded-xl border border-slate-200 px-3 py-2 text-sm', 'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['city'].initial = self.initial.get('city') or PILOT_CITY
