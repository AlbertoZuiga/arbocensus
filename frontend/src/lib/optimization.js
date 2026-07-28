export const STRATEGY_LABELS = {
  global: "Global",
  spatial_term: "Término espacial",
  cluster_first: "Clustering primero",
};

export const strategyLabel = (strategy) =>
  STRATEGY_LABELS[strategy] ?? strategy;

export const formatDuration = (seconds) => {
  const total = Math.round(seconds ?? 0);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  return hours > 0 ? `${hours} h ${minutes} min` : `${minutes} min`;
};

export const totalDurationSec = (travelSec, serviceSec) =>
  (travelSec ?? 0) + (serviceSec ?? 0);

export const formatDurationSplit = (travelSec, serviceSec) =>
  `Caminata ${formatDuration(travelSec ?? 0)} · Censo ${formatDuration(
    serviceSec ?? 0,
  )}`;

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
    format: formatDuration,
    better: "lower",
  },
  {
    key: "total_travel_time_sec",
    label: "Caminata",
    format: formatDuration,
    better: "lower",
  },
  {
    key: "total_service_time_sec",
    label: "Censo",
    format: formatDuration,
    better: null,
  },
  {
    key: "balance_score",
    label: "Balance de carga",
    format: (v) => v.toFixed(2),
    better: "higher",
  },
  {
    key: "dropped_trees",
    label: "Árboles fuera de ruta",
    format: (v) => `${v}`,
    better: "lower",
  },
  {
    key: "degenerate_routes",
    label: "Rutas degeneradas",
    format: (v) => `${v}`,
    better: "lower",
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

// total_time_sec/total_service_time_sec are dropped from the candidate card:
// within one sweep the census time is constant (same trees, same
// service_time_sec), so total duration only replicates travel. dropped_trees
// and degenerate_routes are surfaced as warnings there, not as numbers.
const KEY_METRIC_KEYS = ["total_routes", "total_travel_time_sec", "balance_score"];

export const KEY_METRICS = COMPARISON_METRICS.filter((m) =>
  KEY_METRIC_KEYS.includes(m.key),
);

export function solutionWarnings(solution) {
  const warnings = [];
  if (solution.dropped_trees > 0) {
    warnings.push(
      solution.dropped_trees === 1
        ? "1 árbol fuera de ruta"
        : `${solution.dropped_trees} árboles fuera de ruta`,
    );
  }
  if (solution.degenerate_routes > 0) {
    warnings.push(
      solution.degenerate_routes === 1
        ? "1 ruta muy corta"
        : `${solution.degenerate_routes} rutas muy cortas`,
    );
  }
  // The gate lives in the backend criterion (recommendation.BALANCE_GATE) and
  // arrives serialized; re-deriving it here would drift from the ranking.
  if (solution.balance_below_gate) {
    warnings.push("carga desbalanceada");
  }
  return warnings;
}

export function bestValue(values, better) {
  if (!better || values.length === 0) return null;
  const best = better === "lower" ? Math.min(...values) : Math.max(...values);
  if (values.every((v) => v === best)) return null;
  return best;
}
