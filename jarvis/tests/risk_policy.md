# Risk policy test cases

| Command | Expected |
|---|---|
| `pwd` | LOW |
| `node --version` | LOW |
| `git status` | MEDIUM |
| `rm ./cache` | HIGH |
| `rm -rf ./cache` | CRITICAL |
| `sudo shutdown -h now` | CRITICAL |

The classifier is implemented in `src-tauri/src/lib.rs` and is also callable from the Tauri command bridge for a confirmation UI.
