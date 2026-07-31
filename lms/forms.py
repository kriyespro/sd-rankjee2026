from django import forms
from django.contrib.auth import get_user_model
from django.core.validators import URLValidator

from .models import (
    LmsAssignment,
    LmsComment,
    LmsCourse,
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
    TOPIC_EXISTING = 'existing'
    TOPIC_NEW = 'new'

    topic_mode = forms.ChoiceField(
        choices=[
            (TOPIC_EXISTING, 'Select existing topic'),
            (TOPIC_NEW, 'Create new topic'),
        ],
        initial=TOPIC_EXISTING,
        widget=forms.RadioSelect(
            attrs={'class': 'text-indigo-600 focus:ring-indigo-500'},
        ),
        label='Topic',
    )
    new_topic_title = forms.CharField(
        required=False,
        max_length=160,
        widget=forms.TextInput(attrs={'class': _INPUT, 'placeholder': 'e.g. SEO Basics'}),
        label='New topic title',
    )
    new_topic_description = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={'class': _TEXTAREA, 'rows': 2, 'placeholder': 'Short topic summary (optional)…'}
        ),
        label='New topic description',
    )

    class Meta:
        model = LmsAssignment
        fields = [
            'topic',
            'title',
            'instructions',
            'concept_video',
            'study_topic',
            'skill',
            'course',
            'due_at',
            'is_published',
        ]
        widgets = {
            'topic': forms.Select(attrs={'class': _INPUT}),
            'title': forms.TextInput(attrs={'class': _INPUT, 'placeholder': 'e.g. Meta Ads Poster'}),
            'instructions': forms.Textarea(
                attrs={'class': _TEXTAREA, 'rows': 4, 'placeholder': 'What students should submit…'}
            ),
            'concept_video': forms.Select(attrs={'class': _INPUT}),
            'study_topic': forms.Select(attrs={'class': _INPUT}),
            'skill': forms.Select(attrs={'class': _INPUT}),
            'course': forms.Select(attrs={'class': _INPUT}),
            'due_at': forms.DateTimeInput(
                attrs={'class': _INPUT, 'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M',
            ),
            'is_published': forms.CheckboxInput(
                attrs={'class': 'rounded border-slate-300 text-indigo-600 focus:ring-indigo-500'}
            ),
        }
        input_formats = {'due_at': ['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S']}
        labels = {
            'concept_video': 'Lecture recording',
            'study_topic': 'Study topic',
            'skill': 'Graded test',
            'course': 'Course',
        }
        help_texts = {
            'concept_video': 'Opens the matching video on /learning/ for students.',
            'study_topic': 'Opens the matching chapter on /admin/study/ for students.',
            'skill': 'Links a /assessment/ test — course roster results show on this assignment page.',
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        from assessment.models import Skill
        from learning.models import ConceptVideo
        from tutor_study.models import StudyTopic

        from . import services

        self.user = user
        self.fields['topic'].queryset = LmsTopic.objects.order_by('title')
        self.fields['topic'].required = False
        self.fields['topic'].empty_label = 'Choose a topic…'
        self.fields['concept_video'].queryset = ConceptVideo.objects.select_related('skill').order_by(
            'concept_tag', 'title'
        )
        self.fields['concept_video'].required = False
        self.fields['concept_video'].empty_label = 'No lecture linked…'
        self.fields['concept_video'].label_from_instance = (
            lambda obj: (
                f'[{obj.concept_tag}] {obj.title}'
                + (f' · {obj.skill.name}' if obj.skill_id else '')
            )
        )
        self.fields['study_topic'].queryset = StudyTopic.objects.select_related('parent').order_by(
            'parent__sort_order',
            'parent__title',
            'sort_order',
            'title',
        )
        self.fields['study_topic'].required = False
        self.fields['study_topic'].empty_label = 'No study topic linked…'

        self.fields['skill'].queryset = Skill.objects.filter(is_active=True).select_related('path').order_by(
            'path__level_order', 'order', 'name'
        )
        self.fields['skill'].required = False
        self.fields['skill'].empty_label = 'No graded test linked…'
        self.fields['skill'].label_from_instance = (
            lambda obj: f'{obj.name}' + (f' · {obj.path.name}' if obj.path_id else '')
        )

        self._is_admin = bool(user and services.is_lms_admin(user))
        if self._is_admin:
            self.fields['course'].queryset = LmsCourse.objects.filter(is_active=True).order_by('name')
            self.fields['course'].empty_label = 'Platform-wide (all students, no course)'
        else:
            self.fields['course'].queryset = LmsCourse.objects.filter(
                is_active=True, owner_id=getattr(user, 'id', None)
            ).order_by('name')
            self.fields['course'].empty_label = 'Choose one of your courses…'
        self.fields['course'].required = False

        # Topics are admin/office-managed curriculum categories (services.can_manage_topics) —
        # faculty pick from the existing list only, never mint a new one inline here.
        if not self._is_admin:
            del self.fields['topic_mode']
            del self.fields['new_topic_title']
            del self.fields['new_topic_description']

        self.fields['due_at'].required = False
        self.fields['due_at'].input_formats = ['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S']
        if (
            self._is_admin
            and self.instance
            and self.instance.pk
            and self.instance.topic_id
            and not self.data
        ):
            self.fields['topic_mode'].initial = self.TOPIC_EXISTING

    def clean(self):
        cleaned = super().clean()
        mode = cleaned.get('topic_mode') or self.TOPIC_EXISTING
        if mode == self.TOPIC_NEW:
            title = (cleaned.get('new_topic_title') or '').strip()
            if not title:
                self.add_error('new_topic_title', 'Enter a title for the new topic.')
            else:
                cleaned['topic'] = LmsTopic.objects.create(
                    title=title,
                    description=(cleaned.get('new_topic_description') or '').strip(),
                )
        if not self._is_admin and not cleaned.get('course'):
            self.add_error('course', 'Faculty must select one of their own courses. Create one first under Courses.')
        return cleaned


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
        label='Faculty Remark',
        widget=forms.Textarea(attrs={'class': _TEXTAREA, 'rows': 2, 'placeholder': 'Faculty remark…'}),
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


class LmsCourseForm(forms.ModelForm):
    class Meta:
        model = LmsCourse
        fields = ['name', 'owner', 'catalog_course', 'is_default_for_catalog', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': _INPUT, 'placeholder': 'e.g. Digital Marketing Batch A'}),
            'owner': forms.Select(attrs={'class': _INPUT}),
            'catalog_course': forms.Select(attrs={'class': _INPUT}),
            'is_default_for_catalog': forms.CheckboxInput(
                attrs={'class': 'rounded border-slate-300 text-indigo-600 focus:ring-indigo-500'}
            ),
            'is_active': forms.CheckboxInput(
                attrs={'class': 'rounded border-slate-300 text-indigo-600 focus:ring-indigo-500'}
            ),
        }
        labels = {
            'catalog_course': 'Paid course (/courses/) this batch delivers',
            'is_default_for_catalog': 'Auto-enroll new buyers of that course here',
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        from . import services

        self.user = user
        is_admin = bool(user and services.is_lms_admin(user))
        # Office sets up who teaches what: they assign a faculty/tutor as owner when creating a
        # course, same as admin — they just never get the monetization-linked catalog fields.
        can_assign_owner = is_admin or bool(user and services.is_lms_office(user))
        if can_assign_owner:
            # Any staff account, any flagged faculty, or any Tutor/Faculty-role marketplace
            # account (same role for LMS purposes) can be assigned to own/teach a course.
            self.fields['owner'].queryset = services.lms_owner_queryset()
            self.fields['owner'].required = False
            self.fields['owner'].empty_label = 'Platform-wide (no single owner)'
        else:
            # Faculty self-serving their own course can't reassign ownership — it's forced to
            # themselves in the view.
            del self.fields['owner']

        if is_admin:
            from core.models import Course as CatalogCourse

            self.fields['catalog_course'].queryset = CatalogCourse.objects.filter(is_active=True).order_by('title')
            self.fields['catalog_course'].required = False
            self.fields['catalog_course'].empty_label = 'Not linked to a paid catalog course'
        else:
            # Linking a batch to the sales catalog is an admin/monetization decision only.
            del self.fields['catalog_course']
            del self.fields['is_default_for_catalog']


class LmsCourseMemberForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(
            attrs={'class': _INPUT, 'placeholder': 'Student username or email', 'list': 'lms-student-options'}
        ),
        label='Student',
        help_text='Start typing to pick from the suggestion list, or paste a username/email directly.',
    )

    def clean_username(self):
        raw = self.cleaned_data['username'].strip()
        # Accept "username · email@x.com" (picked from the <datalist>) as well as a bare
        # username or a bare email — whichever the admin/office user actually typed or pasted.
        candidate = raw.split('·')[0].strip() if '·' in raw else raw
        user = User.objects.filter(username__iexact=candidate).first()
        if not user and '@' in candidate:
            user = User.objects.filter(email__iexact=candidate).first()
        if not user:
            raise forms.ValidationError(f'No student found matching "{raw}".')
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
