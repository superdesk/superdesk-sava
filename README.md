# Superdesk SAVA

[![CI](https://github.com/BrianMwangi21/superdesk-sava/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/BrianMwangi21/superdesk-sava/actions/workflows/ci.yml)

**SAVA** boils Superdesk down to a single text box. Using natural language, a user
can ask the system to do things — *"create a text article with the headline 'Messi
goes to the finals' and publish it"* — and an LLM agent translates that into real
actions against Superdesk's own API, acting as the logged-in user.

Think "PostHog AI", but for a newsroom.

## Architecture

SAVA plugs into the Superdesk blueprint the same way `superdesk-planning` does: one
repository with a **client** piece and a **server** piece.

```
superdesk-sava/
├── index.ts                     # root Angular module (registers as a Superdesk "app")
├── client/
│   └── sava-extension/          # superdesk-core client extension
│       └── src/
│           ├── extension.ts     # registers the "SAVA" page + nav icon
│           ├── SavaApp.tsx      # the chat thread (chatscope + Superdesk tokens)
│           ├── sava.css         # token-driven theme
│           └── api.ts           # talks to /sava/command
└── server/
    └── sava/                    # pip-installable Superdesk module
        ├── agent.py             # OpenRouter agent loop + confirmation state machine
        ├── views.py             # POST /sava/command endpoint
        ├── default_settings.py
        └── tools/               # the tool framework
            ├── base.py          # Tool / ToolContext / ToolResult + registry
            ├── lookups.py       # shared non-tool helpers (desks, profiles)
            ├── desks/           # one folder per domain,
            ├── profiles/        #   one file per atomic tool,
            └── articles/        #   each self-registers via @tool
```

### Tools

Every tool is a self-describing, self-registering unit — drop a module under
`tools/<domain>/` with an async handler decorated by `@tool(...)` and it appears in
the agent's toolset with no wiring. Tools receive a `ToolContext` (current user +
helpers like `link_to_item`) and return a `ToolResult` (`for_model` text for the
LLM; `summary`/`links`/`data` for the UI).

Current tools, by domain:
- **lookups** — `list_desks`, `list_stages`, `list_content_profiles`,
  `describe_content_profile`, `find_user`, `list_categories`, `list_coverage_types`
- **articles (read)** — `find_articles`, `find_my_articles`, `find_desk_items`,
  `get_article`
- **articles (write)** — `create_article`, `update_article`, `move_article`,
  `spike_article` ⚠️, `publish_article` ⚠️
- **planning** — `describe_planning_profile`, `create_planning_item`, `add_coverage`,
  `search_planning`
- **events** — `create_event`, `update_event`, `search_events`,
  `link_event_to_planning`, `post_event` ⚠️
- **assignments** — `list_my_assignments`

⚠️ = confirmation-gated (human-in-the-loop).

### Self-discovery

Nothing is hardcoded. The agent discovers required fields at runtime from the
instance's own profiles — articles via `content_types`
(`list_content_profiles` → `describe_content_profile`) and events / planning /
coverages via `planning_types` (`describe_planning_profile`) — and asks the user
for whatever a given profile needs. Requirements differ per deployment (Superdesk
vs superdesk-cp vs superdesk-stt) and can change on the fly, so create tools also
accept a generic `fields` object to carry any instance-specific field with no code
change.

### Human-in-the-loop

Tools flagged `requires_confirmation=True` (e.g. publish) don't run immediately:
the agent loop returns a `pending` action, the client shows an approval card
(with a link to review the item in monitoring), and the user's decision comes back
on the next request to resume — a real approval gate, server-enforced.

### Runtime flow

```
User types in SAVA canvas
      │  POST /sava/command  { prompt, conversation, decision? }
      ▼
SAVA endpoint ──► agent loop (tool calling, as the logged-in user)
      │                 │
      │   confirm-gated ▼
      │        returns { pending } ──► client approval card ──► decision ──► resume
      │                 │
      └────────► Superdesk internal API (create/publish/…)
                 returns { reply, actions, conversation, pending }
```

The agent never has more power than the user does — every tool call runs through
Superdesk's normal services and privilege checks. The server is stateless: the
client round-trips `conversation` (memory) and resolves `pending` via `decision`.
Deep links are host-agnostic — tools return a route, the client prepends its own
origin.

## Model / provider

Prototyping uses **OpenRouter** (OpenAI-API-compatible), so we use the official
`openai` Python SDK pointed at OpenRouter's base URL. Defaults live in
`server/sava/default_settings.py` and can be overridden via environment variables:

| Env var | Default | Meaning |
|---|---|---|
| `SAVA_OPENROUTER_API_KEY` | *(none)* | OpenRouter API key |
| `SAVA_MODEL` | `openai/gpt-oss-120b` | model id |
| `SAVA_OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | API base |
| `SAVA_MAX_STEPS` | `6` | max agent loop iterations per turn |
| `SAVA_MAX_HISTORY_MESSAGES` | `20` | conversation-memory cap |

A client that wants a different model just sets `SAVA_MODEL`.

## Development

This repo is referenced from the blueprint via GitHub
(`github:BrianMwangi21/superdesk-sava#develop`), then linked locally for live edits:

```bash
# client
# 1. install this repo's own runtime deps (e.g. @chatscope) — `npx link` does
#    NOT do this, and the host build resolves linked packages via their real
#    path, so it needs superdesk-sava/node_modules to exist.
cd /path/to/superdesk-sava && npm install
# 2. link it into the host client
cd /path/to/superdesk/client && npx link /path/to/superdesk-sava

# server (inside the right pyenv)
cd /path/to/superdesk/server && pip install -Ue ../../superdesk-sava
```

### Tests

The server suite covers the deterministic core — the tool registry and execution
safety, the agent state machine (reply cleaning, history trimming, confirmation
gating), settings resolution, and the pure lookup helpers. It needs no running
Superdesk services (the LLM and resource calls are never hit).

```bash
pip install -r dev-requirements.txt   # pytest + pytest-asyncio
pytest                                 # config lives in setup.cfg
```

### CI

`.github/workflows/ci.yml` runs on every push to `develop`/`main` and on PRs:

- **Lint & types** — `black --check`, `flake8`, `mypy`. No Superdesk install, so
  it's fast and always reliable.
- **Tests** — installs `superdesk-core` and `superdesk-planning` from their
  moving `develop` branches, then runs `pytest`. This is deliberate: the job
  doubles as an integration canary, so if an upstream change breaks SAVA the
  build goes red and we find out immediately rather than during a demo.

## Status

🚧 Prototype, actively evolving. Working today:
- Natural-language create + publish of articles, end to end.
- Multi-turn conversation memory (stateless round-trip).
- Runtime self-discovery of content profiles + required fields.
- Server-enforced approval gate for publishing, with review links.
- Native, token-driven chat UI.

Natural next tools: `find_articles`, `edit_article`, planning items + coverages.
