# Skip the Overhead: Lean Web Development with Django
## A Case Study in Simple, Maintainable Web Applications

---

# The JavaScript Framework Fatigue

* Complex build pipelines
* Large bundle sizes
* State management overhead
* Frequent breaking changes
* SEO challenges
* Accessibility as an afterthought

---

# Do We Really Need All This?

For many web applications:
* Server-side rendering is enough
* Progressive enhancement > client-side routing
* Forms don't need complex state management
* SEO works out of the box
* Accessibility is simpler

---

# Enter django-resume: A Case Study

A lean Django app that creates interactive resumes:
* Zero JavaScript dependencies
* SPA-like behavior without SPA complexity
* Clean, maintainable architecture
* Extensible through plugins
* Seamless editing experience

---

# The Tech Stack

* Django for routing and templating
* HTMX for interactivity
* Web Components for reusable UI
* JSON fields for flexible data storage
* CSS for styling and animations

No build pipeline. No node_modules. No bundler.

---

# HTMX in Action: Inline Editing

```html
<form hx-post="{{ form.post_url }}"
      hx-target="#identity"
      hx-swap="outerHTML">
  <input type="hidden" 
         data-field="name" 
         name="name" 
         value="{{ form.name.value }}">
  <h2 contenteditable="true" 
      data-field="name">
    {{ form.name.value }}
  </h2>
  <button type="submit">Save</button>
</form>
```

* Seamless updates without page reloads
* Progressive enhancement
* Graceful fallback

---

# Web Components: Reusable without React

```javascript
class BadgeEditor extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <ul class="cluster cluster-list">
        <li>
          <input type="text" placeholder="Add badge">
          <button type="button">Add</button>
        </li>        
      </ul>
    `;
    // Add event listeners...
  }
}
customElements.define('badge-editor', BadgeEditor);
```

* Native browser features
* No framework lock-in
* Encapsulated functionality

---

# JSONField: Flexible Data Storage

```python
class Resume(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    owner = models.ForeignKey(get_user_model(), 
                            on_delete=models.CASCADE)
    plugin_data = models.JSONField(default=dict)
```

Benefits:
* Schema flexibility
* No migrations for plugin data
* Easy data export/import
* LLM-friendly format

---

# Plugin Architecture

```python
class TimelinePlugin(ListPlugin):
    name = "timeline"
    verbose_name = "Timeline"
    
    def get_context(self, request, data, resume_pk):
        return {
            'items': self.items_ordered_by_position(
                data.get('items', [])
            ),
            'edit_url': self.get_edit_url(resume_pk)
        }
```

* Modular functionality
* Clean separation of concerns
* Easy to extend

---

# Performance Benefits

* Fast initial page load
* No client-side routing overhead
* Minimal JavaScript
* Efficient partial page updates
* Cached templates
* No redundant API calls

---

# Developer Experience

* Simple debugging (Python + Browser tools)
* Clear data flow
* Easy to reason about state
* Familiar Django patterns
* Standard HTML/CSS/JS
* No build steps

---

# When to Use This Approach?

✅ Content-focused sites
✅ CRUD applications
✅ Admin interfaces
✅ Forms and workflows
✅ Server-rendered UIs

❌ Real-time applications
❌ Complex client-side state
❌ Offline-first apps
❌ Heavy data visualizations

---

# What About SPAs?

Use them when you need:
* Complex client-state management
* Rich offline functionality
* Real-time features
* Canvas-heavy interfaces

But for many web apps, they're overkill.

---

# Key Takeaways

1. Start simple, add complexity only when needed
2. Use browser features before reaching for frameworks
3. Server-side rendering is often enough
4. HTMX + Web Components = powerful combination
5. JSON storage enables flexibility without complexity

---

# Thank You!

* Project: https://github.com/ephes/django-resume
* Slides: [link to slides]
* Contact: [your contact info]

Questions?