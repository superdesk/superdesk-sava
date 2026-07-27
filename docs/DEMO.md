# SAVA demo runbook

A curated, escalating sequence that shows the full range in ~5 minutes. Prompts
are written for a stock Superdesk instance (desks *Default Desk* / *Alternate
Desk*, profiles *Text* and *Basic One*). Adjust names to your data.

## Pre-flight (do this before you present)

- [ ] Server running with `SAVA_OPENROUTER_API_KEY` set (check `/sava/command`
      responds, not the "SAVA is not configured" message).
- [ ] Client built/linked; the SAVA icon shows at the bottom of the nav (after
      Planning).
- [ ] You're logged in as a user with a desk (e.g. *Admin Admin*).
- [ ] One warm-up prompt already sent once, so the model/provider is hot.
- [ ] Server on the latest `develop` (events tools + date injection + robustness).

## The arc

Each step: **type this** → *what fires* → **point this out**.

### 1. Read — "what have I written?"
**Type:** `Show me the articles I have authored`
*Fires:* `find_my_articles`
**Point out:** plain English → a real federated search, results as cards with
"open" deep links. This is the whole thesis in one line.

### 2. Desk awareness
**Type:** `What's on the Default Desk right now?`
*Fires:* `find_desk_items`
**Point out:** it resolved the desk by **name** — no ids, no menus.

### 3. Create + human-in-the-loop publish (the flagship)
**Type:** `Create a text article headlined "SAVA goes live" with a short body, then publish it`
*Fires:* `list_content_profiles` / `describe_content_profile` → `create_article`
→ **publish pauses** with an approval card.
**Point out:**
- It discovered the *Text* profile's required fields **at runtime** — nothing
  about fields is hardcoded.
- Publishing is **server-enforced human-in-the-loop**: the card is a real gate,
  with a link to review the item first. Click **Publish** to approve.

### 4. Runtime discovery for planning (the "pluggable" story)
**Type:** `What's required to create an event here?`
*Fires:* `describe_planning_profile`
**Point out:** requirements come from the instance's `planning_types` — on
superdesk-cp or superdesk-stt this returns *their* rules with zero code change.

**Then type:** `Create an event this Friday at 9am called "AI in the Newsroom"`
*Fires:* `create_event`
**Point out:** it resolved "this Friday 9am" to a real ISO datetime using the
current-date context injected into the prompt.

### 5. Planning item + coverage
**Type:** `Create a planning item for today about the AI conference and add a text coverage`
*Fires:* `create_planning_item` (+ coverage), or `create_planning_item` then
`add_coverage`.
**Point out:** coverage types are pulled from the vocabulary, not guessed.

### 6. Assignments
**Type:** `What are my assignments?`
*Fires:* `list_my_assignments`
**Point out:** acts as the logged-in user — never more powerful than they are.

### 7. Multi-turn memory
**Type (follow-up, no ids):** `Spike the first one`
*Fires:* resolves "the first one" from the earlier result in the same
conversation → `spike_article`, which is also gated, so a second approval card
appears.
**Point out:** two things at once — it **remembered** the earlier result (the
server is stateless; the client round-trips the conversation), and spiking is
gated too, so destructive actions always get a human check. Approve or cancel to
show the gate both ways.

## If something goes sideways

- **A tool errors live:** the agent reports it in one plain sentence (by design)
  and keeps the chat usable — no traceback in the canvas. Just rephrase.
- **Model returns nothing / odd prefix:** channel markers are stripped; a blank
  reply falls back to "Done." Re-send.
- **"SAVA is not configured":** the API key isn't set in the server env — restart
  the server with `SAVA_OPENROUTER_API_KEY` exported.
- **Relative date looks off:** the prompt is fed the current UTC time + instance
  timezone; state the date explicitly if you want to remove all doubt.

## One-liner for the intro

> "Superdesk has a button for everything. SAVA is one text box that drives them —
> in plain English, as you, with a human in the loop before anything ships."
