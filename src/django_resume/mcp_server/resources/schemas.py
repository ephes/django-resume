"""MCP resource for exposing django-resume plugin schemas and patterns."""

import json
from pydantic import AnyUrl
from mcp.types import Resource, TextResourceContents


class SchemaResource:
    """Exposes plugin schemas and patterns as MCP resources."""

    def list_resources(self) -> list[Resource]:
        """List all available schema resources."""
        resources: list[Resource] = []

        # Plugin module schemas
        resources.append(
            Resource(
                uri=AnyUrl("schemas://plugin-module/simple"),
                name="Schema: Simple Plugin Module",
                description="Python module structure for simple plugins",
                mimeType="application/json",
            )
        )

        resources.append(
            Resource(
                uri=AnyUrl("schemas://plugin-module/list"),
                name="Schema: List Plugin Module",
                description="Python module structure for list plugins",
                mimeType="application/json",
            )
        )

        # Template schemas
        resources.append(
            Resource(
                uri=AnyUrl("schemas://templates/content"),
                name="Schema: Content Template",
                description="HTML template structure for plugin content display",
                mimeType="application/json",
            )
        )

        resources.append(
            Resource(
                uri=AnyUrl("schemas://templates/form"),
                name="Schema: Form Template",
                description="HTML template structure for plugin forms",
                mimeType="application/json",
            )
        )

        # Form field patterns
        resources.append(
            Resource(
                uri=AnyUrl("schemas://forms/field-types"),
                name="Schema: Django Form Field Types",
                description="Common Django form field patterns and usage",
                mimeType="application/json",
            )
        )

        # Validation patterns
        resources.append(
            Resource(
                uri=AnyUrl("schemas://validation/plugin-requirements"),
                name="Schema: Plugin Validation Requirements",
                description="Requirements for valid plugin code",
                mimeType="application/json",
            )
        )

        # Complete examples
        resources.append(
            Resource(
                uri=AnyUrl("schemas://examples/complete-simple-plugin"),
                name="Example: Complete Simple Plugin",
                description="Full working example of a simple plugin",
                mimeType="application/json",
            )
        )

        resources.append(
            Resource(
                uri=AnyUrl("schemas://examples/complete-list-plugin"),
                name="Example: Complete List Plugin",
                description="Full working example of a list plugin",
                mimeType="application/json",
            )
        )

        return resources

    def get_resource(self, uri: str) -> TextResourceContents:
        """Get content of a specific schema resource."""
        if not uri.startswith("schemas://"):
            raise ValueError(f"Invalid URI: {uri}")

        path_part = uri[10:]  # Remove "schemas://"

        if path_part == "plugin-module/simple":
            content = self._get_simple_plugin_module_schema()
        elif path_part == "plugin-module/list":
            content = self._get_list_plugin_module_schema()
        elif path_part == "templates/content":
            content = self._get_content_template_schema()
        elif path_part == "templates/form":
            content = self._get_form_template_schema()
        elif path_part == "forms/field-types":
            content = self._get_form_field_types_schema()
        elif path_part == "validation/plugin-requirements":
            content = self._get_validation_requirements_schema()
        elif path_part == "examples/complete-simple-plugin":
            content = self._get_complete_simple_plugin_example()
        elif path_part == "examples/complete-list-plugin":
            content = self._get_complete_list_plugin_example()
        else:
            raise FileNotFoundError(f"Schema not found: {path_part}")

        return TextResourceContents(
            uri=AnyUrl(uri), text=content, mimeType="application/json"
        )

    def _get_simple_plugin_module_schema(self) -> str:
        """Get schema for simple plugin module structure."""
        schema = {
            "type": "simple_plugin_module",
            "description": "Python module for a simple plugin",
            "required_imports": [
                "from django import forms",
                "from .base import SimplePlugin",
            ],
            "required_classes": [
                {
                    "name": "{PluginName}Form",
                    "type": "Form",
                    "inherits": "forms.Form",
                    "purpose": "Define form fields for data input",
                    "required_fields": "At least one form field",
                },
                {
                    "name": "{PluginName}Plugin",
                    "type": "Plugin",
                    "inherits": "SimplePlugin",
                    "purpose": "Main plugin class",
                    "required_attributes": [
                        "name: str (lowercase with underscores)",
                        "verbose_name: str (human-readable title)",
                        "form_class: Form class reference",
                    ],
                },
            ],
            "naming_conventions": {
                "plugin_name": "lowercase_with_underscores",
                "class_names": "PascalCase",
                "form_class": "{PluginName}Form",
                "plugin_class": "{PluginName}Plugin",
            },
            "template": {
                "imports": [
                    "from django import forms",
                    "from .base import SimplePlugin",
                ],
                "form_class": "class {PluginName}Form(forms.Form):",
                "plugin_class": "class {PluginName}Plugin(SimplePlugin):",
            },
            "example_field_types": {
                "text": "forms.CharField(max_length=200, required=False)",
                "textarea": "forms.CharField(widget=forms.Textarea, required=False)",
                "email": "forms.EmailField(required=False)",
                "url": "forms.URLField(required=False)",
                "integer": "forms.IntegerField(required=False)",
                "decimal": "forms.DecimalField(max_digits=10, decimal_places=2, required=False)",
                "boolean": "forms.BooleanField(required=False)",
                "choice": "forms.ChoiceField(choices=CHOICES, required=False)",
                "date": "forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), required=False)",
            },
        }
        return json.dumps(schema, indent=2)

    def _get_list_plugin_module_schema(self) -> str:
        """Get schema for list plugin module structure."""
        schema = {
            "type": "list_plugin_module",
            "description": "Python module for a list plugin (collections of items)",
            "required_imports": [
                "from django import forms",
                "from .base import ListPlugin",
            ],
            "required_classes": [
                {
                    "name": "{PluginName}ItemForm",
                    "type": "Form",
                    "inherits": "forms.Form",
                    "purpose": "Define form fields for individual items",
                    "required_fields": "Fields representing item data",
                },
                {
                    "name": "{PluginName}Plugin",
                    "type": "Plugin",
                    "inherits": "ListPlugin",
                    "purpose": "Main plugin class for item collections",
                    "required_attributes": [
                        "name: str (lowercase with underscores)",
                        "verbose_name: str (human-readable title)",
                        "item_form_class: Form class for individual items",
                    ],
                },
            ],
            "optional_classes": [
                {
                    "name": "{PluginName}FlatForm",
                    "type": "Form",
                    "inherits": "forms.Form",
                    "purpose": "Bulk editing form for all items",
                    "usage": "Set as flat_form_class attribute",
                }
            ],
            "item_operations": [
                "create: Add new items to the list",
                "update: Modify existing items",
                "delete: Remove items from the list",
                "reorder: Change item positions",
            ],
        }
        return json.dumps(schema, indent=2)

    def _get_content_template_schema(self) -> str:
        """Get schema for content template structure."""
        schema = {
            "type": "content_template",
            "description": "HTML template for displaying plugin content",
            "required_structure": {
                "container": "div with data-plugin attribute",
                "edit_button": "conditional edit button for authenticated users",
                "content_area": "div with contenteditable support",
            },
            "required_variables": [
                "plugin: Plugin instance",
                "data: Plugin data dictionary",
                "show_edit_button: Boolean for edit button visibility",
                "edit_url: URL for editing the plugin",
                "editable: Boolean for contenteditable mode",
            ],
            "template_structure": {
                "container": '<div class="plugin-content" data-plugin="{{ plugin.name }}">',
                "edit_button": '{% if show_edit_button %}<a href="{{ edit_url }}">Edit</a>{% endif %}',
                "content": "<div contenteditable=\"{{ editable|yesno:'true,false' }}\">{{ data.field_name|default:'Click to edit' }}</div>",
                "close_container": "</div>",
            },
            "best_practices": [
                "Use semantic HTML elements",
                "Include data-plugin attribute for JavaScript targeting",
                "Support both editable and read-only modes",
                "Provide fallback content for empty fields",
                "Use Django template filters for safe output",
            ],
            "accessibility": [
                "Include proper ARIA labels",
                "Ensure keyboard navigation works",
                "Use sufficient color contrast",
                "Provide alternative text for images",
            ],
        }
        return json.dumps(schema, indent=2)

    def _get_form_template_schema(self) -> str:
        """Get schema for form template structure."""
        schema = {
            "type": "form_template",
            "description": "HTML template for plugin editing forms",
            "required_structure": {
                "form_element": "form with HTMX attributes",
                "form_fields": "rendered Django form fields",
                "submit_button": "save button",
                "cancel_button": "cancel button with HTMX get",
            },
            "required_variables": [
                "form: Django form instance",
                "edit_url: URL for form submission",
                "cancel_url: URL for cancel action",
            ],
            "htmx_integration": {
                "form_submission": 'hx-post="{{ edit_url }}"',
                "target_update": 'hx-target="#content-area"',
                "swap_strategy": 'hx-swap="outerHTML"',
                "cancel_action": 'hx-get="{{ cancel_url }}"',
            },
            "form_rendering": {
                "manual_fields": "{{ form.field_name.label_tag }} {{ form.field_name }}",
                "field_errors": "{% if form.field_name.errors %}{{ form.field_name.errors }}{% endif %}",
                "help_text": "{% if form.field_name.help_text %}{{ form.field_name.help_text }}{% endif %}",
            },
            "validation_display": [
                "Show field-level errors",
                "Display form-level errors",
                "Provide clear error messages",
                "Highlight invalid fields",
            ],
        }
        return json.dumps(schema, indent=2)

    def _get_form_field_types_schema(self) -> str:
        """Get schema for Django form field types and patterns."""
        schema = {
            "type": "form_field_types",
            "description": "Common Django form field patterns",
            "text_fields": {
                "CharField": {
                    "code": "forms.CharField(max_length=200, required=False)",
                    "use_case": "Short text input like names, titles",
                    "attributes": ["max_length", "min_length", "required", "help_text"],
                },
                "TextField": {
                    "code": "forms.CharField(widget=forms.Textarea(attrs={'rows': 4}), required=False)",
                    "use_case": "Multi-line text like descriptions",
                    "attributes": ["widget", "required", "help_text"],
                },
            },
            "specialized_fields": {
                "EmailField": {
                    "code": "forms.EmailField(required=False)",
                    "use_case": "Email addresses with validation",
                },
                "URLField": {
                    "code": "forms.URLField(required=False)",
                    "use_case": "Website URLs with validation",
                },
                "IntegerField": {
                    "code": "forms.IntegerField(min_value=0, required=False)",
                    "use_case": "Numeric values like counts, years",
                },
            },
            "choice_fields": {
                "ChoiceField": {
                    "code": "forms.ChoiceField(choices=[('option1', 'Option 1'), ('option2', 'Option 2')], required=False)",
                    "use_case": "Single selection from predefined options",
                },
                "MultipleChoiceField": {
                    "code": "forms.MultipleChoiceField(choices=CHOICES, widget=forms.CheckboxSelectMultiple, required=False)",
                    "use_case": "Multiple selections from options",
                },
            },
            "date_time_fields": {
                "DateField": {
                    "code": "forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), required=False)",
                    "use_case": "Date selection with HTML5 date picker",
                },
                "DateTimeField": {
                    "code": "forms.DateTimeField(widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}), required=False)",
                    "use_case": "Date and time selection",
                },
            },
            "file_fields": {
                "FileField": {
                    "code": "forms.FileField(required=False)",
                    "use_case": "General file uploads",
                },
                "ImageField": {
                    "code": "forms.ImageField(required=False)",
                    "use_case": "Image file uploads with validation",
                },
            },
            "validation_patterns": {
                "custom_validator": "validators=[RegexValidator(r'^[a-zA-Z0-9]+$', 'Only alphanumeric characters allowed')]",
                "length_validation": "max_length=100, min_length=5",
                "numeric_validation": "max_value=100, min_value=0",
            },
        }
        return json.dumps(schema, indent=2)

    def _get_validation_requirements_schema(self) -> str:
        """Get schema for plugin validation requirements."""
        schema = {
            "type": "validation_requirements",
            "description": "Requirements for valid plugin code",
            "security_requirements": [
                "No exec() or eval() function calls",
                "No direct file system access",
                "No subprocess or os module imports",
                "No __import__ usage",
                "Sanitized user input",
            ],
            "code_structure_requirements": [
                "Must have a Form class inheriting from forms.Form",
                "Must have a Plugin class inheriting from SimplePlugin or ListPlugin",
                "Form class name must end with 'Form'",
                "Plugin class name must end with 'Plugin'",
                "Plugin must have 'name' and 'verbose_name' attributes",
            ],
            "naming_requirements": {
                "plugin_name": "lowercase with underscores only",
                "class_names": "PascalCase convention",
                "no_reserved_words": "Cannot use Python or Django reserved words",
            },
            "template_requirements": [
                "Must be valid HTML",
                "No <script> tags allowed",
                "Must use Django template syntax correctly",
                "Should include contenteditable support",
                "Should include edit_url for editing",
            ],
            "form_requirements": [
                "At least one form field required",
                "Form fields should have reasonable max_length",
                "Required fields should be validated",
                "Form should handle empty/None values gracefully",
            ],
            "performance_requirements": [
                "No infinite loops or recursion",
                "Efficient database queries",
                "Reasonable template complexity",
                "No blocking operations",
            ],
        }
        return json.dumps(schema, indent=2)

    def _get_complete_simple_plugin_example(self) -> str:
        """Get complete simple plugin example."""
        example = {
            "type": "complete_simple_plugin_example",
            "description": "Complete working example of a simple plugin",
            "module_code": '''from django import forms
from .base import SimplePlugin


class JobTitleForm(forms.Form):
    """Form for job title plugin."""
    
    title = forms.CharField(
        max_length=200,
        required=False,
        help_text="Your current job title"
    )
    
    company = forms.CharField(
        max_length=200,
        required=False,
        help_text="Company name"
    )
    
    location = forms.CharField(
        max_length=100,
        required=False,
        help_text="Work location (city, state)"
    )


class JobTitlePlugin(SimplePlugin):
    """Simple plugin for displaying job title and company."""
    
    name = "job_title"
    verbose_name = "Job Title"
    form_class = JobTitleForm''',
            "content_template": """<div class="plugin-content" data-plugin="{{ plugin.name }}">
    {% if show_edit_button %}
        <a href="{{ edit_url }}" class="edit-button">Edit Job Title</a>
    {% endif %}
    
    <div class="job-info">
        <h3 contenteditable="{{ editable|yesno:'true,false' }}" 
            class="job-title">
            {{ data.title|default:"Your Job Title" }}
        </h3>
        
        <p contenteditable="{{ editable|yesno:'true,false' }}"
           class="company-info">
            {% if data.company %}
                {{ data.company }}
                {% if data.location %} - {{ data.location }}{% endif %}
            {% else %}
                Company Name - Location
            {% endif %}
        </p>
    </div>
</div>""",
            "form_template": """<form hx-post="{{ edit_url }}" 
      hx-target="#job-title-content"
      hx-swap="outerHTML"
      class="plugin-form">
    
    <div class="form-group">
        {{ form.title.label_tag }}
        {{ form.title }}
        {% if form.title.help_text %}
            <small class="form-text text-muted">{{ form.title.help_text }}</small>
        {% endif %}
        {% if form.title.errors %}
            <div class="text-danger">{{ form.title.errors }}</div>
        {% endif %}
    </div>
    
    <div class="form-group">
        {{ form.company.label_tag }}
        {{ form.company }}
        {% if form.company.help_text %}
            <small class="form-text text-muted">{{ form.company.help_text }}</small>
        {% endif %}
    </div>
    
    <div class="form-group">
        {{ form.location.label_tag }}
        {{ form.location }}
        {% if form.location.help_text %}
            <small class="form-text text-muted">{{ form.location.help_text }}</small>
        {% endif %}
    </div>
    
    <div class="form-actions">
        <button type="submit" class="btn btn-primary">Save</button>
        <button type="button" 
                class="btn btn-secondary"
                hx-get="{{ cancel_url }}"
                hx-target="#job-title-content">Cancel</button>
    </div>
</form>""",
        }
        return json.dumps(example, indent=2)

    def _get_complete_list_plugin_example(self) -> str:
        """Get complete list plugin example."""
        example = {
            "type": "complete_list_plugin_example",
            "description": "Complete working example of a list plugin",
            "module_code": '''from django import forms
from .base import ListPlugin


class SkillItemForm(forms.Form):
    """Form for individual skill items."""
    
    name = forms.CharField(
        max_length=100,
        required=True,
        help_text="Skill name (e.g., Python, JavaScript)"
    )
    
    level = forms.ChoiceField(
        choices=[
            ('beginner', 'Beginner'),
            ('intermediate', 'Intermediate'),
            ('advanced', 'Advanced'),
            ('expert', 'Expert'),
        ],
        required=False,
        initial='intermediate',
        help_text="Your proficiency level"
    )
    
    years_experience = forms.IntegerField(
        min_value=0,
        max_value=50,
        required=False,
        help_text="Years of experience (optional)"
    )


class SkillsPlugin(ListPlugin):
    """List plugin for managing skills."""
    
    name = "skills"
    verbose_name = "Skills"
    item_form_class = SkillItemForm''',
            "content_template": """<div class="plugin-content" data-plugin="{{ plugin.name }}">
    {% if show_edit_button %}
        <a href="{{ edit_url }}" class="edit-button">Edit Skills</a>
    {% endif %}
    
    <div class="skills-list">
        {% if data %}
            {% for item in data %}
                <div class="skill-item" data-item-id="{{ item.id }}">
                    <span class="skill-name">{{ item.name }}</span>
                    {% if item.level %}
                        <span class="skill-level badge">{{ item.get_level_display }}</span>
                    {% endif %}
                    {% if item.years_experience %}
                        <span class="skill-years">{{ item.years_experience }} years</span>
                    {% endif %}
                </div>
            {% endfor %}
        {% else %}
            <p class="empty-state">No skills added yet. Click Edit to add your skills.</p>
        {% endif %}
    </div>
</div>""",
            "item_template": """<div class="skill-item-form">
    <div class="form-row">
        <div class="form-group col-md-4">
            {{ form.name.label_tag }}
            {{ form.name }}
        </div>
        <div class="form-group col-md-4">
            {{ form.level.label_tag }}
            {{ form.level }}
        </div>
        <div class="form-group col-md-4">
            {{ form.years_experience.label_tag }}
            {{ form.years_experience }}
        </div>
    </div>
</div>""",
        }
        return json.dumps(example, indent=2)


# Global instance
schema_resource = SchemaResource()
