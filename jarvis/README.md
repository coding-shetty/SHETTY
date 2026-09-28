# JARVIS

JARVIS is a local-first macOS desktop computer agent. The application is isolated under `jarvis/` and does not import or modify the parent repository's Python application.

## Current implementation

- Tauri 2 desktop shell with React/TypeScript UI
- Premium floating assistant UI with state indicators, activity feed, settings, memory view, and diagnostics
- Ollama provider at `http://localhost:11434` with graceful offline errors
- Local persistent memory stored under the platform data directory
- Native macOS application launching through the `open -a` command
- Safe terminal command classifier with confirmation gating for medium/high/critical commands
- Node version workflow and structured activity results
- Provider bridge ready for screen, voice, browser, and additional tools

## Requirements

- macOS 13+ on Apple Silicon recommended
- Rust, Node.js 18+, npm
- Xcode Command Line Tools and Tauri prerequisites
- Ollama with a local model such as `llama3.2`

## Run

```bash
cd jarvis
npm install
npm run tauri dev
```

For UI-only development:

```bash
npm run dev
```

## Build and package

```bash
cd jarvis
npm run build
npm run tauri build
```

The packaged `.app` is produced under `jarvis/src-tauri/target/release/bundle/macos/` on macOS.

## Ollama

```bash
ollama serve
ollama pull llama3.2
```

Configure Ollama URL, text model, vision model, temperature, and context size in the settings surface as provider configuration is expanded.

## macOS permissions

The native computer-control layers must use macOS privacy permissions. Enable Microphone, Accessibility, Screen Recording, and Automation for JARVIS under **System Settings → Privacy & Security**. JARVIS never attempts to bypass those controls.

## Development status

This repository commit establishes a working desktop/chat/diagnostics foundation and real native/terminal/Ollama paths. Screen capture/OCR, local STT/VAD/wake-word, TTS, browser control, and full mouse/keyboard Accessibility bindings are deliberately documented as follow-on native modules rather than falsely represented as complete in the UI.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), [`docs/SECURITY.md`](docs/SECURITY.md), [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md), and [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md).
