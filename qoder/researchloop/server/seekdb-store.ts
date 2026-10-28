import { SeekdbClient } from 'seekdb';
import { chunkFingerprint, chunkIdOf, chunkText } from '../functions/core/chunk.ts';
import type { ActionPatch, Candidate, ImportResult, NewAction, Store } from '../functions/core/store.ts';
import { ACTION_STATUSES, type ActionRecord, type ActionStatus, type ChunkRecord, type SourceRecord, type WorkspaceCounters } from '../functions/core/domain.ts';

// seekdb holds every business record: material chunks (with an ngram fulltext index)
// and action items. Retrieval ranking happens inside the database, not in this process.
const TABLES = {
  sources: 'researchloop.rl_sources',
  chunks: 'researchloop.rl_material_chunks',
  actions: 'researchloop.rl_actions',
};

const SCHEMA = [
  'CREATE DATABASE IF NOT EXISTS researchloop',
  `CREATE TABLE IF NOT EXISTS ${TABLES.sources} (
     id varchar(64) PRIMARY KEY, workspace_id varchar(64) NOT NULL, name varchar(240) NOT NULL,
     created_at varchar(40) NOT NULL, updated_at varchar(40) NOT NULL, chunk_count int NOT NULL,
     revision int NOT NULL DEFAULT 1,
     UNIQUE KEY uk_source (workspace_id, name), KEY idx_source_ws (workspace_id, created_at))`,
  `CREATE TABLE IF NOT EXISTS ${TABLES.chunks} (
     id varchar(64) PRIMARY KEY, workspace_id varchar(64) NOT NULL, source_id varchar(64) NOT NULL,
     source_name varchar(240) NOT NULL, chunk_no int NOT NULL, content text NOT NULL,
     created_at varchar(40) NOT NULL, revision int NOT NULL DEFAULT 1, retired_at varchar(40) NULL,
     KEY idx_chunk_ws (workspace_id, chunk_no), KEY idx_chunk_source (source_id, revision),
     FULLTEXT INDEX ft_chunk(content) WITH PARSER ngram)`,
  `CREATE TABLE IF NOT EXISTS ${TABLES.actions} (
     id varchar(64) PRIMARY KEY, workspace_id varchar(64) NOT NULL, title varchar(300) NOT NULL,
     owner_name varchar(80) NOT NULL, due_date varchar(10) NOT NULL, status varchar(16) NOT NULL,
     ref_chunk_id varchar(64) NULL, ref_source_name varchar(240) NOT NULL DEFAULT '',
     ref_chunk_no int NULL, ref_chunk_revision int NULL, created_at varchar(40) NOT NULL,
     updated_at varchar(40) NOT NULL, completed_at varchar(40) NULL,
     KEY idx_action_ws (workspace_id, due_date))`,
];

// Existing installations gain the versioning columns without dropping anything.
const ADDABLE_COLUMNS = [
  { table: TABLES.sources, name: 'revision', ddl: 'int NOT NULL DEFAULT 1' },
  { table: TABLES.chunks, name: 'revision', ddl: 'int NOT NULL DEFAULT 1' },
  { table: TABLES.chunks, name: 'retired_at', ddl: 'varchar(40) NULL' },
  { table: TABLES.actions, name: 'ref_chunk_revision', ddl: 'int NULL' },
];

type Row = Record<string, unknown>;

const text = (value: unknown, fallback = ''): string => (typeof value === 'string' ? value : fallback);
const num = (value: unknown, fallback = 0): number => (typeof value === 'number' && Number.isFinite(value) ? value : Number(value) || fallback);
const nullable = (value: unknown): string | null => (value === null || value === undefined || value === '' ? null : String(value));

function toChunk(row: Row): ChunkRecord {
  return {
    id: text(row.id), workspaceId: text(row.workspace_id), sourceId: text(row.source_id),
    sourceName: text(row.source_name), chunkNo: num(row.chunk_no), content: text(row.content),
    revision: num(row.revision, 1), retiredAt: nullable(row.retired_at),
  };
}

function toAction(row: Row): ActionRecord {
  const status = text(row.status, 'open') as ActionRecord['status'];
  return {
    id: text(row.id), workspaceId: text(row.workspace_id), title: text(row.title),
    ownerName: text(row.owner_name), dueDate: text(row.due_date),
    status: ACTION_STATUSES.includes(status) ? status : 'open',
    refChunkId: row.ref_chunk_id ? text(row.ref_chunk_id) : null,
    refSourceName: text(row.ref_source_name),
    refChunkNo: row.ref_chunk_no === null || row.ref_chunk_no === undefined ? null : num(row.ref_chunk_no),
    refChunkRevision: row.ref_chunk_revision === null || row.ref_chunk_revision === undefined ? null : num(row.ref_chunk_revision),
    createdAt: text(row.created_at), updatedAt: text(row.updated_at),
    completedAt: nullable(row.completed_at),
  };
}

function toSource(row: Row): SourceRecord {
  return {
    id: text(row.id), workspaceId: text(row.workspace_id), name: text(row.name),
    createdAt: text(row.created_at), chunkCount: num(row.chunk_count), revision: num(row.revision, 1),
  };
}

