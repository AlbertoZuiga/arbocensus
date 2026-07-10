import { useQuery } from "@tanstack/react-query";

import { fetchSolution } from "@/api/optimization.js";
import { formatDurationBreakdown } from "@/lib/optimization.js";
import { cn } from "@/lib/utils";

function useSolutionMetrics(solutionId) {
  const { data: solution } = useQuery({
    queryKey: ["solution-metrics", solutionId],
    queryFn: () => fetchSolution(solutionId),
    enabled: !!solutionId,
    staleTime: Infinity,
  });

  return solution
    ? `${solution.total_routes} rutas · ${formatDurationBreakdown(
        solution.total_travel_time_sec,
        solution.total_service_time_sec,
      )}`
    : "—";
}

function StrategyTab({ label, solutionId, active, onSelect }) {
  const metrics = useSolutionMetrics(solutionId);

  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "flex min-w-[7rem] flex-col rounded-md px-3 py-1.5 text-left transition",
        active
          ? "bg-background shadow-sm"
          : "text-muted-foreground hover:bg-background/60",
      )}
    >
      <span className="text-sm font-medium">{label}</span>
      <span className="text-xs text-muted-foreground">{metrics}</span>
    </button>
  );
}

function StrategyChip({ label, solutionId }) {
  const metrics = useSolutionMetrics(solutionId);

  return (
    <div className="flex min-w-[7rem] flex-col rounded-md border bg-background/90 px-3 py-1.5 text-left shadow-md backdrop-blur">
      <span className="text-sm font-medium">{label}</span>
      <span className="text-xs text-muted-foreground">{metrics}</span>
    </div>
  );
}

export default function StrategyTabs({ strategies, value, onChange }) {
  if (strategies.length === 0) return null;

  if (strategies.length === 1) {
    const [strategy] = strategies;
    return (
      <StrategyChip label={strategy.label} solutionId={strategy.solutionId} />
    );
  }

  return (
    <div className="flex gap-1 rounded-lg border bg-muted/80 p-1 shadow-md backdrop-blur">
      {strategies.map((strategy) => (
        <StrategyTab
          key={strategy.key}
          label={strategy.label}
          solutionId={strategy.solutionId}
          active={value === strategy.key}
          onSelect={() => onChange(strategy.key)}
        />
      ))}
    </div>
  );
}
