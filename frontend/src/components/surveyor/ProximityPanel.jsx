import { useState } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { PROXIMITY_THRESHOLD_M } from "../../utils/geo.js";

const SKIP_REASONS = ["Árbol inexistente", "Acceso bloqueado", "Otro"];

function SkipSheet({ onCancel, onConfirm, isSkipping }) {
  const [selected, setSelected] = useState(null);
  const [otherText, setOtherText] = useState("");

  const reason = selected === "Otro" ? otherText.trim() : selected;
  const canConfirm = !!reason && !isSkipping;

  return (
    <div className="absolute inset-x-0 bottom-0 z-[1100] border-t bg-white p-4 shadow-lg">
      <p className="mb-3 text-sm font-semibold text-slate-700">
        ¿Por qué no se pudo censar?
      </p>
      <div className="flex flex-col gap-2">
        {SKIP_REASONS.map((option) => (
          <Button
            key={option}
            type="button"
            variant={selected === option ? "default" : "outline"}
            className="justify-start"
            onClick={() => setSelected(option)}
          >
            {option}
          </Button>
        ))}
      </div>
      {selected === "Otro" && (
        <Input
          autoFocus
          value={otherText}
          onChange={(event) => setOtherText(event.target.value)}
          placeholder="Describe el motivo"
          className="mt-3"
        />
      )}
      <div className="mt-4 flex gap-2">
        <Button
          type="button"
          variant="ghost"
          className="flex-1"
          onClick={onCancel}
        >
          Cancelar
        </Button>
        <Button
          type="button"
          className="flex-1"
          disabled={!canConfirm}
          onClick={() => onConfirm(reason)}
        >
          Confirmar omisión
        </Button>
      </div>
    </div>
  );
}

export default function ProximityPanel({
  stop,
  distance,
  inRange,
  locked,
  onVisit,
  onSkip,
  isVisiting,
  isSkipping,
}) {
  const [sheetOpen, setSheetOpen] = useState(false);

  if (!stop) return null;

  const skipped = stop.status === "skipped";
  const resolved = stop.visited || skipped;

  const handleConfirmSkip = (reason) => {
    onSkip?.(stop.id, reason);
    setSheetOpen(false);
  };

  return (
    <div className="relative shrink-0">
      <div className="flex items-center gap-3 border-t bg-white px-4 py-3">
        <div className="flex-1">
          <p className="text-sm font-semibold text-slate-700">
            {locked ? "Árbol" : "Próximo árbol"} {stop.sequence}
          </p>
          {skipped ? (
            <p className="text-xs font-medium text-slate-500">
              Omitido{stop.skip_reason ? ` — ${stop.skip_reason}` : ""}
            </p>
          ) : locked ? (
            <p className="text-xs font-medium text-amber-600">
              Visita los árboles anteriores primero
            </p>
          ) : distance == null ? (
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

        {resolved ? null : (
          <Button asChild variant="outline" disabled={locked}>
            <a
              href={`https://www.google.com/maps/dir/?api=1&destination=${stop.lat},${stop.lon}&travelmode=walking`}
              target="_blank"
              rel="noreferrer"
            >
              Navegar
            </a>
          </Button>
        )}

        {skipped ? (
          <Badge variant="secondary" className="bg-slate-200 text-slate-600">
            Omitido
          </Badge>
        ) : stop.visited ? (
          <Badge variant="secondary" className="bg-primary/10 text-primary">
            Visitado
          </Badge>
        ) : (
          <>
            <Button
              type="button"
              variant="outline"
              onClick={() => setSheetOpen(true)}
              disabled={locked || isSkipping}
            >
              No se pudo censar
            </Button>
            <Button
              type="button"
              onClick={() => onVisit(stop.id)}
              disabled={isVisiting || locked}
              className={cn(!inRange && "bg-amber-600 hover:bg-amber-600/90")}
            >
              {inRange ? "Marcar visitado" : "Marcar de todos modos"}
            </Button>
          </>
        )}
      </div>

      {sheetOpen && (
        <SkipSheet
          onCancel={() => setSheetOpen(false)}
          onConfirm={handleConfirmSkip}
          isSkipping={isSkipping}
        />
      )}
    </div>
  );
}
