# Copyright (c) 2026 OceanBase.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Capture the selected branch of a Pi v3 session as immutable text evidence."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import quote

from pydantic import BaseModel, JsonValue

from powercontext.limits import MAX_SOURCE_ID_LENGTH
from powercontext.sources import (
    TEXT_EVIDENCE_PROJECTION_KEY,
    AdapterSourceDefinition,
    ConnectorRunCompletion,
    ConnectorRunSession,
    ConnectorRunStatus,
    TextEvidence,
)
from powercontext.sources.models import Source, SourceMaterialization

PI_EVENT_SOURCE_NAME = "pi-event"
PI_SESSION_CONNECTOR_NAME = "pi-session-history"


class PiSessionInput(BaseModel):
    """One UTF-8 Pi v3 JSONL archive and the branch leaf to read."""

    content: bytes
    leaf_id: str | None = None


class PiEventInput(BaseModel):
    """One visible event on the selected branch, including its original record."""

    session_id: str
    event_id: str
    parent_id: str | None
    event_type: str
    role: str
    content: str
    record: dict[str, JsonValue]


class PiEventSource(Source):
    """Captured Pi event. Identity is the session id plus the event id."""

    session_id: str
    event_id: str
    parent_id: str | None
    event_type: str
    role: str
    content: str
    record: dict[str, JsonValue]


class _PiEventSourceAdapter:
    input_class = PiEventInput
    name = PI_EVENT_SOURCE_NAME
    source_class = PiEventSource

    async def resolve(self, value: PiEventInput, /) -> PiEventSource:
        return PiEventSource(
            name=_pi_event_source_id(value.session_id, value.event_id),
            definition_version="1",
            materialization=SourceMaterialization.CAPTURED,
            session_id=value.session_id,
            event_id=value.event_id,
            parent_id=value.parent_id,
            event_type=value.event_type,
            role=value.role,
            content=value.content,
            record=value.record,
        )

    async def read(self, source: PiEventSource, /) -> PiEventInput:
        return PiEventInput(
            session_id=source.session_id,
            event_id=source.event_id,
            parent_id=source.parent_id,
            event_type=source.event_type,
            role=source.role,
            content=source.content,
            record=source.record,
        )


class _PiEventTextEvidenceProjection:
    name = TEXT_EVIDENCE_PROJECTION_KEY.name
    version = TEXT_EVIDENCE_PROJECTION_KEY.version
    source_class = PiEventSource
    output_class: type[BaseModel] = TextEvidence

    def project(self, source: PiEventSource, /) -> TextEvidence:
        return TextEvidence(
            source_type=PI_EVENT_SOURCE_NAME,
            source_id=source.name,
            content=source.content,
            metadata={
                "session_id": source.session_id,
                "event_id": source.event_id,
                "parent_id": source.parent_id,
                "event_type": source.event_type,
                "role": source.role,
            },
        )


PI_EVENT_SOURCE_DEFINITION = AdapterSourceDefinition(
    _PiEventSourceAdapter(),
    projections=(_PiEventTextEvidenceProjection(),),
)


class _Archive:
    def __init__(self, session_id: str, nodes: tuple[dict[str, Any], ...]) -> None:
        self.session_id = session_id
        self.nodes = nodes
        self.by_id = {node["id"]: node for node in nodes}


def parse_pi_session(value: PiSessionInput, /) -> tuple[PiEventInput, ...]:
    """Return visible events from the root of the selected branch through its leaf."""

    archive = _load_archive(value.content)
    return tuple(
        event
        for record in _branch_records(archive, value.leaf_id)
        if (event := _visible_event(archive.session_id, record)) is not None
    )


class PiSessionConnector:
    """Import new visible events from one Pi session file through a durable checkpoint."""

    name = PI_SESSION_CONNECTOR_NAME
    version = "1"
    source_definitions = frozenset({PI_EVENT_SOURCE_NAME})

    def __init__(self, path: str | Path, leaf_id: str | None = None) -> None:
        self._path = Path(path)
        self._leaf_id = leaf_id

    async def run(self, session: ConnectorRunSession, /) -> ConnectorRunCompletion:
        archive = _load_archive(self._path.read_bytes())
        imported = _load_checkpoint(session.checkpoint)
        fingerprints = {
            _pi_event_source_id(archive.session_id, record["id"]): _record_fingerprint(record)
            for record in archive.nodes
        }
        for identity, fingerprint in imported.items():
            current = fingerprints.get(identity)
            if current is not None and current != fingerprint:
                raise ValueError(f"imported Pi event {identity} was rewritten")  # noqa: TRY003

        for record in _branch_records(archive, self._leaf_id):
            event = _visible_event(archive.session_id, record)
            if event is None:
                continue
            identity = _pi_event_source_id(event.session_id, event.event_id)
            if identity in imported:
                continue
            await session.submit(identity, PI_EVENT_SOURCE_NAME, event)
            imported[identity] = fingerprints[identity]
        return ConnectorRunCompletion(
            status=ConnectorRunStatus.COMPLETE,
            checkpoint={"version": 1, "events": {key: imported[key] for key in sorted(imported)}},
        )


