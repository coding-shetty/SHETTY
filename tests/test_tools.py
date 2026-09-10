import asyncio
import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from shetty.config import Config
from shetty.tools import MAX_FILE_BYTES, ToolError, Tools, URLArgs, read_scoped_file, safe_root


@pytest.fixture
def folder(tmp_path):
    root = tmp_path / "approved"
    root.mkdir()
    (root / "notes.md").write_text("Untrusted file content.", encoding="utf-8")
    return root


@pytest.mark.parametrize("path", ["../outside.txt", "/etc/passwd", ".env", ".ssh/config.txt", "secret.json", "passwords.csv", "app.pem", "a/../../notes.md", "bad\x00.md", "bad\nname.md"])
def test_disallowed_paths_cannot_be_read(folder, path):
    with pytest.raises(ToolError):
        read_scoped_file(folder, path)


def test_only_regular_bounded_utf8_files(folder):
    assert read_scoped_file(folder, "notes.md")["text"] == "Untrusted file content."
    (folder / "big.txt").write_bytes(b"a" * (MAX_FILE_BYTES + 1))
    (folder / "binary.txt").write_bytes(b"\x00\x01")
    (folder / "invalid.txt").write_bytes(b"\xff\xfe")
    (folder / "directory.txt").mkdir()
    os.mkfifo(folder / "fifo.txt")
    for name in ["big.txt", "binary.txt", "invalid.txt", "directory.txt", "fifo.txt"]:
        with pytest.raises(ToolError):
            read_scoped_file(folder, name)
    (folder / "limit.txt").write_bytes(b"a" * MAX_FILE_BYTES)
    assert read_scoped_file(folder, "limit.txt")["bytes"] == MAX_FILE_BYTES


def test_symlink_file_directory_and_swapped_root_cannot_escape(folder, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "private.txt").write_text("Never expose this")
    (folder / "link.txt").symlink_to(outside / "private.txt")
    (folder / "linked-folder").symlink_to(outside, target_is_directory=True)
    for path in ["link.txt", "linked-folder/private.txt"]:
        with pytest.raises(ToolError):
            read_scoped_file(folder, path)
    folder.rename(tmp_path / "original")
    folder.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ToolError):
        read_scoped_file(folder, "private.txt")


def test_folder_grants_are_narrow(folder, config):
    assert safe_root(str(folder), config.data_dir) == folder.resolve()
    for path in ["/", str(Path.home()), str(Path.home() / ".ssh"), "relative/folder", str(config.data_dir)]:
        with pytest.raises(ToolError):
            safe_root(path, config.data_dir)


def test_file_grant_revoked_between_proposal_and_approval(store, config, folder):
    root = store.add_root("Project", str(folder))
    tools = Tools(store, config)
    proposal = tools.propose("read_file", {"root_id": root["id"], "path": "notes.md"})
    assert proposal["result"] is None
    store.delete_record("roots", root["id"])
    result = asyncio.run(tools.decide(proposal["id"], True))
    assert result["status"] == "failed"
    assert "text" not in result["result"]


def test_saving_a_memory_requires_an_explicit_decision(store, config):
    tools = Tools(store, config)
    proposal = tools.propose("save_memory", {"title": "Preference", "content": "Concise replies", "kind": "preference"})
    assert not store.memories()
    result = asyncio.run(tools.decide(proposal["id"], True))
    assert result["status"] == "executed"
    assert len(store.memories()) == 1
    with pytest.raises(ToolError):
        asyncio.run(tools.decide(proposal["id"], True))
    assert len(store.memories()) == 1


def test_unknown_tools_extra_arguments_and_preview_access_fail(store, config, folder):
    tools = Tools(store, config)
    with pytest.raises(ToolError):
        tools.propose("run_shell", {"command": "touch /tmp/should-not-exist"})
    with pytest.raises(ToolError):
        tools.propose("save_memory", {"title": "x", "content": "y", "shell": "rm -rf /"})
    root = store.add_root("Folder", str(folder))
    preview = Tools(store, Config(data_dir=config.data_dir, preview=True))
    assert not preview.macos_available
    assert preview.available_names() == ["save_memory", "create_task"]
    with pytest.raises(ToolError):
        preview.propose("read_file", {"root_id": root["id"], "path": "notes.md"})


@pytest.mark.parametrize("url", ["file:///etc/passwd", "javascript:alert(1)", "https://user:pass@example.com", "https://example.com\n--args", "https://example.com\\evil", "https://example.com/a b", "https://", "http://localhost:99999"])
def test_urls_are_not_commands_or_credentials(url):
    with pytest.raises(ValidationError):
        URLArgs(url=url)


def test_macos_execution_is_argv_not_shell(store, config, monkeypatch):
    monkeypatch.setattr("shetty.tools.platform.system", lambda: "Darwin")
    calls = []
    async def native(*args):
        calls.append(args)
    monkeypatch.setattr("shetty.tools.run_native", native)
    tools = Tools(store, config)
    proposal = tools.propose("open_app", {"app": "Notes"})
    assert calls == []
    asyncio.run(tools.decide(proposal["id"], True))
    assert calls == [("/usr/bin/open", "-b", "com.apple.Notes")]
    with pytest.raises(ToolError):
        tools.propose("open_app", {"app": "Terminal"})
    store.set_setting("desktop_notifications", True)
    text = 'hello" & do shell script "evil"'
    asyncio.run(tools.notify(text))
    assert calls[-1][-1] == text
    assert text not in calls[-1][-2]


def test_expired_task_time_is_revalidated_on_approval(store, config):
    tools = Tools(store, config)
    proposal = store.add_proposal("create_task", {"title": "Old request", "due_at": "2000-01-01T00:00:00Z"})
    assert asyncio.run(tools.decide(proposal["id"], True))["status"] == "failed"
    assert not store.tasks()
