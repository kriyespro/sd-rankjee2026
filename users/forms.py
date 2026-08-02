from django.contrib.auth.forms import UserCreationForm
from django import forms

from core.hometutor_data import PILOT_CITY
from hometutor.models import TutorProfile

from .models import CustomUser, INDIAN_STATES

def clean_phone_value(raw: str) -> str:
    """Normalize to bare 10 digits (strips spaces/dashes and +91/91/0 prefixes), then
    validate as an Indian mobile. Raises ValidationError on anything else."""
    digits = ''.join(c for c in (raw or '') if c.isdigit())
    if len(digits) == 12 and digits.startswith('91'):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith('0'):
        digits = digits[1:]
    if len(digits) != 10 or digits[0] not in '6789':
        raise forms.ValidationError('Enter a valid 10-digit Indian mobile number.')
    return digits


def phone_field(**kwargs):
    return forms.CharField(
        max_length=15,
        label=kwargs.pop('label', 'Mobile number'),
        widget=forms.TextInput(attrs={
            'class': 'w-full rounded-xl border border-slate-200 px-4 py-2.5 text-sm',
            'placeholder': 'e.g. 9876543210',
            'type': 'tel',
            'inputmode': 'tel',
            'autocomplete': 'tel',
        }),
        **kwargs,
    )


def city_field(**kwargs):
    return forms.CharField(
        max_length=60,
        label=kwargs.pop('label', 'Your city'),
        widget=forms.TextInput(attrs={
            'class': 'w-full rounded-xl border border-slate-200 px-4 py-2.5 text-sm',
            'placeholder': f'e.g. {PILOT_CITY}',
            'autocomplete': 'address-level2',
        }),
        **kwargs,
    )


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
        self.fields['email'].required = True
        self.fields['email'].widget.attrs.update({'placeholder': 'you@email.com', 'autocomplete': 'email'})
        self.fields['username'].widget.attrs.update({'placeholder': 'e.g. priya2026'})

    # Contact info mandatory for every public role (student/parent/tutor alike).
    phone = phone_field()
    city = city_field()

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'phone', 'city', 'role')
        labels = {
            'role': 'I am joining as',
            'username': 'Choose a username',
            'email': 'Your email',
        }

    def clean_phone(self):
        return clean_phone_value(self.cleaned_data['phone'])


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
    """Also the contact-info collection point for Google-signup users, who never see the
    email signup form — phone/city stay mandatory here for that path.

    For STUDENT role (pass `student=True`), also collects the academic profile
    (class level + subjects, area optional) that drives dashboard personalization."""

    SUBJECT_SUGGESTIONS = (
        'Maths', 'Science', 'Physics', 'Chemistry', 'Biology', 'English',
        'Hindi', 'Social Science', 'Computer Science', 'Accountancy', 'Economics',
    )

    phone = phone_field()
    city = city_field()

    class Meta:
        model = CustomUser
        fields = ('first_name', 'last_name', 'phone', 'city', 'state', 'class_level', 'subjects', 'area')
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

    def __init__(self, *args, student=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_student = student
        self.fields['first_name'].required = True
        self.fields['last_name'].required = False
        self.fields['state'].required = False
        self.fields['state'].choices = [('', 'Select later')] + list(INDIAN_STATES)
        base_cls = 'w-full rounded-xl border border-slate-200 px-4 py-2.5 text-sm'
        if student:
            self.fields['class_level'].required = True
            self.fields['subjects'].required = True
            self.fields['class_level'].label = 'Your class'
            self.fields['class_level'].widget = forms.Select(
                choices=[('', 'Select class')] + [(i, f'Class {i}') for i in range(1, 13)],
                attrs={'class': base_cls},
            )
            self.fields['subjects'].label = 'Subjects you want help with'
            self.fields['subjects'].widget = forms.TextInput(attrs={
                'class': base_cls,
                'placeholder': 'e.g. Maths, Science',
                'list': 'subject-suggestions',
            })
            self.fields['area'].label = 'Area / locality (optional)'
            self.fields['area'].widget = forms.TextInput(attrs={
                'class': base_cls,
                'placeholder': 'e.g. Satellite',
            })
        else:
            # Parents: contact info only — academic profile belongs to the student account.
            for name in ('class_level', 'subjects', 'area'):
                del self.fields[name]

    def clean_phone(self):
        return clean_phone_value(self.cleaned_data['phone'])


class TutorOnboardingForm(forms.ModelForm):
    QUICK_FIELDS = ('display_name', 'phone', 'city', 'subjects', 'teaching_mode')
    OPTIONAL_FIELDS = ('area', 'teaches_from', 'teaches_to', 'languages', 'fee_label', 'bio')

    # Mandatory contact number — stored on CustomUser (TutorProfile has no phone field;
    # the view copies it to user.phone / user.city on save).
    phone = phone_field()

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
        self.fields['phone'].initial = self.initial.get('phone') or ''
        for name in self.OPTIONAL_FIELDS:
            self.fields[name].required = False
        self.fields['teaches_from'].initial = self.initial.get('teaches_from') or 6
        self.fields['teaches_to'].initial = self.initial.get('teaches_to') or 12

    def clean_phone(self):
        return clean_phone_value(self.cleaned_data['phone'])
