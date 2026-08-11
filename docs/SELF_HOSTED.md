# Self-hosting the SAVA model

SAVA talks to the model through an **OpenAI-compatible chat-completions API**. By
default that's a cloud provider (OpenRouter), billed per token. You can instead
point SAVA at a **model you host yourself** — on your own server, in your own
network — and pay only for the machine, not per token.

This is a **configuration change, not a code change**: SAVA is model-agnostic by
design, so each deployment chooses its own endpoint and model.

---

## 1. The switch

SAVA reads three settings (env-first, see `server/sava/default_settings.py`). To
use a self-hosted endpoint, set:

| Variable | Cloud (default) | Self-hosted (example) |
|---|---|---|
| `SAVA_OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | `http://<your-host>:11434/v1` |
| `SAVA_MODEL` | a cloud model id | the local model tag, e.g. `<model>:<size>` |
| `SAVA_OPENROUTER_API_KEY` | your real key | any non-empty string (see note) |

> **Note on the API key:** most self-hosted runtimes ignore the key, but SAVA
> treats an *empty* key as "not configured" and won't start the client. Set it to
> any placeholder (e.g. `local`) when self-hosting.

A tidy pattern is to keep both configs in the environment file and comment out the
one you're not using, so switching back to cloud is a three-line edit:

```bash
# --- self-hosted ---
SAVA_OPENROUTER_BASE_URL=http://<your-host>:11434/v1
SAVA_MODEL=<model>:<size>
SAVA_OPENROUTER_API_KEY=local
# --- cloud (uncomment to switch back) ---
# SAVA_OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
# SAVA_MODEL=<cloud-model-id>
# SAVA_OPENROUTER_API_KEY=<your-real-key>
```

Environment changes are read at server start, so **restart the Superdesk server**
after editing them.

---

## 2. What the model must support

SAVA drives Superdesk entirely through **tool / function calling** — every action
is a structured tool call. So the single hard requirement is:

- **The model must support tool calling.** A model that only chats will *look*
  like it works but never actually *do* anything (it produces text where a tool
  call should be). This is non-negotiable, and many small models don't support it.

Secondary but important:

- **Enough context window.** SAVA sends a system prompt plus the full tool
  schema on every call. Make sure the model's context comfortably fits that
  prompt **plus** room for the response, or the runtime will silently truncate the
  prompt and the model will misbehave (dropped fields, malformed calls).

### Verifying tool support

If you use [Ollama](https://ollama.com), the model's capabilities are declared on
its library page and in the CLI:

```bash
# Filter the library to tool-capable models:
#   https://ollama.com/search?c=tools

# Confirm a pulled model reports "tools" (ground truth from the manifest):
ollama show <model>:<size>     # look for "tools" under Capabilities
```

Only bare model names (no `user/` prefix) are first-party/official builds; a
`someuser/model` name is a community re-upload — verify before relying on it.

---

## 3. Standing up an endpoint (Ollama example)

Any OpenAI-compatible server works (Ollama, vLLM, llama.cpp server, etc.). Ollama
is the simplest for a single box:

```bash
# 1. Install
curl -fsSL https://ollama.com/install.sh | sh

# 2. Pull a tool-capable model
ollama pull <model>:<size>

# 3. (optional) confirm tool support
ollama show <model>:<size>
```

Ollama exposes the OpenAI-compatible API at `http://<host>:11434/v1`.

### Making it reachable and stable

By default Ollama binds to localhost. To let the Superdesk server reach it across
the network, and to keep it responsive, set a few service options (here via a
systemd drop-in, `/etc/systemd/system/ollama.service.d/override.conf`):

```ini
[Service]
# Listen on all interfaces (see the Security section before doing this)
Environment="OLLAMA_HOST=0.0.0.0:11434"
# Give the prompt (system + tools) room so it isn't truncated
Environment="OLLAMA_CONTEXT_LENGTH=8192"
# Keep the model resident so it doesn't reload between requests
Environment="OLLAMA_KEEP_ALIVE=-1"
```

```bash
systemctl daemon-reload && systemctl restart ollama
```

---

## 4. Choosing a model and sizing the host

Two independent decisions: **which model** (capability) and **what hardware**
(how fast it runs). They trade off directly.

- **Tool calling is the filter.** Start only from models that support it.
- **Small models on CPU** are cheap to run and fine for **simple, single-step
  commands**, but tend to struggle with **complex, multi-step or deeply-nested
  tool flows** (e.g. creating an item *and* attaching sub-objects in one turn).
- **More capable models** handle the full toolset reliably, but at their size they
  effectively need a **GPU** to respond at a usable speed. On CPU, a large model
  may be correct but far too slow to use interactively.
- **Rule of thumb:** match the host to the model tier. A small model wants a
  modest CPU box; a capable model wants a GPU. Either way it's a **fixed** cost you
  control, rather than per-token billing — which is the point of self-hosting.

Pick the smallest model that reliably handles the flows your users actually need,
then size the host to run *that* model at an acceptable speed.

---

## 5. Performance notes

These are the levers that matter when self-hosting, especially on CPU. The numbers
below are **illustrative** — measure on your own hardware.

- **Cold vs. warm.** The first request after the model loads is much slower (it
  loads weights and processes the full prompt from scratch). Subsequent requests
  are far faster. Send a throwaway "warm-up" request before a live session.
- **Keep the model resident.** A keep-alive setting (above) stops the runtime from
  unloading the model between requests, which would re-introduce the cold penalty.
- **Prompt caching depends on a stable prefix.** Runtimes cache the leading part of
  the prompt and reuse it when it doesn't change. SAVA deliberately keeps the
  system-prompt + tool-schema prefix identical across calls (the per-request date
  is attached to the user turn, not the system prompt) so this cache stays warm.
  Anything that changes the prefix every call defeats it and forces a full
  re-process.
- **Context sizing.** If the prompt (system + tools) exceeds the runtime's context,
  it gets truncated and the model misbehaves. Give it headroom (see
  `OLLAMA_CONTEXT_LENGTH`).
- **The tool payload is the dominant per-call cost.** SAVA advertises its whole
  toolset on every call; on CPU, processing that payload is the main latency. A
  bigger/faster host is the direct lever. (Sending fewer tools per call is a
  possible future optimization, but it's a general cost/reliability feature, not a
  requirement.)
- **Host request timeout.** The Superdesk server may cap request duration. A slow
  first (cold) call can exceed the default, surfacing to the browser as a network
  reset. Raise it if needed — for the bundled hypercorn config, set `WEB_TIMEOUT`
  (seconds) in the server environment.

---

## 6. Security

If you set `OLLAMA_HOST=0.0.0.0`, the API is reachable by anything that can route
to the box, **with no authentication**. Open endpoints get found by scanners and
abused. Options, roughly most to least secure:

1. **Keep it private.** Leave the model server on localhost / a private network and
   reach it from the Superdesk server over an **SSH tunnel** or a private overlay
   (e.g. WireGuard/Tailscale). Nothing is exposed publicly.
2. **Expose, but firewall to one source.** If it must listen publicly, restrict the
   port to **only the Superdesk server's IP** (a cloud firewall is safer than an
   on-box one — a bad on-box rule can lock you out of SSH). Always keep the SSH
   port open for yourself.
3. **Open (experiments only).** Wide-open is fine for a short, disposable test —
   tear it down or lock it down afterwards.

---

## 7. Reverting to cloud

Swap the commented block back (Section 1) and restart the server. Because it's just
configuration, you can keep both a cloud and a self-hosted profile side by side and
switch per deployment — useful for comparing behaviour and cost.
