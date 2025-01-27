from django import template
from django.template import engines

register = template.Library()


@register.simple_tag(takes_context=True)
def render_template_string(context, template_string):
    django_engine = engines["django"]
    template_obj = django_engine.from_string(template_string)
    return template_obj.render(context.flatten())
