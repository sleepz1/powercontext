from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from .config import Settings, load_minimax_key


@dataclass
class MiniMaxResult:
    request_id: str
    model: str
    prompt_digest: str
    raw_response: dict[str, Any]
    content: str
    extracted_code: str


SYSTEM_PROMPT = """You are a careful software engineer performing Spec-Driven Development.
You receive a context pack assembled from a database (specs, source, tests).
Your job: fix ONLY the target source file so that the new behavior tests pass
while keeping regression tests green.

Rules:
- Output the COMPLETE updated file content for the single target file.
- Wrap the file in a markdown fence tagged with the file path, e.g.
  ```python:src/refund.py
  ...full file...
  ```
- Do not invent unrelated files. Do not delete existing tests.
- Follow the applicable specs exactly.
"""


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _extract_code(content: str, fallback_name: str = "src/refund.py") -> str:
    # Prefer fenced block with path hint
    pattern = rf"```(?:python)?(?::{re.escape(fallback_name)})?\n(.*?)```"
    matches = re.findall(pattern, content, flags=re.DOTALL | re.IGNORECASE)
    if matches:
        return matches[-1].strip() + "\n"
    # Any python fence
    matches = re.findall(r"```python\n(.*?)```", content, flags=re.DOTALL)
    if matches:
        return matches[-1].strip() + "\n"
    # Generic fence
    matches = re.findall(r"```\n(.*?)```", content, flags=re.DOTALL)
    if matches:
        return matches[-1].strip() + "\n"
    raise ValueError("MiniMax response did not contain an extractable code fence")


class MiniMaxClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.api_key = load_minimax_key(settings)

    def edit_code(self, *, context_pack: str, target_path: str, current_source: str) -> MiniMaxResult:
        user = (
            "Context pack (from seekdb queries):\n"
            "-----BEGIN CONTEXT-----\n"
            f"{context_pack}\n"
            "-----END CONTEXT-----\n\n"
            f"Target file to fix: {target_path}\n"
            "Current source:\n"
            f"```python\n{current_source}\n```\n\n"
            "Produce the full fixed file now."
        )
        prompt_digest = _digest(SYSTEM_PROMPT + "\n" + user)
        payload = {
            "model": self.settings.minimax_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
            "max_tokens": 4096,
        }
        url = f"{self.settings.minimax_base_url.rstrip('/')}/chat/completions"
        r = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=120,
        )
        if r.status_code >= 400:
            raise RuntimeError(f"MiniMax HTTP {r.status_code}: {r.text[:800]}")
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        # Strip MiniMax thinking tags if present
        content_clean = re.sub(r"<think>[\s\S]*?</think>", "", content).strip()
        code = _extract_code(content_clean, fallback_name=target_path)
        request_id = str(data.get("id") or data.get("request_id") or "")
        return MiniMaxResult(
            request_id=request_id,
            model=str(data.get("model") or self.settings.minimax_model),
            prompt_digest=prompt_digest,
            raw_response=data,
            content=content,
            extracted_code=code,
        )

    def save_record(self, result: MiniMaxResult, out_dir: Path) -> Path:
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"minimax_{result.request_id or 'call'}.json"
        record = {
            "request_id": result.request_id,
            "model": result.model,
            "prompt_digest": result.prompt_digest,
            "extracted_code": result.extracted_code,
            "assistant_content": result.content,
            "usage": result.raw_response.get("usage"),
        }
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        # Also store raw (without key)
        raw_path = out_dir / f"minimax_{result.request_id or 'call'}_raw.json"
        raw_path.write_text(
            json.dumps(result.raw_response, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return path
