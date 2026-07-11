from django import forms
from django.core.exceptions import ValidationError

from .models import (
    EngagementChatMessage,
    EngagementDispute,
    EngagementReview,
    DemoRequest,
    SessionAttendance,
    TutorDocument,
    TutorProfile,
)


class TutorProfileForm(forms.ModelForm):
    """Tutor-editable listing fields; staff controls verification & ratings."""

    # Fee/bio tweaks stay live — no re-review. Identity/location/subjects still need approval.
    REAPPROVAL_FIELDS = frozenset({
        'display_name',
        'profile_image',
        'city',
        'area',
        'pincode',
        'subjects',
        'teaching_mode',
        'languages',
        'classes_label',
        'teaches_from',
        'teaches_to',
    })

    class Meta:
        model = TutorProfile
        fields = [
            'display_name',
            'profile_image',
            'city',
            'area',
            'pincode',
            'subjects',
            'teaching_mode',
            'languages',
            'classes_label',
            'teaches_from',
            'teaches_to',
            'fee_label',
            'bio',
        ]
        widgets = {
            'display_name': forms.TextInput(
                attrs={
                    'class': (
                        'w-full rounded-xl border border-slate-200 px-3 py-2 text-sm '
                        'font-medium focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500'
                    ),
                }
            ),
            'profile_image': forms.ClearableFileInput(
                attrs={
                    'class': 'block w-full text-sm text-slate-600 file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100'
                }
            ),
            'city': forms.TextInput(
                attrs={
                    'class': (
                        'w-full rounded-xl border border-slate-200 px-3 py-2 text-sm '
                        'font-medium focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500'
                    ),
                }
            ),
            'area': forms.TextInput(
                attrs={
                    'class': (
                        'w-full rounded-xl border border-slate-200 px-3 py-2 text-sm '
                        'font-medium focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500'
                    ),
                }
            ),
            'pincode': forms.TextInput(
                attrs={
                    'class': (
                        'w-full rounded-xl border border-slate-200 px-3 py-2 text-sm '
                        'font-medium focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500'
                    ),
                    'maxlength': 10,
                }
            ),
            'subjects': forms.TextInput(
                attrs={
                    'placeholder': 'e.g. Math, Physics',
                    'class': (
                        'w-full rounded-xl border border-slate-200 px-3 py-2 text-sm '
                        'font-medium focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500'
                    ),
                }
            ),
            'teaching_mode': forms.Select(
                attrs={
                    'class': (
                        'w-full rounded-xl border border-slate-200 px-3 py-2 text-sm '
                        'font-medium focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500'
                    ),
                }
            ),
            'languages': forms.TextInput(
                attrs={
                    'placeholder': 'e.g. English, Hindi',
                    'class': (
                        'w-full rounded-xl border border-slate-200 px-3 py-2 text-sm '
                        'font-medium focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500'
                    ),
                }
            ),
            'classes_label': forms.TextInput(
                attrs={
                    'placeholder': 'e.g. Class 9–12 · CBSE',
                    'class': (
                        'w-full rounded-xl border border-slate-200 px-3 py-2 text-sm '
                        'font-medium focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500'
                    ),
                }
            ),
            'teaches_from': forms.NumberInput(
                attrs={
                    'min': 1,
                    'max': 12,
                    'class': (
                        'w-full rounded-xl border border-slate-200 px-3 py-2 text-sm '
                        'font-medium focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500'
                    ),
                }
            ),
            'teaches_to': forms.NumberInput(
                attrs={
                    'min': 1,
                    'max': 12,
                    'class': (
                        'w-full rounded-xl border border-slate-200 px-3 py-2 text-sm '
                        'font-medium focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500'
                    ),
                }
            ),
            'fee_label': forms.TextInput(
                attrs={
                    'placeholder': 'e.g. ₹6,500/mo',
                    'class': (
                        'w-full rounded-xl border border-slate-200 px-3 py-2 text-sm '
                        'font-medium focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500'
                    ),
                }
            ),
            'bio': forms.Textarea(
                attrs={
                    'rows': 5,
                    'class': (
                        'w-full rounded-xl border border-slate-200 px-3 py-2 text-sm '
                        'font-medium focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500'
                    ),
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['fee_label'].label = 'Monthly fee'
        self.fields['fee_label'].help_text = (
            'Shown on your public card. Example: ₹6,500/mo (typical home tuition ₹5,000–₹10,000).'
        )
        if self.instance.pk:
            self._initial_status = self.instance.verification_status
        else:
            self._initial_status = None

    def clean(self):
        cleaned = super().clean()
        tf = cleaned.get('teaches_from')
        tt = cleaned.get('teaches_to')
        if tf is not None and tt is not None and tf > tt:
            raise ValidationError('Class range: "from" cannot be greater than "to".')
        return cleaned

    def save(self, commit=True, *, user=None, submit_for_review=True):
        obj = super().save(commit=False)
        if user is not None:
            obj.user = user
        is_new = obj.pk is None
        prev = getattr(self, '_initial_status', None)
        if is_new:
            obj.verification_status = (
                TutorProfile.VerificationStatus.PENDING
                if submit_for_review
                else TutorProfile.VerificationStatus.DRAFT
            )
        elif prev == TutorProfile.VerificationStatus.APPROVED:
            changed = set(self.changed_data) & self.REAPPROVAL_FIELDS
            if changed:
                obj.verification_status = TutorProfile.VerificationStatus.PENDING
        elif prev == TutorProfile.VerificationStatus.DRAFT and submit_for_review:
            obj.verification_status = TutorProfile.VerificationStatus.PENDING
        if commit:
            obj.save()
            self.save_m2m()
        return obj


class TutorDocumentForm(forms.ModelForm):
    class Meta:
        model = TutorDocument
        fields = ['label', 'file']
        widgets = {
            'label': forms.TextInput(
                attrs={
                    'placeholder': 'e.g. Govt ID, degree certificate',
                    'class': (
                        'w-full rounded-xl border border-slate-200 px-3 py-2 text-sm '
                        'font-medium focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500'
                    ),
                }
            ),
            'file': forms.ClearableFileInput(
                attrs={'class': 'block w-full text-sm text-slate-600 file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100'}
            ),
        }

    def clean(self):
        data = super().clean()
        label = (data.get('label') or '').strip()
        f = data.get('file')
        if label and not f:
            raise ValidationError('Please choose a file for this document label.')
        if f and not label:
            raise ValidationError('Please add a label for this document.')
        return data


class DemoRequestForm(forms.ModelForm):
    class Meta:
        model = DemoRequest
        fields = ['message', 'contact_phone']
        widgets = {
            'message': forms.Textarea(
                attrs={
                    'rows': 4,
                    'placeholder': 'Class, board, preferred days…',
                    'class': (
                        'w-full rounded-xl border border-slate-200 px-3 py-2 text-sm '
                        'font-medium focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500'
                    ),
                }
            ),
            'contact_phone': forms.TextInput(
                attrs={
                    'placeholder': 'WhatsApp / phone (recommended)',
                    'class': (
                        'w-full rounded-xl border border-slate-200 px-3 py-2 text-sm '
                        'font-medium focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500'
                    ),
                }
            ),
        }

    def clean(self):
        cleaned = super().clean()
        tutor = getattr(self, '_tutor', None)
        requester = getattr(self, '_requester', None)
        if tutor and requester and DemoRequest.objects.filter(
            tutor=tutor,
            requester=requester,
            status=DemoRequest.Status.PENDING,
        ).exists():
            raise ValidationError('You already have a pending demo request for this tutor.')
        return cleaned


class DemoAcceptForm(forms.Form):
    scheduled_at = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={
                'type': 'datetime-local',
                'class': (
                    'w-full rounded-xl border border-slate-200 px-3 py-2 text-sm '
                    'font-medium focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500'
                ),
            },
            format='%Y-%m-%dT%H:%M',
        ),
        input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S'],
    )


class DemoDeclineForm(forms.Form):
    decline_reason = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                'rows': 2,
                'class': (
                    'w-full rounded-xl border border-slate-200 px-3 py-2 text-sm '
                    'font-medium focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500'
                ),
            }
        ),
    )


