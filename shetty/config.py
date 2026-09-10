from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

DEFAULT_MODEL = "qwen3.5:4b"
CONTEXT_LENGTH = 4096
MAX_MODEL_BYTES = 10 * 1024**3


def local_ollama_url(value: str) -> str:
    """Do not allow configuration to turn the local model client into a proxy."""
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError as exc:
        raise ValueError("Invalid Ollama address.") from exc
    if (
        parts.scheme != "http"
        or parts.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parts.username is not None
        or parts.password is not None
        or parts.path not in {"", "/"}
        or parts.query
        or parts.fragment
        or (port is not None and not 1 <= port <= 65535)
    ):
        raise ValueError("Ollama must use an HTTP loopback address, such as http://127.0.0.1:11434.")
    return value.rstrip("/")


def is_cloud_model(name: str, metadata: dict | None = None) -> bool:
    info = metadata or {}
    # Check Ollama's cloud metadata as well as common name suffixes. A local alias
    # of a cloud model must not bypass this check.
    return (
        "cloud" in name.lower()
        or bool(info.get("remote_host"))
        or bool(info.get("remote_model"))
        or bool(info.get("remote_model_name"))
        or bool((info.get("details") or {}).get("remote_host"))
    )


@dataclass(frozen=True)
class Config:
    data_dir: Path = field(default_factory=lambda: Path.home() / ".shetty")
    ollama_url: str = "http://127.0.0.1:11434"
    default_model: str = DEFAULT_MODEL
    preview: bool = False
    scheduler_interval: float = 15.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "data_dir", Path(self.data_dir).expanduser().absolute())
        object.__setattr__(self, "ollama_url", local_ollama_url(self.ollama_url))
        if is_cloud_model(self.default_model):
            raise ValueError("Cloud models are disabled. Choose an installed local model.")

    @classmethod
    def from_env(cls, *, preview: bool = False) -> "Config":
        return cls(
            data_dir=Path(os.environ.get("SHETTY_DATA_DIR", str(Path.home() / ".shetty"))),
            ollama_url=os.environ.get("SHETTY_OLLAMA_URL", "http://127.0.0.1:11434"),
            default_model=os.environ.get("SHETTY_MODEL", DEFAULT_MODEL),
            preview=preview,
        )
