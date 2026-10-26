"""Boundary regressions beyond the official PC-8 public acceptance."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable

import pytest

from powercontext.builtin.artifacts.memory import EmbeddingProfile
from powercontext.builtin.inference import EmbeddingResult, InferenceUsage
from powercontext.builtin.inference.coalescing import CoalescingEmbeddingModel


class Embedding:
    profile = EmbeddingProfile(profile_id="coalescing-regression", model="offline", dimension=1)

    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    async def embed(self, texts: tuple[str, ...]) -> EmbeddingResult:
        self.calls.append(texts)
        return EmbeddingResult(
            vectors=tuple((float(len(text)),) for text in texts),
            usage=InferenceUsage(requests=3, input_tokens=7, output_tokens=2),
        )


def run(scenario: Awaitable[None]) -> None:
    asyncio.run(asyncio.wait_for(scenario, timeout=5))


def test_late_waiter_shares_inflight_work_with_cache_disabled() -> None:
    async def scenario() -> None:
        started, release = asyncio.Event(), asyncio.Event()

        class Blocked(Embedding):
            async def embed(self, texts: tuple[str, ...]) -> EmbeddingResult:
                started.set()
                await release.wait()
                return await super().embed(texts)

        base = Blocked()
        model = CoalescingEmbeddingModel(base, cache_size=0, coalesce_ms=0)
        first = asyncio.create_task(model.embed(("same", "same")))
        await started.wait()
        late = asyncio.create_task(model.embed(("same",)))
        await asyncio.sleep(0)
        release.set()
        a, b = await asyncio.gather(first, late)
        assert a.vectors == ((4.0,), (4.0,))
        assert b.vectors == ((4.0,),)
        assert a.usage == b.usage == InferenceUsage(requests=3, input_tokens=7, output_tokens=2)
        assert base.calls == [("same",)]
        await model.embed(("same",))
        assert base.calls == [("same",), ("same",)]

    run(scenario())


def test_distinct_batches_charge_provider_usage_once_per_call() -> None:
    async def scenario() -> None:
        base = Embedding()
        model = CoalescingEmbeddingModel(base, max_batch_size=2, coalesce_ms=0)
        first, second = await asyncio.gather(
            model.embed(("a", "bb", "a", "ccc")), model.embed(("bb", "bb", "ccc"))
        )
        assert first.vectors == ((1.0,), (2.0,), (1.0,), (3.0,))
        assert second.vectors == ((2.0,), (2.0,), (3.0,))
        expected = InferenceUsage(requests=6, input_tokens=14, output_tokens=4)
        assert first.usage == second.usage == expected
        cached = await model.embed(("ccc", "a"))
        assert cached.usage.requests == 0
        assert cached.usage.input_tokens in (None, 0)
        assert base.calls == [("a", "bb"), ("ccc",)]

    run(scenario())


def test_failed_batch_does_not_poison_independent_batch_or_retry() -> None:
    async def scenario() -> None:
        class Flaky(Embedding):
            async def embed(self, texts: tuple[str, ...]) -> EmbeddingResult:
                if texts == ("bad",) and ("failed",) not in self.calls:
                    self.calls.append(("failed",))
                    raise RuntimeError("offline failure")
                return await super().embed(texts)

        base = Flaky()
        model = CoalescingEmbeddingModel(base, max_batch_size=1, coalesce_ms=10)
        failed, good = await asyncio.gather(
            model.embed(("bad", "good")), model.embed(("good",)), return_exceptions=True
        )
        assert isinstance(failed, RuntimeError)
        assert isinstance(good, EmbeddingResult)
        assert good.vectors == ((4.0,),)
        assert (await model.embed(("good",))).usage.requests == 0
        assert (await model.embed(("bad",))).vectors == ((3.0,),)
        assert base.calls.count(("good",)) == 1

    run(scenario())


def test_invalid_vector_count_is_shared_and_retryable() -> None:
    async def scenario() -> None:
        class WrongCount(Embedding):
            async def embed(self, texts: tuple[str, ...]) -> EmbeddingResult:
                if not self.calls:
                    self.calls.append(texts)
                    return EmbeddingResult(vectors=())
                return await super().embed(texts)

        base = WrongCount()
        model = CoalescingEmbeddingModel(base, coalesce_ms=10)
        results = await asyncio.gather(model.embed(("x",)), model.embed(("x",)), return_exceptions=True)
        assert all(isinstance(value, ValueError) for value in results)
        assert base.calls == [("x",)]
        assert (await model.embed(("x",))).vectors == ((1.0,),)
        assert len(base.calls) == 2

    run(scenario())


def test_reverse_batch_completion_preserves_positions() -> None:
    async def scenario() -> None:
        started = asyncio.Event()
        gates = {text: asyncio.Event() for text in ("a", "bb", "ccc")}

        class Reordered(Embedding):
            async def embed(self, texts: tuple[str, ...]) -> EmbeddingResult:
                self.calls.append(texts)
                if len(self.calls) == 3:
                    started.set()
                await gates[texts[0]].wait()
                return EmbeddingResult(vectors=((float(len(texts[0])),),))

        base = Reordered()
        model = CoalescingEmbeddingModel(base, max_batch_size=1, coalesce_ms=0)
        task = asyncio.create_task(model.embed(("ccc", "a", "ccc", "bb")))
        await started.wait()
        for text in ("bb", "a", "ccc"):
            gates[text].set()
            await asyncio.sleep(0)
        assert (await task).vectors == ((3.0,), (1.0,), (3.0,), (2.0,))
        assert len(base.calls) == 3

    run(scenario())


def test_abandoned_failure_does_not_leak_unhandled_exceptions() -> None:
    async def scenario() -> None:
        loop = asyncio.get_running_loop()
        errors: list[dict[str, object]] = []
        loop.set_exception_handler(lambda _loop, context: errors.append(context))
        started, release, finished = asyncio.Event(), asyncio.Event(), asyncio.Event()

        class Flaky(Embedding):
            async def embed(self, texts: tuple[str, ...]) -> EmbeddingResult:
                if not self.calls:
                    self.calls.append(texts)
                    started.set()
                    await release.wait()
                    finished.set()
                    raise RuntimeError("abandoned provider failure")
                return await super().embed(texts)

        base = Flaky()
        model = CoalescingEmbeddingModel(base, coalesce_ms=0)
        tasks = [asyncio.create_task(model.embed(("shared",))) for _ in range(2)]
        await started.wait()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        release.set()
        await finished.wait()
        await asyncio.sleep(0)
        assert (await model.embed(("shared",))).vectors == ((6.0,),)
        await asyncio.sleep(0)
        assert errors == []

    run(scenario())


def test_provider_cancellation_releases_shared_keys_for_retry() -> None:
    async def scenario() -> None:
        class CancelOnce(Embedding):
            async def embed(self, texts: tuple[str, ...]) -> EmbeddingResult:
                if not self.calls:
                    self.calls.append(texts)
                    raise asyncio.CancelledError
                return await super().embed(texts)

        base = CancelOnce()
        model = CoalescingEmbeddingModel(base, coalesce_ms=0)
        with pytest.raises(asyncio.CancelledError):
            await model.embed(("retry",))
        assert (await model.embed(("retry",))).vectors == ((5.0,),)

    run(scenario())


def test_unknown_token_counts_remain_unknown() -> None:
    async def scenario() -> None:
        class Unknown(Embedding):
            async def embed(self, texts: tuple[str, ...]) -> EmbeddingResult:
                return EmbeddingResult(
                    vectors=tuple((1.0,) for _ in texts), usage=InferenceUsage(requests=2)
                )

        result = await CoalescingEmbeddingModel(Unknown(), max_batch_size=1, coalesce_ms=0).embed(("a", "b"))
        assert result.usage == InferenceUsage(requests=4)

    run(scenario())


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_batch_size": 0},
        {"max_batch_size": -1},
        {"max_batch_size": True},
        {"max_batch_size": 1.5},
        {"cache_size": -1},
        {"cache_size": True},
        {"cache_size": 1.5},
        {"coalesce_ms": -0.1},
        {"coalesce_ms": float("nan")},
        {"coalesce_ms": float("inf")},
    ],
)
def test_invalid_limits_fail_immediately(kwargs: dict[str, object]) -> None:
    with pytest.raises((TypeError, ValueError)):
        CoalescingEmbeddingModel(Embedding(), **kwargs)
