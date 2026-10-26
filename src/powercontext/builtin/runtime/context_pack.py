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

"""Prefix-reuse context packs for incremental transmission and exact rebuild."""

from __future__ import annotations

import base64
import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

PACK_SCHEMA = "powercontext.context-pack.v1"
DELTA_SCHEMA = "powercontext.context-pack-delta.v1"
_DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}")
# Caller ``chunk_bytes`` is an upper bound. A smaller fixed width keeps an unchanged
# prefix aligned and limits how many already-delivered bytes move into the next delta
# when the tail grows. 63 is a multiple of 3, so Base64 padding is not added per chunk.
_TRANSFER_CHUNK_BYTES = 63
_PACK_FIELDS = frozenset({"schema", "items", "digest", "byte_count"})
_DELTA_FIELDS = frozenset({"schema", "base_digest", "target_digest", "prefix_items", "appended"})


class ContextPackError(Exception):
    """A context pack or delta failed protocol or chunk validation."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ContextPack:
    """One complete context body split into checked chunks."""

    items: tuple[bytes, ...]
    digest: str
    byte_count: int

    @classmethod
    def build(cls, items: tuple[bytes, ...]) -> ContextPack:
        """Build a pack from raw chunks and the digest of its canonical item JSON."""

        normalized = _require_bytes_items(items)
        digest, byte_count, _payload = _encode_pack(normalized)
        return cls(items=normalized, digest=digest, byte_count=byte_count)

    @classmethod
    def from_content(cls, content: str, *, chunk_bytes: int = 512) -> ContextPack:
        """Split ``content`` into deterministic UTF-8 chunks no larger than ``chunk_bytes``."""

        if type(content) is not str:
            raise ContextPackError("invalid-content")
        if type(chunk_bytes) is not int or chunk_bytes <= 0:
            raise ContextPackError("invalid-chunk-size")
        return cls.build(_chunk_content(content, chunk_bytes))

    def to_bytes(self) -> bytes:
        """Serialize the canonical pack. ``len`` of the result is ``byte_count``."""

        _digest, _byte_count, payload = _encode_pack(self.items)
        return payload

    @classmethod
    def from_bytes(cls, payload: bytes) -> ContextPack:
        """Decode a canonical pack and reject any field, digest, or length mismatch."""

        if type(payload) is not bytes:
            raise ContextPackError("invalid-encoding")
        parsed = _load_object(payload)
        if set(parsed) != _PACK_FIELDS:
            raise ContextPackError("invalid-fields")
        if parsed["schema"] != PACK_SCHEMA:
            raise ContextPackError("invalid-schema")
        if type(parsed["digest"]) is not str or _DIGEST_RE.fullmatch(parsed["digest"]) is None:
            raise ContextPackError("invalid-digest")
        if type(parsed["byte_count"]) is not int:
            raise ContextPackError("invalid-byte-count")
        pack = cls.build(_decode_base64_items(parsed["items"]))
        if payload != pack.to_bytes():
            raise ContextPackError("invalid-pack")
        return pack


@dataclass(frozen=True, slots=True)
class ContextPackDelta:
    """How to rebuild a target pack from a shared prefix of a base pack."""

    base_digest: str
    target_digest: str
    prefix_items: int
    appended: tuple[bytes, ...]

    @property
    def byte_count(self) -> int:
        """Serialized size. This value is not a field of the delta JSON."""

        return len(self.to_bytes())

    @classmethod
    def between(cls, base: ContextPack, target: ContextPack) -> ContextPackDelta:
        """Keep the longest shared item prefix and carry the target suffix."""

        if type(base) is not ContextPack or type(target) is not ContextPack:
            raise ContextPackError("invalid-pack")
        prefix = 0
        limit = min(len(base.items), len(target.items))
        while prefix < limit and base.items[prefix] == target.items[prefix]:
            prefix += 1
        return cls(
            base_digest=base.digest,
            target_digest=target.digest,
            prefix_items=prefix,
            appended=target.items[prefix:],
        )

    def to_bytes(self) -> bytes:
        """Serialize the canonical delta without embedding its byte count."""

        payload = {
            "schema": DELTA_SCHEMA,
            "base_digest": self.base_digest,
            "target_digest": self.target_digest,
            "prefix_items": self.prefix_items,
            "appended": [base64.b64encode(item).decode("ascii") for item in self.appended],
        }
        return _dump(payload)

    @classmethod
    def from_bytes(cls, payload: bytes) -> ContextPackDelta:
        """Decode a delta. JSON whitespace is allowed; fields, prefix, and Base64 are not loose."""

        if type(payload) is not bytes:
            raise ContextPackError("invalid-encoding")
        parsed = _load_object(payload)
        if set(parsed) != _DELTA_FIELDS:
            raise ContextPackError("invalid-fields")
        if parsed["schema"] != DELTA_SCHEMA:
            raise ContextPackError("invalid-schema")
        base_digest = parsed["base_digest"]
        target_digest = parsed["target_digest"]
        if type(base_digest) is not str or _DIGEST_RE.fullmatch(base_digest) is None:
            raise ContextPackError("invalid-digest")
        if type(target_digest) is not str or _DIGEST_RE.fullmatch(target_digest) is None:
            raise ContextPackError("invalid-digest")
        prefix = parsed["prefix_items"]
        if type(prefix) is not int or prefix < 0:
            raise ContextPackError("invalid-prefix")
        return cls(
            base_digest=base_digest,
            target_digest=target_digest,
            prefix_items=prefix,
            appended=_decode_base64_items(parsed["appended"]),
        )


def apply_context_pack_delta(base: ContextPack, delta: ContextPackDelta) -> ContextPack:
    """Rebuild the target pack from ``base`` and ``delta`` alone."""

    if type(base) is not ContextPack or type(delta) is not ContextPackDelta:
        raise ContextPackError("invalid-pack")
    if delta.base_digest != base.digest:
        raise ContextPackError("base-digest-mismatch")
    prefix = delta.prefix_items
    if type(prefix) is not int or prefix < 0 or prefix > len(base.items):
        raise ContextPackError("invalid-prefix")
    if any(type(item) is not bytes for item in delta.appended):
        raise ContextPackError("invalid-items")
    rebuilt = ContextPack.build(base.items[:prefix] + delta.appended)
    if rebuilt.digest != delta.target_digest:
        raise ContextPackError("target-digest-mismatch")
    return rebuilt


def _require_bytes_items(items: tuple[bytes, ...] | Sequence[bytes]) -> tuple[bytes, ...]:
    if isinstance(items, (str, bytes)) or not isinstance(items, Sequence):
        raise ContextPackError("invalid-items")
    normalized: list[bytes] = []
    for item in items:
        if type(item) is not bytes:
            raise ContextPackError("invalid-items")
        normalized.append(item)
    return tuple(normalized)


def _chunk_content(content: str, chunk_bytes: int) -> tuple[bytes, ...]:
    data = content.encode("utf-8")
    if not data:
        return ()
    limit = chunk_bytes if chunk_bytes < _TRANSFER_CHUNK_BYTES else _TRANSFER_CHUNK_BYTES
    chunks: list[bytes] = []
    start = 0
    size = len(data)
    while start < size:
        end = _chunk_end(data, start, limit)
        chunks.append(data[start:end])
        start = end
    return tuple(chunks)


def _chunk_end(data: bytes, start: int, limit: int) -> int:
    """Cut on a UTF-8 boundary. A code point that cannot fit raises."""

    end = min(start + limit, len(data))
    if end < len(data):
        while end > start and (data[end] & 0xC0) == 0x80:
            end -= 1
        if end == start:
            raise ContextPackError("invalid-chunk-boundary")
    return end


def _encode_pack(items: tuple[bytes, ...]) -> tuple[str, int, bytes]:
    encoded_items = [base64.b64encode(item).decode("ascii") for item in items]
    unsigned = _dump({"schema": PACK_SCHEMA, "items": encoded_items})
    digest = "sha256:" + hashlib.sha256(unsigned).hexdigest()
    byte_count = 0
    payload = b""
    for _ in range(8):
        payload = _dump({
            "schema": PACK_SCHEMA,
            "items": encoded_items,
            "digest": digest,
            "byte_count": byte_count,
        })
        if len(payload) == byte_count:
            return digest, byte_count, payload
        byte_count = len(payload)
    raise ContextPackError("byte-count-mismatch")


def _dump(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def _load_object(payload: bytes) -> dict[str, Any]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ContextPackError("invalid-encoding") from error
    try:
        parsed = json.loads(text, object_pairs_hook=_object_pairs)
    except json.JSONDecodeError as error:
        raise ContextPackError("invalid-json") from error
    if type(parsed) is not dict:
        raise ContextPackError("invalid-json")
    return parsed


def _object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for key, value in pairs:
        if key in parsed:
            raise ContextPackError("duplicate-field")
        parsed[key] = value
    return parsed


def _decode_base64_items(value: object) -> tuple[bytes, ...]:
    if type(value) is not list:
        raise ContextPackError("invalid-items")
    items: list[bytes] = []
    for item in value:
        if type(item) is not str:
            raise ContextPackError("invalid-items")
        try:
            decoded = base64.b64decode(item, validate=True)
        except ValueError as error:
            raise ContextPackError("invalid-base64") from error
        if base64.b64encode(decoded).decode("ascii") != item:
            raise ContextPackError("invalid-base64")
        items.append(decoded)
    return tuple(items)


__all__ = [
    "ContextPack",
    "ContextPackDelta",
    "ContextPackError",
    "apply_context_pack_delta",
]
