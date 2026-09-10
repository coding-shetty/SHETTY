from __future__ import annotations

import asyncio
import json
import os
import platform
import stat
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, ValidationError, field_validator

from .config import Config
from .db import Store
from .schemas import MemoryInput, StrictModel, TaskInput

# Fixed identifiers, never an arbitrary executable, shell command or AppleScript.
APPS = {
    "Safari": "com.apple.Safari",
    "Notes": "com.apple.Notes",
    "Calendar": "com.apple.iCal",
    "Reminders": "com.apple.reminders",
    "Calculator": "com.apple.calculator",
    "Finder": "com.apple.finder",
    "TextEdit": "com.apple.TextEdit",
    "Music": "com.apple.Music",
    "System Settings": "com.apple.systempreferences",
}
TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".csv", ".json", ".yaml", ".yml", ".toml", ".py", ".js", ".ts", ".html", ".css", ".rst"}
MAX_FILE_BYTES = 64 * 1024


class ToolError(Exception):
    pass


class AppArgs(StrictModel):
    app: Literal["Safari", "Notes", "Calendar", "Reminders", "Calculator", "Finder", "TextEdit", "Music", "System Settings"]


class URLArgs(StrictModel):
    url: str = Field(min_length=1, max_length=2000)

    @field_validator("url")
    @classmethod
    def valid_url(cls, value: str) -> str:
        try:
            parts = urlsplit(value)
            port = parts.port
        except ValueError as exc:
            raise ValueError("Use a valid HTTP or HTTPS website address.") from exc
        if (parts.scheme not in {"http", "https"} or not parts.hostname or parts.username is not None
                or parts.password is not None or "\\" in value or any(ord(c) < 33 or ord(c) == 127 for c in value)
                or (port is not None and not 1 <= port <= 65535)):
            raise ValueError("Only HTTP/HTTPS URLs without credentials or whitespace are allowed.")
        return value


class ReadArgs(StrictModel):
    root_id: str = Field(min_length=1, max_length=64)
    path: str = Field(min_length=1, max_length=512)


TOOL_MODELS = {"save_memory": MemoryInput, "create_task": TaskInput, "read_file": ReadArgs, "open_app": AppArgs, "open_website": URLArgs}
TOOL_DESCRIPTIONS = {
    "save_memory": "Propose saving a note or preference. It is NOT saved until the user approves.",
    "create_task": "Propose a task, optionally with a future one-off reminder (ISO 8601 with timezone). Requires approval.",
    "read_file": "Propose reading one UTF-8 text file in an approved folder. Use a relative path and an existing root_id. Requires approval.",
    "open_app": "Propose opening an allowlisted macOS application. Requires approval; cannot control its contents.",
    "open_website": "Propose opening a HTTP/HTTPS website in the default browser. Requires approval; cannot browse or interact with it.",
}
TOOL_TITLES = {"save_memory": "Save a memory", "create_task": "Create a task", "read_file": "Read a file", "open_app": "Open an application", "open_website": "Open a website"}


def safe_root(path: str, data_dir: Path) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        raise ToolError("Enter an absolute folder path, such as ~/Documents/SHETTY Notes.")
    try:
        root = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ToolError("That folder does not exist or cannot be accessed.") from exc
    home = Path.home().resolve()
    # Choose a narrow, user-owned folder; never grant all of the disk/home/system.
    forbidden = {Path("/"), home, home.parent, Path("/Users"), Path("/System"), Path("/Library"), Path("/etc"), Path("/private"), Path("/usr"), Path("/var"), Path("/bin"), Path("/sbin")}
    resolved_data = data_dir.resolve()
    if root in forbidden or any(part.startswith(".") for part in root.parts):
        raise ToolError("Choose a specific, non-hidden folder rather than a home, system, or hidden directory.")
    if root == resolved_data or root.is_relative_to(resolved_data):
        raise ToolError("SHETTY's private database directory cannot be an approved folder.")
    if not root.is_dir() or not os.access(root, os.R_OK | os.X_OK):
        raise ToolError("Choose a readable folder.")
    return root


