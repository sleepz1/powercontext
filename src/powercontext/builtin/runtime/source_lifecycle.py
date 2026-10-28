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

"""Propagate Source availability into Memory and Topic Memory usability."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import text
from powercontext.artifacts import ArtifactRef, MemoryCitation
from powercontext.builtin.artifacts.topic_memory import TopicMemorySearchResult
from powercontext.sources import SourceRef

Policy = Literal["all", "any"]
NodeKind = Literal["source", "memory", "topic"]
ResolvePurpose = Literal["generation", "audit"]

_SCHEMA_SQL = (
    """
    CREATE TABLE IF NOT EXISTS pc_source_lifecycle_nodes (
        scope_id VARCHAR(128) NOT NULL,
        node_id VARCHAR(256) NOT NULL,
        kind VARCHAR(16) NOT NULL,
        policy VARCHAR(8),
        parents_json TEXT NOT NULL,
        reference_json TEXT NOT NULL,
        available INTEGER NOT NULL,
        lifecycle_revision INTEGER,
        PRIMARY KEY (scope_id, node_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS pc_source_lifecycle_events (
        scope_id VARCHAR(128) NOT NULL,
        node_id VARCHAR(256) NOT NULL,
        sequence INTEGER NOT NULL,
        revision INTEGER NOT NULL,
        available INTEGER NOT NULL,
        reason TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        PRIMARY KEY (scope_id, node_id, sequence)
    )
    """,
)


class SourceLifecycleError(ValueError):
    """Raised for invalid lifecycle registration, events, or resolve requests."""


class SourceLifecycleEvent(BaseModel):
    """One Source availability transition with exact revision and sequence."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    node_id: str
    revision: int
    sequence: int
    available: bool
    reason: str

    @field_validator("node_id", "reason")
    @classmethod
    def _require_text(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("must be a non-empty string")
        return value

    @field_validator("revision", "sequence")
    @classmethod
    def _require_positive(cls, value: int) -> int:
        if not isinstance(value, bool) and isinstance(value, int) and value >= 1:
            return value
        raise ValueError("must be a positive integer")


class SourceLifecycleService:
    """Scope-local DAG of Source / Memory / Topic availability."""

    def __init__(self, runtime: Any, scope_id: str) -> None:
        self._runtime = runtime
        self.scope_id = scope_id

    async def register_source(self, node_id: str, source_ref: SourceRef, *, revision: int) -> None:
        await self._ensure_schema()
        node_id = _require_node_id(node_id)
        if revision < 1:
            raise SourceLifecycleError("source-revision")
        if not isinstance(source_ref, SourceRef):
            raise SourceLifecycleError("source-ref")
        existing = await self._load_node(node_id)
        payload = source_ref.model_dump(mode="json")
        if existing is not None:
            if existing["kind"] != "source" or existing["lifecycle_revision"] != revision:
                raise SourceLifecycleError("source-conflict")
            if json.loads(existing["reference_json"]) != payload:
                raise SourceLifecycleError("source-conflict")
            return
        await self._insert_node(
            node_id=node_id,
            kind="source",
            policy=None,
            parents=(),
            reference=payload,
            available=True,
            lifecycle_revision=revision,
        )

    async def register_memory(
        self,
        node_id: str,
        citation: MemoryCitation,
        *,
        parents: Sequence[str],
        policy: Policy,
    ) -> None:
        await self._ensure_schema()
        node_id = _require_node_id(node_id)
        parents = _normalize_parents(parents)
        policy = _normalize_policy(policy)
        if not isinstance(citation, MemoryCitation):
            raise SourceLifecycleError("memory-citation")
        await self._require_readable_memory(citation)
        await self._register_derived(
            node_id=node_id,
            kind="memory",
            parents=parents,
            policy=policy,
            reference=citation.model_dump(mode="json"),
        )
        await self._sync_memory_state(node_id)

    async def register_topic(
        self,
        node_id: str,
        artifact_ref: ArtifactRef,
        *,
        parents: Sequence[str],
        policy: Policy,
    ) -> None:
        await self._ensure_schema()
        node_id = _require_node_id(node_id)
        parents = _normalize_parents(parents)
        policy = _normalize_policy(policy)
        if not isinstance(artifact_ref, ArtifactRef) or artifact_ref.family != "topic-memory":
            raise SourceLifecycleError("topic-ref")
        await self._require_readable_topic(artifact_ref)
        await self._register_derived(
            node_id=node_id,
            kind="topic",
            parents=parents,
            policy=policy,
            reference=artifact_ref.model_dump(mode="json"),
        )

    async def apply(self, event: SourceLifecycleEvent, /) -> list[str]:
        await self._ensure_schema()
        if not isinstance(event, SourceLifecycleEvent):
            raise SourceLifecycleError("event")
        node = await self._load_node(event.node_id)
        if node is None or node["kind"] != "source":
            raise SourceLifecycleError("unknown-source")
        if int(node["lifecycle_revision"] or 0) != event.revision:
            raise SourceLifecycleError("revision-mismatch")
        prior = await self._load_event(event.node_id, event.sequence)
        payload = event.model_dump(mode="json")
        if prior is not None:
            if json.loads(prior["payload_json"]) != payload:
                raise SourceLifecycleError("sequence-conflict")
            # Identical replay must finish an interrupted native Memory sync without
            # inserting a new event row. Successful replays stay revision-neutral
            # because _sync_memory_state only writes when the entry state differs.
            await self._set_available(event.node_id, event.available)
            await self._propagate()
            return await self._active_ids()
        latest = await self._latest_sequence(event.node_id)
        if latest is not None and event.sequence <= latest:
            raise SourceLifecycleError("sequence-order")
        await self._insert_event(event, payload)
        await self._set_available(event.node_id, event.available)
        await self._propagate()
        return await self._active_ids()

    async def resolve(self, node_id: str, *, purpose: ResolvePurpose) -> SourceRef | MemoryCitation | ArtifactRef:
        await self._ensure_schema()
        node_id = _require_node_id(node_id)
        if purpose not in {"generation", "audit"}:
            raise SourceLifecycleError("purpose")
        node = await self._load_node(node_id)
        if node is None:
            raise SourceLifecycleError("unknown-node")
        available = bool(node["available"])
        if purpose == "generation" and not available:
            raise SourceLifecycleError("unavailable")
        return _decode_reference(node["kind"], node["reference_json"])

    async def unavailable_topic_artifact_ids(self) -> set[str]:
        await self._ensure_schema()
        rows = await self._fetchall(
            text(
                """
                SELECT reference_json FROM pc_source_lifecycle_nodes
                WHERE scope_id = :scope_id AND kind = 'topic' AND available = 0
                """
            ),
            {"scope_id": self.scope_id},
        )
        return {str(json.loads(row[0])["artifact_id"]) for row in rows}

    async def _register_derived(
        self,
        *,
        node_id: str,
        kind: NodeKind,
        parents: tuple[str, ...],
        policy: Policy,
        reference: Mapping[str, Any],
    ) -> None:
        if not parents:
            raise SourceLifecycleError("parents-required")
        if node_id in parents:
            raise SourceLifecycleError("self-loop")
        if len(set(parents)) != len(parents):
            raise SourceLifecycleError("duplicate-parents")
        existing = await self._load_node(node_id)
        if existing is not None:
            if (
                existing["kind"] != kind
                or existing["policy"] != policy
                or tuple(json.loads(existing["parents_json"])) != parents
                or json.loads(existing["reference_json"]) != reference
            ):
                raise SourceLifecycleError("registration-conflict")
            return
        for parent in parents:
            if await self._load_node(parent) is None:
                raise SourceLifecycleError("missing-parent")
        if await self._introduces_cycle(node_id, parents):
            raise SourceLifecycleError("cycle")
        available = await self._supported(parents, policy)
        await self._insert_node(
            node_id=node_id,
            kind=kind,
            policy=policy,
            parents=parents,
            reference=reference,
            available=available,
            lifecycle_revision=None,
        )

    async def _propagate(self) -> None:
        nodes = await self._load_all_nodes()
        changed = True
        while changed:
            changed = False
            for node_id, node in nodes.items():
                if node["kind"] == "source":
                    continue
                parents = tuple(json.loads(node["parents_json"]))
                policy = node["policy"]
                supported = all(nodes[parent]["available"] for parent in parents) if policy == "all" else any(
                    nodes[parent]["available"] for parent in parents
                )
                if bool(node["available"]) != supported:
                    node["available"] = supported
                    await self._set_available(node_id, supported)
                    changed = True
        for node_id, node in nodes.items():
            if node["kind"] == "memory":
                await self._sync_memory_state(node_id, preferred_available=bool(node["available"]))

    async def _sync_memory_state(self, node_id: str, *, preferred_available: bool | None = None) -> None:
        node = await self._load_node(node_id)
        if node is None or node["kind"] != "memory":
            return
        available = bool(node["available"]) if preferred_available is None else preferred_available
        citation = MemoryCitation.model_validate(json.loads(node["reference_json"]))
        async with self._runtime._context(self.scope_id) as context:
            async with self._runtime._locked(self.scope_id):
                service = context.artifacts.memory
                current = await service.head(context.artifacts.memory_artifact_id)
                entries = await service.entries(current)
                entry = next((item for item in entries if item.entry_id == citation.entry_id), None)
                if entry is None:
                    raise SourceLifecycleError("memory-missing")
                manifest = {item.entry_id: item for item in current.content.manifest.entries}
                state = manifest[entry.entry_id].state
                if available and state != "active":
                    await service.reactivate(current, entries=(entry,), reason="source-lifecycle-restore")
                elif not available and state != "inactive":
                    await service.forget(current, entries=(entry,), reason="source-lifecycle-withdraw")

    async def _supported(self, parents: Sequence[str], policy: Policy) -> bool:
        states = []
        for parent in parents:
            node = await self._load_node(parent)
            if node is None:
                raise SourceLifecycleError("missing-parent")
            states.append(bool(node["available"]))
        return all(states) if policy == "all" else any(states)

    async def _introduces_cycle(self, node_id: str, parents: Sequence[str]) -> bool:
        nodes = await self._load_all_nodes()
        graph = {key: tuple(json.loads(value["parents_json"])) for key, value in nodes.items()}
        graph[node_id] = tuple(parents)

        def visit(current: str, stack: set[str]) -> bool:
            if current in stack:
                return True
            stack.add(current)
            for parent in graph.get(current, ()):
                if visit(parent, stack):
                    return True
            stack.remove(current)
            return False

        return visit(node_id, set())

    async def _active_ids(self) -> list[str]:
        rows = await self._fetchall(
            text(
                """
                SELECT node_id FROM pc_source_lifecycle_nodes
                WHERE scope_id = :scope_id AND available = 1
                ORDER BY node_id
                """
            ),
            {"scope_id": self.scope_id},
        )
        return [str(row[0]) for row in rows]

    async def _require_readable_memory(self, citation: MemoryCitation) -> None:
        from powercontext.builtin.runtime.models import GetMemoryEntryRequest

        try:
            await self._runtime.memory.for_scope(self.scope_id).get(GetMemoryEntryRequest(citation=citation))
        except Exception as error:
            raise SourceLifecycleError("memory-unreadable") from error

    async def _require_readable_topic(self, artifact_ref: ArtifactRef) -> None:
        try:
            await self._runtime.records.for_scope(self.scope_id).get_artifact_revision(
                "topic-memory",
                artifact_ref.artifact_id,
                artifact_ref.revision,
            )
        except Exception as error:
            raise SourceLifecycleError("topic-unreadable") from error

    async def _ensure_schema(self) -> None:
        database = self._runtime._provider.database
        async with database.transaction() as connection:
            for statement in _SCHEMA_SQL:
                await connection.exec_driver_sql(statement)

    async def _insert_node(
        self,
        *,
        node_id: str,
        kind: NodeKind,
        policy: str | None,
        parents: Sequence[str],
        reference: Mapping[str, Any],
        available: bool,
        lifecycle_revision: int | None,
    ) -> None:
        await self._execute(
            text(
                """
                INSERT INTO pc_source_lifecycle_nodes (
                    scope_id, node_id, kind, policy, parents_json, reference_json, available, lifecycle_revision
                ) VALUES (
                    :scope_id, :node_id, :kind, :policy, :parents_json, :reference_json, :available, :lifecycle_revision
                )
                """
            ),
            {
                "scope_id": self.scope_id,
                "node_id": node_id,
                "kind": kind,
                "policy": policy,
                "parents_json": json.dumps(list(parents), separators=(",", ":")),
                "reference_json": json.dumps(dict(reference), separators=(",", ":"), sort_keys=True),
                "available": int(available),
                "lifecycle_revision": lifecycle_revision,
            },
        )

    async def _set_available(self, node_id: str, available: bool) -> None:
        await self._execute(
            text(
                """
                UPDATE pc_source_lifecycle_nodes
                SET available = :available
                WHERE scope_id = :scope_id AND node_id = :node_id
                """
            ),
            {"scope_id": self.scope_id, "node_id": node_id, "available": int(available)},
        )

    async def _insert_event(self, event: SourceLifecycleEvent, payload: Mapping[str, Any]) -> None:
        await self._execute(
            text(
                """
                INSERT INTO pc_source_lifecycle_events (
                    scope_id, node_id, sequence, revision, available, reason, payload_json
                ) VALUES (
                    :scope_id, :node_id, :sequence, :revision, :available, :reason, :payload_json
                )
                """
            ),
            {
                "scope_id": self.scope_id,
                "node_id": event.node_id,
                "sequence": event.sequence,
                "revision": event.revision,
                "available": int(event.available),
                "reason": event.reason,
                "payload_json": json.dumps(dict(payload), separators=(",", ":"), sort_keys=True),
            },
        )

    async def _load_node(self, node_id: str) -> dict[str, Any] | None:
        row = await self._fetchone(
            text(
                """
                SELECT node_id, kind, policy, parents_json, reference_json, available, lifecycle_revision
                FROM pc_source_lifecycle_nodes
                WHERE scope_id = :scope_id AND node_id = :node_id
                """
            ),
            {"scope_id": self.scope_id, "node_id": node_id},
        )
        if row is None:
            return None
        return {
            "node_id": str(row[0]),
            "kind": str(row[1]),
            "policy": None if row[2] is None else str(row[2]),
            "parents_json": str(row[3]),
            "reference_json": str(row[4]),
            "available": bool(row[5]),
            "lifecycle_revision": None if row[6] is None else int(row[6]),
        }

    async def _load_all_nodes(self) -> dict[str, dict[str, Any]]:
        rows = await self._fetchall(
            text(
                """
                SELECT node_id, kind, policy, parents_json, reference_json, available, lifecycle_revision
                FROM pc_source_lifecycle_nodes
                WHERE scope_id = :scope_id
                """
            ),
            {"scope_id": self.scope_id},
        )
        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            result[str(row[0])] = {
                "node_id": str(row[0]),
                "kind": str(row[1]),
                "policy": None if row[2] is None else str(row[2]),
                "parents_json": str(row[3]),
                "reference_json": str(row[4]),
                "available": bool(row[5]),
                "lifecycle_revision": None if row[6] is None else int(row[6]),
            }
        return result

    async def _load_event(self, node_id: str, sequence: int) -> dict[str, Any] | None:
        row = await self._fetchone(
            text(
                """
                SELECT payload_json FROM pc_source_lifecycle_events
                WHERE scope_id = :scope_id AND node_id = :node_id AND sequence = :sequence
                """
            ),
            {"scope_id": self.scope_id, "node_id": node_id, "sequence": sequence},
        )
        if row is None:
            return None
        return {"payload_json": str(row[0])}

    async def _latest_sequence(self, node_id: str) -> int | None:
        row = await self._fetchone(
            text(
                """
                SELECT MAX(sequence) FROM pc_source_lifecycle_events
                WHERE scope_id = :scope_id AND node_id = :node_id
                """
            ),
            {"scope_id": self.scope_id, "node_id": node_id},
        )
        if row is None or row[0] is None:
            return None
        return int(row[0])

    async def _execute(self, statement: Any, params: Mapping[str, Any]) -> None:
        database = self._runtime._provider.database
        async with database.transaction() as connection:
            await connection.execute(statement, dict(params))

    async def _fetchone(self, statement: Any, params: Mapping[str, Any]) -> Any:
        database = self._runtime._provider.database
        async with database.transaction() as connection:
            result = await connection.execute(statement, dict(params))
            return result.one_or_none()

    async def _fetchall(self, statement: Any, params: Mapping[str, Any]) -> Sequence[Any]:
        database = self._runtime._provider.database
        async with database.transaction() as connection:
            result = await connection.execute(statement, dict(params))
            return result.all()


class SourceLifecycleApplication:
    """Attach source-lifecycle services to one built-in Runtime."""

    def __init__(self, runtime: Any) -> None:
        self._runtime = runtime
        self._services: dict[str, SourceLifecycleService] = {}

    def for_scope(self, scope_id: str, /) -> SourceLifecycleService:
        service = self._services.get(scope_id)
        if service is None:
            service = SourceLifecycleService(self._runtime, scope_id)
            self._services[scope_id] = service
        return service

    def wrap_topic_search(
        self,
        search: Callable[..., Awaitable[TopicMemorySearchResult]],
    ) -> Callable[..., Awaitable[TopicMemorySearchResult]]:
        async def filtered(scope_id: str, query: str, /, **kwargs: Any) -> TopicMemorySearchResult:
            result = await search(scope_id, query, **kwargs)
            blocked = await self.for_scope(scope_id).unavailable_topic_artifact_ids()
            if not blocked:
                return result
            hits = tuple(hit for hit in result.hits if hit.artifact_ref.artifact_id not in blocked)
            return result.model_copy(update={"hits": hits})

        return filtered


def _require_node_id(node_id: str) -> str:
    if not isinstance(node_id, str) or not node_id.strip():
        raise SourceLifecycleError("node-id")
    return node_id


def _normalize_parents(parents: Sequence[str]) -> tuple[str, ...]:
    if not isinstance(parents, Sequence) or isinstance(parents, (str, bytes)):
        raise SourceLifecycleError("parents")
    return tuple(_require_node_id(parent) for parent in parents)


def _normalize_policy(policy: Policy) -> Policy:
    if policy not in {"all", "any"}:
        raise SourceLifecycleError("policy")
    return policy


def _decode_reference(kind: str, payload: str) -> SourceRef | MemoryCitation | ArtifactRef:
    data = json.loads(payload)
    if kind == "source":
        return SourceRef.model_validate(data)
    if kind == "memory":
        return MemoryCitation.model_validate(data)
    return ArtifactRef.model_validate(data)


__all__ = [
    "SourceLifecycleApplication",
    "SourceLifecycleError",
    "SourceLifecycleEvent",
    "SourceLifecycleService",
]
