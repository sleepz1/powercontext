export type ActionStatus = 'open' | 'doing' | 'done';

export interface ChunkRecord {
  id: string;
  workspaceId: string;
  sourceId: string;
  sourceName: string;
  chunkNo: number;
  content: string;
  revision: number;
  retiredAt: string | null;
}

export interface SourceRecord {
  id: string;
  workspaceId: string;
  name: string;
  createdAt: string;
  chunkCount: number;
  revision: number;
}

export interface ActionRecord {
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

export interface SearchHit {
  chunk: ChunkRecord;
  score: number;
  matchedKeywords: string[];
}

export interface WorkspaceCounters {
  sources: number;
  chunks: number;
  actions: number;
  openActions: number;
}

export const ACTION_STATUSES: ActionStatus[] = ['open', 'doing', 'done'];

export const STATUS_LABELS: Record<ActionStatus, string> = {
  open: '待开始',
  doing: '进行中',
  done: '已完成',
};

export const LIMITS = {
  workspaceId: 64,
  sourceName: 120,
  importText: 200_000,
  maxChunksPerSource: 460,
  query: 120,
  resultLimit: 20,
  actionTitle: 200,
  ownerName: 40,
};
