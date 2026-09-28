# Security

- Ollama is local by default; screen and microphone data are not uploaded by this app.
- Frontend code cannot run shell commands directly.
- Commands are classified LOW, MEDIUM, HIGH, or CRITICAL before execution.
- Non-LOW commands require an explicit `confirmed` flag; destructive patterns are never silently executed.
- Native macOS privacy controls are respected; the app does not bypass TCC.
- Memory is opt-in and stored locally. Do not store passwords, cookies, API keys, or authentication tokens.
- Logs and activity labels must remain high-level and redact sensitive content.
- Future Keychain integrations should use macOS Keychain APIs rather than local plaintext files.
