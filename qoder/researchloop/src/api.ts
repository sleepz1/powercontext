import type { ActionRecord, ActionStatus, ChunkRecord, SourceRecord, WorkspaceCounters } from "@/functions/core/domain.ts";
import { SAMPLE_MATERIALS, SAMPLE_WORKSPACE } from "@/functions/core/samples.ts";

// Same-origin core service; Vite dev/preview proxies /api to the local seekdb-backed server.
const ENDPOINT = "";

export interface Health {
  ok: boolean;
  backend: "seekdb";
  label: string;
  today: string;
}

export interface SearchOutput {
  ok: boolean;
  query: string;
  terms: string[];
  engine: string;
  retrieval: "database-fulltext-ranked";
  tookMs: number;
  hits: { chunk: ChunkRecord; dbScore: number | null; matched: string[]; provenance: string }[];
}

export interface ReportItem {
  id: string;
  title: string;
  ownerName: string;
  dueDate: string;
  statusLabel: string;
  provenance: string;
  overdue: boolean;
}

export interface ReportOutput {
  ok: boolean;
  today: string;
  range: { start: string; end: string; nextStart: string; nextEnd: string };
  completed: ReportItem[];
  pending: ReportItem[];
  nextWeek: ReportItem[];
  text: string;
  rule: "template";
}

export interface StateOutput {
  ok: boolean;
  counters: WorkspaceCounters;
  sources: SourceRecord[];
  actions: ActionRecord[];
}

export class ApiError extends Error {
  code: string;
  status: number;
  constructor(code: string, message: string, status: number) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

export const FALLBACK_MESSAGES: Record<string, string> = {
  backend_unavailable: "seekdb 数据服务当前不可用，页面不会用示例结果替代真实检索。请确认本机 seekdb 与核心服务已启动后重试。",
  empty_material: "资料内容为空，请粘贴文本或选择 Markdown / TXT 文件。",
  material_too_large: "资料超出单份长度上限，请拆成多份导入。",
  no_keywords: "请输入包含实词的问题。",
  invalid_due_date: "截止日期格式应为 YYYY-MM-DD。",
  not_found: "接口不存在。",
  internal_error: "服务处理失败，请稍后重试。",
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${ENDPOINT}${path}`, {
      credentials: "same-origin",
      ...init,
      headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError("network_error", "网络请求失败，请检查连接后重试。", 0);
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new ApiError("invalid_response", "服务返回了无法解析的内容。", response.status);
  }
  const record = (payload ?? {}) as Record<string, unknown>;
  if (!response.ok || record.ok !== true) {
    const code = typeof record.error === "string" ? record.error : `http_${response.status}`;
    const message = typeof record.message === "string" ? record.message : FALLBACK_MESSAGES[code] ?? "请求失败。";
    throw new ApiError(code, message, response.status);
  }
  return payload as T;
}

export const api = {
  health: () => request<Health>("/api/health"),
  state: (workspace: string) => request<StateOutput>(`/api/state?workspace=${encodeURIComponent(workspace)}`),
  search: (workspace: string, query: string, limit = 6) =>
    request<SearchOutput>(`/api/search?workspace=${encodeURIComponent(workspace)}&q=${encodeURIComponent(query)}&limit=${limit}`),
  chunks: (workspace: string, sourceId: string, limit = 20) =>
    request<{ ok: boolean; chunks: ChunkRecord[] }>(`/api/chunks?workspace=${encodeURIComponent(workspace)}&sourceId=${encodeURIComponent(sourceId)}&limit=${limit}`),
  importSource: (workspace: string, name: string, text: string) =>
    request<{ ok: boolean; source: SourceRecord; created: number; skipped: number; retired: number; revision: number }>("/api/sources", {
      method: "POST",
      body: JSON.stringify({ workspace, name, text }),
    }),
  createAction: (input: {
    workspace: string; title: string; ownerName: string; dueDate: string; status: ActionStatus;
    refChunkId: string | null; idempotencyKey: string;
  }) => request<{ ok: boolean; action: ActionRecord }>("/api/actions", { method: "POST", body: JSON.stringify(input) }),
  patchAction: (workspace: string, id: string, patch: Record<string, unknown>) =>
    request<{ ok: boolean; action: ActionRecord }>(`/api/actions/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ workspace, ...patch }),
    }),
  report: (workspace: string, week?: string) =>
    request<ReportOutput>(`/api/report?workspace=${encodeURIComponent(workspace)}${week ? `&week=${encodeURIComponent(week)}` : ""}`),
};

export const WORKSPACES = [
  { id: SAMPLE_WORKSPACE, label: "公开示例空间" },
  { id: "my-space", label: "我的空间" },
];

export const sampleMaterials = SAMPLE_MATERIALS;

export const describeError = (error: unknown): string =>
  error instanceof ApiError ? (FALLBACK_MESSAGES[error.code] ? `${error.message}` : error.message) : "未知错误，请重试。";
