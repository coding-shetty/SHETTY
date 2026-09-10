# SHETTY

**A local-first personal assistant for your Mac.** A place to think, remember, and get things done—powered by an existing Ollama model, with you in control.

This is a working **v0.1 foundation**, not a fully autonomous movie-style JARVIS. It defaults to `qwen3.5:4b` for the confirmed **base Apple M4 / 16 GB unified-memory** MacBook Pro. No paid APIs, cloud credentials, frontend build system, or new model downloads are required.

## What works now

| Capability | Boundaries |
| --- | --- |
| Local chat through Ollama | One generation at a time; 4,096-token context; 768-token reply budget; 2-minute model keep-alive. No fabricated offline replies. |
| Persistent conversations | SQLite storage; recent conversations; deletion of a conversation and its linked approval/file-result records. |
| Notes and preferences | Create, edit, search, and delete. Relevant notes, preferences, and active tasks can be included in local model context; this is optional, bounded, and not perfect recall. |
| Tasks and one-off reminders | Persisted locally; checked every 15 seconds while the server runs. Overdue reminders appear once after waking/restarting. Optional macOS notifications. |
| Approval-based tools | Model suggestions are enabled only when Ollama reports tool support. Every tool request must be approved once, within 10 minutes. Declining does nothing. |
| Scoped text-file reads | No folders approved by default. Approve a dedicated folder, then each individual read. UTF-8 text only, up to 64 KiB; no writes, hidden files, or symlinks. |
| macOS application/website opening | Fixed app allowlist and HTTP/HTTPS URLs. Opening is not controlling an app or reading a website. |
| Voice output | Click the speaker beside a reply to use macOS's built-in `say`; speech plays on the Mac running SHETTY. No microphone capture or cloud TTS. |
| Optional login service | Explicit per-user `launchd` installation. Starts SHETTY at login; does not start Ollama, wake the Mac, or prevent sleep. |

**Not implemented:** microphone transcription, wake words, Playwright browsing, app-content automation, screenshots/vision, screen clicking, arbitrary shell commands, recurring autonomous jobs, plugin installation, or model downloads. See [the roadmap](docs/ROADMAP.md).

## Run on your Mac

