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

function ChildRoute({ route, selected, onSelect }) {
  return (
    <li>
      <button
        type="button"
        aria-pressed={selected}
        onClick={onSelect}
        className={cn(
          "grid w-full grid-cols-[2.25rem_1fr_2.5rem] items-center gap-2 rounded px-2 py-1.5 text-left transition",
          selected
            ? "bg-background shadow-sm ring-2 ring-primary"
            : "hover:bg-background/60",
        )}
      >
        <span
          className={cn(
            "rounded px-1 py-0.5 text-center text-[11px] font-medium tabular-nums ring-1 ring-inset",
            selected
              ? "bg-primary text-primary-foreground ring-primary"
              : "bg-background/80 text-muted-foreground ring-border",
          )}
        >
          R{route.number}
        </span>
        <span className="flex flex-col gap-1">
          <ProgressBar totals={route.totals} className="h-1" />
          <span
            className={cn(
              "text-[11px] leading-none",
              selected ? "font-medium text-foreground" : "text-muted-foreground",
            )}
          >
            {route.totals.visited} censados · {route.totals.skipped} omitidos ·{" "}
            {route.totals.pending} pendientes
          </span>
        </span>
        <span
          className={cn(
            "text-right text-[11px] tabular-nums",
            selected ? "font-semibold text-foreground" : "text-muted-foreground",
          )}
        >
          {progressPercent(route.totals)}%
        </span>
      </button>
    </li>
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
      <CardContent className="flex flex-col gap-2 overflow-y-auto p-3 pt-0">
        {rows.length === 0 && (
          <p className="text-sm text-muted-foreground">{emptyMessage}</p>
        )}
        {rows.map((row) => {
          const selected = selectedKey === row.key;
          const childRoutes = row.routes ?? [];
          const expandable = childRoutes.length > 0;
          const expanded = expandable && expandedKeys.has(row.key);
          const selectedChild = childRoutes.find(
            (route) => route.key === selectedKey,
          );
          const childSelected = !!selectedChild;
          return (
            <div
              key={row.key}
              className={cn(
                "overflow-hidden rounded-lg border transition",
                selected && "border-primary ring-2 ring-primary",
                !selected && childSelected && "border-primary/50",
                !selected && !childSelected && "border-border",
              )}
            >
              <button
                type="button"
                aria-pressed={selected}
                onClick={() => onSelect(selected ? null : row.key)}
                className={cn(
                  "flex w-full flex-col gap-1 p-2.5 text-left transition",
                  selected ? "bg-primary/10" : "hover:bg-muted/40",
                )}
              >
                <span className="flex items-baseline justify-between gap-2">
                  <span className="text-sm font-semibold">{row.label}</span>
                  {selected ? (
                    <span className="shrink-0 rounded-full bg-primary px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-primary-foreground">
                      En el mapa
                    </span>
                  ) : (
                    <span className="text-xs text-muted-foreground">
                      {row.sublabel}
                    </span>
                  )}
                </span>
                <RowTotals totals={row.totals} />
              </button>

              {expandable && (
                <>
                  <button
                    type="button"
                    aria-expanded={expanded}
                    aria-label={`${expanded ? "Ocultar" : "Ver"} rutas de ${row.label}`}
                    onClick={() => toggleExpanded(row.key)}
                    className={cn(
                      "flex w-full items-center gap-1 border-t px-2.5 py-1.5 text-xs transition hover:bg-muted/40 hover:text-foreground",
                      !expanded && childSelected
                        ? "font-medium text-foreground"
                        : "text-muted-foreground",
                    )}
                  >
                    {expanded ? (
                      <ChevronDown className="h-3.5 w-3.5" />
                    ) : (
                      <ChevronRight className="h-3.5 w-3.5" />
                    )}
                    {expanded && "Ocultar rutas"}
                    {!expanded &&
                      (childSelected
                        ? `R${selectedChild.number} en el mapa`
                        : `Ver ${childRoutes.length} ${
                            childRoutes.length === 1 ? "ruta" : "rutas"
                          }`)}
                  </button>

                  {expanded && (
                    <ul className="flex flex-col gap-0.5 border-t bg-muted/50 p-1.5">
                      {childRoutes.map((route) => (
                        <ChildRoute
                          key={route.key}
                          route={route}
                          selected={selectedKey === route.key}
                          onSelect={() =>
                            onSelect(
                              selectedKey === route.key ? null : route.key,
                            )
                          }
                        />
                      ))}
                    </ul>
                  )}
                </>
              )}
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
