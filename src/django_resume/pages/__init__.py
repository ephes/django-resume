from importlib.metadata import entry_points

from django.utils.module_loading import autodiscover_modules

from .base import ByCapability, ResumePage, by_capability
from .builtins import register_builtin_pages
from .registry import PageRegistry, page_registry

#: Entry-point group through which a separately distributed package registers
#: its resume pages without being an installed Django app.
ENTRY_POINT_GROUP = "django_resume.pages"

#: Entry points already processed, so loading is idempotent: a second
#: ``autodiscover_pages()`` (e.g. a re-run of ``AppConfig.ready`` or a manual
#: call) does not re-invoke a registering callable or re-register a page.
#: ``resume_pages`` autodiscovery is idempotent for free via Python's import
#: cache; entry-point *targets* run outside any import, so they need this guard.
_loaded_entry_points: set[tuple[str, str]] = set()


def load_entry_point_pages() -> None:
    """Register pages contributed by separately distributed packages.

    A package that is *not* an installed Django app (so its ``resume_pages``
    module is never autodiscovered) can still ship pages by declaring entry
    points in the :data:`ENTRY_POINT_GROUP` group. Each entry point loads to
    either a :class:`~django_resume.pages.ResumePage` subclass (registered
    directly) or a zero-argument callable (invoked so it can register its own
    pages). Anything else is a misconfiguration and raises ``TypeError`` early.

    Runs at startup, before ``django_resume.urls`` is built, so entry-point
    pages get routes under the same ordering guarantee as built-ins and
    autodiscovered ``resume_pages`` modules. Each entry point is processed at
    most once (see :data:`_loaded_entry_points`), so the call is idempotent.
    """
    for entry_point in entry_points(group=ENTRY_POINT_GROUP):
        identity = (entry_point.name, entry_point.value)
        if identity in _loaded_entry_points:
            continue
        target = entry_point.load()
        if isinstance(target, type):
            # A class target must be a ResumePage subclass. Any other class is a
            # misconfiguration: classes are callable, so without this guard one
            # would fall through to the callable branch and be instantiated
            # silently (registering no page) instead of failing loudly.
            if not issubclass(target, ResumePage):
                raise TypeError(
                    f"Entry point {entry_point.name!r} in group "
                    f"{ENTRY_POINT_GROUP!r} loads a class that is not a "
                    f"ResumePage subclass: {target!r}"
                )
            page_registry.register(target)
        elif callable(target):
            target()
        else:
            raise TypeError(
                f"Entry point {entry_point.name!r} in group {ENTRY_POINT_GROUP!r} "
                f"must load to a ResumePage subclass or a callable, got {target!r}"
            )
        _loaded_entry_points.add(identity)


def autodiscover_pages() -> None:
    """Discover and register third-party pages on startup.

    Two extension points, in order:

    #. Every installed app's top-level ``resume_pages`` module is imported
       (mirroring how Django's admin discovers ``admin`` modules); the module
       calls ``page_registry.register(...)`` at import time.
    #. Separately distributed packages register via ``django_resume.pages``
       entry points (:func:`load_entry_point_pages`).

    Both must run before ``django_resume.urls`` is imported, so the generated
    page routes include the discovered pages.
    """
    autodiscover_modules("resume_pages")
    load_entry_point_pages()


__all__ = [
    "ResumePage",
    "ByCapability",
    "by_capability",
    "PageRegistry",
    "page_registry",
    "register_builtin_pages",
    "autodiscover_pages",
    "load_entry_point_pages",
    "ENTRY_POINT_GROUP",
]
