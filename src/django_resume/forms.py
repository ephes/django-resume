from django import forms

from django_resume.models import Resume


class ResumeForm(forms.ModelForm):
    class Meta:
        model = Resume
        fields = ["name", "slug"]
