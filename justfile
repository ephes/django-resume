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

# Count lines of code in the repository (by language + by top-level folder)
loc:
    cloc --vcs=git .
    @echo ""
    @echo "--- Python SLOC by folder ---"
    @sloccount --details . 2>/dev/null | awk '/^[0-9]/ && $2=="python" {sums[$3]+=$1} END{for(d in sums) printf "%8d  %s\n", sums[d], d}' | sort -rn
