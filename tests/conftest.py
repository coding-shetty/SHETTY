from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from shetty.app import create_app
from shetty.config import Config
from shetty.db import Store
from shetty.ollama import Ollama


class FakeEngine:
    """Protocol-level local Ollama substitute, used ONLY in tests."""
    def __init__(self):
        self.requests = []
        self.models = [
            {"name": "qwen3.5:4b", "size": 3_400_000_000},
            {"name": "qwen3.5:9b", "size": 6_600_000_000},
            {"name": "qwen2.5-coder:32b", "size": 19_000_000_000},
            {"name": "nemotron-3-super:cloud", "size": 0},
        ]
        self.capabilities = ["completion", "tools", "thinking"]
        self.show_extra = {}
        self.reply = {"content": "Hello from the test engine.", "thinking": "PRIVATE INTERNAL TEXT"}
        self.chat_error = False
        self.offline = False

    async def handler(self, request):
        if self.offline:
            raise httpx.ConnectError("not running", request=request)
        payload = json.loads(request.content) if request.content else None
        self.requests.append((request.url.path, payload))
        path = request.url.path
        if path == "/api/tags":
            return httpx.Response(200, json={"models": self.models})
        if path == "/api/show":
            result = dict(self.show_extra)
            if self.capabilities is not None:
                result["capabilities"] = self.capabilities
            return httpx.Response(200, json=result)
        if path == "/api/ps":
            return httpx.Response(200, json={"models": []})
        if path == "/api/chat":
            if self.chat_error:
                return httpx.Response(500, json={"error": "test engine ran out of memory"})
            return httpx.Response(200, json={"message": self.reply, "eval_count": 12})
        if path == "/api/generate":
            return httpx.Response(200, json={"done": True})
        raise AssertionError(f"Unexpected model API request: {path}")

    def client(self, config):
        return Ollama(config, httpx.AsyncClient(base_url=config.ollama_url, transport=httpx.MockTransport(self.handler), follow_redirects=False, trust_env=False))


@pytest.fixture
def config(tmp_path):
    return Config(data_dir=tmp_path / "data", scheduler_interval=3600)


@pytest.fixture
def store(config):
    return Store(config.data_dir)


@pytest.fixture
def engine():
    return FakeEngine()


@pytest.fixture
def client(config, engine):
    application = create_app(config, ollama=engine.client(config))
    with TestClient(application, base_url="http://127.0.0.1:8765") as test_client:
        token = test_client.get("/api/bootstrap").json()["token"]
        test_client.headers["X-Shetty-Token"] = token
        yield test_client
