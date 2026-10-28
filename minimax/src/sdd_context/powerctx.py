from __future__ import annotations

import json
from typing import Any

import requests

from .config import Settings


class PowerContextClient:
    def __init__(self, settings: Settings):
        self.base = settings.powercontext_url.rstrip("/")
        self.scope_key = settings.powercontext_scope_key
        self.scope_id: str | None = None

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        r = requests.post(
            f"{self.base}{path}",
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        if r.status_code >= 400:
            raise RuntimeError(f"PowerContext {path} HTTP {r.status_code}: {r.text}")
        return r.json()

    def _get(self, path: str) -> dict[str, Any]:
        r = requests.get(f"{self.base}{path}", timeout=30)
        if r.status_code >= 400:
            raise RuntimeError(f"PowerContext {path} HTTP {r.status_code}: {r.text}")
        return r.json()

    def ensure_scope(self) -> str:
        data = self._post(
            "/v1/scopes",
            {
                "title": "AE-02 MiniMax SDD",
                "summary": "Contest task state for MiniMax SDD context module",
                "idempotency_key": self.scope_key,
            },
        )
        self.scope_id = data["scope_id"]
        return self.scope_id

    def remember_task_state(self, text: str, reason: str = "task progress") -> dict[str, Any]:
        if not self.scope_id:
            self.ensure_scope()
        return self._post(
            "/v1/memory/remember",
            {
                "scope_id": self.scope_id,
                "kind": "decision",
                "text": text,
                "reason": reason,
            },
        )

    def ingest_source(self, source_id: str, content: str, metadata: dict | None = None) -> dict:
        if not self.scope_id:
            self.ensure_scope()
        return self._post(
            "/v1/sources/content",
            {
                "scope_id": self.scope_id,
                "source_id": source_id,
                "content": content,
                "metadata": metadata or {},
            },
        )

    def prepare(self, query: str, max_bytes: int = 8000) -> dict[str, Any]:
        if not self.scope_id:
            self.ensure_scope()
        return self._post(
            "/v1/context/prepare",
            {"scope_id": self.scope_id, "query": query, "max_bytes": max_bytes},
        )

    def health(self) -> dict[str, Any]:
        live = self._get("/health/live")
        ready = self._get("/health/ready")
        return {"live": live, "ready": ready}
