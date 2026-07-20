from django import forms
from django.contrib.auth import get_user_model

from .models import LmsAssignment, LmsBatch, LmsComment, LmsSubmission

User = get_user_model()

_INPUT = (
    'w-full rounded-xl border border-slate-200 px-3 py-2 text-sm '
    'font-medium focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500'
)
_TEXTAREA = _INPUT


class LmsAssignmentForm(forms.ModelForm):
    class Meta:
        model = LmsAssignment
        fields = ['title', 'instructions', 'batch', 'due_at', 'is_published']
        widgets = {
            'title': forms.TextInput(attrs={'class': _INPUT, 'placeholder': 'e.g. Meta Ads Poster'}),
            'instructions': forms.Textarea(
                attrs={'class': _TEXTAREA, 'rows': 4, 'placeholder': 'What students should submit…'}
            ),
            'batch': forms.Select(attrs={'class': _INPUT}),
            'due_at': forms.DateTimeInput(
                attrs={'class': _INPUT, 'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M',
            ),
            'is_published': forms.CheckboxInput(
                attrs={'class': 'rounded border-slate-300 text-indigo-600 focus:ring-indigo-500'}
            ),
        }
        input_formats = {'due_at': ['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S']}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['batch'].queryset = LmsBatch.objects.filter(is_active=True)
        self.fields['batch'].required = False
        self.fields['batch'].empty_label = 'All students (no batch)'
        self.fields['due_at'].required = False
        self.fields['due_at'].input_formats = ['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S']


class LmsSubmissionForm(forms.ModelForm):
    class Meta:
        model = LmsSubmission
        fields = ['caption', 'image', 'file', 'video_url', 'website_url']
        widgets = {
            'caption': forms.Textarea(
                attrs={'class': _TEXTAREA, 'rows': 3, 'placeholder': 'Say something about your work…'}
            ),
            'image': forms.ClearableFileInput(
                attrs={'class': 'block w-full text-sm text-slate-600', 'accept': 'image/*'}
            ),
            'file': forms.ClearableFileInput(
                attrs={'class': 'block w-full text-sm text-slate-600', 'accept': '.pdf,application/pdf'}
            ),
            'video_url': forms.URLInput(
                attrs={'class': _INPUT, 'placeholder': 'YouTube / Drive video link'}
            ),
            'website_url': forms.URLInput(
                attrs={'class': _INPUT, 'placeholder': 'Website / portfolio URL'}
            ),
        }

    def clean(self):
        cleaned = super().clean()
        has_media = bool(
            cleaned.get('image')
            or cleaned.get('file')
            or (cleaned.get('video_url') or '').strip()
            or (cleaned.get('website_url') or '').strip()
        )
        # On edit, existing image/file may already be on instance
        if not has_media and self.instance and self.instance.pk:
            has_media = bool(
                self.instance.image
                or self.instance.file
                or (self.instance.video_url or '').strip()
                or (self.instance.website_url or '').strip()
            )
        if not has_media:
            raise forms.ValidationError('Add an image, PDF, video link, or website URL.')
        return cleaned


class LmsReviewForm(forms.Form):
    marks = forms.IntegerField(
        required=False,
        min_value=0,
        max_value=100,
        widget=forms.NumberInput(attrs={'class': _INPUT, 'placeholder': '0–100'}),
    )
    remark = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': _TEXTAREA, 'rows': 2, 'placeholder': 'Staff remark…'}),
    )
    status = forms.ChoiceField(
        choices=LmsSubmission.Status.choices,
        widget=forms.Select(attrs={'class': _INPUT}),
    )
    is_pinned = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(
            attrs={'class': 'rounded border-slate-300 text-indigo-600 focus:ring-indigo-500'}
        ),
    )


class LmsCommentForm(forms.ModelForm):
    class Meta:
        model = LmsComment
        fields = ['body']
        widgets = {
            'body': forms.TextInput(
                attrs={
                    'class': _INPUT,
                    'placeholder': 'Write a comment…',
                    'autocomplete': 'off',
                }
            ),
        }


class LmsBatchForm(forms.ModelForm):
    class Meta:
        model = LmsBatch
        fields = ['name', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': _INPUT, 'placeholder': 'e.g. Digital Marketing Batch A'}),
            'is_active': forms.CheckboxInput(
                attrs={'class': 'rounded border-slate-300 text-indigo-600 focus:ring-indigo-500'}
            ),
        }


class LmsBatchMemberForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': _INPUT, 'placeholder': 'Student username'}),
    )

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        user = User.objects.filter(username__iexact=username).first()
        if not user:
            raise forms.ValidationError('User not found.')
        return user
