# Skip the Overhead: Lean Web Development with Django

## Abstract

Do we really need complex JavaScript frameworks to build interactive websites? This talk argues we don’t. By combining Django, HTMX, and web components, we can create fast, interactive sites without unnecessary complexity.

To showcase how these advantages come together in practice, we’ll explore a small example. Introducing [django-resume](https://github.com/ephes/django-resume/), a lightweight third-party Django app that adds a resume and CV section to your site—with no dependencies besides Django itself. It demonstrates:

- Achieving SPA-like behavior using HTMX with server-side rendering.
- Storing all data in a single JSONField to simplify database interactions and data export.
- Enabling inline editing with contenteditable elements and web components.
- Adding features through plugins without database migrations.
- Using JSON data with Large Language Models (LLMs) for content creation.

## Notes

1. **Introduction**
	- Questioning the need for complex frontend frameworks.
	- Introducing django-resume as an example of simplicity in action.
2. **Server-Side Rendering with HTMX**
	- How HTMX provides interactivity without SPA overhead.
	- Benefits for performance and SEO.
3. **Simplifying Data Management with JSONField**
	- Storing all content in one JSONField.
	- Simplifying queries and data export.
4. **Inline Editing with Web Components**
	- Using contenteditable for inline editing.
	- Enhancing user experience with web components.
5. **Extensibility Through Plugins**
	- Adding features without database migrations.
	- Encouraging community contributions.
6. **Leveraging LLMs with JSON Data**
	- Using JSON data for content generation and enhancement.
	- Potential applications and considerations.
7. **Conclusion**
	- Emphasizing the benefits of simplicity.
	- Encouraging leaner development practices.
