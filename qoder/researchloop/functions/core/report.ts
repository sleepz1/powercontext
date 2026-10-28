import { provenance } from './chunk.ts';
import { STATUS_LABELS, type ActionRecord } from './domain.ts';

export interface WeekRange {
  start: string;
  end: string;
  nextStart: string;
  nextEnd: string;
}

const dayKey = (date: Date): string => date.toISOString().slice(0, 10);

export function weekRange(anchor: string): WeekRange {
  const [year, month, day] = anchor.split('-').map(Number);
  const utc = new Date(Date.UTC(year, month - 1, day));
  const weekday = (utc.getUTCDay() + 6) % 7; // Monday = 0
  const start = new Date(utc);
  start.setUTCDate(utc.getUTCDate() - weekday);
  const end = new Date(start);
  end.setUTCDate(start.getUTCDate() + 6);
  const nextStart = new Date(end);
  nextStart.setUTCDate(end.getUTCDate() + 1);
  const nextEnd = new Date(nextStart);
  nextEnd.setUTCDate(nextStart.getUTCDate() + 6);
  return { start: dayKey(start), end: dayKey(end), nextStart: dayKey(nextStart), nextEnd: dayKey(nextEnd) };
}

const inRange = (date: string | null, range: [string, string]): date is string =>
  !!date && date >= range[0] && date <= range[1];

export interface ReportItem {
  id: string;
  title: string;
  ownerName: string;
  dueDate: string;
  statusLabel: string;
  provenance: string;
  overdue: boolean;
}

export interface ReportSections {
  range: WeekRange;
  completed: ReportItem[];
  pending: ReportItem[];
  nextWeek: ReportItem[];
  text: string;
  rule: 'template';
}

const toItem = (action: ActionRecord, today: string): ReportItem => ({
  id: action.id,
  title: action.title,
  ownerName: action.ownerName,
  dueDate: action.dueDate,
  statusLabel: STATUS_LABELS[action.status],
  provenance: action.refChunkId
    ? provenance({ sourceName: action.refSourceName, chunkNo: (action.refChunkNo ?? 0), revision: action.refChunkRevision ?? undefined })
    : '未关联资料',
  overdue: action.status !== 'done' && action.dueDate < today,
});

export function buildWeeklyReport(
  actions: ActionRecord[],
  anchor: string,
  range: WeekRange,
  today: string,
): ReportSections {
  const completed = actions
    .filter(action => action.status === 'done' && inRange(action.completedAt, [range.start, range.end]))
    .map(action => toItem(action, today));
  const pending = actions
    .filter(action => action.status !== 'done' && action.dueDate <= range.end)
    .sort((a, b) => a.dueDate.localeCompare(b.dueDate) || a.title.localeCompare(b.title, 'zh-Hans-CN'))
    .map(action => toItem(action, today));
  const nextWeek = actions
    .filter(action => action.status !== 'done' && (inRange(action.dueDate, [range.nextStart, range.nextEnd]) || action.status === 'doing'))
    .sort((a, b) => a.dueDate.localeCompare(b.dueDate))
    .map(action => toItem(action, today));

  const lines: string[] = [`# 研途周报（${range.start} ~ ${range.end}）`, '', '本周整理由模板规则生成，出处指向已入库资料分块。'];
  const section = (title: string, items: ReportItem[]) => {
    lines.push('', `## ${title}`);
    if (!items.length) {
      lines.push('- 暂无记录');
      return;
    }
    for (const item of items) {
      const tail = item.overdue ? `（已逾期，截止 ${item.dueDate}）` : `（截止 ${item.dueDate}）`;
      lines.push(`- ${item.title}｜${item.ownerName}｜${item.statusLabel}${tail}｜出处：${item.provenance}`);
    }
  };
  section('本周完成', completed);
  section('待解决问题', pending);
  section('下周计划', nextWeek);

  return { range, completed, pending, nextWeek, text: lines.join('\n'), rule: 'template' };
}
