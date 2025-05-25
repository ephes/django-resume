from typing import Type
from django import forms
from django_resume.plugins.base import ListPlugin, ListItemFormMixin, ContextDict


class CertificationForm(ListItemFormMixin, forms.Form):
    """Form for individual certification entries."""

    name = forms.CharField(
        label="Certification Name",
        max_length=200,
        help_text="e.g., AWS Certified Solutions Architect",
    )
    organization = forms.CharField(
        label="Issuing Organization",
        max_length=200,
        help_text="e.g., Amazon Web Services",
    )
    issue_date = forms.CharField(
        label="Issue Date", widget=forms.DateInput(attrs={"type": "date"})
    )
    expiration_date = forms.CharField(
        label="Expiration Date",
        widget=forms.DateInput(attrs={"type": "date"}),
        required=False,
        help_text="Leave blank if certification doesn't expire",
    )
    credential_id = forms.CharField(
        label="Credential ID",
        max_length=100,
        required=False,
        help_text="Certificate number or ID (optional)",
    )
    position = forms.IntegerField(widget=forms.NumberInput(), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_initial_position()

    @staticmethod
    def get_max_position(items: list[dict]) -> int:
        """Return the maximum position value from the existing items."""
        positions = [item.get("position", 0) for item in items]
        return max(positions) if positions else -1

    def set_initial_position(self) -> None:
        """Set the position to the next available position."""
        if "position" not in self.initial:
            self.initial["position"] = self.get_max_position(self.existing_items) + 1

    def set_context(self, item: dict, context: ContextDict) -> ContextDict:
        context["cert"] = {
            "id": item["id"],
            "name": item["name"],
            "organization": item["organization"],
            "issue_date": item["issue_date"],
            "expiration_date": item.get("expiration_date", ""),
            "credential_id": item.get("credential_id", ""),
            "edit_url": context["edit_url"],
            "delete_url": context["delete_url"],
        }
        return context

    @staticmethod
    def get_initial() -> ContextDict:
        """Default values for new certification entries."""
        return {
            "name": "Certification Name",
            "organization": "Issuing Organization",
            "issue_date": "2024-01-01",
            "expiration_date": "",
            "credential_id": "",
        }


class CertificationFlatForm(forms.Form):
    """Form for the overall certifications section."""

    title = forms.CharField(
        label="Section Title", max_length=100, initial="Certifications"
    )

    @staticmethod
    def set_context(item: dict, context: ContextDict) -> ContextDict:
        context["certifications"] = {"title": item.get("title", "Certifications")}
        context["certifications"]["edit_flat_url"] = context["edit_flat_url"]
        return context


class CertificationsPlugin(ListPlugin):
    name: str = "certifications"
    verbose_name: str = "Certifications"

    # AI prompt for LLM-based content generation
    prompt = """
    Create a django-resume plugin to display professional certifications.
    Each certification should include the name, issuing organization, 
    issue date, and optional expiration date and credential ID.
    
    The plugin should allow users to add multiple certifications and
    display them in a clean, organized format. Include functionality
    for both admin and inline editing.
    """

    @staticmethod
    def get_form_classes() -> dict[str, Type[forms.Form]]:
        return {"item": CertificationForm, "flat": CertificationFlatForm}
