0.1.3 - 2024-10-13
==================

### Features

- Added a resume detail page used as a cover letter
- Added add resume button to the main page / resume list
- Added delete buttons to the resume list
- Added a base template for the resume pages
- Do not require token for CV when user is logged in
- Better print styles for the CV
- Scroll animate project-boxes up
- Super simple markdown support for cover letter text

0.1.2 - 2024-10-11
==================

### Features
- Area labels for project links without text
- Project links are working now in pdf export
- Global edit button for the whole CV

### Refactor
- Moved all plugin templates in folders named after the plugin
- Removed dead templates

0.1.1 - 2024-10-11
==================

### Refactor
- The main `Person` model was renamed to `Resume`

### Features
- Added permission checks to the Simple and List base Plugins

0.1.0 - 2024-10-10
==================

### Initial Release

The CV is kind of working. Editing via Django-Admin or inline via
contenteditable="true" is possible.