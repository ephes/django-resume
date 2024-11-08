0.1.7 - 2024-11-08
==================

### Fixes
- Avoid h1 -> h3
- Reserve space for image to avoid layout shift

0.1.6 - 2024-11-08
==================

### Fixes
- Use preload for the fonts

0.1.5 - 2024-11-08
==================

### Features
- Added a new custom 403 page for the CV page when there's no token with a 
  mailto link to the owner of the CV to request access

### Fixes
- Some minor style fixes
- Fixed the input field overflow in the project item badge editor
- New e2e tests for inline editing
- Use the correct fonts (inter + martian mono)

0.1.4 - 2024-11-01
==================

### Features

- Theme switching is now possible
- Better looking edit panel
- New url for CV + redirect to old url
- Cover letter is now a ListPlugin
- Added an avatar image to the Cover

### Fixes

- Fixed image upload via the admin

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