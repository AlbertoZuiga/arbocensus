import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { isStopLocked } from "../../utils/stops.js";

export default function StopList({
  stops,
  selectedStopId,
  nextPendingStopId,
  onSelectStop,
}) {
  return (
    <ul className="divide-y divide-slate-100">
      {stops.map((stop) => {
        const selected = stop.id === selectedStopId;
        const locked = isStopLocked(stop, nextPendingStopId);
        return (
          <li key={stop.id}>
            <button
              type="button"
              onClick={() => onSelectStop(stop.id)}
              className={cn(
                "flex w-full items-center gap-3 px-4 py-3 text-left transition-colors",
                selected ? "bg-accent" : "bg-white hover:bg-accent/50",
                locked && "opacity-60",
              )}
            >
              <span
                className={cn(
                  "flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white",
                  stop.visited
                    ? "bg-primary"
                    : selected
                      ? "bg-blue-600"
                      : "bg-slate-500",
                )}
              >
                {stop.sequence}
              </span>
              <span className="flex-1 text-sm text-slate-700">
                Árbol {stop.sequence}
              </span>
              {stop.visited && <Badge>Visitado</Badge>}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
