import { ACTION_STATUSES, LIMITS, type ActionStatus } from './domain.ts';

export class InputError extends Error {
  code: string;
  constructor(code: string, message: string) {
    super(message);
    this.code = code;
  }
}

const fail = (code: string, message: string): never => {
  throw new InputError(code, message);
};

export function workspaceId(value: unknown): string {
  const text = typeof value === 'string' ? value.trim() : '';
  if (!/^[a-z0-9][a-z0-9_-]{0,63}$/.test(text) || text.length > LIMITS.workspaceId) {
    fail('invalid_workspace', '工作区标识需为 1–64 位小写字母、数字、下划线或短横线。');
  }
  return text;
}

export function sourceName(value: unknown): string {
  const text = typeof value === 'string' ? value.trim() : '';
  if (!text) fail('invalid_source_name', '资料名不能为空。');
  if (text.length > LIMITS.sourceName) fail('invalid_source_name', `资料名最长 ${LIMITS.sourceName} 个字符。`);
  if (text.includes('/') || text.includes('\\')) fail('invalid_source_name', '资料名不能包含路径分隔符。');
  return text;
}

export function importText(value: unknown): string {
  const text = typeof value === 'string' ? value.replace(/\r\n?/g, '\n') : '';
  if (!text.trim()) fail('empty_material', '资料内容为空，请粘贴或选择 Markdown / TXT 文本。');
  if (text.length > LIMITS.importText) fail('material_too_large', `单份资料最长 ${LIMITS.importText} 个字符。`);
  return text;
}

export function queryText(value: unknown): string {
  const text = typeof value === 'string' ? value.trim() : '';
  if (!text) fail('empty_query', '请输入检索问题。');
  if (text.length > LIMITS.query) fail('query_too_long', `检索问题最长 ${LIMITS.query} 个字符。`);
  return text;
}

export function resultLimit(value: unknown, fallback: number): number {
  const parsed = typeof value === 'string' ? Number(value) : typeof value === 'number' ? value : fallback;
  if (!Number.isInteger(parsed) || parsed < 1 || parsed > LIMITS.resultLimit) {
    fail('invalid_limit', `返回条数需为 1–${LIMITS.resultLimit} 的整数。`);
  }
  return parsed;
}

export function actionTitle(value: unknown): string {
  const text = typeof value === 'string' ? value.trim() : '';
  if (!text) fail('invalid_action_title', '行动项标题不能为空。');
  if (text.length > LIMITS.actionTitle) fail('invalid_action_title', `行动项标题最长 ${LIMITS.actionTitle} 个字符。`);
  return text;
}

export function ownerName(value: unknown): string {
  const text = typeof value === 'string' ? value.trim() : '';
  if (!text) fail('invalid_owner', '请填写负责人。');
  if (text.length > LIMITS.ownerName) fail('invalid_owner', `负责人最长 ${LIMITS.ownerName} 个字符。`);
  return text;
}

export function dueDate(value: unknown): string {
  const text = typeof value === 'string' ? value.trim() : '';
  if (!/^\d{4}-\d{2}-\d{2}$/.test(text)) fail('invalid_due_date', '截止日期格式应为 YYYY-MM-DD。');
  const [year, month, day] = text.split('-').map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) {
    fail('invalid_due_date', '截止日期不是有效日历日期。');
  }
  return text;
}

export function statusValue(value: unknown): ActionStatus {
  if (typeof value !== 'string' || !ACTION_STATUSES.includes(value as ActionStatus)) {
    fail('invalid_status', '状态只能是待开始、进行中或已完成。');
  }
  return value as ActionStatus;
}

export function chunkId(value: unknown): string | null {
  if (value === null || value === undefined || value === '') return null;
  const text = typeof value === 'string' ? value.trim() : '';
  if (!/^[a-f0-9]{64}$/.test(text)) fail('invalid_chunk_ref', '关联出处标识无效，请从检索结果重新选择。');
  return text;
}

export function isoDate(value: unknown): string {
  const text = typeof value === 'string' ? value.trim() : '';
  if (!/^\d{4}-\d{2}-\d{2}$/.test(text)) fail('invalid_week', '周报日期格式应为 YYYY-MM-DD。');
  return text;
}
