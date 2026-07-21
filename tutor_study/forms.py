from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q

from .body_format import normalize_study_body_text
from .models import AssignmentSubmission, StudyAssignment, StudyMaterial, StudyTopic


class StudyMaterialForm(forms.ModelForm):
    def __init__(self, *args, tutor_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tutor_user = tutor_user
        _ctrl = 'w-full rounded-lg border border-[#dadce0] px-4 py-3 text-sm text-[#202124] focus:border-[#1a73e8] focus:ring-1 focus:ring-[#1a73e8] outline-none'
        self.fields['study_topic'].widget.attrs.update({'class': _ctrl})
        if tutor_user is not None:
            self.fields['study_topic'].queryset = StudyTopic.objects.filter(
                Q(tutor=tutor_user) | Q(tutor__isnull=True)
            ).select_related('parent')
            self.fields['study_topic'].required = False
            self.fields['study_topic'].empty_label = 'General'

    def clean_body(self):
        """Normalise line endings so Windows / JSON copy-paste never stores literal \\r\\n."""
        return normalize_study_body_text(self.cleaned_data.get('body', '') or '')

    def clean_study_topic(self):
        topic = self.cleaned_data.get('study_topic')
        if not topic or not self.tutor_user:
            return topic
        if topic.tutor_id and topic.tutor_id != self.tutor_user.pk:
            raise ValidationError('Choose the shared catalog or a topic you created.')
        return topic

    class Meta:
        model = StudyMaterial
        fields = ('title', 'body', 'attachment', 'is_published', 'study_topic')
        widgets = {
            'title': forms.TextInput(
                attrs={
                    'class': 'w-full rounded-lg border border-[#dadce0] px-4 py-3 text-sm text-[#202124] placeholder:text-[#80868b] focus:border-[#1a73e8] focus:ring-1 focus:ring-[#1a73e8] outline-none transition-shadow',
                }
            ),
            'body': forms.Textarea(
                attrs={
                    'rows': 12,
                    'class': 'w-full rounded-lg border border-[#dadce0] px-4 py-3 text-sm text-[#202124] placeholder:text-[#80868b] focus:border-[#1a73e8] focus:ring-1 focus:ring-[#1a73e8] outline-none transition-shadow',
                }
            ),
            'attachment': forms.ClearableFileInput(attrs={'class': 'block w-full text-sm text-[#5f6368]'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'rounded border-[#dadce0] text-[#1a73e8]'}),
        }


class StudyAssignmentForm(forms.ModelForm):
    due_at = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(
            attrs={
                'type': 'datetime-local',
                'class': 'w-full rounded-lg border border-[#dadce0] px-4 py-3 text-sm text-[#202124] focus:border-[#1a73e8] focus:ring-1 focus:ring-[#1a73e8] outline-none',
            },
            format='%Y-%m-%dT%H:%M',
        ),
        input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f'],
    )

    def __init__(self, *args, tutor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._tutor = tutor
        _ctrl = 'w-full rounded-lg border border-[#dadce0] px-4 py-3 text-sm text-[#202124] focus:border-[#1a73e8] focus:ring-1 focus:ring-[#1a73e8] outline-none'
        if tutor is not None:
            self.fields['material'].queryset = StudyMaterial.objects.filter(tutor=tutor)
            self.fields['study_topic'].queryset = StudyTopic.objects.filter(
                Q(tutor=tutor) | Q(tutor__isnull=True)
            ).select_related('parent')
            self.fields['study_topic'].required = False
            self.fields['study_topic'].empty_label = 'General'
        else:
            self.fields['study_topic'].queryset = StudyTopic.objects.none()
        self.fields['study_topic'].widget.attrs.update({'class': _ctrl})
        self.fields['instructions'].widget.attrs.update({'rows': 6, 'class': _ctrl})
        self.fields['title'].widget.attrs.update({'class': _ctrl})
        self.fields['material'].widget.attrs.update({'class': _ctrl})
        self.fields['skill'].widget.attrs.update({'class': _ctrl})

    def clean_study_topic(self):
        topic = self.cleaned_data.get('study_topic')
        if not topic or not self._tutor:
            return topic
        if topic.tutor_id and topic.tutor_id != self._tutor.pk:
            raise ValidationError('Choose the shared catalog or a topic you created.')
        return topic

    class Meta:
        model = StudyAssignment
        fields = ('title', 'instructions', 'material', 'skill', 'due_at', 'study_topic')


class AssignmentSubmissionForm(forms.ModelForm):
    class Meta:
        model = AssignmentSubmission
        fields = ('drive_url',)
        widgets = {
            'drive_url': forms.URLInput(
                attrs={
                    'class': 'w-full rounded-lg border border-[#dadce0] px-4 py-3 text-sm text-[#202124] placeholder:text-[#80868b] focus:border-[#1a73e8] focus:ring-1 focus:ring-[#1a73e8] outline-none',
                    'placeholder': 'https://drive.google.com/file/d/...',
                }
            ),
        }
