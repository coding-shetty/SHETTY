# Troubleshooting

## Ollama unavailable

Run `ollama serve`, confirm `curl http://localhost:11434/api/tags`, and pull the configured model. JARVIS reports the actual connection failure instead of fabricating a response.

## Native app controls unavailable

Application launching, Accessibility, screen capture, and Automation require the macOS desktop build. The Linux development environment intentionally returns a clear limitation message.

## Permission warnings

Open **System Settings → Privacy & Security** and grant only the permissions needed for the current feature. Restart JARVIS after changing TCC permissions.

## Build issues

Install Xcode Command Line Tools and the Tauri prerequisites documented at https://tauri.app/start/prerequisites/. Delete `node_modules` and run `npm install` again if the frontend dependency tree is stale.
