# Development

```bash
cd jarvis
npm install
npm run build
npm test
npm run tauri dev
```

Rust checks:

```bash
cd src-tauri
cargo fmt --check
cargo test
```

Before each commit from the repository root:

```bash
git status --short
git diff --name-only
```

Only `jarvis/` should be changed by JARVIS work. macOS-only commands are guarded so the frontend can be built in CI on Linux, while native acceptance tests must run on macOS.
