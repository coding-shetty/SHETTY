from __future__ import annotations

import argparse
import asyncio
import logging
import json
import sqlite3
from logging.handlers import RotatingFileHandler
import os
import sys

from .config import Config


def configure_logs(config: Config) -> None:
    directory = config.data_dir / "logs"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    handler = RotatingFileHandler(directory / "shetty.log", maxBytes=1024 * 1024, backupCount=2)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler, logging.StreamHandler()])
    logging.getLogger("httpx").setLevel(logging.WARNING)


async def doctor(config: Config) -> int:
    from .ollama import Ollama
    print("SHETTY diagnostics · configured target: Apple M4 / 16 GB")
    model = config.default_model
    database = config.data_dir / "shetty.sqlite3"
    if database.exists():
        # Read-only: diagnostics must not recover or modify a running server's DB.
        with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
            row = connection.execute("SELECT value FROM settings WHERE key='model'").fetchone()
            if row:
                model = json.loads(row[0])
    print(f"Ollama: {config.ollama_url}\nData: {config.data_dir}\nSelected model: {model}")
    client = Ollama(config)
    try:
        state = await client.status(model, refresh=True)
        print(state["message"])
        for model in state["models"]:
            print(f"  {model['name']}: {model['size'] / 1e9:.1f} GB on disk" + (f" — {model['blocked']}" if model["blocked"] else ""))
        print("Reported capabilities: " + (", ".join(state["capabilities"]) or "not verified"))
        print("File size is not runtime RAM. No model was downloaded or loaded by this check.")
        return 0 if state["ready"] else 1
    finally:
        await client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="SHETTY — a local-first personal assistant")
    sub = parser.add_subparsers(dest="command")
    serve = sub.add_parser("serve", help="Start the local web interface (default)")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--preview", action="store_true", help="Sandbox demonstration only: disables file and macOS access")
    sub.add_parser("doctor", help="Check local Ollama and model metadata without loading a model")
    service = sub.add_parser("service", help="Manage an optional macOS login service")
    service.add_argument("action", choices=["install", "uninstall", "status"])
    args = parser.parse_args()
    # Restrict newly created SQLite WAL, backups, and logs to this OS account.
    os.umask(0o077)
    try:
        config = Config.from_env(preview=getattr(args, "preview", False))
        if args.command == "doctor":
            raise SystemExit(asyncio.run(doctor(config)))
        if args.command == "service":
            from .service import manage_service
            print(manage_service(args.action, config))
            return
        host = getattr(args, "host", "127.0.0.1")
        if host not in {"127.0.0.1", "localhost", "::1"} and not config.preview:
            parser.error("Non-loopback binding requires --preview (no file/macOS access). Do not expose your personal assistant to a network.")
        port = getattr(args, "port", 8765)
        if not 1 <= port <= 65535:
            parser.error("Port must be between 1 and 65535.")
        configure_logs(config)
        from .app import create_app
        import uvicorn
        print(f"\nSHETTY · http://{host}:{port}\nLocal model: {config.default_model} · context: 4096 · no paid APIs\n")
        if config.preview:
            print("SANDBOX PREVIEW: disposable data only. This is not your Mac. File and macOS access are disabled.\n")
        uvicorn.run(create_app(config), host=host, port=port, access_log=False, log_config=None)
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(f"SHETTY: {exc}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
