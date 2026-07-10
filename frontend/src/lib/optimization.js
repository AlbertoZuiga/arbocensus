export const STRATEGY_LABELS = {
  global: "Global",
  spatial_term: "Término espacial",
  cluster_first: "Clustering primero",
};

export const strategyLabel = (strategy) =>
  STRATEGY_LABELS[strategy] ?? strategy;

const STATUS_SUMMARIES = {
  queued: "En cola",
  running: "Optimizando…",
};

export const strategySummary = (job) => {
  const strategies = Object.keys(job.solution_ids ?? {});
  if (strategies.length > 0) return strategies.map(strategyLabel).join(", ");
  return STATUS_SUMMARIES[job.status] ?? "Sin soluciones";
};

export const formatDuration = (seconds) => {
  const total = Math.round(seconds ?? 0);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  return hours > 0 ? `${hours} h ${minutes} min` : `${minutes} min`;
};

export const formatDurationBreakdown = (travelSec, serviceSec) => {
  const travel = travelSec ?? 0;
  const service = serviceSec ?? 0;
  return `Total ${formatDuration(travel + service)} · Caminata ${formatDuration(
    travel,
  )} · Censo ${formatDuration(service)}`;
};

const ACTIVE_STATUSES = ["queued", "running"];
export const MAX_POLL_MS = 15 * 60 * 1000;

export function pollInterval(status, createdAt, now = Date.now()) {
  if (!ACTIVE_STATUSES.includes(status)) return false;
  if (createdAt) {
    const elapsed = now - new Date(createdAt).getTime();
    if (elapsed >= MAX_POLL_MS) return false;
  }
  return 3000;
}

export const formatElapsed = (value, now = Date.now()) => {
  if (!value) return null;
  const minutes = Math.max(0, Math.floor((now - new Date(value).getTime()) / 60000));
  return `hace ${minutes} min`;
};

export const formatTimestamp = (value, dateStyle = "long") =>
  value
    ? new Date(value).toLocaleString("es-CL", { dateStyle, timeStyle: "short" })
    : "Sin iniciar";

export const COMPARISON_METRICS = [
  {
    key: "total_routes",
    label: "Rutas",
    format: (v) => `${v}`,
    better: null,
  },
  {
    key: "total_time_sec",
    label: "Duración total",
    format: (_value, solution) =>
      formatDurationBreakdown(
        solution.total_travel_time_sec,
        solution.total_service_time_sec,
      ),
    better: "lower",
  },
  {
    key: "balance_score",
    label: "Balance de carga",
    format: (v) => v.toFixed(2),
    better: "higher",
  },
  {
    key: "sum_max_radius_m",
    label: "Radio máx. (suma)",
    format: (v) => `${v} m`,
    better: "lower",
  },
  {
    key: "interleave_per_route",
    label: "Solapamiento por ruta",
    format: (v) => v.toFixed(2),
    better: "lower",
  },
  {
    key: "worst_pair_iou",
    label: "IoU peor par",
    format: (v) => v.toFixed(2),
    better: "lower",
  },
];

export function bestValue(values, better) {
  if (!better || values.length === 0) return null;
  const best = better === "lower" ? Math.min(...values) : Math.max(...values);
  if (values.every((v) => v === best)) return null;
  return best;
}