def _pi_event_source_id(session_id: str, event_id: str) -> str:
    """Stable Source id for one session event, bounded to the catalog limit."""

    literal = f"pi:{quote(session_id, safe='')}:{quote(event_id, safe='')}"
    if len(literal) <= MAX_SOURCE_ID_LENGTH:
        return literal
    digest = hashlib.sha256(session_id.encode() + b"\0" + event_id.encode()).hexdigest()
    return f"pi#{digest}"


def _load_archive(content: bytes) -> _Archive:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("Pi session is not valid UTF-8") from error  # noqa: TRY003
    records: list[Any] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as error:
            raise ValueError("Pi session line is not JSON") from error  # noqa: TRY003
    if not records:
        raise ValueError("Pi session archive is empty")  # noqa: TRY003
    session_id = _session_id(records[0])
    seen: set[str] = set()
    nodes = tuple(_validate_entry(record, seen) for record in records[1:])
    return _Archive(session_id, nodes)


def _session_id(header: object) -> str:
    if not isinstance(header, dict) or header.get("type") != "session":
        raise ValueError("Pi session header is missing")  # noqa: TRY003
    version = header.get("version")
    if type(version) is not int or version != 3:
        raise ValueError("Pi session version must be 3")  # noqa: TRY003
    session_id = header.get("id")
    if not isinstance(session_id, str) or not session_id:
        raise ValueError("Pi session id must be a non-empty string")  # noqa: TRY003
    return session_id


def _validate_entry(record: object, seen: set[str]) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise ValueError("Pi session entry must be an object")  # noqa: TRY003, TRY004
    if record.get("type") == "session":
        raise ValueError("Pi session has more than one header")  # noqa: TRY003
    event_type = record.get("type")
    if not isinstance(event_type, str) or not event_type:
        raise ValueError("Pi session entry type is required")  # noqa: TRY003
    event_id = record.get("id")
    if not isinstance(event_id, str) or not event_id:
        raise ValueError("Pi session entry id must be a non-empty string")  # noqa: TRY003
    if event_id in seen:
        raise ValueError("Pi session entry id is duplicated")  # noqa: TRY003
    if "parentId" not in record:
        raise ValueError("Pi session entry parent is required")  # noqa: TRY003
    parent_id = record["parentId"]
    if parent_id is not None and (not isinstance(parent_id, str) or parent_id not in seen):
        raise ValueError("Pi session entry parent is missing")  # noqa: TRY003
    seen.add(event_id)
    return record


def _branch_records(archive: _Archive, leaf_id: str | None) -> tuple[dict[str, Any], ...]:
    if not archive.nodes:
        raise ValueError("Pi session leaf is missing")  # noqa: TRY003
    selected = archive.nodes[-1]["id"] if leaf_id is None else leaf_id
    if not isinstance(selected, str) or selected not in archive.by_id:
        raise ValueError("Pi session leaf is missing")  # noqa: TRY003
    path: list[dict[str, Any]] = []
    current: str | None = selected
    while current is not None:
        record = archive.by_id[current]
        path.append(record)
        parent_id = record["parentId"]
        if parent_id is not None and not isinstance(parent_id, str):
            raise ValueError("Pi session entry parent is missing")  # noqa: TRY003
        current = parent_id
    path.reverse()
    return tuple(path)


def _visible_event(session_id: str, record: dict[str, Any]) -> PiEventInput | None:
    event_type = record["type"]
    rendered = _render_event(event_type, record)
    if rendered is None:
        return None
    role, body = rendered
    parent_id = record["parentId"]
    return PiEventInput(
        session_id=session_id,
        event_id=record["id"],
        parent_id=parent_id if isinstance(parent_id, str) else None,
        event_type=event_type,
        role=role,
        content=f"{role}: {body}",
        record=record,
    )


