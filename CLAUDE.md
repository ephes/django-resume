# Django Resume Project

A pluggable framework for managing resumes in Django.

## Project Structure

This is a Django package (`django-resume`) with an example project for testing and development.

- `/src/django_resume/` - Main package source code
- `/example/` - Example Django project for testing
- `/tests/` - Test suite
- `/docs/` - Documentation

## Development Setup

```bash
# Install dependencies
uv sync --dev

# Run example project
cd example
python manage.py runserver

# Run tests
pytest

# Run type checking
mypy src/

# Run coverage
coverage run -m pytest
coverage report
```

## Key Commands

### Testing
- `pytest` - Run test suite
- `pytest tests/` - Run specific test directory
- `coverage run -m pytest && coverage report` - Run tests with coverage

### Type Checking
- `mypy src/` - Type check source code

### Development Server
- `cd example && python manage.py runserver` - Start development server
- `cd example && python manage.py migrate` - Apply migrations
- `cd example && python manage.py createsuperuser` - Create admin user

### Plugin Management
- `python manage.py create_plugin_from_stdin` - Create plugin from stdin
- `python manage.py remove_plugin_by_name` - Remove plugin by name
- `python manage.py remove_all_resumes` - Remove all resumes

### LLM Content Generation
- `llm-content` - Generate content using LLM (requires llm package)

## File Locations

### Main Package
- Models: `src/django_resume/models.py`
- Views: `src/django_resume/views.py`
- Admin: `src/django_resume/admin.py`
- Plugins: `src/django_resume/plugins/`
- Templates: `src/django_resume/templates/`
- Static files: `src/django_resume/static/`

### Tests
- Unit tests: `tests/`
- E2E tests: `e2e_tests/`
- Test settings: `tests/settings.py`

### Documentation
- Docs source: `docs/`
- Online docs: https://django-resume.readthedocs.io/

## Dependencies

- Python >=3.10
- Django >=4.2
- Development tools: pytest, mypy, coverage
- Frontend testing: vitest, jsdom

## Useful Notes

- Uses uv for dependency management
- Has pre-commit hooks enabled
- Supports multiple resume themes and plugins
- Built with HTMX for dynamic interactions
- Includes comprehensive test coverage