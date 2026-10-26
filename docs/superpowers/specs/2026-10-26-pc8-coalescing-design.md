# PC-8 coalescing embedding design

Goal: implement the official memory-02-embedding-batches interface while retaining the combined contest submission and PDF implementation.

Base: 8da40f161dd28ba13290be7886c4ab4dd4d67844. Branch: codex/pc8-coalescing-embedding. Execution: GitHub Actions Ubuntu 24.04, Python 3.12, unchanged competition requirements and acceptance tests. No local checkout or local code execution.

One event-loop-local wrapper owns an insertion-ordered pending queue, a text-to-future map spanning queued and running work, a bounded OrderedDict LRU of successful vectors, a scheduled flush handle, and strong references to batch tasks. Each input call registers all its distinct misses before awaiting anything. A zero coalescing window schedules a flush on the next event-loop turn; a positive window uses a timer. A flush partitions distinct pending texts into bounded independent requests.

Each text future returns its vector and an identity-bearing successful batch receipt. The caller restores original positions, including duplicates, and sums usage from distinct receipts only. Cache entries contain only vectors and incur zero request usage. Unknown token fields stay unknown unless at least one waited batch reports a count.

Shield futures from caller cancellation. Provider failures fail only their batch, are never cached, and release text keys for retry. Consume future exceptions even if all callers cancel. A provider CancelledError cancels its dependent futures and still releases keys. Validate vector counts before caching any member of a batch.

Alternatives considered: a sequential global dispatcher would couple unrelated slow/failing requests; independent per-call batching would violate the cross-scope request budget. Shared text futures and independent batch tasks meet both cancellation isolation and budget constraints.

Deliverables: src/powercontext/builtin/inference/coalescing.py; focused regressions in tests/builtin/inference/test_coalescing.py; cloud workflow and this design/plan. No schema, dependency, existing API, official test, master/main, or existing submission branch changes.

Acceptance: all official PC-8 tests, extra boundary regressions, frozen baseline ancestry, and prior CSV/Pi/PDF/rerank/incremental/count-trigger tests. Cloud test results establish self-test completion; official competition score remains pending platform evaluation.
