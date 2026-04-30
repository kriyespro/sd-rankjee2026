from django import forms

from .models import TutorLeadRequest


class TutorLeadRequestForm(forms.ModelForm):
    class Meta:
        model = TutorLeadRequest
        fields = [
            "requester_type",
            "full_name",
            "phone",
            "email",
            "city",
            "area",
            "class_grade",
            "board",
            "subjects",
            "teaching_mode",
            "budget_inr",
            "start_date_text",
            "schedule_notes",
            "additional_notes",
        ]
        widgets = {
            "requester_type": forms.Select(attrs={"class": "w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"}),
            "full_name": forms.TextInput(attrs={"class": "w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"}),
            "phone": forms.TextInput(attrs={"class": "w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"}),
            "email": forms.EmailInput(attrs={"class": "w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"}),
            "city": forms.TextInput(attrs={"class": "w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"}),
            "area": forms.TextInput(attrs={"class": "w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"}),
            "class_grade": forms.TextInput(attrs={"class": "w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"}),
            "board": forms.TextInput(attrs={"class": "w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"}),
            "subjects": forms.TextInput(
                attrs={
                    "class": "w-full rounded-xl border border-slate-200 px-3 py-2 text-sm",
                    "placeholder": "Maths, Science, English",
                }
            ),
            "teaching_mode": forms.Select(
                choices=[("", "Any"), ("ONLINE", "Online"), ("OFFLINE", "Offline"), ("HYBRID", "Hybrid")],
                attrs={"class": "w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"},
            ),
            "budget_inr": forms.NumberInput(attrs={"class": "w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"}),
            "start_date_text": forms.TextInput(
                attrs={
                    "class": "w-full rounded-xl border border-slate-200 px-3 py-2 text-sm",
                    "placeholder": "Immediate / Next week / Next month",
                }
            ),
            "schedule_notes": forms.TextInput(
                attrs={
                    "class": "w-full rounded-xl border border-slate-200 px-3 py-2 text-sm",
                    "placeholder": "Preferred timing, days, duration",
                }
            ),
            "additional_notes": forms.Textarea(
                attrs={"class": "w-full rounded-xl border border-slate-200 px-3 py-2 text-sm", "rows": 4}
            ),
        }
