import { progressPercent } from "@/lib/progress.js";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import ProgressBar from "./ProgressBar.jsx";

const DIMENSIONS = [
  { key: "routes", label: "Rutas" },
  { key: "surveyors", label: "Censistas" },
];

export default function ProgressBreakdown({
  dimension,
  onDimensionChange,
  rows,
  selectedKey,
  onSelect,
  emptyMessage,
}) {
  return (
    <Card className="flex min-h-0 flex-col">
      <CardHeader className="flex flex-row items-center gap-2 p-3">
        <div className="flex gap-1 rounded-lg bg-muted p-1">
          {DIMENSIONS.map(({ key, label }) => (
            <button
              key={key}
              type="button"
              aria-pressed={dimension === key}
              onClick={() => onDimensionChange(key)}
              className={cn(
                "rounded-md px-3 py-1 text-sm transition",
                dimension === key
                  ? "bg-background font-medium shadow-sm"
                  : "text-muted-foreground hover:bg-background/60",
              )}
            >
              {label}
            </button>
          ))}
        </div>
        {selectedKey && (
          <Button
            variant="ghost"
            size="sm"
            className="ml-auto"
            onClick={() => onSelect(null)}
          >
            Ver todas
          </Button>
        )}
      </CardHeader>
      <CardContent className="flex flex-col gap-1 overflow-y-auto p-3 pt-0">
        {rows.length === 0 && (
          <p className="text-sm text-muted-foreground">{emptyMessage}</p>
        )}
        {rows.map((row) => {
          const selected = selectedKey === row.key;
          return (
            <button
              key={row.key}
              type="button"
              aria-pressed={selected}
              onClick={() => onSelect(selected ? null : row.key)}
              className={cn(
                "flex flex-col gap-1 rounded-md p-2 text-left transition",
                selected ? "bg-muted" : "hover:bg-muted/50",
              )}
            >
              <span className="flex items-baseline justify-between gap-2">
                <span className="text-sm font-medium">{row.label}</span>
                <span className="text-xs text-muted-foreground">
                  {row.sublabel}
                </span>
              </span>
              <ProgressBar totals={row.totals} />
              <span className="flex flex-wrap justify-between gap-x-2 text-xs text-muted-foreground">
                <span>{progressPercent(row.totals)}% avance</span>
                <span>
                  {row.totals.visited} censados · {row.totals.skipped} omitidos ·{" "}
                  {row.totals.pending} pendientes
                </span>
              </span>
            </button>
          );
        })}
      </CardContent>
    </Card>
  );
}
