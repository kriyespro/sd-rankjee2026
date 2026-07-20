from django import forms
from django.contrib.auth import get_user_model
from django.core.validators import URLValidator

from .models import (
    LmsAssignment,
    LmsBatch,
    LmsComment,
    LmsSubmission,
    LmsSubmissionUrl,
    LmsTopic,
)

User = get_user_model()

_INPUT = (
    'w-full rounded-xl border border-slate-200 px-3 py-2 text-sm '
    'font-medium focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500'
)
_TEXTAREA = _INPUT


class LmsAssignmentForm(forms.ModelForm):
    class Meta:
        model = LmsAssignment
        fields = ['topic', 'title', 'instructions', 'batch', 'due_at', 'is_published']
        widgets = {
            'topic': forms.Select(attrs={'class': _INPUT}),
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
        self.fields['topic'].queryset = LmsTopic.objects.order_by('title')
        self.fields['topic'].required = False
        self.fields['topic'].empty_label = 'No topic yet'
        self.fields['batch'].queryset = LmsBatch.objects.filter(is_active=True)
        self.fields['batch'].required = False
        self.fields['batch'].empty_label = 'All students (no batch)'
        self.fields['due_at'].required = False
        self.fields['due_at'].input_formats = ['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S']


class LmsSubmissionForm(forms.Form):
    caption = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={'class': _TEXTAREA, 'rows': 3, 'placeholder': 'Say something about your work…'}
        ),
    )

    def __init__(self, *args, instance=None, **kwargs):
        self.instance = instance
        super().__init__(*args, **kwargs)
        if instance and instance.pk and not self.data:
            self.fields['caption'].initial = instance.caption

    @property
    def url_rows(self):
        if self.data:
            return self._parse_url_rows_from_data(self.data)
        if self.instance and self.instance.pk:
            rows = [
                {'url': row.url, 'kind': row.kind}
                for row in self.instance.urls.all()
            ]
            if not rows:
                if (self.instance.video_url or '').strip():
                    rows.append({'url': self.instance.video_url.strip(), 'kind': LmsSubmissionUrl.Kind.DRIVE})
                if (self.instance.website_url or '').strip():
                    rows.append({'url': self.instance.website_url.strip(), 'kind': LmsSubmissionUrl.Kind.WEBSITE})
            if rows:
                return rows
        return [
            {'url': '', 'kind': LmsSubmissionUrl.Kind.DRIVE},
            {'url': '', 'kind': LmsSubmissionUrl.Kind.WEBSITE},
        ]

    def _parse_url_rows_from_data(self, data):
        rows = []
        i = 0
        while f'url_{i}' in data or f'url_kind_{i}' in data:
            url = (data.get(f'url_{i}') or '').strip()
            kind = (data.get(f'url_kind_{i}') or LmsSubmissionUrl.Kind.DRIVE).upper()
            if kind not in LmsSubmissionUrl.Kind.values:
                kind = LmsSubmissionUrl.Kind.DRIVE
            if url:
                rows.append({'url': url, 'kind': kind})
            i += 1
        return rows

    def clean(self):
        cleaned = super().clean()
        url_items = self._parse_url_rows_from_data(self.data)
        validator = URLValidator()
        for item in url_items:
            try:
                validator(item['url'])
            except forms.ValidationError:
                raise forms.ValidationError(f'Invalid URL: {item["url"]}')
        if not url_items:
            raise forms.ValidationError('Add at least one Google Drive or website link.')
        cleaned['url_items'] = url_items
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


class LmsTopicForm(forms.ModelForm):
    class Meta:
        model = LmsTopic
        fields = ['title', 'description']
        widgets = {
            'title': forms.TextInput(attrs={'class': _INPUT, 'placeholder': 'e.g. SEO Basics'}),
            'description': forms.Textarea(
                attrs={'class': _TEXTAREA, 'rows': 3, 'placeholder': 'Short topic summary…'}
            ),
        }
