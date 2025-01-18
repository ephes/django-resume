# Skip the Overhead: Lean Web Development with Django

### A Case Study in Simple, Maintainable Web Applications

--- <!-- Slide 1 -->

## Who am I?

> Be nice to us folks who wear glasses. We paid money to see you. --Bob Golen

- Django Developer since 2013
- Python-Podcast Host
- Creator of [django-resume](https://github.com/ephes/django-resume)

## Notes

--- <!-- Slide 2 -->

# What to Expect

> Developers are drawn to complexity like moths to a flame, often with the same result. --Neal Ford

- What's up with modern web development?
- How to build interactive sites with less overhead
- A case study / demo with `django-resume`

## Notes

--- <!-- Slide 3 -->

# Modern Web Development

> god: i have made a Single page webapp
>
> angels: you fucked up a perfectly good website is what you did. look at it. it’s got dependency
> injections. --[Eric Meyer](https://mastodon.social/@Meyerweb/111103984979396842)

- **Backend**
    - JSON/REST APIs
    - (Or, heaven forbid, GraphQL)
- **Frontend**
    - React/Vue/Angular + Store (Redux, Vuex, etc.)
- **CSS**
    - Tailwind or Bootstrap or another large framework
- **Build Pipeline**
    - TypeScript, Webpack/Vite, Babel

Hmm,

## Notes

Ah, modern web development - what a joy! There's so much happening at once. You've
got your trusty relational database sitting there, protected by a backend that's
doing all the heavy lifting with business logic.

Then there's the frontend - a whole different animal altogether. Thank goodness for
all these frameworks that make life easier. Want your JavaScript to feel more like
Java? TypeScript has got you covered. Want your HTML to look more JavaScript-y?
Say hello to JSX. Sure, you might throw in another framework for CSS, but hey,
you'll need something like webpack or vite anyway to bundle everything into
something browsers can actually understand.

Since your app's state lives in the frontend now, that's another ball to juggle.
But don't sweat it - there's a library for everything these days. Need to keep
your frontend and backend in sync? Just serialize and deserialize your state on
both ends. Four JSON data types ought to be enough for anybody! And while everyone
calls them REST APIs, let's be honest - they're just JSON APIs with tight coupling,
just like in the good old client/server days. Nothing actually RESTful about them!
Or you could jump on the GraphQL bandwagon - it's like talking directly to your
database! Forget loose coupling - we're all about that tight integration here!

--- <!-- Slide 4 -->

# Shooting for the Moon

> We choose to go to the moon in this decade and do the other things, not because they are easy, but because they are
> hard. --[John F. Kennedy](https://speakola.com/political/john-f-kennedy-moon-1962)

Fade to:

> “The Programmers’ Credo: we do these things not because they are easy, but because we thought they were going to be
> easy.” – [Pinboard](https://x.com/Pinboard/status/761656824202276864)

## Notes

But there's one challenge that's trickier than all the tech stuff: people. Some
developers are dead set on their favorite programming language and won't budge an
inch. Others would rather write backend code all day than touch HTML or CSS. Next
thing you know, you've got separate frontend and backend teams. And that's where
things get interesting.

Take this scenario: The frontend team needs to use the backend development server,
but they're not exactly Python wizards. They've got their own way of handling
virtual environments. Then there's the Tailwind CLI process scanning through a
gigabyte of dependencies for HTML changes. When it's set up right, it takes
milliseconds. When it's not? Try 40 seconds. No wonder the frontend team's
complaining about slow feedback loops. We only caught this because we were pair
programming. But oh, pair programming is "expensive," they say. Very expensive.
And getting backend and frontend developers to pair together? That's "priceless" -
and by priceless, I mean so expensive that no one will pay for it.

--- <!-- Slide 5 -->

# Non-Functional Requirements: What We Really Want

- Smooth user experience
- Appealing visuals
- Developer experience

## Notes

So maybe we're not choosing SPAs because they're easy. Then why are we? What's
really driving this? Oh right - we want to deliver an amazing user experience.
And by "user," we mean the stakeholders who sign the checks, not the people
actually using the site. It's all about creating that wow factor. The site needs
to look slick, feel smooth, and generally knock their socks off. Heaven forbid
it feels like a website - it needs to feel like a proper desktop app. Full page
reloads? How very 2010.

Then there's the developer experience. Let's be real: HTML and CSS are just...
weird. Do they even count as programming languages? Sure, JavaScript is closer
to the real deal, but that dynamic typing stuff makes people nervous. Nothing
a little TypeScript can't fix though, right?

And hey, surely we can take our trusty enterprise Java development department -
you know, the ones who've been cranking out Spring Boot apps since forever -
and transform them into a cutting-edge web development team. They won't even
know what hit them.

--- <!-- Slide 6 -->

# Achieving Modern Web Goals Without the Bloat

> Einstein repeatedly argued that there must be simplified explanations of nature, because God is not capricious or
> arbitrary. No such faith comforts the software engineer. --Fred Brooks

- Django
- htmx
- Modern CSS

The items on the list could have markers from "The Stack" for example.

## Notes

What if we could have it all? What if we could build sleek, modern websites without
all the complexity? What if we could nail that user experience without drowning in
overhead?

That's where Django comes in. It's been around the block a few times, and it's
still crushing it. You get a rock-solid ORM, a killer admin interface, and all the
bells and whistles right out of the box. Version upgrades? Smooth sailing, at
least in recent years. Try saying that about your average JavaScript framework!
Django is what you'd call "boring technology" - and that's a compliment. You've
only got so many innovation tokens to spend on a project, so why blow them on your
web framework?

For years, people would say "Django doesn't have a frontend story." Everyone was
pairing Django Rest Framework with some JavaScript framework for the frontend. Then
htmx showed up, and suddenly Django's back in the frontend game - better than ever.
And unlike those SPA setups where frontend and backend are joined at the hip
through JSON APIs, htmx actually delivers on the REST promise.

CSS has been stepping up its game too. All those things you needed a preprocessor
for? Now they're built right in (looking at you, CSS custom properties). And with
container queries, you can finally write CSS that responds to its container instead
of the viewport. The main reasons for using CSS frameworks like Bootstrap? Gone.
And while Tailwind's still going strong, let's talk about a different approach:
pure Vanilla CSS that's naturally responsive because it's built from small layout
primitives - kind of like how we build complex software from smaller modules.
Take Tailwind, where you're constantly styling individual elements. But with a
layout primitive from the "Every Layout" book called "The Stack," you can control
spacing between elements using the lobotomized owl selector. And yes, you can even
embrace the cascade - imagine that!

--- <!-- Slide 7 -->
One of them will win!

![One of them will win!](img/three-headed_dragon_htmx.jpg)

And htmx isn't alone in this game. You've got Livewire over in Laravel-land,
Hotwire in the Rails world, and Liveview strutting its stuff in Phoenix. They're
all following the same playbook: add a bit of JavaScript once so you don't have
to write it constantly. Some are more tightly woven into their backend frameworks,
while htmx plays it solo. Hard to say which approach will come out on top, but
one of them definitely will. You can feel which way the wind's blowing on this
one.

So what's the secret sauce here? HOWL (Hypermedia On Whatever you'd Like). Instead
of pushing JSON back and forth, we're sending good old HTML. The client just swaps
out pieces of the page as needed. Simple as that.

Here's where SPAs really shine: updating parts of the page without that dreaded
full reload. Nobody notices a 50-100ms network hiccup, but that 1-1.5 second page
reload with its lovely flash of white? That's when people start drumming their
fingers. You can even get live updates from the server using htmx with polling.
And when you're done polling? Just send a "stop polling" response and call it a
day.

--- <!-- Slide 8 -->

# django-resume: A Case Study in Lean Web Development

![Need to update my CV -> Procrastinate by Building a Resume App!](img/drake_hotline_bling_resume.jpg)

https://imgflip.com/memetemplates

## Notes

So how does all this play out in the real world? Let me tell you about
django-resume. You know how it goes - as a freelancer, you really should update
your CV. Or... you could put that off by building an entire resume app instead.
That's the origin story of django-resume right there.

But hey, I did my homework first. Actually found a few solid options out there.
Only catch? They were all built with heavyweight frameworks like Next.js. And I
thought to myself: I could knock this out with Django. I mean, how hard could it be?

--- <!-- Slide 9 -->

# Functional Requirements

> Technology is the art of arranging the world so we don't have to experience it. --Max Frisch

- **Single Source of Truth**
    - Manage all resume content in one centralized system.

- **Easy Customization**
    - Adaptable to different professional needs:
        - Developers, academics, designers, and more.

## Notes

What are the core functional requirements beyond the obvious needs for speed, polish,
and user experience? At its heart,this project needs to solve a key problem: managing CV
updates in a single, centralized location. Currently, each freelancing platform handles
resumes differently, and LinkedIn adds its own layer of complexity. I want to integrate
myresume directly into my website rather than maintaining it as a separate document.
Building this as a Django app means Ican seamlessly incorporate it into my existing
site.

While my immediate focus is on supporting software freelancers, django-resume should be
flexible enough to serve a broader audience. Academics might need to showcase their
publications, designers their portfolios, and other professionals their specific
achievements. Rather than implementing every possible use case myself, the solution is
tomake django-resume highly customizable and extensible. The priority is creating a
framework that makes it simple for users to add and adapt features to their needs.

--- <!-- Slide 10 -->

# Plugin Architecture

> Anything worth doing is worth doing badly. — G. K. Chesterton

- **Central `JSONField` for Plugin Data**
    - No additional models or migrations required.
    - Each plugin stores its data under its unique namespace in the `JSONField`.

- **Django Forms for Validation**
    - Define and validate the structure of plugin-specific data.

- **Templates for Rendering and Editing**
    - Render plugin data as HTML for display.
    - Provide user interfaces for editing plugin data.

## Notes

How can we implement this flexibility? The solution is a plugin architecture. While I
strongly favor relational databases and Django's ORM, allowing plugins to define their
own models could quickly become unwieldy. Instead, we'll store all plugin data in a
single JSONField. Though this approach has certain limitations, it's an elegant solution
for managing smaller datasets that can be efficiently retrieved in a single database
query. Each plugin maintains its own namespace within the JSONField, preventing data
conflicts. This approach eliminates the need for additional models or migrations.

For data structure definition and validation, we'll leverage Django Forms. The only
requirement is that all data must be JSON-serializable.

The rendering and editing system will be template-based. Each plugin requires a minimum
of two templates: one for rendering the data as HTML, and another for providing the data
editing interface. The core of each plugin includes aget_context method that generates a
dictionary of data to be included in the template rendering context.

--- <!-- Slide 11 -->

# Web Components for UI Edge Cases

> UIs are big, messy, mutable, stateful bags of
> sadness. --[Josh Abernathy](http://joshaber.github.io/2015/01/30/why-react-native-matters/)

- **Examples in django-resume**
    - <badge-editor>:
        - Handles dynamic lists (e.g., skills or tags)
        - Updates locally → Single server request on "Save"
    - <editable-form>:
        - Links `contenteditable=true` fields to hidden form inputs
        - Enables inline editing without custom form templates
- **Why Not SPAs?**
    - Web Components are:
        - Built into the browser → No extra JavaScript framework
        - Standards-based → Durable & future-proof

## Notes

While htmx excels at partial page updates, some scenarios require additional frontend
logic. Consider managing dynamic elements like skills or tag lists. Though we could
implement this functionality with htmx, it would necessitate complex server-side logic to
handle partially edited lists. A simpler backend approach is to use a single view that
processes complete plugin data and either saves it (returning rendered HTML) or returns
the edit interface with any validation errors. This streamlined backend approach does
require some frontend logic for dynamic list management, which is where web components
come in.

We've implemented a custom `<badge-editor>` element to handle dynamic lists. It manages
list updates locally and consolidates changes into a single server request when the user
saves their changes. Similarly, our `<editable-form>`element connects contenteditable
fields with hidden form inputs, enabling inline editing without custom form styling.

Why not opt for a full Single Page Application (SPA)? The advantages of web components
are compelling: they're native browser features requiring no additional JavaScript
frameworks, they're based on web standards ensuring longevity and future compatibility,
and they provide the perfect balance of frontend functionality without the overhead of a
full SPA.While writing web components requires more boilerplate code compared to React
or Vue components, we can leverage LLMs to generate this code and assist with unit test
creation.

--- <!-- Slide 12 -->

# Leveraging LLMs for Automation

> Open source AI models will soon become unbeatable.
> Period. --[Yann LeCun](https://twitter.com/ylecun/status/1713304307519369704?s=12&t=7QYkNVuO9zKdwimgbPv89w)

> Journalism is making the same mistake with AI that they made with bloggers. They jumped to the incorrect conclusion
> that we were trying to do what they do. --[Dave Winer](https://mastodon.social/@davew/112379962302476793)

> ZIZEK: that AI will be the death of learning & so on; to this, I say NO! My student brings me their essay, which has
> been written by AI, & I plug it into my grading AI, & we are free! While the 'learning' happens, our superego
> satisfied,
> we are free now to learn whatever we want --[Zack Brown](https://x.com/LuminanceBloom/status/1600598003391266816)

- **Structured JSON Generation**

- **Streamlining Plugin Development**
    - Use LLMs to generate plugin boilerplate:
        - Forms, templates, and registry setup
        - Example prompt: "Create a plugin for certifications (name, issuer, date)"
    - Saves time and lowers the barrier for customization

## Notes

LLMs offer multiple ways to enhance our development process, beyond just generating web
component boilerplate. One fundamental application is generating sample data. LLMs excel
at creating content that conforms to predefined structures, so we can feed them our
JSONField schema and receive perfectly structured example data in return.

We can take this integration even further. Earlier, we discussed the importance of
maintaining a simple plugin interface to facilitate resume customization for diverse
users. Since we already have a collection of plugins, we could have django-resume
generate pairs of prompts and corresponding plugin implementations to serve as context
for the LLM. This would enable few-shot learning - for instance, when a user requests "
Create a plugin for publications (title, authors,date)", the LLM can reference existing
implementations to generate appropriate code. This approach could significantly lower the
barrier to customization, making it easier for users to extend their resumes with new
plugins.

--- <!-- Slide 13 -->

# Demo: django-resume in Action

1. **Overview of django-resume**
    - The admin interface for managing plugins and resume content.
    - Example plugins: Projects, Certifications, Skills.

2. **Showcasing Interactivity**
    - Adding a new plugin via the registry.
    - Using htmx for partial updates (e.g., editing a skill or certification inline).

3. **Web Components in Action**
    - Demonstrate `BadgeEditor` for dynamic lists.
    - Inline editing with `EditableForm` and `contenteditable=true`.

4. **Highlight Extensibility**
    - How new plugins fit seamlessly into the system.
    - JSONField data structure in action.

*Let’s see how django-resume keeps it simple yet powerful!*

--- <!-- Slide 14 -->

# Q&A & How to Stay in Touch

> The B in Benoit B. Mandelbrot stands for Benoit B.
> Mandelbrot. [Steve Lord](https://bladerunner.social/@stevelord/111127300258697213)

- **Questions?**

- **How to Get Involved**
    - Contribute to [django-resume on GitHub](https://github.com/ephes/django-resume)
    - Share feedback or suggest features.

- **Stay Connected**
    - GitHub: [ephes](https://github.com/ephes)
    - Fediverse: [@jochen@wersdoerfer.de](https://wersdoerfer.de/@jochen)
    - Podcast: [Python Podcast](https://python-podcast.de/show/)
    - Blog: [Ephes Blog](https://wersdoerfer.de/blogs/ephes_blog/)

# Quotes to use

> Everything that irritates us about others can lead us to an understanding of
> ourselves. --[Carl Jung](https://wist.info/jung-carl/39693/)


