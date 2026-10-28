import type { ActionRecord, ActionStatus, ChunkRecord, SourceRecord, WorkspaceCounters } from './domain.ts';

export interface Candidate {
  chunk: ChunkRecord;
  dbScore: number | null;
}

export interface ImportResult {
  source: SourceRecord;
  created: number;
  skipped: number;
  retired: number;
  revision: number;
}

export interface NewAction {
  id: string;
  workspaceId: string;
  title: string;
  ownerName: string;
  dueDate: string;
  status: ActionStatus;
  refChunkId: string | null;
  refSourceName: string;
  refChunkNo: number | null;
  refChunkRevision: number | null;
  createdAt: string;
  updatedAt: string;
  completedAt: string | null;
}

export interface ActionPatch {
  title?: string;
  ownerName?: string;
  dueDate?: string;
  status?: ActionStatus;
  completedAt?: string | null;
  updatedAt: string;
}

export interface Store {
  backend: 'seekdb';
  label: string;
  counters(workspaceId: string): Promise<WorkspaceCounters>;
  listSources(workspaceId: string, limit: number): Promise<SourceRecord[]>;
  importSource(input: { workspaceId: string; name: string; text: string }): Promise<ImportResult>;
  listChunks(workspaceId: string, sourceId: string, limit: number): Promise<ChunkRecord[]>;
  chunkById(workspaceId: string, id: string): Promise<ChunkRecord | null>;
  searchChunks(workspaceId: string, terms: string[], fetchLimit: number): Promise<Candidate[]>;
  listActions(workspaceId: string, status: ActionStatus | 'all'): Promise<ActionRecord[]>;
  createAction(input: NewAction): Promise<ActionRecord>;
  updateAction(workspaceId: string, id: string, patch: ActionPatch): Promise<ActionRecord | null>;
}
