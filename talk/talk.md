# Skip the Overhead: Lean Web Development with Django
## A Case Study in Simple, Maintainable Web Applications

--- <!-- Slide 1 -->

# Who am I?

- Django Developer since 2013
- Python-Podcast Host
- Creator of [django-resume](https://github.com/ephes/django-resume)

--- <!-- Slide 2 -->

# What to Expect

- Why modern web development became so complex
- How to build interactive sites with less overhead
- A case study with django-resume

--- <!-- Slide 3 -->

# The Mainstream Approach / maybe two slides

Hmm, maybe a picture of a rocket - or challanger?

Or better: a person sitting in a heap of stuff trying to assemble an IKEA shelf having only an imbus key and a hammer.

 > The Programmers’ Credo: we do these things not because they are easy, but because we thought they were going to be easy --[Pinboard](https://x.com/Pinboard/status/761656824202276864)

Maybe scatter all the words over a slide?

- Backend Framework With
	- JSON API
	- Or god forbid GraphQL
- Frontend Framework With
	- Some store for state management
- CSS Framework
	- Tailwind / Bootstrap / whatever
- Typescript to get lots of squiggly lines + Build pipeline

Separated over at least 2 Teams. Deployed to Kubernetes.

Anecdote: One of the developers put their Python in a weirdly named virtualenv and the tailwind build step ran over it on every change which led to taking 40s instead of a few milliseconds for each. Spoiler: It was the Frontend Dev who was not aware of virtualenvs which made him kind of less productive (found out via pair programming - do it!).

Secure file download problem:
https://www.wimdeblauwe.com/blog/2024/12/31/problems-i-no-longer-have-by-using-server-side-rendering/

--- <!-- Slide 4 -->

# What We Want

- Fast, responsive applications
- Smooth page transitions
- Good developer experience
- SEO friendly
- Maintainable code
- Real-time updates

--- <!-- Slide 5 -->



> UIs are big, messy, mutable, stateful bags of sadness.   --[Josh Abernathy](http://joshaber.github.io/2015/01/30/why-react-native-matters/)

# This alone is more than enough to get you in deep trouble.

- HTML
- CSS
- Django

--- <!-- Slide 5 -->

# How far can we go with the Things on the previous Slide?

- Use browser features before reaching for frameworks
- Server-side rendering is often enough
- HTMX + Web Components = powerful combination
- JSON storage enables flexibility without complexity

--- <!-- Slide 6 -->

# django-resume

Just a simple Django app that allows you to create a resume and CV.

- Short Demo?
- How is this possible?

--- <!-- Slide 5 -->

# Simplifying Data Management with JSONField





# Quotes


> god: i have made a Single page webapp
> 
> angels: you fucked up a perfectly good website is what you did.  look at it.  it’s got dependency injections. --[Eric Meyer](https://mastodon.social/@Meyerweb/111103984979396842)



> Anything worth doing is worth doing badly. — G. K. Chesterton

> The B in Benoit B. Mandelbrot stands for Benoit B. Mandelbrot. [Steve Lord](https://bladerunner.social/@stevelord/111127300258697213)

> Everything that irritates us about others can lead us to an understanding of ourselves.  --[Carl Jung](https://wist.info/jung-carl/39693/)