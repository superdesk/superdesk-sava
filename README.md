# Superdesk SAVA

[![CI](https://github.com/superdesk/superdesk-sava/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/superdesk/superdesk-sava/actions/workflows/ci.yml)

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
        ├── shared_tools.py      # the tools, from superdesk-tools, run as the user
        ├── results.py           # what a tool call shows: reply text, cards, links
        ├── views.py             # POST /sava/command endpoint
        └── default_settings.py
```

### Tools

SAVA's tools come from [superdesk-tools](https://github.com/superdesk/superdesk-tools), the
same newsroom tools the Superdesk MCP server offers. `shared_tools.py` gives the model their
schemas and runs each call through the Superdesk API **as the logged-in user**, with the
session the request came with: Superdesk applies that user's privileges, desk membership and
locks exactly as in its interface.

`SAVA_TOOLSETS` picks the toolsets (default: discovery, search, authoring, workflow,
publishing, planning: about 70 tools). Every schema is sent on every model call, so fewer
toolsets mean faster, cheaper calls.

Nothing is hardcoded: content profiles (`get_content_profile`), the languages of events
(`get_event_languages`) and the like are read from the instance at runtime.

### Chat history

Conversations are stored server-side in the `sava_conversations` Mongo resource,
scoped to the logged-in user, and listed in a sidebar (grouped by day) with
rename and delete. The first turn creates a conversation titled from the prompt,
then a small model call replaces that with a short title (best effort). Because
this is a new resource, run the usual `python manage.py app:initialize_data` once
after installing so its Mongo index is created.

### Provenance

Articles, events and planning items the tools create or edit carry a record of it under
`extra.ai_provenance`, written by superdesk-tools with SAVA as the agent:

```json
"extra": {"ai_provenance": {"created": true, "actions": [
  {"agent": "sava", "tool": "create_planning_item", "at": "2026-09-01T20:14:03+00:00",
   "user": "<user id>", "model": "openai/gpt-oss-120b", "conversation": "<chat id>"}
]}}
```

The human stays the item's creator. Workflow actions (publish, spike, cancel...) are not
recorded there; the chat history keeps those. `SAVA_PROVENANCE_TAG` (e.g. `AI-assisted`) also
adds a visible `subject` entry (scheme `ai_provenance`). Note that `extra` and `subject` are
part of NINJS publish output, so subscribers receive the provenance unless a formatter strips it.

### Streaming

The canvas talks to `POST /sava/command/stream`, which returns server-sent
events: `status` and `tool_start` (progress), `action` (a finished tool call),
`delta` (reply text as it arrives), `discard` (drop narration that preceded a
tool call), then `done` with the same body `POST /sava/command` returns. Closing
the connection (the Stop button) cancels the turn server-side: the agent keeps
whatever reply text arrived, closes any half-run tool call in the history, and
saves the turn. `POST /sava/command` remains for non-streaming clients.

### Human-in-the-loop

Tools that need consent (publishing, spiking, cancelling, replacing an article's text...)
answer with a question instead of acting. The agent loop returns it as a `pending` card with
the tool's own question, written from the item as it is now; the user's decision comes back
on the next request. On a yes the tool is called again and acts, unless its question changed
in the meantime, in which case the user is asked again.

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
      └────────► Superdesk API, as the user (superdesk-tools)
                 returns { reply, actions, conversation, pending }
```

The agent never has more power than the user does — every tool call goes through
Superdesk's API with the user's own session. The server is stateless: the
client round-trips `conversation` (memory) and resolves `pending` via `decision`.
Deep links are host-agnostic — tools return a route, the client prepends its own
origin.

## Model / provider

Prototyping uses **OpenRouter** (OpenAI-API-compatible), so we use the official
`openai` Python SDK pointed at OpenRouter's base URL. Defaults live in
`server/sava/default_settings.py` and can be overridden via environment variables
or in the Superdesk `settings.py` (environment wins, then `settings.py`, then the
defaults):

| Env var | Default | Meaning |
|---|---|---|
| `SAVA_OPENROUTER_API_KEY` | *(none)* | OpenRouter API key |
| `SAVA_MODEL` | `openai/gpt-oss-120b` | model id |
| `SAVA_OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | API base |
| `SAVA_MAX_STEPS` | `6` | max agent loop iterations per turn |
| `SAVA_MAX_HISTORY_MESSAGES` | `20` | conversation-memory cap |
| `SAVA_TOOLSETS` | `discovery,search,authoring,workflow,publishing,planning` | superdesk-tools toolsets the model gets |
| `SAVA_ALLOW_PUBLISH` | `1` | whether the publishing tools exist (they always ask first) |
| `SAVA_PROVENANCE_TAG` | *(empty)* | a subject tag for items SAVA creates or edits |
| `SAVA_SUPERDESK_API_URL` | *(this Superdesk's `SERVER_URL`)* | the API the tools call |

A client that wants a different model just sets `SAVA_MODEL`. To point SAVA at a
model you host yourself, see [docs/SELF_HOSTED.md](docs/SELF_HOSTED.md).

Every turn writes one `SAVA turn:` log line at INFO with the model, outcome,
number of model calls, tools run, prompt/completion token counts, wall time and
user id — the raw data for any cost or latency discussion.

## Development

This repo is referenced from the blueprint via GitHub
(`github:superdesk/superdesk-sava#develop`), then linked locally for live edits:

```bash
# client
# 1. install this repo's own runtime deps (e.g. @chatscope) — `npx link` does
#    NOT do this, and the host build resolves linked packages via their real
#    path, so it needs superdesk-sava/node_modules to exist.
cd /path/to/superdesk-sava && npm install
# 2. link it into the host client
cd /path/to/superdesk/client && npx link /path/to/superdesk-sava

# server (inside the right pyenv); superdesk-tools is private: installing needs an SSH key that reads it
cd /path/to/superdesk/server && pip install -Ue ../../superdesk-sava
# to work on the tools too, install them from a local checkout
pip install -e ../../superdesk-tools
```

### Tests

The server suite covers the deterministic core — the agent state machine (reply
cleaning, history trimming, confirmation round-trips), the shared-tools adapter
(schemas, results, cards), and settings resolution. It needs no running
Superdesk services (the LLM and resource calls are never hit).

```bash
pip install -r dev-requirements.txt   # pytest + pytest-asyncio
pytest                                 # config lives in setup.cfg
```

### CI

`.github/workflows/ci.yml` runs on every push to `develop`/`main` and on PRs:

- **Lint & types** — `black --check`, `flake8`, `mypy`. No Superdesk install, so
  it's fast and always reliable.
- **Client lint** — `eslint` over the extension with the shared
  `superdesk-code-style` rules. The TypeScript type-check needs the host's
  `superdesk-api` typings, so it runs as part of the Superdesk client build rather
  than here.
- **Tests** — installs `superdesk-core` and `superdesk-planning` from their
  moving `develop` branches, then runs `pytest`. This is deliberate: the job
  doubles as an integration canary, so if an upstream change breaks SAVA the
  build goes red and we find out immediately rather than during a demo. It needs
  the repository secret `SUPERDESK_TOOLS_TOKEN` (read access to superdesk-tools).

## Status

🚧 Prototype, actively evolving. Working today:
- Natural-language create + publish of articles, end to end.
- Multi-turn conversation memory (stateless round-trip).
- Runtime self-discovery of content profiles + required fields.
- Server-enforced approval gate for publishing, with review links.
- Native, token-driven chat UI.

New tools come from superdesk-tools, so the MCP server and SAVA gain them together.
