"""Settings for the live-server Playwright tests.

These reuse the *real* bundled example project's settings (so the ``core``
example app and its ``PortfolioPage`` are exercised exactly as a user would run
them via ``manage.py runserver``) and only swap in a dedicated, throwaway test
database so the committed ``example/db.sqlite3`` is never touched and the live
server thread can share state with the test thread.
"""

import sys
from pathlib import Path

E2E_DIR = Path(__file__).resolve().parent
EXAMPLE_DIR = E2E_DIR.parent / "example"
if str(EXAMPLE_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLE_DIR))

from example.settings import *  # noqa: E402, F403

_E2E_DB = str(E2E_DIR / "e2e_test_db.sqlite3")
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": _E2E_DB,
        "TEST": {"NAME": _E2E_DB},
    }
}