class SessionAttendanceForm(forms.ModelForm):
    class Meta:
        model = SessionAttendance
        fields = ['scheduled_for', 'status', 'tutor_note']
        widgets = {
            'scheduled_for': forms.DateTimeInput(
                attrs={
                    'type': 'datetime-local',
                    'class': (
                        'w-full rounded-xl border border-slate-200 px-3 py-2 text-sm '
                        'font-medium focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500'
                    ),
                },
                format='%Y-%m-%dT%H:%M',
            ),
            'status': forms.Select(
                attrs={
                    'class': (
                        'w-full rounded-xl border border-slate-200 px-3 py-2 text-sm '
                        'font-medium focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500'
                    ),
                }
            ),
            'tutor_note': forms.Textarea(
                attrs={
                    'rows': 2,
                    'class': (
                        'w-full rounded-xl border border-slate-200 px-3 py-2 text-sm '
                        'font-medium focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500'
                    ),
                }
            ),
        }
        input_formats = {'scheduled_for': ['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S']}


class EngagementReviewForm(forms.ModelForm):
    class Meta:
        model = EngagementReview
        fields = ['rating', 'comment']
        widgets = {
            'rating': forms.Select(
                choices=[(5, '5 - Excellent'), (4, '4 - Good'), (3, '3 - Average'), (2, '2 - Weak'), (1, '1 - Poor')],
                attrs={
                    'class': (
                        'w-full rounded-xl border border-slate-200 px-3 py-2 text-sm '
                        'font-medium focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500'
                    ),
                },
            ),
            'comment': forms.Textarea(
                attrs={
                    'rows': 3,
                    'class': (
                        'w-full rounded-xl border border-slate-200 px-3 py-2 text-sm '
                        'font-medium focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500'
                    ),
                },
            ),
        }


class EngagementChatMessageForm(forms.ModelForm):
    class Meta:
        model = EngagementChatMessage
        fields = ['body', 'support_flag']
        widgets = {
            'body': forms.Textarea(
                attrs={
                    'rows': 2,
                    'placeholder': 'Type your message...',
                    'class': (
                        'w-full rounded-xl border border-slate-200 px-3 py-2 text-sm '
                        'font-medium focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500'
                    ),
                }
            ),
        }


class EngagementDisputeForm(forms.ModelForm):
    class Meta:
        model = EngagementDispute
        fields = ['reason']
        widgets = {
            'reason': forms.Textarea(
                attrs={
                    'rows': 3,
                    'placeholder': 'Explain the issue (timing, attendance, payment, behavior, etc.)',
                    'class': (
                        'w-full rounded-xl border border-slate-200 px-3 py-2 text-sm '
                        'font-medium focus:ring-2 focus:ring-rose-500 focus:border-rose-500'
                    ),
                }
            ),
        }
