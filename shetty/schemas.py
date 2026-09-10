from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ChatInput(StrictModel):
    message: str = Field(min_length=1, max_length=4000)


class MemoryInput(StrictModel):
    title: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1, max_length=8000)
    kind: Literal["note", "preference"] = "note"


class TaskInput(StrictModel):
    title: str = Field(min_length=1, max_length=160)
    due_at: datetime | None = None

    @field_validator("due_at")
    @classmethod
    def aware_time(cls, value: datetime | None) -> datetime | None:
        if value is not None:
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("A reminder needs a timezone offset.")
            value = value.astimezone(timezone.utc)
            if value <= datetime.now(timezone.utc):
                raise ValueError("Choose a future time for the reminder.")
        return value


class TaskUpdate(StrictModel):
    completed: StrictBool


class PreferenceUpdate(StrictModel):
    include_memory: StrictBool | None = None
    offer_tools: StrictBool | None = None
    desktop_notifications: StrictBool | None = None


class ModelInput(StrictModel):
    model: str = Field(min_length=1, max_length=180, pattern=r"^[a-zA-Z0-9_./:@-]+$")


class FolderInput(StrictModel):
    path: str = Field(min_length=1, max_length=1024)
    label: str = Field(min_length=1, max_length=60)


class ProposalInput(StrictModel):
    tool: str = Field(min_length=1, max_length=80)
    arguments: dict
    conversation_id: str | None = None


class ApprovalInput(StrictModel):
    approve: StrictBool


class SpeechInput(StrictModel):
    text: str = Field(min_length=1, max_length=5000)
