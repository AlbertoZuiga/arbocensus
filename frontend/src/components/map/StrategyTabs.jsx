import { useQuery } from "@tanstack/react-query";

import { fetchSolution } from "@/api/optimization.js";
import { formatDuration } from "@/lib/optimization.js";
import { cn } from "@/lib/utils";

function StrategyTab({ label, solutionId, active, onSelect }) {
  const { data: solution } = useQuery({
    queryKey: ["solution-metrics", solutionId],
    queryFn: () => fetchSolution(solutionId),
    enabled: !!solutionId,
    staleTime: Infinity,
  });

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
      <span className="text-xs text-muted-foreground">
        {solution
          ? `${solution.total_routes} rutas · ${formatDuration(
              solution.total_travel_time_sec,
            )}`
          : "—"}
      </span>
    </button>
  );
}

export default function StrategyTabs({ strategies, value, onChange }) {
  if (strategies.length === 0) return null;
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
