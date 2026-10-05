# Synthetic import preview prototype

A standalone design prototype for a "review before creating" step in the
JSON Resume browser import. It is not part of the package: production views,
forms, URLs and the importer are unchanged, and the page cannot upload, fetch,
create or modify anything.

`generate.py` configures throwaway dummy-database Django settings in a fresh
interpreter and builds pre-create summaries for the invented documents in
`fixtures.json`. It calls the current importer's byte parser, pinned schema
validator, envelope validator and pure plugin mapping/report helpers, following
the order of `import_resume_document` but stopping before the slug-existence
query and `Resume.objects.create`. Database, ORM, transaction, create/file/URL
importer, socket/DNS/HTTP and subprocess seams raise if called.

The page shows, per fixture and mode (restore envelope, the current default, or
portable only): validation result, intended name/slug, planned plugin content,
mapped/restored/omitted plugins, adapter loss notes, source sections no adapter
reads, and whether production would keep the source for exact unchanged
re-export. Owner and slug are simulated; slug availability is unknown. The
inline script only switches precomputed panels; without JavaScript every panel
is shown. Structural schema validation does not check email/URI formats, and a
restored envelope is unsigned structural data, not verified provenance.

## Run

```sh
uv run python experiments/2026-10-04-import-preview/generate.py --output /tmp/resume-import-preview
uv run pytest experiments/2026-10-04-import-preview/test_preview.py
```

`--output` must not exist; a failed run removes only the directory it created.
It writes `preview.html` (self-contained) and `reports.json` (reports only, no
source documents). Generated files are not committed.

The tests are outside the repository's default `tests/` path, so `just check`
does not run them. One test runs the real create importer against
pytest-django's throwaway test database and asserts the prototype reports and
planned plugin data match exactly.

Out of scope: the production preview/confirm view, confirmation tokens or
sessions, staged URL bytes, update-in-place identity, any writer, remote
publishing, and real resume data. See `docs/dev/jsonresume.txt`.
