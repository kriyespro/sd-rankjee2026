from django.contrib.auth.forms import UserCreationForm
from django import forms

from core.hometutor_data import PILOT_CITY
from hometutor.models import TutorProfile

from .models import CustomUser, INDIAN_STATES


class ParentLinkRequestForm(forms.Form):
    identifier = forms.CharField(
        max_length=150,
        label="Student's username or email",
        widget=forms.TextInput(attrs={
            'class': 'w-full rounded-xl border border-slate-200 px-4 py-2.5 text-sm',
            'placeholder': 'e.g. ravi_kumar or ravi@example.com',
        }),
    )


class CustomUserCreationForm(UserCreationForm):
    PUBLIC_ROLE_CHOICES = (
        (CustomUser.Role.STUDENT, 'Student — learn & practice'),
        (CustomUser.Role.PARENT, 'Parent — find tutors for my child'),
        (CustomUser.Role.TUTOR, 'Tutor — teach & earn'),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['role'].choices = self.PUBLIC_ROLE_CHOICES
        self.fields['role'].widget = forms.RadioSelect()
        self.fields['role'].initial = CustomUser.Role.STUDENT
        self.fields['username'].help_text = 'Pick a simple username — letters and numbers are fine.'
        self.fields['email'].widget.attrs.update({'placeholder': 'you@email.com'})
        self.fields['username'].widget.attrs.update({'placeholder': 'e.g. priya2026'})

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'role')
        labels = {
            'role': 'I am joining as',
            'username': 'Choose a username',
            'email': 'Your email',
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
            'first_name': forms.TextInput(attrs={
                'class': 'w-full rounded-xl border border-slate-200 px-4 py-2.5 text-sm',
                'placeholder': 'e.g. Priya',
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'w-full rounded-xl border border-slate-200 px-4 py-2.5 text-sm',
                'placeholder': 'Optional',
            }),
            'state': forms.Select(attrs={'class': 'w-full rounded-xl border border-slate-200 px-4 py-2.5 text-sm'}),
        }
        labels = {
            'first_name': 'Your first name',
            'last_name': 'Last name (optional)',
            'state': 'Your state (optional)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['first_name'].required = True
        self.fields['last_name'].required = False
        self.fields['state'].required = False
        self.fields['state'].choices = [('', 'Select later')] + list(INDIAN_STATES)


class TutorOnboardingForm(forms.ModelForm):
    QUICK_FIELDS = ('display_name', 'city', 'subjects', 'teaching_mode')
    OPTIONAL_FIELDS = ('area', 'teaches_from', 'teaches_to', 'languages', 'fee_label', 'bio')

    class Meta:
        model = TutorProfile
        fields = (
            'display_name', 'city', 'subjects', 'teaching_mode',
            'area', 'teaches_from', 'teaches_to', 'languages', 'fee_label', 'bio',
        )
        widgets = {
            'display_name': forms.TextInput(attrs={
                'class': 'w-full rounded-xl border border-slate-200 px-4 py-2.5 text-sm',
                'placeholder': 'Name students will see',
            }),
            'city': forms.TextInput(attrs={
                'class': 'w-full rounded-xl border border-slate-200 px-4 py-2.5 text-sm',
                'placeholder': 'e.g. Ahmedabad',
            }),
            'area': forms.TextInput(attrs={
                'class': 'w-full rounded-xl border border-slate-200 px-4 py-2.5 text-sm',
                'placeholder': 'e.g. Satellite (optional)',
            }),
            'subjects': forms.TextInput(attrs={
                'class': 'w-full rounded-xl border border-slate-200 px-4 py-2.5 text-sm',
                'placeholder': 'Math, Science, English',
            }),
            'languages': forms.TextInput(attrs={
                'class': 'w-full rounded-xl border border-slate-200 px-4 py-2.5 text-sm',
                'placeholder': 'English, Hindi (optional)',
            }),
            'teaching_mode': forms.Select(attrs={'class': 'w-full rounded-xl border border-slate-200 px-4 py-2.5 text-sm'}),
            'teaches_from': forms.NumberInput(attrs={'class': 'w-full rounded-xl border border-slate-200 px-4 py-2.5 text-sm', 'min': 1, 'max': 12}),
            'teaches_to': forms.NumberInput(attrs={'class': 'w-full rounded-xl border border-slate-200 px-4 py-2.5 text-sm', 'min': 1, 'max': 12}),
            'fee_label': forms.TextInput(attrs={
                'class': 'w-full rounded-xl border border-slate-200 px-4 py-2.5 text-sm',
                'placeholder': 'e.g. from ₹5000/month (optional)',
            }),
            'bio': forms.Textarea(attrs={
                'class': 'w-full rounded-xl border border-slate-200 px-4 py-2.5 text-sm',
                'rows': 3,
                'placeholder': 'A short intro — you can add more later.',
            }),
        }
        labels = {
            'display_name': 'Your name on the listing',
            'city': 'City you teach in',
            'subjects': 'Subjects you teach',
            'teaching_mode': 'How do you teach?',
            'area': 'Area / locality',
            'teaches_from': 'From class',
            'teaches_to': 'Up to class',
            'languages': 'Languages',
            'fee_label': 'Fee (rough idea)',
            'bio': 'Short bio',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['city'].initial = self.initial.get('city') or PILOT_CITY
        for name in self.OPTIONAL_FIELDS:
            self.fields[name].required = False
        self.fields['teaches_from'].initial = self.initial.get('teaches_from') or 6
        self.fields['teaches_to'].initial = self.initial.get('teaches_to') or 12
