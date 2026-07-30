# SAVA — presentation blueprint

A slide-by-slide content blueprint for the SAVA talk. Feed it into a slide
generator (e.g. Gemini) to produce the deck, or read it straight as speaker notes.

## Prompt to paste into the slide generator first

> You are a presentation designer. Turn the following slide-by-slide blueprint
> into a clean, modern deck (16:9). Use a minimal newsroom-tech aesthetic: lots
> of whitespace, one strong idea per slide, a restrained accent color. Keep body
> text short — bullets are prompts for me to speak to, not paragraphs. Add simple
> diagrams where noted. Here is the blueprint:

---

## Slide 1 — Title
**SAVA — One text box for the whole newsroom**
Subtitle: *Superdesk, driven in plain English.*
Your name · Sourcefabric · 30 July 2026

---

## Slide 2 — The shift I noticed
**Software is collapsing into a single chat box.**
- For 20 years, products grew by *adding buttons* — more menus, more panels, more tabs.
- The best products of the last two years are doing the opposite: **one input, natural language, the software figures out the rest.**
- This isn't a chatbot bolted on the side. It's becoming the *primary way you drive the product.*

*Speaker note: This is the trend that made me build SAVA.*

---

## Slide 3 — It's already happening (the market proof)
**Everyone is moving the same direction.** *(grid of logos + one-liners)*

| Product | The old way → the new way |
|---|---|
| **PostHog (Max)** | Dashboards & filters → "ask your analytics a question" |
| **Linear** | Issue forms & menus → command bar + AI agents you assign work to |
| **Notion** | Pages & databases → "ask Notion" / AI writes and finds |
| **Intercom (Fin)** | Ticket queues → an AI agent that resolves the conversation |
| **Vercel (v0)** | Config & code → describe a UI, get the app |
| **GitHub (Copilot)** | Menus & docs → chat that writes and explains code |
| **Salesforce (Agentforce)** | CRM screens → agents that take actions in the CRM |
| **Shopify (Sidekick)** | Admin panels → "set up my store" in plain English |

*Speaker note: Analytics, dev tools, support, CRM, commerce — every category. Newsrooms are next.*

---

## Slide 4 — Two generations of this idea
**Not all "AI in product" is equal.**
- **Gen 1 — Copilot:** it *answers questions.* "What were my sales last week?" Read-only, safe, useful.
- **Gen 2 — Agent:** it *takes actions,* as you, through the product's real API. "Create this article and publish it."
- Gen 2 is harder — and it's where the real leverage is. **SAVA is Gen 2.**

---

## Slide 5 — The problem, in a newsroom
**Superdesk has a button for everything.** *(screenshot of the crowded UI)*
- Powerful, but every task means hunting through desks, stages, profiles, menus.
- New journalists face a steep learning curve.
- The knowledge of *how* to do things lives in people's heads, not the interface.

---

## Slide 6 — The idea
**What if Superdesk were one text box?**
> *"Create a text article headlined 'SAVA goes live', then publish it."*
- No menus. No ids. No clicking through five screens.
- Plain English in → real Superdesk actions out.
- **"PostHog AI, but for a newsroom."**

---

## Slide 7 — Live demo *(the centerpiece)*
**Watch it drive Superdesk.** *(placeholder — switch to the live app here)*
Demo arc:
1. "Show me the articles I've written" → real search
2. "What's on the Default Desk?" → resolves the desk by name
3. "Create a text article… and publish it" → **approval card pops up**
4. "What's required to create an event here?" → reads the instance's own rules
5. "Spike the first one" → remembers context, gates the destructive action

---

## Slide 8 — How it works
**A natural-language agent wired into Superdesk's own API.** *(simple diagram)*
```
You type  →  SAVA agent (LLM + tools)  →  Superdesk's real services  →  done
                     │
              human approval gate before anything ships
```
- One text box (client extension) + an agent loop (server module).
- **26 tools** — search, create, edit, publish, plan, cover, assign.
- Plugs into Superdesk the same way Planning does.

---

## Slide 9 — Three things that make it real (not a toy)
**1. It acts *as you.***
Every action runs through Superdesk's normal permission checks. The agent is never more powerful than the user.

**2. Human-in-the-loop.**
Publishing, spiking, posting an event — all *pause* for an explicit approval card. Destructive actions always get a human check.

**3. Nothing is hardcoded.**
It reads each instance's *own* required fields at runtime. Drop it into superdesk-cp or superdesk-stt and it learns *their* rules — zero code change.

*Speaker note: #3 is the "pluggable" superpower — one extension that fits every Superdesk deployment.*

---

## Slide 10 — It's a real repo, not a hackathon script
**Built to ship.**
- 42 automated tests over the core logic.
- CI that also acts as an **integration canary** — if upstream Superdesk changes and breaks us, we find out immediately.
- Open source (AGPLv3), documented, with a demo runbook.

---

## Slide 11 — Why this matters for Superdesk
**The interface stops being the bottleneck.**
- Onboarding: a new journalist is productive on day one.
- Speed: multi-step workflows become one sentence.
- Accessibility: the product meets people in their own words.
- A foundation: every new capability is just *another tool* the agent can use.

---

## Slide 12 — Where it goes next
**From assistant to autonomous newsroom teammate.**
- More domains (ingest, publishing workflows, analytics).
- Proactive suggestions ("this event has no coverage assigned").
- Voice input.
- Per-newsroom tuning.

---

## Slide 13 — Close
**Superdesk has a button for everything.**
**SAVA is one text box that drives them all —**
**in plain English, as you, with a human in the loop before anything ships.**
*Thank you · Questions?*
