import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from shetty.db import Store
from shetty.scheduler import tick
from shetty.schemas import TaskInput
from shetty.tools import Tools


def test_private_database_and_persistence(store, config):
    note = store.save_memory("A useful note", "Keep it simple.", "note")
    assert (os.stat(store.path).st_mode & 0o777) == 0o600
    assert (os.stat(config.data_dir).st_mode & 0o777) == 0o700
    reopened = Store(config.data_dir)
    assert reopened.memories()[0]["id"] == note["id"]
    assert reopened.memories()[0]["content"] == "Keep it simple."


def test_memories_are_editable_searchable_and_deletable(store):
    note = store.save_memory("100% local", "No cloud.", "note")
    store.save_memory("Other note", "Something else.", "note")
    assert len(store.memories("%")) == 1
    assert not store.memories("' OR 1=1 --")
    edited = store.save_memory("Preferred answer style", "Be concise.", "preference", note["id"])
    assert edited["kind"] == "preference"
    assert "Be concise." in store.memory_context("unrelated question")
    assert "Something else." not in store.memory_context("unrelated question")
    assert store.delete_record("memories", note["id"])
    with pytest.raises(KeyError):
        store.save_memory("No", "Gone", "note", note["id"])


def test_approval_claim_is_atomic_and_one_use(store):
    proposal = store.add_proposal("save_memory", {"title": "x", "content": "y", "kind": "note"})
    def claim(_):
        try:
            store.claim_proposal(proposal["id"], True)
            return True
        except ValueError:
            return False
    with ThreadPoolExecutor(max_workers=8) as executor:
        assert sum(executor.map(claim, range(20))) == 1


def test_expired_or_denied_cannot_be_approved(store):
    expired = store.add_proposal("save_memory", {})
    with store.connect() as conn:
        conn.execute("UPDATE proposals SET expires_at='2000-01-01T00:00:00+00:00' WHERE id=?", (expired["id"],))
    assert store.proposal(expired["id"])["status"] == "expired"
    with pytest.raises(ValueError):
        store.claim_proposal(expired["id"], True)
    denied = store.add_proposal("save_memory", {})
    assert store.claim_proposal(denied["id"], False)["status"] == "denied"
    with pytest.raises(ValueError):
        store.claim_proposal(denied["id"], True)


def test_restart_does_not_retry_indeterminate_actions(store, config):
    proposal = store.add_proposal("open_app", {"app": "Notes"})
    store.claim_proposal(proposal["id"], True)
    reopened = Store(config.data_dir)
    reopened.recover_interrupted_actions()
    result = reopened.proposal(proposal["id"])
    assert result["status"] == "failed"
    assert "may have completed" in result["result"]["error"]


def test_due_reminders_are_once_only_and_survive_restart(store, config):
    old = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    task = store.add_task("Catch up after wake", old)
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    store.add_task("Later", future)
    done = store.add_task("Already done", old)
    store.complete_task(done["id"], True)
    tools = Tools(store, config)
    assert asyncio.run(tick(store, tools)) == 1
    assert asyncio.run(tick(store, tools)) == 0
    assert len(store.all("SELECT * FROM events WHERE category='reminder'")) == 1
    assert store.one("SELECT * FROM tasks WHERE id=?", (task["id"],))["notified_at"]
    reopened = Store(config.data_dir)
    assert asyncio.run(tick(reopened, Tools(reopened, config))) == 0
    store.complete_task(task["id"], True)
    store.complete_task(task["id"], False)
    assert asyncio.run(tick(store, tools)) == 0


def test_concurrent_scheduler_claims_create_one_event(store):
    store.add_task("Exactly once in app", "2000-01-01T00:00:00+00:00")
    with ThreadPoolExecutor(max_workers=4) as executor:
        assert sum(executor.map(lambda _: len(store.claim_due_tasks()), range(8))) == 1
    assert len(store.all("SELECT * FROM events WHERE category='reminder'")) == 1


@pytest.mark.parametrize("due_at", ["2027-01-01T10:00:00", "2000-01-01T10:00:00Z"])
def test_task_times_must_be_aware_and_future(due_at):
    with pytest.raises(ValidationError):
        TaskInput(title="Test", due_at=due_at)


def test_timezone_normalizes_to_utc():
    model = TaskInput(title="Test", due_at="2099-01-01T10:00:00+05:30")
    assert model.due_at.isoformat() == "2099-01-01T04:30:00+00:00"


def test_conversation_deletion_cascades_records_but_keeps_memory(store):
    conversation = store.create_conversation()
    message = store.add_message(conversation["id"], "assistant", "Request")
    proposal = store.add_proposal("save_memory", {}, conversation["id"], message["id"])
    store.save_memory("Saved separately", "Kept", "note")
    assert store.delete_conversation(conversation["id"])
    assert not store.messages(conversation["id"])
    assert store.proposal(proposal["id"]) is None
    assert len(store.memories()) == 1
