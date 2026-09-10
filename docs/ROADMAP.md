# Roadmap: grow capability without pretending it is intelligence

The starting point is the handoff's **14-inch November 2024 MacBook Pro, base M4, 16 GB unified memory**. macOS Tahoe 26.5.2 and approximately 91.5 GB free of 494.38 GB were user-reported screenshot details, not hardware/OS measurements performed by this application. The existing model recommendations remain provisional.

## Phase 1 — this pull request

- Local chat, explicit saved memory, tasks/reminders, bounded approved reads.
- Ask-first app/website opening; macOS speech output; optional login service.
- Capability discovery from installed Ollama metadata and honest offline UI.
- Automated protocol/security/state tests; actual Mac/model validation still required.

### Mac acceptance checklist before relying on it

- [ ] Run `python -m shetty doctor`; verify `qwen3.5:4b` is installed and local.
- [ ] Send several ordinary messages and test whether it follows your preferences accurately.
- [ ] Measure cold/warm reply latency and Activity Monitor Memory Pressure with your normal applications open.
- [ ] If tools are reported, test a correct request, a malformed one, an ambiguous one, and a deliberate refusal. Check the exact proposals rather than trusting chat claims.
- [ ] Approve opening Calculator. Decline a separate request and verify nothing opens.
- [ ] Read a harmless file from a dedicated folder; revoke access and verify a queued read fails.
- [ ] Test the speaker/stop controls and both in-app and optional OS reminders.
- [ ] Install/status/uninstall the login agent. Test sleep/wake and a missed reminder.
- [ ] Back up the private data directory while the server is stopped; do not commit it.

## Phase 2 — listen, without always listening

Candidate: [whisper.cpp](https://github.com/ggml-org/whisper.cpp).

Begin with deliberate push-to-talk, an independently verified small speech model, and user-approved model download/storage. Measure transcription quality for your accent/languages, CPU load, and latency. Do not add continuous capture, a wake word, or audio retention by default. macOS built-in speech remains the output path. No hosted transcription fallback unless explicitly requested later.

## Phase 3 — reliable direct automation

1. Prefer [macOS Shortcuts](https://support.apple.com/guide/shortcuts-mac/welcome/mac) or bounded AppleScript handlers with typed inputs and explicit confirmation.
2. Add one useful integration at a time, such as a vetted Shortcut for adding a Calendar event. Show destination, content, and permissions before approval. Native tools should return evidence, not an LLM's guess.
3. Candidate browser driver: [Playwright](https://github.com/microsoft/playwright). Use a dedicated browser profile/context, domain/action allowlists, read-only navigation first, and separate confirmations for form submissions, sending messages, purchases, uploads, and account changes. Never silently reuse or scrape your personal browser profile.

Opening a URL in this release is **not** Playwright automation or web research. Browser binaries and dependencies are not part of the runtime install.

## Phase 4 — selective screen understanding

Verify installed-model vision support through metadata **and an actual harmless image test**. Start with a screenshot selected by the user; display what will be sent to the local model and avoid sensitive areas. Define image retention, maximum resolution, latency/memory budget, and exact action approvals before enabling capture. Prefer DOM/accessibility/direct APIs to guessed pixel clicks. Do not continuously watch the display.

## Phase 5 — event-driven background workflows

Move beyond one-off reminders only after permissions, idempotency, durable job state, retries, expiration, visible status, and pause/kill controls are designed and tested. Start with local notifications and read-only summaries. Do not schedule arbitrary shell commands or let the model invent recurring actions. The Mac must still be awake; no promise of unattended human-level reliability.

## Vetting an open-source capability

Before installing or running a GitHub project:

- Does it solve a specific missing capability? A plugin does not make a weak model smarter.
- Inspect the repository, maintainers, license, maintenance history, issues, security notices and dependencies. Popularity alone is not vetting.
- Read install scripts/build hooks and locate every network call, telemetry toggle, model download, credential request, background service and paid integration.
- Pin a reviewed release/commit and dependency versions. Never `curl | sh` or automatically execute model-suggested code.
- Test in an isolated environment with disposable files/accounts. Establish the disk/RAM cost on M4/16 GB.
- Specify the narrow tool contract, allowed destinations, data access, side effects, approval UI, timeout, output limits, audit events and rollback strategy.
- Add injection, traversal, malformed-input, double-approval, failure/restart, and permission-revocation tests before exposing it to the assistant.
- Obtain explicit user approval for installation, downloads, new permissions, or costs. Keep uninstall and data-deletion instructions.

No external capability repositories have been installed or automatically trusted by this release. Python web dependencies are the runtime foundation; test tooling used to inspect the interface is not an assistant plugin.
