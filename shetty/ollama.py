from __future__ import annotations

import asyncio
import copy
import time

import httpx

from .config import CONTEXT_LENGTH, MAX_MODEL_BYTES, Config, is_cloud_model


class ModelError(Exception):
    """A safe, user-facing local-model failure."""


class Ollama:
    def __init__(self, config: Config, client: httpx.AsyncClient | None = None):
        self.config = config
        self.client = client or httpx.AsyncClient(
            base_url=config.ollama_url,
            timeout=httpx.Timeout(180, connect=3, pool=3, write=10),
            trust_env=False,
            follow_redirects=False,
        )
        self._cache: dict[str, tuple[float, dict]] = {}
        self._status_lock = asyncio.Lock()

    async def close(self) -> None:
        await self.client.aclose()

    def invalidate(self) -> None:
        self._cache.clear()

    async def request(self, method: str, path: str, *, payload=None, metadata=False) -> dict:
        try:
            kwargs = {"timeout": 6} if metadata else {}
            response = await self.client.request(method, path, json=payload, **kwargs)
            if response.is_redirect:
                raise ModelError("Ollama returned a redirect. Redirects are blocked to keep inference local.")
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict):
                raise ModelError("Ollama returned an unexpected response.")
            if result.get("error"):
                raise ModelError("Ollama could not complete the request: " + str(result["error"])[:250])
            return result
        except httpx.TimeoutException as exc:
            raise ModelError("Ollama took too long. Close memory-heavy apps, check ollama ps, and try again.") from exc
        except httpx.ConnectError as exc:
            raise ModelError("Ollama is not connected. Open the Ollama app on this Mac, or run ollama serve.") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise ModelError("Ollama could not complete the request. Check that it is running and the selected model is installed.") from exc

    @staticmethod
    def describe_model(item: dict) -> dict:
        name = str(item.get("name") or item.get("model") or "")
        size = item.get("size") if isinstance(item.get("size"), (int, float)) else 0
        blocked = None
        if is_cloud_model(name, item):
            blocked = "Cloud model · not allowed in local-only mode"
        elif size > MAX_MODEL_BYTES:
            blocked = "Too large for this 16 GB profile (over 10 GiB on disk)"
        return {"name": name, "size": size, "blocked": blocked}

    async def status(self, model: str, *, refresh: bool = False) -> dict:
        async with self._status_lock:
            cached = self._cache.get(model)
            if not refresh and cached and time.monotonic() - cached[0] < 8:
                return copy.deepcopy(cached[1])
            state = {
                "connected": False, "ready": False, "model": model, "models": [],
                "capabilities": [], "capabilities_verified": False, "loaded_models": [],
                "context_length": CONTEXT_LENGTH, "message": "Checking Ollama…",
            }
            try:
                tags = await self.request("GET", "/api/tags", metadata=True)
                models = tags.get("models", [])
                if not isinstance(models, list):
                    raise ModelError("Ollama returned an invalid model list.")
                state["connected"] = True
                state["models"] = [self.describe_model(item) for item in models if isinstance(item, dict)]
                selected = next((item for item in state["models"] if item["name"] == model), None)
                if not selected:
                    raise ModelError(f"{model} is not installed. Select one of your existing local models in Settings.")
                if selected["blocked"]:
                    raise ModelError(selected["blocked"])
                info = await self.request("POST", "/api/show", payload={"model": model}, metadata=True)
                if is_cloud_model(model, info):
                    selected["blocked"] = "Ollama reports a remote model · blocked"
                    raise ModelError("This model points to a cloud service. Select a fully local model.")
                caps = info.get("capabilities")
                state["capabilities_verified"] = isinstance(caps, list)
                state["capabilities"] = [c for c in (caps or []) if isinstance(c, str)] if isinstance(caps, list) else []
                if state["capabilities_verified"] and "completion" not in state["capabilities"]:
                    raise ModelError("Ollama does not report text generation for this model. Choose a chat model.")
                state["ready"] = True
                state["message"] = "Connected to local Ollama"
                try:
                    running = await self.request("GET", "/api/ps", metadata=True)
                    state["loaded_models"] = [m.get("name", m.get("model", "")) for m in running.get("models", []) if isinstance(m, dict)]
                except ModelError:
                    pass  # /ps is diagnostic, not a prerequisite for chatting.
            except ModelError as exc:
                state["message"] = str(exc)
            self._cache[model] = (time.monotonic(), copy.deepcopy(state))
            return state

    async def ensure_ready(self, model: str) -> dict:
        # Recheck metadata before inference, including remote aliases and size.
        state = await self.status(model, refresh=True)
        if not state["ready"]:
            raise ModelError(state["message"])
        return state

    async def chat(self, model: str, messages: list[dict], capabilities: list[str], tools: list[dict]) -> dict:
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "keep_alive": "2m",
            "options": {"num_ctx": CONTEXT_LENGTH, "num_predict": 768, "temperature": 0.4},
        }
        if "thinking" in capabilities:
            payload["think"] = False
        if "tools" in capabilities and tools:
            payload["tools"] = tools
        result = await self.request("POST", "/api/chat", payload=payload)
        message = result.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content", ""), str):
            raise ModelError("Ollama returned an invalid chat message.")
        # Deliberately do not surface or persist the model's hidden thinking field.
        return {
            "content": message.get("content", "")[:20000],
            "tool_calls": message.get("tool_calls", []) if isinstance(message.get("tool_calls", []), list) else [],
            "eval_count": result.get("eval_count"),
        }

    async def unload(self, model: str) -> None:
        if is_cloud_model(model):
            return
        info = await self.request("POST", "/api/show", payload={"model": model}, metadata=True)
        if is_cloud_model(model, info):
            raise ModelError("This model now points to a cloud service. It cannot be managed in local-only mode.")
        await self.request("POST", "/api/generate", payload={"model": model, "keep_alive": 0, "stream": False})
        self.invalidate()
