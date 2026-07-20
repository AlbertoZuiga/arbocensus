import { useEffect, useState } from "react";
import { Camera } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import CameraCapture from "./CameraCapture.jsx";
import { PROXIMITY_THRESHOLD_M } from "../../utils/geo.js";

const REGISTER_OPTIONS = [
  { value: "alive", label: "Vivo", action: "visit", photoRequired: true },
  { value: "removed", label: "Removido / talado", action: "visit", photoRequired: true },
  { value: "not_found", label: "No encontrado", action: "visit", photoRequired: false },
  {
    value: "blocked",
    label: "Acceso bloqueado",
    action: "skip",
    reason: "Acceso bloqueado",
    photoRequired: false,
  },
  { value: "other", label: "Otro", action: "skip", photoRequired: false },
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

function RegisterSheet({ onCancel, onVisit, onSkip, isSaving }) {
  const [selectedValue, setSelectedValue] = useState(null);
  const [otherText, setOtherText] = useState("");
  const [photo, setPhoto] = useState(null);

  const selected = REGISTER_OPTIONS.find(
    (option) => option.value === selectedValue
  );
  const reason =
    selected?.value === "other" ? otherText.trim() : selected?.reason;
  const missingPhoto = !!selected?.photoRequired && !photo;
  const canConfirm =
    !!selected &&
    !missingPhoto &&
    (selected.action !== "skip" || !!reason) &&
    !isSaving;

  const handleConfirm = () => {
    if (selected.action === "visit") {
      onVisit({ status: selected.value, photo });
    } else {
      onSkip({ reason, photo });
    }
  };

  return (
    <div className="absolute inset-x-0 bottom-0 z-[1100] max-h-[75dvh] overflow-y-auto rounded-t-2xl border-t bg-white p-4 pb-[max(1rem,env(safe-area-inset-bottom))] shadow-lg">
      <p className="text-base font-bold text-slate-900">Registrar árbol</p>
      <p className="mt-0.5 text-sm text-muted-foreground">
        La foto se toma con la cámara en el momento del registro.
      </p>
      <p className="mb-1 mt-4 text-sm font-medium text-slate-700">
        Estado del árbol
      </p>
      <div className="grid grid-cols-2 gap-2">
        {REGISTER_OPTIONS.map((option) => (
          <Button
            key={option.value}
            type="button"
            variant={selectedValue === option.value ? "default" : "outline"}
            aria-pressed={selectedValue === option.value}
            className="h-12"
            onClick={() => setSelectedValue(option.value)}
          >
            {option.label}
          </Button>
        ))}
      </div>
      {selected?.value === "other" && (
        <Input
          autoFocus
          value={otherText}
          onChange={(event) => setOtherText(event.target.value)}
          placeholder="Describe el motivo"
          className="mt-3"
        />
      )}
      <PhotoCaptureField
        photo={photo}
        onChange={setPhoto}
        optional={!selected?.photoRequired}
      />
      <div className="mt-4 flex gap-2">
        <Button
          type="button"
          variant="ghost"
          className="h-12 flex-1"
          onClick={onCancel}
        >
          Cancelar
        </Button>
        <Button
          type="button"
          className="h-12 flex-[2] text-base font-bold"
          disabled={!canConfirm}
          onClick={handleConfirm}
        >
          Confirmar registro
        </Button>
      </div>
      {missingPhoto && (
        <p className="mt-2 text-center text-xs text-muted-foreground">
          Toma la foto para poder confirmar
        </p>
      )}
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
  const [registerSheetOpen, setRegisterSheetOpen] = useState(false);

  useEffect(() => {
    setRegisterSheetOpen(false);
  }, [stop?.id]);

  if (!stop) return null;

  const skipped = stop.status === "skipped";
  const resolved = stop.visited || skipped;
  const isSaving = isVisiting || isSkipping;

  const handleConfirmVisit = (payload) => {
    onVisit?.(stop.id, payload);
    setRegisterSheetOpen(false);
  };

  const handleConfirmSkip = (payload) => {
    onSkip?.(stop.id, payload);
    setRegisterSheetOpen(false);
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
          <Button
            type="button"
            size="lg"
            onClick={() => setRegisterSheetOpen(true)}
            disabled={isSaving || locked}
            className={cn(
              "h-auto min-h-14 w-full whitespace-normal px-3 text-base font-bold leading-tight",
              !inRange && "bg-amber-600 hover:bg-amber-600/90",
            )}
          >
            {inRange ? "Registrar" : "Registrar de todos modos"}
          </Button>
        )}
      </div>

      {registerSheetOpen && (
        <RegisterSheet
          onCancel={() => setRegisterSheetOpen(false)}
          onVisit={handleConfirmVisit}
          onSkip={handleConfirmSkip}
          isSaving={isSaving}
        />
      )}
    </div>
  );
}