export async function ensureSeekdbSchema(client: SeekdbClient): Promise<string[]> {
  const applied: string[] = [];
  for (const statement of SCHEMA) await client.execute(statement);
  const rows = (await client.execute(
    "SELECT TABLE_NAME, COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='researchloop' AND TABLE_NAME IN ('rl_sources','rl_material_chunks','rl_actions')",
  ) ?? []) as Row[];
  const present = new Set(rows.map(row => `${text(row.TABLE_NAME ?? row.table_name)}.${text(row.COLUMN_NAME ?? row.column_name)}`));
  for (const column of ADDABLE_COLUMNS) {
    const bare = column.table.split('.').pop() ?? column.table;
    if (present.has(`${bare}.${column.name}`)) continue;
    await client.execute(`ALTER TABLE ${column.table} ADD COLUMN ${column.name} ${column.ddl}`);
    applied.push(`${bare}.${column.name}`);
  }
  return applied;
}

export function seekdbStore(client: SeekdbClient): Store {
  const run = async (sql: string, params: unknown[] = []): Promise<Row[]> => {
    const result = await client.execute(sql, params);
    return (result ?? []) as Row[];
  };

  const chunkColumns = 'id, workspace_id, source_id, source_name, chunk_no, content, revision, retired_at';

  return {
    backend: 'seekdb',
    label: 'seekdb 1.4.0 · 库内 ngram 全文检索',

    async counters(workspaceId): Promise<WorkspaceCounters> {
      const [row] = await run(
        `SELECT (SELECT COUNT(*) FROM ${TABLES.sources} WHERE workspace_id=?) AS sources,
                (SELECT COUNT(*) FROM ${TABLES.chunks} WHERE workspace_id=? AND retired_at IS NULL) AS chunks,
                (SELECT COUNT(*) FROM ${TABLES.actions} WHERE workspace_id=?) AS actions,
                (SELECT COUNT(*) FROM ${TABLES.actions} WHERE workspace_id=? AND status<>'done') AS open_actions`,
        [workspaceId, workspaceId, workspaceId, workspaceId],
      );
      return {
        sources: num(row?.sources), chunks: num(row?.chunks),
        actions: num(row?.actions), openActions: num(row?.open_actions),
      };
    },

    async listSources(workspaceId, limit) {
      const rows = await run(
        `SELECT id, workspace_id, name, created_at, chunk_count, revision FROM ${TABLES.sources}
         WHERE workspace_id=? ORDER BY created_at DESC LIMIT ${Math.max(1, Math.min(200, limit))}`,
        [workspaceId],
      );
      return rows.map(toSource);
    },

    // Same-name import policy: identical content stays idempotent; changed content
    // opens a new revision, retires (never deletes) the previous chunks, and keeps
    // existing citations resolvable through their original chunk ids.
    async importSource({ workspaceId, name, text: material }): Promise<ImportResult> {
      const pieces = chunkText(material);
      const now = new Date().toISOString();
      const sourceId = await chunkIdOf(`source|${workspaceId}|${name}`);
      const ids: string[] = [];
      for (let index = 0; index < pieces.length; index += 1) {
        ids.push(await chunkIdOf(chunkFingerprint(workspaceId, name, index, pieces[index])));
      }
      const [current] = await run(
        `SELECT id, workspace_id, name, created_at, chunk_count, revision FROM ${TABLES.sources}
         WHERE workspace_id=? AND name=? LIMIT 1`,
        [workspaceId, name],
      );
      const activeRows = await run(
        `SELECT ${chunkColumns} FROM ${TABLES.chunks} WHERE workspace_id=? AND source_id=? AND retired_at IS NULL`,
        [workspaceId, sourceId],
      );
      const active = activeRows.map(toChunk);
      const currentRevision = current ? num(current.revision, 1) : 0;
      const sameSet = active.length === ids.length && active.every((chunk, index) => chunk.id === ids[index] && chunk.chunkNo === index);

      if (current && sameSet) {
        return {
          source: toSource(current), created: 0, skipped: pieces.length, retired: 0, revision: currentRevision,
        };
      }

      const revision = currentRevision + 1;
      let created = 0;
      for (let index = 0; index < pieces.length; index += 1) {
        const before = await run(`SELECT id FROM ${TABLES.chunks} WHERE id=?`, [ids[index]]);
        await run(
          `INSERT INTO ${TABLES.chunks} (id, workspace_id, source_id, source_name, chunk_no, content, created_at, revision, retired_at)
           VALUES (?,?,?,?,?,?,?,?,NULL) ON DUPLICATE KEY UPDATE revision=VALUES(revision), retired_at=NULL, source_id=VALUES(source_id), source_name=VALUES(source_name)`,
          [ids[index], workspaceId, sourceId, name, index, pieces[index], now, revision],
        );
        if (!before.length) created += 1;
      }

      const [stale] = await run(
        `SELECT COUNT(*) AS stale FROM ${TABLES.chunks}
         WHERE workspace_id=? AND source_id=? AND retired_at IS NULL AND revision<>?`,
        [workspaceId, sourceId, revision],
      );
      const retired = num(stale?.stale);
      if (retired > 0) {
        await run(
          `UPDATE ${TABLES.chunks} SET retired_at=? WHERE workspace_id=? AND source_id=? AND retired_at IS NULL AND revision<>?`,
          [now, workspaceId, sourceId, revision],
        );
      }

      await run(
        `INSERT INTO ${TABLES.sources} (id, workspace_id, name, created_at, updated_at, chunk_count, revision)
         VALUES (?,?,?,?,?,?,?) ON DUPLICATE KEY UPDATE updated_at=VALUES(updated_at), chunk_count=VALUES(chunk_count), revision=VALUES(revision)`,
        [sourceId, workspaceId, name, now, now, pieces.length, revision],
      );

      return {
        source: {
          id: sourceId, workspaceId, name,
          createdAt: current ? text(current.created_at) : now,
          chunkCount: pieces.length, revision,
        },
        created,
        skipped: pieces.length - created,
        retired,
        revision,
      };
    },

    async listChunks(workspaceId, sourceId, limit) {
      const rows = await run(
        `SELECT ${chunkColumns} FROM ${TABLES.chunks}
         WHERE workspace_id=? AND source_id=? AND retired_at IS NULL ORDER BY chunk_no ASC
         LIMIT ${Math.max(1, Math.min(200, limit))}`,
        [workspaceId, sourceId],
      );
      return rows.map(toChunk);
    },

    async chunkById(workspaceId, id) {
      const rows = await run(
        `SELECT ${chunkColumns} FROM ${TABLES.chunks} WHERE workspace_id=? AND id=? LIMIT 1`,
        [workspaceId, id],
      );
      return rows.length ? toChunk(rows[0]) : null;
    },

    // One statement: seekdb filters and scores with MATCH(...) AGAINST(...) on the ngram index.
    async searchChunks(workspaceId, terms, fetchLimit): Promise<Candidate[]> {
      const phrase = terms.join(' ');
      const limit = Math.max(1, Math.min(80, fetchLimit));
      const rows = await run(
        `SELECT ${chunkColumns}, MATCH(content) AGAINST(?) AS score
         FROM ${TABLES.chunks}
         WHERE workspace_id=? AND retired_at IS NULL AND MATCH(content) AGAINST(?)
         ORDER BY score DESC LIMIT ${limit}`,
        [phrase, workspaceId, phrase],
      );
      return rows.map(row => ({ chunk: toChunk(row), dbScore: Number(row.score ?? 0) }));
    },

    async listActions(workspaceId, status) {
      const where = status === 'all' ? 'workspace_id=?' : 'workspace_id=? AND status=?';
      const params = status === 'all' ? [workspaceId] : [workspaceId, status as ActionStatus];
      const rows = await run(
        `SELECT id, workspace_id, title, owner_name, due_date, status, ref_chunk_id, ref_source_name,
                ref_chunk_no, ref_chunk_revision, created_at, updated_at, completed_at
         FROM ${TABLES.actions} WHERE ${where} ORDER BY due_date ASC LIMIT 200`,
        params,
      );
      return rows.map(toAction);
    },

    async createAction(input: NewAction): Promise<ActionRecord> {
      await run(
        `INSERT INTO ${TABLES.actions} (id, workspace_id, title, owner_name, due_date, status, ref_chunk_id,
           ref_source_name, ref_chunk_no, ref_chunk_revision, created_at, updated_at, completed_at)
         VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) ON DUPLICATE KEY UPDATE updated_at=VALUES(updated_at)`,
        [input.id, input.workspaceId, input.title, input.ownerName, input.dueDate, input.status,
          input.refChunkId, input.refSourceName, input.refChunkNo, input.refChunkRevision,
          input.createdAt, input.updatedAt, input.completedAt],
      );
      const rows = await run(`SELECT * FROM ${TABLES.actions} WHERE id=? AND workspace_id=? LIMIT 1`, [input.id, input.workspaceId]);
      return toAction(rows[0]);
    },

    async updateAction(workspaceId, id, patch: ActionPatch): Promise<ActionRecord | null> {
      const columns: string[] = ['updated_at=?'];
      const params: unknown[] = [patch.updatedAt];
      if (patch.title !== undefined) { columns.push('title=?'); params.push(patch.title); }
      if (patch.ownerName !== undefined) { columns.push('owner_name=?'); params.push(patch.ownerName); }
      if (patch.dueDate !== undefined) { columns.push('due_date=?'); params.push(patch.dueDate); }
      if (patch.status !== undefined) { columns.push('status=?'); params.push(patch.status); }
      if (patch.completedAt !== undefined) { columns.push('completed_at=?'); params.push(patch.completedAt); }
      params.push(id, workspaceId);
      await run(`UPDATE ${TABLES.actions} SET ${columns.join(', ')} WHERE id=? AND workspace_id=?`, params);
      const rows = await run(`SELECT * FROM ${TABLES.actions} WHERE id=? AND workspace_id=? LIMIT 1`, [id, workspaceId]);
      return rows.length ? toAction(rows[0]) : null;
    },
  };
}
