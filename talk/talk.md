# Skip the Overhead: Lean Web Development with Django
## A Case Study in Simple, Maintainable Web Applications

--- <!-- Slide 1 -->

> UIs are big, messy, mutable, stateful bags of sadness.   --[Josh Abernathy](http://joshaber.github.io/2015/01/30/why-react-native-matters/)

# This alone is more than enough to get you in deep trouble.

- HTML
- CSS
- Django

--- <!-- Slide 2 -->

# The Mainstream Approach

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

--- <!-- Slide 3 -->

# How far can we go with the Things on the First Slide?

- Use browser features before reaching for frameworks
- Server-side rendering is often enough
- HTMX + Web Components = powerful combination
- JSON storage enables flexibility without complexity

--- <!-- Slide 4 -->

# django-resume

Just a simple Django app that allows you to create a resume and CV.

- Short Demo?

--- <!-- Slide 5 -->




# Quotes


> god: i have made a Single page webapp
> 
> angels: you fucked up a perfectly good website is what you did.  look at it.  it’s got dependency injections. --[Eric Meyer](https://mastodon.social/@Meyerweb/111103984979396842)



> Anything worth doing is worth doing badly. — G. K. Chesterton

> The B in Benoit B. Mandelbrot stands for Benoit B. Mandelbrot. [Steve Lord](https://bladerunner.social/@stevelord/111127300258697213)

> Everything that irritates us about others can lead us to an understanding of ourselves.  --[Carl Jung](https://wist.info/jung-carl/39693/)