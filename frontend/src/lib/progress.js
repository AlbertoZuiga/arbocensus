export const STATUS_ORDER = ["visited", "skipped", "pending"];

export const STATUS_COLORS = {
  visited: "#16a34a",
  skipped: "#f59e0b",
  pending: "#94a3b8",
};

export const STATUS_LABELS = {
  visited: "Censados",
  skipped: "Omitidos",
  pending: "Pendientes",
};

export const PROGRESS_POLL_MS = 30000;

export const UNASSIGNED_KEY = "unassigned";

export function resolvedCount(totals) {
  return (totals?.visited ?? 0) + (totals?.skipped ?? 0);
}

export function progressPercent(totals) {
  const total = totals?.total ?? 0;
  if (!total) return 0;
  return Math.round((resolvedCount(totals) / total) * 100);
}

export function statusSegments(totals) {
  const total = totals?.total ?? 0;
  return STATUS_ORDER.map((status) => ({
    status,
    count: totals?.[status] ?? 0,
    percent: total ? ((totals?.[status] ?? 0) / total) * 100 : 0,
  }));
}

export function isCensusComplete(progress) {
  return !!progress?.solution && progress.totals.pending === 0;
}

export function progressPollInterval(query) {
  const { status, data } = query.state;
  if (status === "error") return false;
  if (!data?.solution) return false;
  if (isCensusComplete(data)) return false;
  return PROGRESS_POLL_MS;
}

export function stopsPollInterval(query, live) {
  if (!live || query.state.status === "error") return false;
  return PROGRESS_POLL_MS;
}
