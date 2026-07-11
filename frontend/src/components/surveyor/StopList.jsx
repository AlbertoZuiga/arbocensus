import { Check, ChevronRight, CloudCheck, Lock, SkipForward } from "lucide-react";
import { cn } from "@/lib/utils";
import { isStopLocked, isStopResolved } from "../../utils/stops.js";

const dateFormatter = new Intl.DateTimeFormat("es-CL", {
  day: "2-digit",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
});

function StatusBadge({ stop, locked }) {
  if (stop.visited) {
    return (
      <span className="flex items-center gap-1 rounded-full bg-primary/10 px-2.5 py-1 text-xs font-bold text-primary">
        <Check className="h-3.5 w-3.5" aria-hidden="true" />
        Visitado
      </span>
    );
  }
  if (stop.status === "skipped") {
    return (
      <span className="flex items-center gap-1 rounded-full bg-slate-200 px-2.5 py-1 text-xs font-bold text-slate-600">
        <SkipForward className="h-3.5 w-3.5" aria-hidden="true" />
        Omitido
      </span>
    );
  }
  if (locked) {
    return (
      <span className="flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-500">
        <Lock className="h-3.5 w-3.5" aria-hidden="true" />
        Bloqueado
      </span>
    );
  }
  return (
    <span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-bold text-amber-800">
      Pendiente
    </span>
  );
}

function StopCard({ stop, selected, locked, onSelect }) {
  const resolved = isStopResolved(stop);
  return (
    <li>
      <button
        type="button"
        onClick={onSelect}
        aria-current={selected ? "true" : undefined}
        aria-label={`Árbol ${stop.sequence}${resolved ? ", registrado" : ""}`}
        className={cn(
          "flex min-h-[68px] w-full items-center gap-3 rounded-xl border bg-white p-3 text-left shadow-sm transition-colors",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
          selected
            ? "border-primary ring-1 ring-primary"
            : "border-slate-200 active:bg-slate-50",
          locked && "opacity-60",
        )}
      >
        <span
          className={cn(
            "flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-base font-bold text-white",
            stop.visited
              ? "bg-primary"
              : stop.status === "skipped"
                ? "bg-slate-400"
                : selected
                  ? "bg-blue-600"
                  : "bg-slate-500",
          )}
          aria-hidden="true"
        >
          {stop.sequence}
        </span>

        <span className="flex min-w-0 flex-1 flex-col gap-0.5">
          <span className="flex items-center gap-2">
            <span className="truncate text-base font-semibold text-slate-900">
              Árbol {stop.sequence}
            </span>
            {resolved && (
              <CloudCheck
                className="h-4 w-4 shrink-0 text-primary"
                aria-label="Sincronizado"
              />
            )}
          </span>
          <span className="truncate text-xs text-slate-500">
            {stop.visited && stop.visited_at
              ? dateFormatter.format(new Date(stop.visited_at))
              : stop.status === "skipped"
                ? (stop.skip_reason ?? "Sin motivo registrado")
                : `ID ${stop.tree_id?.slice(0, 8) ?? "—"}`}
          </span>
        </span>

        <span className="flex shrink-0 items-center gap-1">
          <StatusBadge stop={stop} locked={locked} />
          <ChevronRight className="h-5 w-5 text-slate-400" aria-hidden="true" />
        </span>
      </button>
    </li>
  );
}

export default function StopList({
  stops,
  selectedStopId,
  nextPendingStopId,
  onSelectStop,
}) {
  return (
    <ul className="flex flex-col gap-2 p-3">
      {stops.map((stop) => (
        <StopCard
          key={stop.id}
          stop={stop}
          selected={stop.id === selectedStopId}
          locked={isStopLocked(stop, nextPendingStopId)}
          onSelect={() => onSelectStop(stop.id)}
        />
      ))}
    </ul>
  );
}