def checked_relative_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or not path.parts or any(part in {"..", "."} or part.startswith(".") for part in path.parts):
        raise ToolError("Use a relative path inside the approved folder. Hidden files and parent traversal are blocked.")
    if "\x00" in value or "\\" in value or any(ord(c) < 32 for c in value):
        raise ToolError("Invalid file path.")
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        raise ToolError("Only supported text files are readable. No keys, binaries, PDFs, or images in this version.")
    lowered = path.name.casefold()
    if any(word in lowered for word in ("credential", "secret", "password", "token", "id_rsa", "id_ed25519")):
        raise ToolError("Likely credential files are blocked. Do not store secrets in approved folders.")
    return path


def read_scoped_file(root: Path, relative: str) -> dict:
    """Traverse via directory descriptors + O_NOFOLLOW, closing symlink/TOCTOU escapes.

    macOS and Linux both support openat through dir_fd. No fallback that weakens
    checks on platforms without it. Hard links and misleading filenames cannot
    be classified safely; approved folders must contain only intended data.
    """
    path = checked_relative_path(relative)
    descriptors: list[int] = []
    try:
        # Walk the absolute root too. If it was replaced with a symlink since the
        # grant, reject it instead of following it into another directory.
        fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
        descriptors.append(fd)
        for part in root.parts[1:] + path.parts[:-1]:
            fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            descriptors.append(fd)
        file_fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        descriptors.append(file_fd)
        info = os.fstat(file_fd)
        if not stat.S_ISREG(info.st_mode):
            raise ToolError("Only regular files can be read.")
        if info.st_size > MAX_FILE_BYTES:
            raise ToolError("This file exceeds the 64 KiB read limit. Make a smaller text excerpt.")
        # os.read may return short reads; keep going, but never over the bound.
        chunks = bytearray()
        while len(chunks) <= MAX_FILE_BYTES:
            data = os.read(file_fd, min(8192, MAX_FILE_BYTES + 1 - len(chunks)))
            if not data:
                break
            chunks.extend(data)
        if len(chunks) > MAX_FILE_BYTES:
            raise ToolError("This file exceeds the 64 KiB read limit.")
        if b"\x00" in chunks:
            raise ToolError("This looks like a binary file, not plain text.")
        try:
            text = chunks.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ToolError("The file is not UTF-8 text.") from exc
        return {"path": str(path), "text": text, "bytes": len(chunks)}
    except (OSError, RuntimeError) as exc:
        raise ToolError("File cannot be read. Check its name, macOS permissions, and that no path component is a symlink.") from exc
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


async def run_native(*args: str) -> None:
    try:
        process = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
        try:
            _, error = await asyncio.wait_for(process.communicate(), timeout=15)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            if process.returncode is None:
                process.kill()
                await process.wait()
            raise
        if process.returncode:
            raise ToolError("macOS rejected this action. Check the application's availability and Automation permissions.")
    except (OSError, asyncio.TimeoutError) as exc:
        raise ToolError("The macOS action could not be completed.") from exc


