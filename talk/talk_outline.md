## Outline: *Skip the Overhead: Lean Web Development with Django*

1. **Title & Introduction (~2 min)**
    - **Slide 1: "Who am I?"**
        - Quick personal intro (Django dev since 2013, podcast host, django-resume creator).
        - Set the tone for a practical, experience-based talk.
    - **Slide 2: "What to Expect"**
        - Brief overview of the session:
            1. Why modern web dev became so complex.
            2. How to build interactive sites with less overhead.
            3. A case study with django-resume.

2. **The Mainstream Approach & Its Pitfalls (~5 min)**
    - **Slide 3: "The Mainstream Approach"** (might split into two slides)
        - Show the typical stack:
            - JSON/GraphQL API on the backend
            - Frontend framework (React/Vue) with a global state store
            - CSS frameworks, TypeScript + build pipeline
            - Possibly Kubernetes or other container orchestration
        - *Anecdote:* The dev who inadvertently caused 40s build times due to how the tailwind step ran over the Python
          virtualenv.
        - Emphasize the overhead in team separation, complex build pipelines, and how small issues can snowball into
          major productivity blockers.
    - Wrap up with the *Pinboard quote* about things we thought were going to be easy.

3. **What We Really Want (Non-Functional Requirements) (~2 min)**
    - **Slide 4: "What We Want"**
        - Fast, responsive, SEO-friendly, easy to maintain, real-time updates, etc.
        - Acknowledge that SPAs *promise* this, but we can achieve the same with simpler means.

4. **Introducing Django + htmx + Modern CSS (~4 min)**
    - Explain how server-side rendering (SSR) with Django already covers performance, SEO, and maintainability.
    - **Key point:** htmx allows partial page updates without the overhead of a full SPA.
    - Modern CSS (container queries, advanced layout techniques, etc.) handles much of what used to require heavy JS.

5. **Functional Requirements: django-resume as a Case Study (~4 min)**
    - Summarize the need for a customizable resume system (developers, academics, designers, etc.).
    - **Plugin Architecture**:
        - Using a `JSONField` for data storage → no complicated DB migrations.
        - Plugins each have their own Forms, Templates, and `unique_name`.
        - This keeps the core simple while allowing big customization.

6. **Web Components for UI Edge Cases (~2 min)**
    - Show how web components (e.g., `BadgeEditor`, `EditableForm`) handle dynamic lists or contenteditable fields
      elegantly.
    - Mention the advantage of not needing a heavy React/Vue toolchain and how it integrates with Django forms.

7. **Leveraging LLMs for Automation (~2 min)**
    - **Short mention**: LLMs can generate plugin code, especially with few-shot learning from existing plugins.
    - Eliminates boilerplate when new plugin types are needed (e.g., "add a certifications plugin").

8. **5-Minute Demo (~5 min)**
    - Quickly show:
        1. The Django admin or basic UI for django-resume.
        2. Adding a plugin (e.g., projects or certifications) through the plugin registry.
        3. Basic partial updates with htmx.
        4. A snippet of how contenteditable + `EditableForm` solves styling issues without extra form templates.

9. **Q&A & Closing (~1–2 min)**
    - Invite questions from the audience.
    - **Final Slide: "How to Get in Touch"**
        - Provide GitHub link, Twitter/X handle, or any other contact info.
        - Encourage feedback, contributions to django-resume, or further discussion.

---

### Suggested Timing Breakdown

- **Intro (Slides 1–2):** 2 minutes
- **Mainstream Approach & Pitfalls (Slide 3):** 5 minutes
- **What We Want (Slide 4):** 2 minutes
- **Django + htmx + Modern CSS:** 4 minutes
- **Functional Reqs / Plugin Architecture:** 4 minutes
- **Web Components:** 2 minutes
- **LLMs for Automation:** 2 minutes
- **Demo:** 5 minutes
- **Q&A + Closing:** 1 minute (or 2, if time allows)

**Total:** ~27 minutes — you can trim or slightly shorten sections if needed to keep it to ~25 minutes.

Use this outline as a flexible guide. Adapt the anecdotes and timing to fit your personal presentation style and
audience engagement. Good luck with your talk!