def _render_event(event_type: str, record: Mapping[str, Any]) -> tuple[str, str] | None:
    if event_type == "message":
        return _render_message(record.get("message"))
    if event_type in {"compaction", "branch_summary"}:
        summary = record.get("summary")
        if not isinstance(summary, str):
            raise ValueError("Pi summary entry requires text")  # noqa: TRY003
        if not summary:
            return None
        return event_type, summary
    if event_type == "custom_message":
        body = _plain_text(record.get("content"))
        if body is None:
            return None
        return "custom", body
    return None


def _render_message(message: object) -> tuple[str, str] | None:
    if not isinstance(message, dict):
        raise ValueError("Pi message entry requires an object")  # noqa: TRY003, TRY004
    role = message.get("role")
    if not isinstance(role, str) or not role:
        raise ValueError("Pi message role is required")  # noqa: TRY003
    if role == "bashExecution":
        command = message.get("command", "")
        output = message.get("output", "")
        if not isinstance(command, str) or not isinstance(output, str):
            raise ValueError("Pi bash execution must contain text")  # noqa: TRY003
        return role, f"$ {command}\n{output}"
    if role == "toolResult":
        tool_name = message.get("toolName", "")
        tool_call_id = message.get("toolCallId", "")
        if not isinstance(tool_name, str) or not isinstance(tool_call_id, str):
            raise ValueError("Pi tool result identity must be text")  # noqa: TRY003
        return role, f"[tool_result {tool_name} {tool_call_id}] {_plain_text(message.get('content')) or ''}"
    body = _message_body(message.get("content"))
    if body is None:
        return None
    return role, body


def _message_body(content: object) -> str | None:
    parts = _visible_parts(content, allow_tool_calls=True)
    if not parts:
        return None
    return "\n".join(parts)


def _plain_text(content: object) -> str | None:
    if content is None:
        return None
    parts = _visible_parts(content, allow_tool_calls=False)
    if not parts:
        return None
    return "\n".join(parts)


def _visible_parts(content: object, *, allow_tool_calls: bool) -> list[str]:
    if content is None:
        return []
    if isinstance(content, str):
        return [content] if content else []
    if not isinstance(content, list):
        raise ValueError("Pi message content must be text or blocks")  # noqa: TRY003, TRY004
    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            raise ValueError("Pi content block must be an object")  # noqa: TRY003, TRY004
        block_type = block.get("type")
        if block_type == "text":
            text = block.get("text", "")
            if not isinstance(text, str):
                raise ValueError("Pi text block must contain text")  # noqa: TRY003
            parts.append(text)
        elif allow_tool_calls and block_type == "toolCall":
            parts.append(_format_tool_call(block))
    if not any(parts):
        return []
    return parts


def _format_tool_call(block: Mapping[str, Any]) -> str:
    name = block.get("name", "")
    call_id = block.get("id", "")
    if not isinstance(name, str) or not isinstance(call_id, str):
        raise ValueError("Pi tool call name and id must be text")  # noqa: TRY003, TRY004
    arguments = block.get("arguments", {})
    if arguments is None:
        arguments = {}
    try:
        encoded = json.dumps(arguments, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as error:
        raise ValueError("Pi tool call arguments must be JSON") from error  # noqa: TRY003
    return f"[tool_call {name} {call_id}] {encoded}"


def _record_fingerprint(record: Mapping[str, Any]) -> str:
    encoded = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def _load_checkpoint(checkpoint: object) -> dict[str, str]:
    if checkpoint is None:
        return {}
    if not isinstance(checkpoint, dict) or checkpoint.get("version") != 1:
        raise ValueError("Pi session checkpoint is invalid")  # noqa: TRY003
    events = checkpoint.get("events")
    if not isinstance(events, dict):
        raise ValueError("Pi session checkpoint is invalid")  # noqa: TRY003, TRY004
    imported: dict[str, str] = {}
    for identity, fingerprint in events.items():
        if not isinstance(identity, str) or not isinstance(fingerprint, str):
            raise ValueError("Pi session checkpoint is invalid")  # noqa: TRY003, TRY004
        imported[identity] = fingerprint
    return imported


__all__ = [
    "PI_EVENT_SOURCE_DEFINITION",
    "PiEventInput",
    "PiSessionConnector",
    "PiSessionInput",
    "parse_pi_session",
]
