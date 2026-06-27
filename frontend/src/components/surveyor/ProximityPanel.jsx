import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { PROXIMITY_THRESHOLD_M } from "../../utils/geo.js";

export default function ProximityPanel({
  stop,
  distance,
  inRange,
  locked,
  onVisit,
  isVisiting,
}) {
  if (!stop) return null;

  return (
    <div className="flex shrink-0 items-center gap-3 border-t bg-white px-4 py-3">
      <div className="flex-1">
        <p className="text-sm font-semibold text-slate-700">
          {locked ? "Árbol" : "Próximo árbol"} {stop.sequence}
        </p>
        {distance == null ? (
          <p className="text-xs text-muted-foreground">Esperando ubicación GPS…</p>
        ) : (
          <p
            className={cn(
              "text-xs font-medium",
              inRange ? "text-primary" : "text-amber-600",
            )}
          >
            {inRange
              ? `A ${Math.round(distance)} m — en rango`
              : `A ${Math.round(distance)} m — fuera del rango de ${PROXIMITY_THRESHOLD_M} m`}
          </p>
        )}
      </div>
      <Button asChild variant="outline">
        <a
          href={`https://www.google.com/maps/dir/?api=1&destination=${stop.lat},${stop.lon}&travelmode=walking`}
          target="_blank"
          rel="noreferrer"
        >
          Navegar
        </a>
      </Button>
      {stop.visited ? (
        <Badge variant="secondary" className="bg-primary/10 text-primary">
          Visitado
        </Badge>
      ) : locked ? (
        <span className="max-w-[8rem] text-right text-xs font-medium text-slate-500">
          Visita los árboles anteriores primero
        </span>
      ) : (
        <Button
          type="button"
          onClick={() => onVisit(stop.id)}
          disabled={isVisiting}
          className={cn(!inRange && "bg-amber-600 hover:bg-amber-600/90")}
        >
          {inRange ? "Marcar visitado" : "Marcar de todos modos"}
        </Button>
      )}
    </div>
  );
}
