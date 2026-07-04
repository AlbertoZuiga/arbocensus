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
    key: "total_travel_time_sec",
    label: "Tiempo total de viaje",
    format: formatDuration,
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
