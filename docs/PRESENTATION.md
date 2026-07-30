# superdesk-sava — presentation blueprint

A tight 5-slide deck to run *before* the live demo. Feed it into a slide
generator (e.g. Gemini) to produce the deck. Show the slides, then switch to the
app and walk `docs/DEMO.md`.

## Prompt to paste into the slide generator

> Turn the attached blueprint into a polished slide deck (16:9). One slide per
> "Slide N" section; use the headline as the title and the bullets as short,
> spoken talking points (not paragraphs). Style: minimal newsroom-tech — lots of
> whitespace, one idea per slide, a single restrained accent color, clean
> sans-serif. Build the diagram and logo row where noted.

---

## Slide 1 — Intro
**superdesk-sava**
*One text box for the whole newsroom — Superdesk, driven in plain English.*
- Superdesk has a button for everything. superdesk-sava is one text box that drives them.
- You type what you want; an AI agent does it through Superdesk's real API.

---

## Slide 2 — Others are already doing it
**Software is collapsing into a single chat box.**

*(clean logo row + one-liners)*
- **PostHog** — dashboards → "ask your analytics"
- **Linear** — issue forms → AI agents you assign work to
- **Intercom** — ticket queues → an AI agent that resolves it
- **GitHub Copilot / Vercel v0** — menus & code → describe it, get it

Every category is moving here. Newsrooms are next.

---

## Slide 3 — How it works
**A natural-language agent wired into Superdesk's own API.**

```
You type  →  sava agent (LLM + 26 tools)  →  Superdesk's real services  →  done
                     │
              human approval gate before anything ships
```
- Acts **as you** — never more powerful than the logged-in user.
- **Human-in-the-loop** — publish / spike / post pause for approval.
- **Nothing hardcoded** — reads each instance's own required fields at runtime, so it fits any Superdesk deployment.

---

## Slide 4 — Live demo
**Let's drive Superdesk in plain English.** *(switch to the app)*
- Find my articles → what's on a desk → create + publish (with the gate)
- Ask what an event needs → create it → follow-up by memory: "spike the first one"

---

## Slide 5 — Try it
**superdesk-sava**
- Open source, plugs in like superdesk-planning.
- **github.com/BrianMwangi21/superdesk-sava**
