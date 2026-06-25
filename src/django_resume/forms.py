from django import forms

from django_resume.models import Resume


class ResumeForm(forms.ModelForm):
    class Meta:
        model = Resume
        fields = ["name", "slug"]


class JsonResumeImportForm(forms.Form):
    file = forms.FileField(label="JSON Resume file", required=False)
    source_url = forms.URLField(label="JSON Resume URL", required=False)
    slug = forms.SlugField(max_length=Resume._meta.get_field("slug").max_length)
    name = forms.CharField(
        max_length=Resume._meta.get_field("name").max_length,
        required=False,
    )
    portable_only = forms.BooleanField(required=False)

    def clean(self):
        cleaned_data = super().clean()
        has_file = bool(cleaned_data.get("file"))
        has_url = bool(cleaned_data.get("source_url"))
        if has_file == has_url:
            raise forms.ValidationError(
                "Provide either a JSON Resume file or a JSON Resume URL."
            )
        return cleaned_data
