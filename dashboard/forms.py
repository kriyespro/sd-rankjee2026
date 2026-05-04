from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

from assessment.models import Question, Skill, SkillPath
from core.models import EarningTask
from learning.models import ConceptVideo

from blog.models import BlogPost

from .models import StudentDailyClassLog

User = get_user_model()


BASE_INPUT_CLASS = "w-full rounded-xl border border-slate-200 px-4 py-2.5 text-base bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-500"
BASE_TEXTAREA_CLASS = "w-full rounded-xl border border-slate-200 px-4 py-2.5 text-base bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-500"
BASE_SELECT_CLASS = "w-full rounded-xl border border-slate-200 px-4 py-2.5 text-base bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-500"


class _StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            w = field.widget
            if isinstance(w, (forms.TextInput, forms.EmailInput, forms.URLInput, forms.NumberInput, forms.PasswordInput)):
                w.attrs.setdefault("class", BASE_INPUT_CLASS)
            elif isinstance(w, forms.Textarea):
                w.attrs.setdefault("class", BASE_TEXTAREA_CLASS)
                w.attrs.setdefault("rows", 4)
            elif isinstance(w, (forms.Select, forms.SelectMultiple)):
                w.attrs.setdefault("class", BASE_SELECT_CLASS)
            elif isinstance(w, forms.ClearableFileInput):
                w.attrs.setdefault("class", BASE_INPUT_CLASS)


class SkillPathForm(_StyledModelForm):
    class Meta:
        model = SkillPath
        fields = ("name", "description", "level_order", "is_active")


class SkillForm(_StyledModelForm):
    class Meta:
        model = Skill
        fields = ("path", "name", "description", "order", "is_active")


class QuestionForm(_StyledModelForm):
    class Meta:
        model = Question
        fields = (
            "skill",
            "question_set",
            "text",
            "concept_tag",
            "explanation",
            "difficulty",
            "option_a",
            "option_b",
            "option_c",
            "option_d",
            "correct_option",
        )


class ConceptVideoForm(_StyledModelForm):
    class Meta:
        model = ConceptVideo
        fields = (
            "skill",
            "title",
            "concept_tag",
            "video_url",
            "thumbnail",
            "duration_seconds",
            "text_summary",
        )


class VideoQuestionImportForm(forms.Form):
    skill = forms.ModelChoiceField(queryset=Skill.objects.filter(is_active=True).order_by("name"), required=False)
    concept_tag = forms.CharField(max_length=50, required=False)
    csv_file = forms.FileField(required=False)
    csv_text = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 10,
                "placeholder": "Paste CSV rows here...",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["skill"].widget.attrs.setdefault("class", BASE_SELECT_CLASS)
        self.fields["concept_tag"].widget.attrs.setdefault("class", BASE_INPUT_CLASS)
        self.fields["csv_file"].widget.attrs.setdefault("class", BASE_INPUT_CLASS)
        self.fields["csv_text"].widget.attrs.setdefault("class", BASE_TEXTAREA_CLASS)

    def clean(self):
        cleaned = super().clean()
        csv_file = cleaned.get("csv_file")
        csv_text = (cleaned.get("csv_text") or "").strip()
        if not csv_file and not csv_text:
            raise forms.ValidationError("Provide either a CSV file upload or pasted CSV text.")
        return cleaned


class StudentDailyClassLogForm(_StyledModelForm):
    class Meta:
        model = StudentDailyClassLog
        fields = ("log_date", "topic", "details", "attendance")
        widgets = {
            "log_date": forms.DateInput(attrs={"type": "date"}),
        }


class EarningTaskForm(_StyledModelForm):
    class Meta:
        model = EarningTask
        fields = (
            "title",
            "description",
            "reward_amount",
            "required_skill",
            "is_active",
            "auto_approve_domain",
        )


class VipManualUserForm(forms.Form):
    username = forms.CharField(max_length=150)
    email = forms.EmailField(required=False)
    password1 = forms.CharField(widget=forms.PasswordInput)
    password2 = forms.CharField(widget=forms.PasswordInput, label="Confirm password")
    role = forms.ChoiceField(
        choices=[
            (User.Role.STUDENT, "Student"),
            (User.Role.TUTOR, "Tutor"),
        ],
        widget=forms.RadioSelect,
    )
    attach_my_referral = forms.BooleanField(
        required=False,
        initial=True,
        label="Count toward my referrals",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            w = field.widget
            if isinstance(w, forms.RadioSelect):
                continue
            elif isinstance(w, (forms.TextInput, forms.EmailInput, forms.PasswordInput)):
                w.attrs.setdefault("class", BASE_INPUT_CLASS)
            elif isinstance(w, (forms.Select, forms.SelectMultiple)):
                w.attrs.setdefault("class", BASE_SELECT_CLASS)

    def clean_username(self):
        u = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=u).exists():
            raise forms.ValidationError("That username is already taken.")
        return u

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("That email is already registered.")
        return email

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Passwords do not match.")
        if p1:
            try:
                validate_password(p1)
            except DjangoValidationError as e:
                for msg in e.messages:
                    self.add_error("password1", msg)
        return cleaned


class VipBlogPostForm(_StyledModelForm):
    slug = forms.SlugField(required=False)

    class Meta:
        model = BlogPost
        fields = (
            "title",
            "slug",
            "excerpt",
            "body",
            "category",
            "meta_title",
            "meta_description",
        )

