from django import forms
from django.core.exceptions import ValidationError

from .models import ServerPackage


class StudentServerBuyForm(forms.Form):
    domain_name = forms.CharField(
        max_length=255,
        label="Domain name",
        help_text="The domain you want configured on the server (e.g. example.com).",
    )
    package = forms.ModelChoiceField(
        label="Server setup",
        queryset=ServerPackage.objects.none(),
        empty_label=None,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["package"].queryset = ServerPackage.objects.filter(is_active=True).order_by(
            "sort_order", "id"
        )

    def clean_domain_name(self):
        raw = (self.cleaned_data.get("domain_name") or "").strip().lower()
        if not raw or " " in raw or "/" in raw:
            raise ValidationError("Enter a valid domain name (no spaces or paths).")
        return raw
