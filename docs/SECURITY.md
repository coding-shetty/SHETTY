# Security boundaries and limits

SHETTY v0.1 is a single-user local application. It is not a security sandbox, multi-user service, secret manager, or production-hardened autonomous agent.

## Deliberate safeguards

- Normal startup binds to loopback. Host checks reject unrelated hosts, including common DNS-rebinding targets. API requests reject cross-origin/cross-site browser traffic. Every mutation needs a random per-process token obtained through same-origin bootstrap.
- Incoming mutation bodies are capped at 128 KiB, including chunked requests. Typed fields have smaller limits. No permissive CORS, API keys, remote model URL entry, or browser-to-localhost backend calls.
- No remote scripts, fonts, telemetry, images, model HTML, or analytics. Browser camera, microphone, and geolocation access are disabled. Model/user text is escaped.
- Ollama uses HTTP loopback, does not honor proxy environment variables, and does not follow redirects. Metadata and names advertising remote/cloud inference are rejected before chat. No pull, push, model creation, or payment endpoints exist.
- The selected 16 GB profile blocks model files over 10 GiB. This is not a runtime memory-safety guarantee.
- Model tools can only create proposals from the server's currently offered finite registry. They cannot approve their own requests, change settings, grant folder access, invoke arbitrary HTTP endpoints, write files, install tools, or run shell commands.
- Proposals expire after 10 minutes. User approval is an atomic one-use claim. Arguments and folder access are revalidated. An indeterminate action is never retried automatically after a crash.
- Text reads traverse open directory descriptors with `O_NOFOLLOW`; symlinked path components and root substitution are rejected. Only regular, bounded UTF-8 files with approved extensions are allowed. Parent traversal, hidden paths and likely credential names are blocked. Files are never written.
- macOS calls use argument arrays, not `shell=True`. Application bundle IDs are allowlisted. Website addresses must be HTTP/HTTPS with no embedded credentials/control characters. Speech uses stdin, not command options. Notification content is an AppleScript argument after `--`, not interpolated script source.
- Data directory/database permissions are owner-only. Diagnostic logs rotate; API access logging is off. Reminder titles and tool results may exist in the local journal/database.

## What these safeguards do not solve

1. **Malicious local software/OS users:** another process running as you can read the database, fetch the token, modify the checkout, replace Ollama, or invoke macOS directly. There is no strong process sandbox or network-user authentication.
2. **Provider trust:** local-only checks rely on an honest installed Ollama server reporting its metadata accurately. SHETTY cannot control Ollama's own updates/network behavior or other applications. Opening an approved website naturally makes network requests and may use existing browser cookies.
3. **Prompt injection and model mistakes:** notes, files, task titles, and tool results are untrusted reference data. Prompt instructions alone are not a security boundary; validation and approval happen outside the model. Still review exact arguments. Never blindly run commands a model puts in chat.
4. **Sensitive material inside an approved folder:** a filename filter cannot classify every secret, disguised credential, hard link, or unsafe document. Approve small folders containing only intentionally shareable material. Do not grant broad/system directories or Full Disk Access as a workaround.
5. **At-rest encryption or forensic erasure:** SQLite is not app-encrypted. FileVault and OS-account protection are recommended. Logical deletes may remain in WAL files, backups, snapshots, or chat copies. Revoke permissions and delete historical copies separately. Standalone manual approval records have no per-record deletion UI yet.
6. **Guaranteed notification/action delivery:** macOS can reject operations and the process can crash between side effect and result recording. Check actual application state before retrying an indeterminate action. Do not rely on this version for safety-critical reminders.
7. **Fully offline installation or zero total cost:** dependency installation requires downloading free packages initially. Hardware, storage, electricity, maintenance, and websites/services you explicitly visit can still have costs. No paid API fallback is implemented.

## Preview mode is intentionally different

`--preview` permits a network-bound, embeddable sandbox UI, including Arena's `*.e2b.app` hosts. It disables file access and macOS execution, not access to sandbox notes/chat data. **Use disposable data only.** It is not a way to safely expose your personal Mac to the internet. Never port-forward the normal app or mistake the random mutation token for a user login system.

## If something looks wrong

Decline the request. Stop the app (or uninstall its login service), inspect Activity and `~/.shetty/logs`, and revoke relevant folder grants. Keep the original files outside approved directories while investigating. Report a minimal reproduction without attaching personal notes, tokens, database files, or credentials to a public issue.