You need **Python 3.11 or later** and your existing Ollama installation. If `python3 --version` is older, install a current Python from [python.org](https://www.python.org/downloads/macos/) or your usual trusted package manager. Do not replace macOS's system Python.

From this checkout:

```sh
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Open your already-installed Ollama app. Alternatively, if Ollama is not already serving, run this in a separate Terminal tab:

```sh
ollama serve
```

Do not start a second Ollama server if its app is already running. Then:

```sh
python -m shetty doctor
python -m shetty
```

Open **http://127.0.0.1:8765**. The `shetty` command also works while the virtual environment is active. Use Control-C to stop the foreground server.

`doctor` checks the selected installed model and `/api/show` metadata without loading or downloading a model. Its exit code is 1 if Ollama/the selected model is unavailable. Memory and task management still work without Ollama.

### First five minutes

1. In **Settings**, check the local engine. Start with the already-installed `qwen3.5:4b`. No `ollama pull` is needed.
2. Send a short chat. Verify the response and latency on your actual Mac.
3. Add a harmless preference in **Memory**, then ask a relevant question. Turn **Use saved context** off to stop future automatic memory/task inclusion. Earlier chat text is not retroactively forgotten.
4. Create a task/reminder. Reminders appear in **Tasks** and **Activity**; enable macOS notifications only if you want them.
5. On your Mac, use the composer's **+** workbench to propose opening Calculator. Review it in **Activity**, choose **Approve once**, and check the result. No model tool support is needed for the manual workbench.

For a model-proposed tool, review the exact arguments in the conversation. After approval, **Continue with this result** explicitly requests another local reply. There is no autonomous agent loop. If a model does not report tools, plain chat and the manual controls still work.

### Approved files

Create a small folder specifically for material you want SHETTY to read, for example `~/Documents/SHETTY Notes`. Add its absolute path in **Settings → Approve a folder**. Then request a relative text-file path through the workbench or a tool-capable model.

Approval saves the file result in the local approval record. If linked to a conversation, a bounded excerpt can be sent to the local model on a later turn. Revoking the folder stops future reads, not historical excerpts. Delete the linked conversation to remove its records; standalone manual approval records are retained in the local database. Never place secrets in approved folders—filename checks cannot identify every sensitive file or hard link.

## Model and memory budget

The target is the **base M4, not M4 Pro**. These are conservative, size-based starting points, **not benchmarks of these exact models**:

- **Default:** installed `qwen3.5:4b` (reported 3.4 GB on disk).
- **Later comparisons:** `qwen3.5:9b`, `qwen3:8b`, and, for simpler work, `qwen3.5:2b`. Test accuracy, tool behavior, latency, and memory pressure yourself.
- **Blocked by this profile:** models over 10 GiB on disk, including the reported 23 GB `qwen3.6:latest` and 19 GB `qwen2.5-coder:32b`.
- **Cloud blocked:** cloud-named models and remote-model metadata reported by Ollama, including `nemotron-3-super:cloud` and advertised remote aliases.

Disk size is not total runtime memory. Context, KV cache, macOS, and other applications all share the 16 GB. The 10 GiB cutoff is a guardrail, not a guarantee that every smaller model runs well. SHETTY unloads its previously used model when switching; other apps may still load models independently. Check `ollama ps`, close memory-heavy apps, and stop unused models yourself. No models are automatically deleted.

Tools and vision are displayed only from Ollama's reported capabilities. Vision metadata does **not** enable screenshot functionality. Older Ollama versions that omit capabilities get plain chat, without assumed model tool support.

## Optional start-at-login service

First verify the foreground app works. Stop it with Control-C. With the **same virtual environment** active on your Mac:

```sh
python -m shetty service install
python -m shetty service status
```

The agent is `~/Library/LaunchAgents/local.shetty.assistant.plist`. It records the absolute Python virtual-environment path; keep the checkout and `.venv` in place. Only one server can use a data directory at a time. The service restarts SHETTY after exits, with a 30-second throttle.

To stop and remove the service **without deleting your data**:

```sh
python -m shetty service uninstall
```

Ollama must be running separately for chat. The Mac must be logged in, powered, and awake. In-app reminder recording is transactional and once-only; an OS notification can be missed if the process crashes after recording the reminder. Check Tasks/Activity rather than relying on notification delivery for critical obligations.

## Local data and configuration

By default:

```text
~/.shetty/
  shetty.sqlite3       # conversations, memories, tasks, grants, approvals, events
  shetty.sqlite3-*     # SQLite's live WAL files, when present
  server.lock         # exclusive running-instance lock; do not manually remove
  logs/shetty.log      # rotating diagnostic log: 1 MiB + two backups
```

The dedicated directory is owner-only and the database is mode `0600`. **The app does not encrypt the database.** Use FileVault, a protected macOS account, and appropriate backups. Deletion is logical deletion, not guaranteed secure erasure from WAL files, snapshots, or backups. Journal entries may retain reminder titles; changing permissions does not erase historical copies.

Optional environment variables (no `.env` file is automatically loaded):

| Variable | Default | Purpose |
| --- | --- | --- |
| `SHETTY_DATA_DIR` | `~/.shetty` | Dedicated private storage folder; do not use your home/root directory itself. |
| `SHETTY_OLLAMA_URL` | `http://127.0.0.1:11434` | HTTP loopback only. Remote servers, credentials, redirects, and proxies are not supported. |
| `SHETTY_MODEL` | `qwen3.5:4b` | Initial model; a choice saved in Settings takes precedence. |

Normal operation binds to loopback only. This is a **single-user local application, not an authenticated network service**. Host/origin checks, mutation tokens, request size limits, and a restrictive CSP help protect the local web interface. They are not protection against malware or another process running as your OS user. See [security boundaries](docs/SECURITY.md).

### Sandbox preview

The Arena preview is **a separate Linux sandbox, not your Mac**. It cannot reach Ollama on your Mac. Its notes/tasks use sandbox storage. File access, speech, application opening, and macOS notifications are disabled. No mock model responses or fake user data are seeded.

For disposable preview data only:

```sh
SHETTY_DATA_DIR="$PWD/.shetty-dev" python -m shetty serve --host 0.0.0.0 --port 8765 --preview
```

This allows the Arena preview host and uses relative browser API URLs. **Do not use preview mode to expose personal data or your Mac to a network.** It has no login system. Its data directory is Git-ignored.

## Development and validation

```sh
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest -q
python -m compileall -q shetty
```

The frontend is plain local HTML/CSS/JavaScript with system fonts and SVGs. No Node.js build is required. The Python tests cover the Ollama protocol using an explicitly test-only mock transport, memory/task persistence, approval/replay/expiry checks, file scope and symlinks, request security, scheduler recovery, model concurrency, and launch-agent generation.

**Validation boundary:** automated tests run in Linux. Real model quality/speed, macOS speech, notifications, app opening, filesystem permissions, and launchd must be tested on the actual Mac. No claim of benchmarking or end-to-end Mac validation is made.

- [Architecture and extension points](docs/ARCHITECTURE.md)
- [Security boundaries](docs/SECURITY.md)
- [Roadmap and open-source tool vetting](docs/ROADMAP.md)

## Troubleshooting

- **Ollama not connected:** open Ollama on the same Mac as SHETTY, or run `ollama serve`. The sandbox cannot access your Mac's localhost.
- **Model missing:** use Settings to choose an already-installed, allowed local model. SHETTY never pulls one automatically.
- **Slow/empty replies:** inspect `ollama ps` and Activity Monitor's Memory Pressure. Try the 4B default, a shorter request, and fewer heavy applications. Output is intentionally bounded and may be cut off at the reply budget.
- **A model offers no tools:** inspect `ollama show <model>` / `python -m shetty doctor`. Do not infer capabilities from a name. Use manual controls if support is absent or unreliable.
- **File access denied:** verify the exact folder/path, UTF-8 format and size; check macOS Files and Folders permissions. No Full Disk Access is required or requested by this app.
- **No sound/notification:** these play on the server's Mac, not a remote browser. Check system volume, installed macOS voices, notification settings, and relevant OS permissions.
- **Port/instance already in use:** check `python -m shetty service status`. Stop either the foreground app or the login service, rather than running both against the same data directory.
