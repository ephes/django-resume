=============
django-resume
=============

.. image:: https://img.shields.io/readthedocs/django-resume?style=for-the-badge
   :target: https://django-resume.readthedocs.io/en/latest/

.. image:: https://img.shields.io/pypi/v/django-resume.svg?style=for-the-badge
   :target: https://pypi.org/project/django-resume/

.. image:: https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white&style=for-the-badge
   :target: https://github.com/pre-commit/pre-commit
   :alt: pre-commit

A pluggable framework for managing your resume in Django.

Watch the Talk
--------------

For a quick introduction, you can watch the video on YouTube. 🍿

.. image:: images/skip-the-overhead-preview.png
   :alt: Watch the Talk
   :target: https://fosdem.org/2025/schedule/event/fosdem-2025-6174-skip-the-overhead-lean-web-development-with-django/

Documentation
-------------

Please see https://django-resume.readthedocs.io/ .

CV Preview
----------

Click the image to view the complete, interactive CV on my website.

.. image:: images/wersdoerfer-de-resume-queen-cleo-cv.png
   :alt: Preview of the CV
   :target: https://wersdoerfer.de/resume/queen-cleo/cv/

Resume Preview
--------------

Click the image to view the complete, interactive resume on my website.

.. image:: images/wersdoerfer-de-resume-queen-cleo-cover.png
   :alt: Preview of the Resume
   :target: https://wersdoerfer.de/resume/queen-cleo/

Editor safety
-------------

Default plugin JSON editors accept strict JSON objects up to 2 MiB and 64
container levels. Duplicate members and non-finite numbers are rejected.
Root admin forms carry a signed document revision: if any stored field changes,
reload the form and reapply the edit. Fresh raw JSON edits remain supported.

Inline language selection projects only the stored theme language, keeping
unrelated sections out of that lookup. JSON Resume schema diagnostics stop at
20 errors and use bounded locations/messages without echoing invalid values.

Browser JSON Resume imports read at most the input byte limit plus one byte,
checking actual bytes before parsing, signing a preview or creating a resume.
Read failures return a file-field diagnostic. Custom image forms may supply a
one-shot ``image_fields`` iterable: each form snapshots it before field setup,
preflights every upload before storing any, and tracks only its own new files
for failure cleanup.