class Tools:
    def __init__(self, store: Store, config: Config):
        self.store = store
        self.config = config

    @property
    def macos_available(self) -> bool:
        return platform.system() == "Darwin" and not self.config.preview

    def available_names(self) -> list[str]:
        names = ["save_memory", "create_task"]
        if not self.config.preview and self.store.roots():
            names.append("read_file")
        if self.macos_available:
            names.extend(["open_app", "open_website"])
        return names

    def schemas(self) -> list[dict]:
        return [{"type": "function", "function": {"name": name, "description": TOOL_DESCRIPTIONS[name], "parameters": TOOL_MODELS[name].model_json_schema()}} for name in self.available_names()]

    def validate(self, name: str, arguments: dict) -> dict:
        if name not in self.available_names():
            raise ToolError("This tool is not available. macOS actions need your Mac; file reads need an approved folder and are disabled in preview.")
        try:
            result = TOOL_MODELS[name].model_validate(arguments).model_dump(mode="json")
        except ValidationError as exc:
            raise ToolError("Invalid tool arguments: " + "; ".join(error["msg"] for error in exc.errors())[:300]) from exc
        if name == "read_file":
            root = self.store.one("SELECT * FROM roots WHERE id=?", (result["root_id"],))
            if not root:
                raise ToolError("The approved folder no longer exists.")
            checked_relative_path(result["path"])
        return result

    def propose(self, name: str, arguments: dict, conversation_id=None, message_id=None) -> dict:
        validated = self.validate(name, arguments)
        if conversation_id and not self.store.conversation(conversation_id):
            raise ToolError("Conversation not found.")
        proposal = self.store.add_proposal(name, validated, conversation_id, message_id)
        self.store.event("approval", "Permission requested", TOOL_TITLES[name])
        return proposal

    async def decide(self, proposal_id: str, approve: bool) -> dict:
        if not self.store.proposal(proposal_id):
            raise KeyError("Request not found.")
        try:
            proposal = self.store.claim_proposal(proposal_id, approve)
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
        name = proposal["tool"]
        if not approve:
            self.store.event("denied", "Request declined", TOOL_TITLES.get(name, name))
            return proposal
        try:
            # Revalidate at execution, especially after folder revocation or time passing.
            args = self.validate(name, proposal["arguments"])
            if name == "save_memory":
                result = self.store.save_memory(**args)
            elif name == "create_task":
                result = self.store.add_task(**args)
            elif name == "read_file":
                root = self.store.one("SELECT * FROM roots WHERE id=?", (args["root_id"],))
                result = read_scoped_file(Path(root["path"]), args["path"])
            elif name == "open_app":
                await run_native("/usr/bin/open", "-b", APPS[args["app"]])
                result = {"message": f"Asked macOS to open {args['app']}."}
            elif name == "open_website":
                await run_native("/usr/bin/open", args["url"])
                result = {"message": "Asked the default browser to open the approved website."}
            else:
                raise ToolError("Unknown tool.")
            completed = self.store.finish_proposal(proposal_id, "executed", result)
            self.store.event("executed", TOOL_TITLES[name], "Approved by you and completed.")
            return completed
        except (ToolError, OSError) as exc:
            self.store.event("error", "Action failed", TOOL_TITLES.get(name, name))
            return self.store.finish_proposal(proposal_id, "failed", {"error": str(exc)})

    async def notify(self, title: str) -> None:
        if self.macos_available and self.store.setting("desktop_notifications", False):
            script = 'on run argv\n display notification (item 1 of argv) with title "SHETTY"\nend run'
            # Data is an argv value, not interpolated AppleScript source.
            await run_native("/usr/bin/osascript", "-e", script, "--", title[:160])


class Speech:
    """macOS built-in output only. No audio capture, browser/cloud TTS, or downloads."""

    def __init__(self, tools: Tools):
        self.tools = tools
        self.task: asyncio.Task | None = None

    async def stop(self) -> None:
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        self.task = None

    async def say(self, text: str) -> None:
        if not self.tools.macos_available:
            raise ToolError("Speech plays through macOS on your Mac. It is unavailable in this sandbox preview.")
        await self.stop()
        # Launch before returning so missing permissions/binaries become a visible error.
        try:
            process = await asyncio.create_subprocess_exec("/usr/bin/say", stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        except OSError as exc:
            raise ToolError("macOS speech could not start.") from exc

        async def speak():
            try:
                await asyncio.wait_for(process.communicate(input=text.encode("utf-8")), timeout=600)
                if process.returncode:
                    self.tools.store.event("error", "Speech could not finish", "Check macOS voice availability.")
            except asyncio.CancelledError:
                if process.returncode is None:
                    process.kill()
                    await process.wait()
                raise
            except asyncio.TimeoutError:
                if process.returncode is None:
                    process.kill()
                    await process.wait()
                self.tools.store.event("error", "Speech timed out", "The speech process was stopped.")

        self.task = asyncio.create_task(speak())
