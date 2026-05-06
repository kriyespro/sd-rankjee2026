import json

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import URLValidator

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
    h1_tag = forms.CharField(
        required=False,
        max_length=220,
        help_text="Main headline for the post.",
    )
    intro_text = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": "Opening paragraph under the H1 heading.",
            }
        ),
    )
    sections_payload = forms.CharField(required=False, widget=forms.HiddenInput())
    links_payload = forms.CharField(required=False, widget=forms.HiddenInput())

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Allow "paste-only" publishing (especially for staff/superuser workflows).
        # BlogPost.save() already auto-derives title/slug/excerpt/meta from body when blank.
        self.fields["title"].required = False
        self.fields["title"].help_text = (
            "Optional. If blank, we'll auto-extract the title from the first markdown heading in the body."
        )
        self.fields["body"].required = False
        self.fields["body"].help_text = (
            "Optional manual markdown override. Leave blank to auto-build from H1, sections, and links below."
        )
        self.fields["body"].widget.attrs.setdefault(
            "placeholder",
            "Optional: add full markdown body manually. If empty, the structured editor data is used.",
        )
        self._parsed_sections = []
        self._parsed_links = []

    def _parse_json_items(self, raw_value, field_name):
        if not raw_value:
            return []
        try:
            parsed = json.loads(raw_value)
        except json.JSONDecodeError:
            raise forms.ValidationError("Invalid structured content data. Please re-add sections/links.")
        if not isinstance(parsed, list):
            raise forms.ValidationError("Structured content must be a list.")
        return parsed

    def _clean_sections(self, sections):
        cleaned = []
        for row in sections:
            if not isinstance(row, dict):
                continue
            h2 = (row.get("h2") or "").strip()
            content = (row.get("content") or "").strip()
            if not h2 and not content:
                continue
            if not h2:
                raise forms.ValidationError("Each section needs an H2 heading.")
            cleaned.append({"h2": h2[:220], "content": content})
        return cleaned

    def _clean_links(self, links):
        cleaned = []
        validator = URLValidator()
        for row in links:
            if not isinstance(row, dict):
                continue
            label = (row.get("label") or "").strip()
            url = (row.get("url") or "").strip()
            if not label and not url:
                continue
            if not url:
                raise forms.ValidationError("Each link needs a URL.")
            try:
                validator(url)
            except DjangoValidationError:
                raise forms.ValidationError(f"Invalid URL: {url}")
            cleaned.append({"label": label[:180], "url": url})
        return cleaned

    def _compose_body(self, h1_tag, intro_text, sections, links):
        parts = []
        if h1_tag:
            parts.append(f"# {h1_tag}")
        if intro_text:
            parts.append(intro_text)
        for section in sections:
            parts.append(f"## {section['h2']}")
            if section["content"]:
                parts.append(section["content"])
        if links:
            parts.append("### Useful links")
            for link in links:
                label = link["label"] or link["url"]
                parts.append(f"- [{label}]({link['url']})")
        return "\n\n".join(parts).strip()

    def clean(self):
        cleaned = super().clean()
        h1_tag = (cleaned.get("h1_tag") or "").strip()
        intro_text = (cleaned.get("intro_text") or "").strip()
        manual_body = (cleaned.get("body") or "").strip()

        sections_raw = cleaned.get("sections_payload")
        links_raw = cleaned.get("links_payload")
        sections = self._clean_sections(self._parse_json_items(sections_raw, "sections_payload"))
        links = self._clean_links(self._parse_json_items(links_raw, "links_payload"))

        auto_body = self._compose_body(h1_tag, intro_text, sections, links)
        if not manual_body and not auto_body:
            raise forms.ValidationError(
                "Add a manual body or provide H1/sections content to generate the post body."
            )

        self._parsed_sections = sections
        self._parsed_links = links
        cleaned["body"] = manual_body or auto_body
        return cleaned
