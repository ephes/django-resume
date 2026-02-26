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
