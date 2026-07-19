import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

import { progressPercent } from "@/lib/progress.js";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import ProgressBar from "./ProgressBar.jsx";

const DIMENSIONS = [
  { key: "routes", label: "Rutas" },
  { key: "surveyors", label: "Censistas" },
];

function RowTotals({ totals }) {
  return (
    <>
      <ProgressBar totals={totals} />
      <span className="flex flex-wrap justify-between gap-x-2 text-xs text-muted-foreground">
        <span>{progressPercent(totals)}% avance</span>
        <span>
          {totals.visited} censados · {totals.skipped} omitidos ·{" "}
          {totals.pending} pendientes
        </span>
      </span>
    </>
  );
}

export default function ProgressBreakdown({
  dimension,
  onDimensionChange,
  rows,
  selectedKey,
  onSelect,
  emptyMessage,
}) {
  const [expandedKeys, setExpandedKeys] = useState(() => new Set());

  const toggleExpanded = (key) => {
    setExpandedKeys((current) => {
      const next = new Set(current);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

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
          const expandable = (row.routes?.length ?? 0) > 0;
          const expanded = expandable && expandedKeys.has(row.key);
          return (
            <div key={row.key} className="flex flex-col">
              <div
                className={cn(
                  "flex items-start gap-1 rounded-md transition",
                  selected ? "bg-muted" : "hover:bg-muted/50",
                )}
              >
                {expandable && (
                  <button
                    type="button"
                    aria-expanded={expanded}
                    aria-label={`${expanded ? "Ocultar" : "Ver"} rutas de ${row.label}`}
                    onClick={() => toggleExpanded(row.key)}
                    className="rounded-md p-2 text-muted-foreground hover:text-foreground"
                  >
                    {expanded ? (
                      <ChevronDown className="h-4 w-4" />
                    ) : (
                      <ChevronRight className="h-4 w-4" />
                    )}
                  </button>
                )}
                <button
                  type="button"
                  aria-pressed={selected}
                  onClick={() => onSelect(selected ? null : row.key)}
                  className={cn(
                    "flex min-w-0 flex-1 flex-col gap-1 p-2 text-left",
                    expandable && "pl-0",
                  )}
                >
                  <span className="flex items-baseline justify-between gap-2">
                    <span className="text-sm font-medium">{row.label}</span>
                    <span className="text-xs text-muted-foreground">
                      {row.sublabel}
                    </span>
                  </span>
                  <RowTotals totals={row.totals} />
                </button>
              </div>
              {expanded && (
                <ul className="mb-1 ml-4 flex flex-col gap-1 border-l pl-3">
                  {row.routes.map((route) => (
                    <li key={route.key} className="flex flex-col gap-1 p-1">
                      <span className="text-sm">{route.label}</span>
                      <RowTotals totals={route.totals} />
                    </li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
