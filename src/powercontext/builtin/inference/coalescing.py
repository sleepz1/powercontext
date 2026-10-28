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

"""Share event-loop-local embedding work and cache successful vectors."""

from __future__ import annotations

import asyncio
import math
from collections import OrderedDict
from dataclasses import dataclass
from typing import TypeAlias

from powercontext.builtin.inference.models import EmbeddingResult, EmbeddingVector, InferenceUsage
from powercontext.builtin.inference.protocols import EmbeddingModel, QueryEmbeddingModel


@dataclass(frozen=True, eq=False, slots=True)
class _BatchReceipt:
    """Identity, rather than equal usage values, distinguishes provider calls."""

    usage: InferenceUsage


_TextResult: TypeAlias = tuple[EmbeddingVector, _BatchReceipt]
_Batch: TypeAlias = tuple[tuple[str, asyncio.Future[_TextResult]], ...]


class CoalescingEmbeddingModel:
    """Coalesce queued and running requests within one event loop.

    Successful vectors are cached by exact text for this fixed model/profile.
    Cancelling an embed caller never cancels shared provider work. Each caller
    accounts for each provider batch it waited on once, even if it repeats a text.
    """

    def __init__(
        self,
        model: EmbeddingModel,
        *,
        max_batch_size: int = 64,
        coalesce_ms: float = 5.0,
        cache_size: int = 1024,
    ) -> None:
        if isinstance(max_batch_size, bool) or not isinstance(max_batch_size, int) or max_batch_size < 1:
            raise ValueError("max_batch_size must be a positive integer")  # noqa: TRY003
        if isinstance(cache_size, bool) or not isinstance(cache_size, int) or cache_size < 0:
            raise ValueError("cache_size must be a nonnegative integer")  # noqa: TRY003
        if not math.isfinite(coalesce_ms) or coalesce_ms < 0:
            raise ValueError("coalesce_ms must be finite and nonnegative")  # noqa: TRY003
        self.profile = model.profile
        self._model = model
        self._max_batch_size = max_batch_size
        self._coalesce_seconds = coalesce_ms / 1000
        self._cache_size = cache_size
        self._cache: OrderedDict[str, EmbeddingVector] = OrderedDict()
        self._inflight: dict[str, asyncio.Future[_TextResult]] = {}
        self._pending: dict[str, asyncio.Future[_TextResult]] = {}
        self._flush_handle: asyncio.Handle | None = None
        self._tasks: set[asyncio.Task[None]] = set()

    async def embed(self, texts: tuple[str, ...], /) -> EmbeddingResult:
        """Return ordered vectors and usage from distinct waited provider batches."""
        if not texts:
            return EmbeddingResult(vectors=())
        loop = asyncio.get_running_loop()
        vectors: dict[str, EmbeddingVector] = {}
        waiting: dict[str, asyncio.Future[_TextResult]] = {}
        # Registration has no await: concurrent callers see the same pending work.
        for text in texts:
            if text in self._cache:
                vectors[text] = self._cache[text]
                self._cache.move_to_end(text)
            elif text not in waiting:
                future = self._inflight.get(text)
                if future is None:
                    future = loop.create_future()
                    self._inflight[text] = future
                    self._pending[text] = future
                waiting[text] = future
        if self._pending and self._flush_handle is None:
            self._flush_handle = loop.call_later(self._coalesce_seconds, self._flush)
        receipts: set[_BatchReceipt] = set()
        if waiting:
            results = await asyncio.gather(*(asyncio.shield(future) for future in waiting.values()))
            for text, (vector, receipt) in zip(waiting, results, strict=True):
                vectors[text] = vector
                receipts.add(receipt)
        return EmbeddingResult(
            vectors=tuple(vectors[text] for text in texts),
            usage=_sum_usage(receipts),
        )

    async def embed_query(self, texts: tuple[str, ...], /) -> EmbeddingResult:
        """Preserve asymmetric query providers without mixing their document cache.

        Symmetric providers use the shared embed path, including its cache.
        Providers with a separate query API retain their own query behavior and
        usage; those vectors are never inserted into the document-vector cache.
        """
        if not texts:
            return EmbeddingResult(vectors=())
        if isinstance(self._model, QueryEmbeddingModel):
            return await self._model.embed_query(texts)
        return await self.embed(texts)

    def _flush(self) -> None:
        self._flush_handle = None
        queued = tuple(self._pending.items())
        self._pending.clear()
        for offset in range(0, len(queued), self._max_batch_size):
            batch = queued[offset : offset + self._max_batch_size]
            task = asyncio.create_task(self._run_batch(batch))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

    def _complete_batch(self, batch: _Batch, result: EmbeddingResult) -> None:
        if len(result.vectors) != len(batch):
            raise ValueError("embedding vector count does not match the batch")  # noqa: TRY003
        receipt = _BatchReceipt(result.usage)
        for (text, future), vector in zip(batch, result.vectors, strict=True):
            if self._cache_size:
                self._cache[text] = vector
                self._cache.move_to_end(text)
                if len(self._cache) > self._cache_size:
                    self._cache.popitem(last=False)
            future.set_result((vector, receipt))

    async def _run_batch(self, batch: _Batch) -> None:
        try:
            result = await self._model.embed(tuple(text for text, _ in batch))
            self._complete_batch(batch, result)
        except asyncio.CancelledError:
            for _, future in batch:
                future.cancel()
        except Exception as error:
            for _, future in batch:
                future.set_exception(error)
                # All callers may have been cancelled; still retrieve the error.
                # Retrieving it does not prevent remaining awaiters from raising it.
                future.exception()
        finally:
            for text, future in batch:
                if self._inflight.get(text) is future:
                    del self._inflight[text]


def _sum_usage(receipts: set[_BatchReceipt]) -> InferenceUsage:
    input_counts = [receipt.usage.input_tokens for receipt in receipts if receipt.usage.input_tokens is not None]
    output_counts = [receipt.usage.output_tokens for receipt in receipts if receipt.usage.output_tokens is not None]
    return InferenceUsage(
        requests=sum(receipt.usage.requests for receipt in receipts),
        input_tokens=sum(input_counts) if input_counts else None,
        output_tokens=sum(output_counts) if output_counts else None,
    )


__all__ = ["CoalescingEmbeddingModel"]
