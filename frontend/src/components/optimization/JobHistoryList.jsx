import { cn } from "@/lib/utils";
import JobStatusBadge from "./JobStatusBadge";

const STRATEGY_LABELS = {
  global: "Global",
  spatial_term: "Término espacial",
  cluster_first: "Clustering primero",
};

const formatTimestamp = (value) => {
  if (!value) return "Sin iniciar";
  return new Date(value).toLocaleString("es-CL", {
    dateStyle: "short",
    timeStyle: "short",
  });
};

const strategySummary = (job) => {
  const strategies = Object.keys(job.solution_ids ?? {});
  if (strategies.length === 0) return "Sin soluciones";
  return strategies.map((s) => STRATEGY_LABELS[s] ?? s).join(", ");
};

export default function JobHistoryList({ jobs, selectedJobId, onSelect }) {
  if (!jobs || jobs.length === 0) return null;

  return (
    <ul className="flex flex-col gap-2">
      {jobs.map((job) => (
        <li key={job.id}>
          <button
            type="button"
            onClick={() => onSelect(job.id)}
            aria-pressed={job.id === selectedJobId}
            className={cn(
              "w-full rounded-md border p-3 text-left transition-colors",
              job.id === selectedJobId
                ? "border-primary bg-accent"
                : "hover:bg-accent/50",
            )}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-medium">
                {formatTimestamp(job.started_at)}
              </span>
              <JobStatusBadge status={job.status} />
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              {strategySummary(job)}
            </p>
          </button>
        </li>
      ))}
    </ul>
  );
}
