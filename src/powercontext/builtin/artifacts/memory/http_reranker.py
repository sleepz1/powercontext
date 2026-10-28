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

"""HTTP scoring adapter for Memory reranking."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from typing import NoReturn

import httpx

from powercontext.builtin.artifacts.memory.models import MemoryHit
from powercontext.builtin.artifacts.memory.reranking import MemoryRerankDecision, _validate_bounds
from powercontext.builtin.inference import InferenceUsage

_DEFAULT_POLICY_ID = "http-cross-encoder-v1"


class HTTPMemoryReranker:
    """Score Memory candidates with an HTTP rerank service and select globally.

    Ranks stay the 1-based positions in the full candidate pool. Batches never
    renumber them, and every batch participates in one score-ordered selection.
    """

    def __init__(
        self,
        endpoint: str,
        *,
        client: httpx.AsyncClient,
        batch_size: int = 32,
        policy_id: str = _DEFAULT_POLICY_ID,
    ) -> None:
        if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size < 1:
            _invalid("batch_size must be a positive integer")
        self.policy_id = policy_id
        self._endpoint = endpoint
        self._client = client
        self._batch_size = batch_size

    async def rerank(
        self,
        query: str,
        candidates: tuple[MemoryHit, ...],
        limit: int,
        /,
    ) -> MemoryRerankDecision:
        """Return the original ranks of the top ``limit`` service scores.

        Equal scores keep the smaller original rank. ``usage.requests`` is the
        number of HTTP calls made for this successful selection.
        """

        _validate_bounds(len(candidates), limit)
        scores: dict[int, float] = {}
        requests = 0
        for start in range(0, len(candidates), self._batch_size):
            batch = candidates[start : start + self._batch_size]
            body = {
                "query": query,
                "candidates": [
                    {"rank": start + offset + 1, "text": candidate.text} for offset, candidate in enumerate(batch)
                ],
            }
            expected = {start + offset + 1 for offset in range(len(batch))}
            response = await self._client.post(self._endpoint, json=body)
            requests += 1
            try:
                response.raise_for_status()
                scores.update(_scores_for_batch(_decode_json(response), expected))
            finally:
                await response.aclose()
        selected = tuple(rank for rank, _score in sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:limit])
        return MemoryRerankDecision(
            selected_ranks=selected,
            usage=InferenceUsage(requests=requests),
            discarded_rank_count=0,
            used_fallback=False,
        )


def _decode_json(response: httpx.Response) -> object:
    try:
        return response.json()
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        _invalid("rerank response is not valid JSON", cause=error)


def _scores_for_batch(payload: object, expected: set[int]) -> dict[int, float]:
    if not isinstance(payload, Mapping) or set(payload) != {"scores"}:
        _invalid("rerank response schema is invalid")
    rows = payload.get("scores")
    if not isinstance(rows, list):
        _invalid("rerank response schema is invalid")
    found: dict[int, float] = {}
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != {"rank", "score"}:
            _invalid("rerank response schema is invalid")
        rank = row.get("rank")
        if isinstance(rank, bool) or not isinstance(rank, int) or rank not in expected or rank in found:
            _invalid("rerank response schema is invalid")
        found[rank] = _finite_score(row.get("score"))
    if set(found) != expected:
        _invalid("rerank response schema is invalid")
    return found


def _finite_score(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        _invalid("rerank score must be a finite number")
    return float(value)


def _invalid(message: str, *, cause: BaseException | None = None) -> NoReturn:
    if cause is None:
        raise ValueError(message)
    raise ValueError(message) from cause
