from django import forms

from .models import AssignmentSubmission, StudyAssignment, StudyMaterial


class StudyMaterialForm(forms.ModelForm):
    class Meta:
        model = StudyMaterial
        fields = ('title', 'body', 'attachment', 'is_published')
        widgets = {
            'title': forms.TextInput(attrs={'class': 'w-full rounded-xl border border-slate-200 px-4 py-3'}),
            'body': forms.Textarea(attrs={'rows': 12, 'class': 'w-full rounded-xl border border-slate-200 px-4 py-3'}),
            'attachment': forms.ClearableFileInput(attrs={'class': 'block w-full text-sm text-slate-600'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'rounded border-slate-300'}),
        }


class StudyAssignmentForm(forms.ModelForm):
    due_at = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(
            attrs={'type': 'datetime-local', 'class': 'w-full rounded-xl border border-slate-200 px-4 py-3'},
            format='%Y-%m-%dT%H:%M',
        ),
        input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f'],
    )

    def __init__(self, *args, tutor=None, **kwargs):
        super().__init__(*args, **kwargs)
        if tutor is not None:
            self.fields['material'].queryset = StudyMaterial.objects.filter(tutor=tutor)
        self.fields['instructions'].widget.attrs.update(
            {'rows': 6, 'class': 'w-full rounded-xl border border-slate-200 px-4 py-3'}
        )
        self.fields['title'].widget.attrs.update({'class': 'w-full rounded-xl border border-slate-200 px-4 py-3'})
        self.fields['material'].widget.attrs.update({'class': 'w-full rounded-xl border border-slate-200 px-4 py-3'})
        self.fields['skill'].widget.attrs.update({'class': 'w-full rounded-xl border border-slate-200 px-4 py-3'})

    class Meta:
        model = StudyAssignment
        fields = ('title', 'instructions', 'material', 'skill', 'due_at')


class AssignmentSubmissionForm(forms.ModelForm):
    class Meta:
        model = AssignmentSubmission
        fields = ('drive_url',)
        widgets = {
            'drive_url': forms.URLInput(
                attrs={
                    'class': 'w-full rounded-xl border border-slate-200 px-4 py-3',
                    'placeholder': 'https://drive.google.com/file/d/...',
                }
            ),
        }


class AssignmentSubmissionForm(forms.ModelForm):
    class Meta:
        model = AssignmentSubmission
        fields = ('drive_url',)
