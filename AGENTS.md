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

## Editor and response contracts

- Browser imports must bound actual reads before parsing/signing/creation.
- Snapshot custom image-field inventories per form; preflight all uploads
  before storage and clean only files owned by the failed form.
- Execution settings accept actual booleans only; never use truthiness.
- New item forms keep their signed proposed identity on create. Item delete
  controls sign original stored data before adding display fields; compare
  that revision under the existing writer transaction and return 409 on conflict.
  Delete URLs use their own `delete_revision` query parameter (htmx appends
  the enclosing form's `edit_revision` to DELETE query strings).
- Owner artifact and inline responses must explicitly disable shared caching.
- Regression fixtures use synthetic resumes and temporary/in-memory storage.
