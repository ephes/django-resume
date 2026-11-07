"""Submit existing editor tests with a revision for the current stored state.

Stale-form regressions use separately loaded GET forms instead of this helper.
"""

import inspect

from django import forms
from django.urls import resolve

from django_resume.models import Resume
from django_resume.plugins.base import LockedResumeMutationMixin, set_edit_revision


def revision_data(view, resume, data, scope="simple"):
    state = view.data.get_data(resume)
    if scope == "flat":
        state = state.get("flat", {})
    elif scope.startswith("item:"):
        state = view.data.get_item_by_id(resume, scope.removeprefix("item:"))
    form = forms.Form()
    set_edit_revision(form, resume, view.plugin_name, scope, state)
    return {**data, "edit_revision": form["edit_revision"].value()}


def post_current_editor(client, url, data=None, **kwargs):
    method = inspect.unwrap(resolve(url).func)
    view = getattr(method, "__self__", None)
    if isinstance(view, LockedResumeMutationMixin) and "delete" not in method.__name__:
        resume = Resume.objects.filter(pk=resolve(url).kwargs["resume_id"]).first()
        if resume is not None:
            data = data or {}
            scope = "simple"
            if "flat" in method.__name__:
                scope = "flat"
            elif "item" in method.__name__:
                scope = "item:" + str(data.get("id", ""))
            data = revision_data(view, resume, data, scope)
    return client.post(url, data or {}, **kwargs)
