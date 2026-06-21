"""A separately distributed django-resume page, shipped via an entry point.

This package is intentionally *not* a Django app and is not listed in the
example project's ``INSTALLED_APPS``. It contributes a resume page purely
through the ``django_resume.pages`` entry point declared in its
``pyproject.toml``, so ``django_resume.pages.load_entry_point_pages()`` finds
and registers it on startup. It demonstrates the entry-point extension point
end to end.
"""
