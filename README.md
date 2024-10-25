# django-resume
A pluggable framework for managing your resume

## Installation

```bash
pip install django-resume
```

## Running Tests

```bash
pytest
```

## Run mypy

```bash
uv run mypy src
```

## Run coverage

```bash
coverage run -m pytest
coverage report
```

## Run the javascript tests

```bash
npx vitest run
```

## Run end to end tests

Install browsers for playwright:
    
```shell
playwright install
```

Create a testuser for the e2e tests user, using the password `password`:
```shell
DJANGO_SUPERUSER_USERNAME=playwright \
DJANGO_SUPERUSER_EMAIL=playwright@example.com \
DJANGO_SUPERUSER_PASSWORD=password \
python manage.py createsuperuser --noinput
```

Start the development server like this to use the playwright settings
(mainly setting DEBUG = True to have the static files served by Django):
```shell
python manage.py runserver 0.0.0.0:8000 --settings=tests.playwright_settings
```

The `base_url` is set via `tool.pytest.ini_options` in `pyproject.toml`.  Run the tests with:

```shell
pytest e2e_tests
```

Run playwright tests in head-full mode:
```shell
pytest e2e_tests --headed --slowmo 1000
```

Cleanup the test database after running the tests:
```shell
python manage.py remove_all_resumes
```