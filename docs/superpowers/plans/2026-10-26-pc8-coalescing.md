# PC-8 coalescing embedding implementation plan

> Execute inline with cloud verification after each implementation step.

**Goal:** satisfy every behavior of memory-02-embedding-batches.
**Architecture:** shared text futures, independent bounded batch tasks, successful-vector LRU and per-call batch receipts.
**Tech Stack:** Python asyncio, existing EmbeddingModel/EmbeddingResult/InferenceUsage; GitHub Actions Linux.

- [x] Read the official instruction, public tests, inference contracts and repository guidance.
- [x] Create an isolated branch based on the PDF submission.
- [x] Add the cloud acceptance workflow and run the unmodified official test to confirm the missing-interface failure.
- [ ] Commit additional boundary tests before product implementation.
- [ ] Run the cloud tests to confirm the additional tests share the same missing-interface failure.
- [ ] Add the wrapper in src/powercontext/builtin/inference/coalescing.py. Validate constructor limits, preserve profile, register distinct misses synchronously, flush queued texts into max_batch_size chunks, shield shared futures, resolve receipts and restore input order.
- [ ] Run make -C competition test-embedding and the focused tests in cloud Linux. Fix implementation defects against the unchanged behavioral assertions.
- [ ] Run make -C competition check-baseline test-csv test-pi test-pdf test-rerank test-incremental test-count-trigger.
- [ ] Check formatting/types for the changed module and focused test file. Review task behavior and diff.
- [ ] Create a reviewable PR against 2026-competition with the exact tested commit and cloud logs; retain the independent branch and do not merge master/main.
- [ ] Update the existing Notion competition hub with ownership, exact version, validation and official-score status.

Focused tests: late in-flight reuse without cache, distinct-batch provider usage, isolated batch failure and retry, shared invalid-vector errors, reversed batch completion, abandoned errors after all callers cancel, provider cancellation cleanup, unknown tokens and invalid limits.
Commands:
```bash
make -C competition install check-baseline test-embedding
PYTHONPATH=src PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 competition/.venv/bin/python -m pytest -q -o addopts= --confcutdir=tests/builtin/inference tests/builtin/inference/test_coalescing.py
make -C competition test-csv test-pi test-pdf test-rerank test-incremental test-count-trigger
```
