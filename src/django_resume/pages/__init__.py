from importlib.metadata import entry_points

from django.utils.module_loading import autodiscover_modules

from .base import ByCapability, ResumePage, by_capability
from .builtins import register_builtin_pages
from .registry import PageRegistrationError, PageRegistry, page_registry

#: Entry-point group through which a separately distributed package registers
#: its resume pages without being an installed Django app.
ENTRY_POINT_GROUP = "django_resume.pages"

#: Entry points already processed, so loading is idempotent: a second
#: ``autodiscover_pages()`` (e.g. a re-run of ``AppConfig.ready`` or a manual
#: call) does not re-invoke a registering callable or re-register a page.
#: ``resume_pages`` autodiscovery is idempotent for free via Python's import
#: cache; entry-point *targets* run outside any import, so they need this guard.
_loaded_entry_points: dict[tuple[str, str], tuple[str, str] | None] = {}


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
    Distinct distributions declaring the same name and target are rejected
    before any new registrations.
    """
    providers = _loaded_entry_points.copy()
    pending = []
    for entry_point in entry_points(group=ENTRY_POINT_GROUP):
        declaration = (entry_point.name, entry_point.value)
        dist = entry_point.dist
        provider = (dist.name, dist.version) if dist is not None else None
        if declaration in providers:
            previous = providers[declaration]
            if previous != provider:
                raise PageRegistrationError(
                    f"Duplicate entry point {entry_point.name!r} targeting "
                    f"{entry_point.value!r} in group {ENTRY_POINT_GROUP!r}: "
                    f"declared by both {previous!r} and {provider!r} "
                    "(distribution name, version)."
                )
            continue
        providers[declaration] = provider
        pending.append((entry_point, declaration, provider))

    for entry_point, declaration, provider in pending:
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
            before = dict(page_registry.pages)
            try:
                target()
            except BaseException:
                # A callback may replace or unregister existing pages as well
                # as add new ones. Retry must start from the complete old set.
                page_registry.pages = before
                raise
        else:
            raise TypeError(
                f"Entry point {entry_point.name!r} in group {ENTRY_POINT_GROUP!r} "
                f"must load to a ResumePage subclass or a callable, got {target!r}"
            )
        _loaded_entry_points[declaration] = provider


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
    "PageRegistrationError",
    "page_registry",
    "register_builtin_pages",
    "autodiscover_pages",
    "load_entry_point_pages",
    "ENTRY_POINT_GROUP",
]
