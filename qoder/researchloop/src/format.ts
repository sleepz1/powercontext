export const todayLabel = (offsetDays = 0): string =>
  new Date(Date.now() + offsetDays * 86_400_000 + 8 * 3_600_000).toISOString().slice(0, 10);

export const backendTitle = (backend: string | undefined): string =>
  backend === "seekdb" ? "seekdb 数据服务" : "后端未就绪";
