from django import forms

from assessment.models import Question, Skill, SkillPath
from core.models import EarningTask
from learning.models import ConceptVideo


BASE_INPUT_CLASS = "w-full rounded-xl border border-slate-200 px-4 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-500"
BASE_TEXTAREA_CLASS = "w-full rounded-xl border border-slate-200 px-4 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-500"
BASE_SELECT_CLASS = "w-full rounded-xl border border-slate-200 px-4 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-500"


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

