import { useEffect, useState } from "react";
import { Camera } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import CameraCapture from "./CameraCapture.jsx";
import { PROXIMITY_THRESHOLD_M } from "../../utils/geo.js";

const SKIP_REASONS = ["Árbol inexistente", "Acceso bloqueado", "Otro"];

const TREE_STATUSES = [
  { value: "alive", label: "Vivo" },
  { value: "removed", label: "Removido / talado" },
  { value: "not_found", label: "No encontrado" },
  { value: "other", label: "Otro" },
];

function networkErrorMessage(error) {
  if (!error) return null;
  if (!error.response) {
    return "Sin conexión. No se guardó el registro — intenta de nuevo cuando tengas señal.";
  }
  return error.response?.data?.detail ?? "No se pudo guardar. Intenta de nuevo.";
}

function PhotoCaptureField({ photo, onChange, optional = false }) {
  const [cameraOpen, setCameraOpen] = useState(false);
  const [previewUrl, setPreviewUrl] = useState(null);

  useEffect(() => {
    if (!photo) {
      setPreviewUrl(null);
      return undefined;
    }
    const url = URL.createObjectURL(photo);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [photo]);

  return (
    <div className="mt-4">
      <p className="mb-1 text-sm font-medium text-slate-700">
        Foto del árbol{optional ? " (opcional)" : ""}
      </p>
      {photo ? (
        <div className="relative overflow-hidden rounded-lg">
          {previewUrl && (
            <img
              src={previewUrl}
              alt="Foto capturada del árbol"
              className="h-36 w-full object-cover"
            />
          )}
          <Button
            type="button"
            size="sm"
            variant="secondary"
            className="absolute bottom-2 right-2 shadow"
            onClick={() => setCameraOpen(true)}
          >
            <Camera className="mr-1 h-4 w-4" />
            Repetir foto
          </Button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setCameraOpen(true)}
          className="flex h-24 w-full flex-col items-center justify-center gap-1 rounded-lg border-2 border-dashed border-slate-300 bg-slate-50 text-slate-600 transition active:bg-slate-100"
        >
          <Camera className="h-6 w-6" />
          <span className="text-sm font-semibold">Tomar foto</span>
        </button>
      )}
      {cameraOpen && (
        <CameraCapture
          onCapture={(file) => {
            onChange(file);
            setCameraOpen(false);
          }}
          onClose={() => setCameraOpen(false)}
        />
      )}
    </div>
  );
}

function VisitSheet({ onCancel, onConfirm }) {
  const [status, setStatus] = useState("alive");
  const [photo, setPhoto] = useState(null);

  return (
    <div className="absolute inset-x-0 bottom-0 z-[1100] max-h-[75vh] overflow-y-auto rounded-t-2xl border-t bg-white p-4 shadow-lg">
      <p className="text-base font-bold text-slate-900">Registrar visita</p>
      <p className="mt-0.5 text-sm text-muted-foreground">
        La foto se toma con la cámara en el momento de la visita.
      </p>
      <PhotoCaptureField photo={photo} onChange={setPhoto} />
      <p className="mb-1 mt-4 text-sm font-medium text-slate-700">
        Estado del árbol
      </p>
      <div className="grid grid-cols-2 gap-2">
        {TREE_STATUSES.map((option) => (
          <Button
            key={option.value}
            type="button"
            variant={status === option.value ? "default" : "outline"}
            className="h-12"
            onClick={() => setStatus(option.value)}
          >
            {option.label}
          </Button>
        ))}
      </div>
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
          className="flex-[2]"
          disabled={!photo}
          onClick={() => onConfirm({ status, photo })}
        >
          Confirmar visita
        </Button>
      </div>
      {!photo && (
        <p className="mt-2 text-center text-xs text-muted-foreground">
          Toma la foto para poder confirmar
        </p>
      )}
    </div>
  );
}

