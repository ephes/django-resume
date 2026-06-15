help:
    @just --list --unsorted

# Run the example Django project
serve-example:
    cd example && uv run python manage.py runserver

# Build and serve the documentation locally
docs-serve port="8001":
    uv run sphinx-build -b html docs docs/_build/html
    uv run python -m http.server {{port}} --directory docs/_build/html

# Run lint, typecheck, and tests
check:
    just lint
    just typecheck
    just test

# Run tests with coverage
test:
    uv run coverage run -m pytest
    uv run coverage report

# Run type checking
typecheck:
    uv run mypy src/

# Run linting and formatting
lint:
    uv run ruff check --fix .
    uv run ruff format .

# Count lines of code in the repository with language, area, and directory summaries
loc:
    @uv run count-lines-of-code
