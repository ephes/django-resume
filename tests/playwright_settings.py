from pathlib import Path
from .settings import *  # noqa

DEBUG = True
ALLOWED_HOSTS = ["*"]

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Media files for testing avatar uploads
MEDIA_URL = "/media/"
MEDIA_ROOT = str(BASE_DIR / "e2e_tests" / "media/")