function SkipSheet({ onCancel, onConfirm, isSkipping }) {
  const [selected, setSelected] = useState(null);
  const [otherText, setOtherText] = useState("");
  const [photo, setPhoto] = useState(null);

  const reason = selected === "Otro" ? otherText.trim() : selected;
  const canConfirm = !!reason && !isSkipping;

  return (
    <div className="absolute inset-x-0 bottom-0 z-[1100] max-h-[75vh] overflow-y-auto rounded-t-2xl border-t bg-white p-4 shadow-lg">
      <p className="mb-3 text-base font-bold text-slate-900">
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
      <PhotoCaptureField photo={photo} onChange={setPhoto} optional />
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
          onClick={() => onConfirm({ reason, photo })}
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
  visitError,
  skipError,
}) {
  const [visitSheetOpen, setVisitSheetOpen] = useState(false);
  const [skipSheetOpen, setSkipSheetOpen] = useState(false);

  useEffect(() => {
    setVisitSheetOpen(false);
    setSkipSheetOpen(false);
  }, [stop?.id]);

  if (!stop) return null;

  const skipped = stop.status === "skipped";
  const resolved = stop.visited || skipped;

  const handleConfirmVisit = (payload) => {
    onVisit?.(stop.id, payload);
    setVisitSheetOpen(false);
  };

  const handleConfirmSkip = (payload) => {
    onSkip?.(stop.id, payload);
    setSkipSheetOpen(false);
  };

  const errorMessage = networkErrorMessage(visitError ?? skipError);

  return (
    <div className="relative shrink-0">
      <div className="flex flex-col gap-3 border-t bg-white px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-base font-bold text-slate-900">
              {locked ? "Árbol" : "Próximo árbol"} {stop.sequence}
            </p>
            {skipped ? (
              <p className="text-sm font-medium text-slate-500">
                Omitido{stop.skip_reason ? ` — ${stop.skip_reason}` : ""}
              </p>
            ) : locked ? (
              <p className="text-sm font-semibold text-amber-700">
                Visita los árboles anteriores primero
              </p>
            ) : distance == null ? (
              <p className="text-sm text-muted-foreground">Esperando ubicación GPS…</p>
            ) : (
              <p
                className={cn(
                  "text-sm font-bold",
                  inRange ? "text-primary" : "text-amber-700",
                )}
              >
                {inRange
                  ? `A ${Math.round(distance)} m — en rango`
                  : `A ${Math.round(distance)} m — fuera del rango de ${PROXIMITY_THRESHOLD_M} m`}
              </p>
            )}
          </div>

          {skipped ? (
            <Badge variant="secondary" className="bg-slate-200 text-slate-600">
              Omitido
            </Badge>
          ) : stop.visited ? (
            <Badge variant="secondary" className="bg-primary/10 text-primary">
              Visitado
            </Badge>
          ) : (
            <Button asChild size="lg" variant="outline" disabled={locked} className="shrink-0">
              <a
                href={`https://www.google.com/maps/dir/?api=1&destination=${stop.lat},${stop.lon}&travelmode=walking`}
                target="_blank"
                rel="noreferrer"
              >
                Navegar
              </a>
            </Button>
          )}
        </div>

        {!resolved && errorMessage && (
          <p className="rounded-md bg-red-50 px-3 py-2 text-sm font-semibold text-red-700">
            {errorMessage}
          </p>
        )}

        {resolved ? null : (
          <div className="flex flex-col gap-2 sm:flex-row">
            <Button
              type="button"
              size="lg"
              variant="outline"
              className="h-auto min-h-14 w-full whitespace-normal px-3 text-base leading-tight sm:flex-1"
              onClick={() => setSkipSheetOpen(true)}
              disabled={locked || isSkipping}
            >
              No se pudo censar
            </Button>
            <Button
              type="button"
              size="lg"
              onClick={() => setVisitSheetOpen(true)}
              disabled={isVisiting || locked}
              className={cn(
                "h-auto min-h-14 w-full whitespace-normal px-3 text-base font-bold leading-tight sm:flex-[2]",
                !inRange && "bg-amber-600 hover:bg-amber-600/90",
              )}
            >
              {inRange ? "Marcar visitado" : "Marcar de todos modos"}
            </Button>
          </div>
        )}
      </div>

      {visitSheetOpen && (
        <VisitSheet
          onCancel={() => setVisitSheetOpen(false)}
          onConfirm={handleConfirmVisit}
        />
      )}

      {skipSheetOpen && (
        <SkipSheet
          onCancel={() => setSkipSheetOpen(false)}
          onConfirm={handleConfirmSkip}
          isSkipping={isSkipping}
        />
      )}
    </div>
  );
}
