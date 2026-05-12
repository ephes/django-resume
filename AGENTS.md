# django-resume Agent Notes

## Environment

- Use `uv` for Python commands and dependency management.
- Install dev dependencies with `uv sync --dev`.

## Validation

- After implementing a feature or any multi-file behavior change, run `just check`.
- Do not stop at `just test` alone when `just check` is available.
- For narrow iterations, targeted tests are fine while developing, but finish with `just check`.

## Git Hooks

- Use `uvx prek install` to install the repo pre-commit hook.
- If hook environments are missing, run `uvx prek install-hooks`.

## Releases

- The release process lives in `docs/dev/develop.txt`.
- Agents preparing a release should stop before `uv publish` or `git push` and report those commands for the maintainer to run.
