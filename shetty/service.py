"""Explicit, per-user launchd installation. Never requires sudo or keeps the Mac awake."""
from __future__ import annotations

import os
import platform
import plistlib
import subprocess
import sys
from pathlib import Path

from .config import Config

LABEL = "local.shetty.assistant"


def agent_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def agent_definition(config: Config, executable: str | None = None) -> dict:
    # Do not resolve the venv executable's symlink: that would lose the venv.
    return {
        "Label": LABEL,
        "ProgramArguments": [executable or os.path.abspath(sys.executable), "-m", "shetty", "serve"],
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 30,
        "EnvironmentVariables": {
            "SHETTY_DATA_DIR": str(config.data_dir),
            "SHETTY_OLLAMA_URL": config.ollama_url,
            "SHETTY_MODEL": config.default_model,
            "PYTHONUNBUFFERED": "1",
        },
        "ProcessType": "Background",
        # The application writes rotating logs, not an unbounded launchd log.
        "StandardOutPath": "/dev/null",
        "StandardErrorPath": "/dev/null",
    }


def manage_service(action: str, config: Config) -> str:
    if platform.system() != "Darwin":
        raise ValueError("The login service is macOS-only. Run this command on your Mac.")
    path = agent_path()
    domain = f"gui/{os.getuid()}"
    if action == "install":
        if path.exists() or path.is_symlink():
            raise ValueError(f"A launch agent already exists at {path}. Run shetty service uninstall before reinstalling.")
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("xb") as handle:
                plistlib.dump(agent_definition(config), handle)
            path.chmod(0o600)
            result = subprocess.run(["/bin/launchctl", "bootstrap", domain, str(path)], capture_output=True, text=True, timeout=20)
            if result.returncode:
                path.unlink(missing_ok=True)
                raise ValueError("launchd could not start SHETTY. Ensure you are logged into a macOS desktop session and no old agent is loaded.")
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ValueError("Could not install the per-user launch agent. Check folder permissions and launchctl status.") from exc
        return "Installed. SHETTY starts at login and runs while your Mac is awake. Open http://127.0.0.1:8765. Logs: " + str(config.data_dir / "logs")
    if action == "uninstall":
        if not path.exists():
            return "No SHETTY login service is installed. Your data has not been changed."
        if path.is_symlink():
            raise ValueError("Refusing to remove a symlinked launch agent.")
        with path.open("rb") as handle:
            if plistlib.load(handle).get("Label") != LABEL:
                raise ValueError("This file does not describe the SHETTY service; it was not changed.")
        stopped = subprocess.run(["/bin/launchctl", "bootout", domain + "/" + LABEL], capture_output=True, timeout=20)
        if stopped.returncode:
            status = subprocess.run(["/bin/launchctl", "print", domain + "/" + LABEL], capture_output=True, timeout=20)
            if status.returncode == 0:
                raise ValueError("The service is still loaded. Its launch agent was kept; check launchctl permissions before retrying.")
        path.unlink()
        return "Login service removed. Your conversations, notes, and tasks are kept."
    if action == "status":
        result = subprocess.run(["/bin/launchctl", "print", domain + "/" + LABEL], capture_output=True, text=True, timeout=20)
        return result.stdout if result.returncode == 0 else "SHETTY's login service is not loaded."
    raise ValueError("Unknown service action.")
