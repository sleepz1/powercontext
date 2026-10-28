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

"""Admit one Source-driven invocation when a journal count threshold is reached."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from powercontext.builtin.persistence.cursors import SourceCursorRepository
from powercontext.builtin.persistence.processing_intents import ArtifactProcessingIntentRepository
from powercontext.builtin.persistence.tables import SOURCE_JOURNAL_HEADS_TABLE


async def request_pending_source_count(
    connection: AsyncConnection,
    scope_id: str,
    binding_name: str,
    threshold: int | None,
) -> bool:
    """Request one invocation when new journal identities meet ``threshold``.

    The count is ``journal head - successful cursor`` for this binding. Duplicate
    captures and receipt trust upgrades do not advance the head, so they cannot
    admit work. An accepted invocation that has not been acknowledged is left
    untouched: failure keeps that request, and a later success rechecks the
    cursor before another admission.
    """

    if threshold is None:
        return False
    cursor = await SourceCursorRepository().load(connection, scope_id, binding_name)
    position = 0 if cursor is None else cursor.cursor.sequence
    head = await connection.scalar(
        select(SOURCE_JOURNAL_HEADS_TABLE.c.position).where(SOURCE_JOURNAL_HEADS_TABLE.c.scope_id == scope_id)
    )
    if head is None or int(head) - position < threshold:
        return False
    intents = ArtifactProcessingIntentRepository()
    current = await intents.load(connection, scope_id, binding_name, for_update=True)
    if current is not None and current.requested_generation != current.handled_generation:
        return False
    await intents.request(connection, scope_id, binding_name)
    return True


__all__ = ["request_pending_source_count"]
