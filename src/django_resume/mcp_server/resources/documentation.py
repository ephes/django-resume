"""MCP resource for exposing django-resume documentation."""

from pydantic import AnyUrl
from mcp.types import Resource, TextResourceContents

from ..utils.django_setup import get_project_root


class DocumentationResource:
    """Exposes django-resume documentation as MCP resources."""

    def __init__(self):
        self.project_root = get_project_root()
        self.docs_path = self.project_root / "docs"

    def list_resources(self) -> list[Resource]:
        """List all available documentation resources."""
        resources: list[Resource] = []

        if not self.docs_path.exists():
            return resources

        # Add guide documentation
        guide_path = self.docs_path / "guide"
        if guide_path.exists():
            for doc_file in guide_path.glob("*.txt"):
                uri = f"docs://guide/{doc_file.stem}"
                resources.append(
                    Resource(
                        uri=AnyUrl(uri),
                        name=f"Guide: {doc_file.stem.replace('_', ' ').title()}",
                        description=f"Documentation guide: {doc_file.stem}",
                        mimeType="text/plain",
                    )
                )

        # Add reference documentation
        ref_path = self.docs_path / "ref"
        if ref_path.exists():
            for doc_file in ref_path.glob("*.txt"):
                uri = f"docs://ref/{doc_file.stem}"
                resources.append(
                    Resource(
                        uri=AnyUrl(uri),
                        name=f"Reference: {doc_file.stem.replace('_', ' ').title()}",
                        description=f"API reference: {doc_file.stem}",
                        mimeType="text/plain",
                    )
                )

        # Add development documentation
        dev_path = self.docs_path / "dev"
        if dev_path.exists():
            for doc_file in dev_path.glob("*.txt"):
                uri = f"docs://dev/{doc_file.stem}"
                resources.append(
                    Resource(
                        uri=AnyUrl(uri),
                        name=f"Development: {doc_file.stem.replace('_', ' ').title()}",
                        description=f"Development guide: {doc_file.stem}",
                        mimeType="text/plain",
                    )
                )

        # Add curated best practices
        resources.append(
            Resource(
                uri=AnyUrl("docs://best-practices/plugin-patterns"),
                name="Best Practices: Plugin Patterns",
                description="Common patterns and best practices for plugin development",
                mimeType="text/markdown",
            )
        )

        resources.append(
            Resource(
                uri=AnyUrl("docs://best-practices/form-design"),
                name="Best Practices: Form Design",
                description="Guidelines for designing effective plugin forms",
                mimeType="text/markdown",
            )
        )

        resources.append(
            Resource(
                uri=AnyUrl("docs://workflows/playwright-admin"),
                name="Workflow: Playwright + Django Admin",
                description="Recommended workflow using Django admin forms with Playwright automation",
                mimeType="text/markdown",
            )
        )

        return resources

    def get_resource(self, uri: str) -> TextResourceContents:
        """Get content of a specific documentation resource."""
        if not uri.startswith("docs://"):
            raise ValueError(f"Invalid URI: {uri}")

        # Extract path from URI
        path_part = uri[7:]  # Remove "docs://"

        if path_part.startswith("best-practices/"):
            return self._get_best_practices_content(path_part)

        if path_part.startswith("workflows/"):
            return self._get_workflow_content(path_part)

        # Handle regular documentation files
        parts = path_part.split("/")
        if len(parts) != 2:
            raise ValueError(f"Invalid documentation URI: {uri}")

        category, doc_name = parts
        file_path = self.docs_path / category / f"{doc_name}.txt"

        if not file_path.exists():
            raise FileNotFoundError(f"Documentation not found: {file_path}")

        content = file_path.read_text(encoding="utf-8")
        return TextResourceContents(
            uri=AnyUrl(uri), text=content, mimeType="text/plain"
        )

    def _get_best_practices_content(self, path_part: str) -> TextResourceContents:
        """Get curated best practices content."""
        if path_part == "best-practices/plugin-patterns":
            content = self._generate_plugin_patterns_guide()
        elif path_part == "best-practices/form-design":
            content = self._generate_form_design_guide()
        else:
            raise FileNotFoundError(f"Best practices document not found: {path_part}")

        return TextResourceContents(
            uri=AnyUrl(f"docs://{path_part}"), text=content, mimeType="text/markdown"
        )

    def _get_workflow_content(self, path_part: str) -> TextResourceContents:
        """Get workflow guide content."""
        if path_part == "workflows/playwright-admin":
            content = self._generate_playwright_admin_workflow()
        else:
            raise FileNotFoundError(f"Workflow document not found: {path_part}")

        return TextResourceContents(
            uri=AnyUrl(f"docs://{path_part}"), text=content, mimeType="text/markdown"
        )

    def _generate_plugin_patterns_guide(self) -> str:
        """Generate a comprehensive plugin patterns guide."""
        return """# Plugin Development Patterns

## Simple Plugin Pattern

Simple plugins are for single-value data fields like name, title, or description.

### Structure:
```python
from django import forms
from .base import SimplePlugin

class YourPluginForm(forms.Form):
    field_name = forms.CharField(max_length=200, required=False)

class YourPlugin(SimplePlugin):
    name = "your_plugin"
    verbose_name = "Your Plugin Title"
    form_class = YourPluginForm
```

### Key Principles:
1. **Single Responsibility**: Each plugin handles one piece of data
2. **Form-First Design**: Start with the form, then build the plugin
3. **Validation**: Use Django form validation for data integrity
4. **Templates**: Separate content and form templates for flexibility

## List Plugin Pattern

List plugins handle collections of items like work experience, education, skills.

### Structure:
```python
from .base import ListPlugin

class ItemForm(forms.Form):
    title = forms.CharField(max_length=200)
    description = forms.TextField(required=False)

class YourListPlugin(ListPlugin):
    name = "your_list_plugin"
    verbose_name = "Your List Plugin"
    item_form_class = ItemForm
    flat_form_class = FlatForm  # Optional: for bulk editing
```

## Template Patterns

### Content Template (content.html):
```html
<div class="plugin-content" data-plugin="{{ plugin.name }}">
    {% if show_edit_button %}
        <a href="{{ edit_url }}" class="edit-button">Edit</a>
    {% endif %}
    
    <div contenteditable="{{ editable|yesno:'true,false' }}">
        {{ data.field_name|default:"Click to edit" }}
    </div>
</div>
```

### Form Template (form.html):
```html
<form hx-post="{{ edit_url }}" hx-target="#{{ plugin.name }}-content">
    {{ form.field_name }}
    <button type="submit">Save</button>
    <button type="button" hx-get="{{ cancel_url }}">Cancel</button>
</form>
```

## Security Patterns

### Input Validation:
- Always use Django form validation
- Sanitize HTML input with bleach if needed
- Validate file uploads with proper extensions

### XSS Prevention:
- Use Django's built-in template escaping
- Mark content as safe only when necessary
- Validate all user input

## Performance Patterns

### Database Optimization:
- Use select_related() for foreign keys
- Minimize database queries in templates
- Cache expensive computations

### Template Optimization:
- Keep templates simple and focused
- Use template fragments for reusable parts
- Minimize JavaScript in templates
"""

    def _generate_form_design_guide(self) -> str:
        """Generate a form design guide."""
        return """# Form Design Guidelines

## Django Form Best Practices

### Field Types and Validation

```python
# Text Fields
title = forms.CharField(
    max_length=200,
    required=True,
    help_text="Brief title or heading"
)

# Rich Text Fields  
description = forms.CharField(
    widget=forms.Textarea(attrs={'rows': 4}),
    required=False,
    help_text="Detailed description (Markdown supported)"
)

# Choices and Options
priority = forms.ChoiceField(
    choices=[
        ('low', 'Low'),
        ('medium', 'Medium'),  
        ('high', 'High'),
    ],
    initial='medium',
    required=False
)

# Dates
start_date = forms.DateField(
    widget=forms.DateInput(attrs={'type': 'date'}),
    required=False
)

# Files and Images
image = forms.ImageField(
    required=False,
    help_text="Optional image (JPG, PNG)"
)
```

### Form Layout Patterns

#### Horizontal Form Layout:
```html
<div class="form-row">
    <div class="form-group col-md-6">
        {{ form.start_date.label_tag }}
        {{ form.start_date }}
    </div>
    <div class="form-group col-md-6">
        {{ form.end_date.label_tag }}
        {{ form.end_date }}
    </div>
</div>
```

#### Vertical Form Layout:
```html
<div class="form-group">
    {{ form.title.label_tag }}
    {{ form.title }}
    {% if form.title.help_text %}
        <small class="form-text text-muted">{{ form.title.help_text }}</small>
    {% endif %}
</div>
```

## HTMX Integration

### Progressive Enhancement:
```html
<form hx-post="{{ edit_url }}" 
      hx-target="#content-area"
      hx-swap="outerHTML">
    
    <!-- Form fields -->
    
    <button type="submit">Save</button>
    <button type="button" 
            hx-get="{{ cancel_url }}"
            hx-target="#content-area">Cancel</button>
</form>
```

### Real-time Validation:
```html
<input name="email" 
       hx-post="{{ validate_url }}"
       hx-trigger="blur"
       hx-target="#email-validation">
<div id="email-validation"></div>
```

## Accessibility Guidelines

### Semantic HTML:
- Use proper form labels and associations
- Include helpful text and error messages
- Ensure keyboard navigation works

### Screen Reader Support:
```html
<label for="id_title">Title</label>
<input type="text" id="id_title" name="title" 
       aria-describedby="title-help">
<div id="title-help">Enter a descriptive title</div>
```

## Mobile-Friendly Design

### Responsive Form Controls:
```css
.form-control {
    width: 100%;
    font-size: 16px; /* Prevents zoom on iOS */
}

@media (max-width: 768px) {
    .form-row {
        flex-direction: column;
    }
}
```

### Touch-Friendly Targets:
- Minimum 44px touch targets
- Adequate spacing between form elements
- Large, clear submit buttons
"""

    def _generate_playwright_admin_workflow(self) -> str:
        """Generate the Playwright + Django Admin workflow guide."""
        return """# Recommended Workflow: Playwright + Django Admin

## Overview

The recommended approach for creating plugins is to use Django's admin interface with Playwright automation. This approach is more reliable than direct code validation and provides a user-friendly interface.

## Why This Approach?

### Advantages:
- **User-Friendly**: Django admin provides a polished interface for plugin creation
- **Built-in Validation**: Django forms handle validation automatically
- **Visual Feedback**: Immediate preview of how the plugin will look
- **Reliable**: No complex code validation - Django handles the heavy lifting
- **Iterative**: Easy to test and refine plugins through the web interface

### Compared to Direct Code Creation:
- Less prone to validation errors
- More intuitive for users familiar with web interfaces
- Better error messaging from Django itself
- Real-time preview capabilities

## Workflow Steps

### 1. Start the Development Server

```bash
cd example
python manage.py runserver
```

The Django admin will be available at: http://localhost:8000/admin/

### 2. Navigate to Plugin Creation

1. Open Django admin: http://localhost:8000/admin/
2. Log in with admin credentials
3. Navigate to "Django Resume" → "Plugins"
4. Click "Add Plugin"

### 3. Fill Out Plugin Form

Use the admin form fields:

- **Name**: Plugin identifier (lowercase, underscores)
- **Module**: Python code for the plugin
- **Content Template**: HTML template for display
- **Form Template**: HTML template for editing
- **Prompt**: Optional description of plugin purpose
- **Model**: Note which AI model helped create it
- **Is Active**: Enable the plugin immediately

### 4. Playwright Automation Pattern

For AI assistants, use Playwright to automate form filling:

```python
# Navigate to admin
await page.goto("http://localhost:8000/admin/")

# Login (if needed)
await page.fill('[name="username"]', "admin")
await page.fill('[name="password"]', "admin")
await page.click('[type="submit"]')

# Navigate to plugin creation
await page.click('text="Django Resume"')
await page.click('text="Plugins"')
await page.click('text="Add Plugin"')

# Fill form fields
await page.fill('[name="name"]', plugin_name)
await page.fill('[name="module"]', module_code)
await page.fill('[name="content_template"]', content_template)
await page.fill('[name="form_template"]', form_template)

# Submit
await page.click('[name="_save"]')
```

### 5. Test and Iterate

1. After saving, navigate to resume views to see the plugin in action
2. Test the plugin's display and editing functionality
3. Return to admin to refine if needed
4. Use Django's built-in validation for error guidance

## Plugin Code Templates

### Basic Simple Plugin Template

```python
from django import forms
from .base import SimplePlugin

class {PluginName}Form(forms.Form):
    {field_name} = forms.CharField(
        max_length=200,
        required=True,
        help_text="{field_description}"
    )

class {PluginName}Plugin(SimplePlugin):
    name = "{plugin_name}"
    verbose_name = "{Plugin Display Name}"
    form_class = {PluginName}Form
```

### Basic Content Template

```html
{% if data.{field_name} %}
<div class="plugin-content">
    <h3>{section_title}</h3>
    <p contenteditable="true" 
       data-plugin="{plugin_name}" 
       data-field="{field_name}">{{ data.{field_name} }}</p>
    
    {% if show_edit_button %}
        <a href="{{ edit_url }}" class="edit-link">Edit</a>
    {% endif %}
</div>
{% endif %}
```

### Basic Form Template

```html
<div class="form-group">
    {{ form.{field_name}.label_tag }}
    {{ form.{field_name} }}
    {% if form.{field_name}.help_text %}
        <small class="form-text text-muted">{{ form.{field_name}.help_text }}</small>
    {% endif %}
    {{ form.{field_name}.errors }}
</div>
```

## Best Practices for Automation

### Form Field Strategies:
1. **Start Simple**: Begin with basic CharField fields
2. **Use Help Text**: Provide clear guidance for users
3. **Test Immediately**: Save and preview after each change
4. **Iterate Quickly**: Use Django admin's edit capabilities

### Error Handling:
1. **Read Django Messages**: Admin interface shows clear error messages
2. **Fix One Thing at a Time**: Address validation errors systematically
3. **Use Browser DevTools**: Inspect form errors directly

### Template Tips:
1. **Copy Existing Patterns**: Look at existing plugins for reference
2. **Test Rendering**: Preview templates in the resume view
3. **Keep It Simple**: Start with basic HTML, enhance later

## Integration with MCP Tools

While this workflow emphasizes the admin interface, MCP tools can still assist:

1. **Use Documentation Resources**: Reference plugin patterns and examples
2. **Use Schema Resources**: Get template code structures
3. **Use Validation Tools**: Check code before pasting into admin
4. **Use Playwright Tools**: Automate the admin form filling process

## Troubleshooting

### Common Issues:
1. **Import Errors**: Check Python syntax in module field
2. **Template Errors**: Validate HTML in template fields
3. **Form Validation**: Read Django's error messages carefully
4. **Plugin Not Showing**: Ensure 'Is Active' is checked

### Quick Fixes:
1. **Save Draft**: Use "Save and continue editing" to test changes
2. **Preview**: Navigate to resume views to see results
3. **Edit Mode**: Use admin interface to refine plugin
4. **Copy Working Examples**: Base new plugins on existing ones

This workflow provides a robust, user-friendly approach to plugin development that leverages Django's strengths while supporting AI automation through Playwright.
"""


# Global instance
documentation_resource = DocumentationResource()
