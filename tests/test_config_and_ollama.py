import asyncio

import httpx
import pytest

from shetty.config import Config, is_cloud_model, local_ollama_url
from shetty.ollama import ModelError, Ollama


@pytest.mark.parametrize("url", ["https://api.example.com", "http://192.168.1.1:11434", "http://localhost.evil.test", "http://user@localhost", "http://127.0.0.1/private", "http://127.0.0.1?api_key=secret", "ftp://localhost", "http://localhost:99999", "http://localhost#x"])
def test_ollama_must_remain_loopback(url):
    with pytest.raises(ValueError):
        local_ollama_url(url)


@pytest.mark.parametrize("url", ["http://127.0.0.1:11434", "http://localhost:11434/", "http://[::1]:11434"])
def test_loopback_allowed(url):
    assert local_ollama_url(url) == url.rstrip("/")


def test_remote_metadata_and_name_guards():
    assert is_cloud_model("example:cloud")
    assert is_cloud_model("innocent:4b", {"remote_host": "https://ollama.com"})
    assert is_cloud_model("innocent:4b", {"remote_model": "remote-version"})
    assert not is_cloud_model("qwen3.5:4b")
    with pytest.raises(ValueError):
        Config(default_model="example:cloud")


def test_status_checks_capabilities_without_loading(config, engine):
    async def run():
        client = engine.client(config)
        result = await client.status("qwen3.5:4b")
        assert result["ready"]
        assert result["capabilities_verified"]
        assert result["capabilities"] == engine.capabilities
        assert all(path in {"/api/tags", "/api/show", "/api/ps"} for path, _ in engine.requests)
        await client.close()
    asyncio.run(run())


@pytest.mark.parametrize("model", ["qwen2.5-coder:32b", "nemotron-3-super:cloud", "not-installed:4b"])
def test_blocked_or_missing_models_never_generate(config, engine, model):
    async def run():
        client = engine.client(config)
        with pytest.raises(ModelError):
            await client.ensure_ready(model)
        assert not any(path == "/api/chat" for path, _ in engine.requests)
        await client.close()
    asyncio.run(run())


def test_remote_alias_blocked_even_with_local_name(config, engine):
    engine.show_extra = {"remote_host": "https://ollama.com", "remote_model": "big-remote-model"}
    async def run():
        client = engine.client(config)
        result = await client.status("qwen3.5:4b")
        assert not result["ready"]
        assert "cloud" in result["message"]
        await client.close()
    asyncio.run(run())


def test_payload_is_bounded_and_thinking_is_not_exposed(config, engine):
    async def run():
        client = engine.client(config)
        result = await client.chat("qwen3.5:4b", [{"role": "user", "content": "Hello"}], engine.capabilities, [{"type": "function"}])
        assert result["content"] == "Hello from the test engine."
        assert "thinking" not in result
        payload = engine.requests[-1][1]
        assert payload["options"]["num_ctx"] == 4096
        assert payload["options"]["num_predict"] == 768
        assert payload["keep_alive"] == "2m"
        assert payload["think"] is False
        assert "tools" in payload
        await client.chat("qwen3.5:4b", [], ["completion"], [{"type": "function"}])
        payload = engine.requests[-1][1]
        assert "think" not in payload and "tools" not in payload
        await client.close()
    asyncio.run(run())


def test_older_ollama_can_chat_but_does_not_assume_tools(config, engine):
    engine.capabilities = None
    async def run():
        client = engine.client(config)
        result = await client.status("qwen3.5:4b")
        assert result["ready"] and not result["capabilities_verified"]
        assert result["capabilities"] == []
        await client.close()
    asyncio.run(run())


def test_redirect_is_blocked_not_followed(config):
    requests = []
    def redirect(request):
        requests.append(str(request.url))
        return httpx.Response(307, headers={"location": "https://example.com/chat"})
    async def run():
        http = httpx.AsyncClient(base_url=config.ollama_url, transport=httpx.MockTransport(redirect), follow_redirects=False)
        client = Ollama(config, http)
        with pytest.raises(ModelError, match="redirect"):
            await client.request("POST", "/api/chat", payload={})
        assert len(requests) == 1
        assert requests[0].startswith("http://127.0.0.1")
        await client.close()
    asyncio.run(run())


def test_offline_is_real_not_a_demo_response(config, engine):
    engine.offline = True
    async def run():
        client = engine.client(config)
        result = await client.status("qwen3.5:4b")
        assert not result["connected"] and not result["ready"]
        assert "ollama serve" in result["message"]
        await client.close()
    asyncio.run(run())
