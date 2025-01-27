import pytest

from django_resume.plugin_generator import (
    generate_simple_plugin,
    get_simple_plugin_context,
    parse_llm_output_as_simple_plugin,
)


@pytest.fixture
def llm_output():
    return """
I'll help create a plugin for displaying burial pyramid information based on your requirements. Here's the implementation:

===pyramid===

===pyramid.py===
from django import forms
from django_resume.plugins import SimplePlugin

class PyramidForm(forms.Form):
    name = forms.CharField(
        label="Pyramid name",
        max_length=100,
        initial="Great Pyramid of Giza"
    )
    location = forms.CharField(
        label="Location",
        max_length=100,
        initial="Giza, Egypt"
    )
    height = forms.IntegerField(
        label="Height (meters)",
        min_value=50,
        initial=146,
        error_messages={
            'min_value': "Your puny pyramid is pathetic!"
        }
    )
    construction_year = forms.IntegerField(
        label="Construction started",
        initial=-2500,
        required=False
    )

class PyramidPlugin(SimplePlugin):
    name: str = "pyramid"
    verbose_name: str = "Burial Pyramid"
    admin_form_class = inline_form_class = PyramidForm

===django_resume/plugins/pyramid/plain/content.html===
<section id="pyramid" class="stack">
  {% if show_edit_button %}
    <div class="cluster">
      <h2>{{ pyramid.name }}</h2>
      <svg class="edit-icon-small" hx-get="{{ pyramid.edit_url }}" hx-target="#pyramid" hx-swap="outerHTML">
        <use href="#edit"></use>
      </svg>
    </div>
  {% else %}
    <h2>{{ pyramid.name }}</h2>
  {% endif %}
  <div class="stack">
    <p><strong>Location:</strong> {{ pyramid.location }}</p>
    <p><strong>Height:</strong> {{ pyramid.height }} meters</p>
    {% if pyramid.construction_year %}
      <p><strong>Construction started:</strong> {{ pyramid.construction_year }} BCE</p>
    {% endif %}
  </div>
</section>

===django_resume/plugins/pyramid/plain/form.html===
<editable-form id="pyramid" class="stack">
  <form
    id="form-pyramid"
    class="stack-small"
    hx-post="{{ form.post_url }}"
    hx-target="#pyramid"
    hx-swap="outerHTML"
  >
    <input type="hidden" data-field="name" name="name" value="{{ form.name.value }}">
    <input type="hidden" data-field="location" name="location" value="{{ form.location.value }}">
    <input type="hidden" data-field="height" name="height" value="{{ form.height.value }}">
    <input type="hidden" data-field="construction_year" name="construction_year" value="{{ form.construction_year.value }}">
  </form>
  <h2 contenteditable="true" data-field="name">{{ form.name.value }}</h2>
  {% for error in form.name.errors %}
    <p class="error">{{ error|escape }}</p>
  {% endfor %}
  <div class="stack">
    <p>
      <strong>Location:</strong>
      <span contenteditable="true" data-field="location">{{ form.location.value }}</span>
    </p>
    {% for error in form.location.errors %}
      <p class="error">{{ error|escape }}</p>
    {% endfor %}
    <p>
      <strong>Height:</strong>
      <span contenteditable="true" data-field="height">{{ form.height.value }}</span> meters
    </p>
    {% for error in form.height.errors %}
      <p class="error">{{ error|escape }}</p>
    {% endfor %}
    <p>
      <strong>Construction started:</strong>
      <span contenteditable="true" data-field="construction_year">{{ form.construction_year.value }}</span> BCE
    </p>
    {% for error in form.construction_year.errors %}
      <p class="error">{{ error|escape }}</p>
    {% endfor %}
  </div>
  <div>
    <button id="submit-pyramid" type="submit">
      <svg class="edit-icon-small">
        <use href="#ok"></use>
      </svg>
    </button>
  </div>
</editable-form>    
    """


def test_generate_simple_plugin(mocker, llm_output):
    prompt = "Test Prompt"
    mocker.patch(
        "django_resume.plugin_generator.context_to_output_via_llm",
        return_value=llm_output,
    )
    plugin = generate_simple_plugin(prompt)
    assert plugin.prompt == prompt


def test_get_simple_plugin_context():
    prompt = "Create a django-resume plugin to add details about a burial pyramid."
    llm_context = get_simple_plugin_context(prompt)
    assert "burial pyramid" in llm_context


def test_parse_llm_output_as_simple_plugin(llm_output):
    parsed_output = parse_llm_output_as_simple_plugin(llm_output)
    assert "name" in parsed_output
    assert "module" in parsed_output
    assert "content_template" in parsed_output
    assert "form_template" in parsed_output
