# Architecture

```text
React UI
  ↓ Tauri invoke
Rust command router
  ├─ OllamaProvider (localhost HTTP)
  ├─ safe terminal tools
  ├─ local memory store
  ├─ native macOS application control
  └─ diagnostics / permission status
```

The UI never executes operating-system commands. It requests named Rust commands; the Rust layer validates, classifies, executes, and returns structured results. The agent prompt explicitly forbids claiming success without a confirmed tool result.

## Extension points

- `src/api.ts`: typed frontend command bridge
- `src-tauri/src/lib.rs`: command registry, provider call, safety policy, persistence
- Add `screen_capture`, `accessibility`, and `browser` modules as separate Rust commands with dedicated permission checks.

## State model

The UI exposes IDLE, LISTENING, THINKING, ACTING, SPEAKING, CONFIRMATION, and ERROR. Activity records are high-level user-visible events only; private chain-of-thought is never surfaced.
