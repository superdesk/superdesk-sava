# Superdesk SAVA

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
├── client/
│   └── sava-extension/        # superdesk-core client extension
│       └── src/
│           ├── extension.ts   # registers the "SAVA" page + nav icon
│           ├── SavaApp.tsx    # the blank canvas: heading + text box + examples
│           └── api.ts         # POSTs the prompt to the server
└── server/
    └── sava/                  # pip-installable Superdesk module
        ├── agent.py           # OpenRouter agent loop + tool dispatch
        ├── tools.py           # tool definitions -> Superdesk internal API
        └── default_settings.py
```

### Runtime flow

```
User types in SAVA canvas
      │  POST /sava/command  { prompt }
      ▼
SAVA server endpoint  ──►  OpenRouter agent loop (tool calling)
      │                          │
      │            each tool call ▼
      └──────────►  Superdesk internal API (as the logged-in user)
                         create_article / publish_article / ...
```

The agent never has more power than the user does — every tool call runs through
Superdesk's normal services and privilege checks.

## Model / provider

Prototyping uses **OpenRouter** (OpenAI-API-compatible), so we use the official
`openai` Python SDK pointed at OpenRouter's base URL. Defaults live in
`server/sava/default_settings.py` and can be overridden via environment variables:

| Env var | Default | Meaning |
|---|---|---|
| `SAVA_OPENROUTER_API_KEY` | *(none)* | OpenRouter API key |
| `SAVA_MODEL` | `openai/gpt-oss-120b` | model id |
| `SAVA_OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | API base |

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

## Status

🚧 Early prototype. First end-to-end slice: create a text article with a headline
and publish it.
