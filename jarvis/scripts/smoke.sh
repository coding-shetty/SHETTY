#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f package.json ]
[ -f src-tauri/Cargo.toml ]
[ -f README.md ]
npm run build
echo "JARVIS frontend build passed"
