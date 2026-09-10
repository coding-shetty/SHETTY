# Architecture

```text
Local browser UI (no external assets; relative /api URLs)
  │ same-origin, per-process mutation token, bounded request body
  ▼
FastAPI application — one server per private data directory
  ├── Ollama client → HTTP loopback only
  │     /api/tags → /api/show → verified capability/size/locality checks
  │     /api/chat → ordinary answer + optional proposals, NEVER execution
  │     one generation at a time; 4K context; 768-token reply budget
  ├── SQLite store → conversations, notes, tasks, approved folders, audit journal
  ├── Approval queue → pending → running → executed / failed
  │                       └── denied / expired (terminal)
  ├── Bounded tool dispatcher → memory, task, text-file read, allowlisted macOS open
  ├── Optional native output → macOS say / notification
  └── 15-second reminder scheduler → transactional in-app event + optional OS notice
```

## Modules

- `config.py`: local-only connection configuration and model profile guardrails.
- `ollama.py`: metadata discovery, capability verification, chat and unload; no model downloads or browser calls to localhost.
- `app.py`: API, conversation assembly, single-generation lock, lifecycle.
- `security.py`: ASGI host/origin/token checks, actual request-byte bound including chunked bodies, CSP and browser permissions policy.
- `db.py`: short-lived SQLite connections, schema-version guard, transactional approval and scheduler claims. No ORM or vector database.
- `instance.py`: filesystem lock prevents multiple schedulers/recovery routines for the same data directory.
- `tools.py`: Pydantic-validated finite tool registry; descriptor-relative, no-symlink text-file reads; fixed macOS command arguments. No shell or dynamic imports.
- `scheduler.py`: overdue one-off reminder handling. No LLM invocation during a scheduler tick.
- `service.py`: explicit per-user launchd install/status/uninstall.
- `static/`: dependency-free web client; escaped text, no raw model HTML or remote image rendering.

## Context and memory

Only user-selected preferences/relevant notes and a small active-task snapshot are added when saved context is enabled. Matching is simple keyword scoring, not embeddings or perfect recall. A rolling character budget keeps recent chat groups together. It is a heuristic—not tokenizer-exact context accounting. Ollama's `num_ctx` is the actual context limit, and older/longer information can be omitted.

Reference data has a separate untrusted-data label and never changes the tool allowlist. Native assistant/tool groups are assembled from persisted proposal status, so a pending request is explicitly described as **not executed**. Executed results, including bounded file excerpts, can be used on the next user turn. Manual requests linked to a conversation are also reference context. The application never chains another generation or action automatically after approval.

The model's separate `thinking` field is neither displayed nor stored. Requests use `think: false` only when thinking support is reported. The model may still make incorrect natural-language claims; the application-owned approval journal, not chat wording, is the source of execution status.

## Failure semantics

- A disconnected Ollama does not disable memory/tasks and does not trigger cloud fallback.
- Invalid, unavailable, unoffered, or excess model tool calls are not queued; at most three valid calls from one reply can be proposed.
- Approval is claimed atomically before execution. A double click/replayed request cannot run an action twice.
- A process restart marks interrupted `running` approvals as failed/indeterminate after acquiring the instance lock. It never retries them; the action might have happened before the crash.
- Reminder notification claims and in-app events are committed together. Reopening a delivered task does not send the same reminder again. Set a new reminder by creating a new task.
- Native notifications are best effort after the transaction. A crash may lose an OS notification but not its in-app record.
- The audit journal retains the latest 1,000 ordinary events; the UI displays the latest 100. Conversations, memories, tasks, and approval records are not automatically purged.

## Extending the tool registry

A new tool needs a strict argument model, narrow capabilities, an explicit availability gate, human-readable approval details, revalidation at execution, a bounded result, an audit event, and negative tests. Add it to the fixed registry, not a runtime plugin loader. Do not make arbitrary commands, package installation, or permissions changes model-callable.

See the security and roadmap documents before adding Playwright, Shortcuts, transcription, or image input.
