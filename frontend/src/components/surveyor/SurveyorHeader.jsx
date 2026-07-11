import { useIsMutating } from "@tanstack/react-query";
import { CloudOff, LoaderCircle, MapPin, MapPinOff, TreePine } from "lucide-react";
import { cn } from "@/lib/utils";
import RouteSelector from "./RouteSelector.jsx";
import UserMenu from "../UserMenu.jsx";
import { useOnlineStatus } from "../../hooks/useOnlineStatus.js";

function SyncStatus() {
  const online = useOnlineStatus();
  const pendingMutations = useIsMutating();

  if (!online) {
    return (
      <span
        role="status"
        className="flex items-center gap-1 rounded-full bg-red-100 px-2 py-1 text-xs font-bold text-red-700"
      >
        <CloudOff className="h-3.5 w-3.5" aria-hidden="true" />
        Sin conexión
      </span>
    );
  }
  if (pendingMutations > 0) {
    return (
      <span
        role="status"
        className="flex items-center gap-1 rounded-full bg-amber-100 px-2 py-1 text-xs font-bold text-amber-800"
      >
        <LoaderCircle className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
        Guardando…
      </span>
    );
  }
  return null;
}

function GpsStatus({ position }) {
  return (
    <span
      role="status"
      aria-label={position ? "GPS activo" : "Buscando señal GPS"}
      className={cn(
        "flex items-center gap-1 rounded-full px-2 py-1 text-xs font-bold",
        position ? "bg-primary/10 text-primary" : "bg-slate-100 text-slate-500",
      )}
    >
      {position ? (
        <MapPin className="h-3.5 w-3.5" aria-hidden="true" />
      ) : (
        <MapPinOff className="h-3.5 w-3.5" aria-hidden="true" />
      )}
      GPS
    </span>
  );
}

export default function SurveyorHeader({
  routes,
  activeRouteId,
  activeIndex,
  onSelectRoute,
  stopsCount,
  resolvedCount,
  position,
}) {
  const progress = stopsCount > 0 ? (resolvedCount / stopsCount) * 100 : 0;

  return (
    <header className="pt-safe sticky top-0 z-[1000] border-b bg-white shadow-sm">
      <div className="flex items-center justify-between gap-2 px-4 pt-2">
        <div className="flex min-w-0 items-center gap-2">
          <TreePine className="h-5 w-5 shrink-0 text-primary" aria-hidden="true" />
          <span className="truncate text-base font-extrabold tracking-tight text-slate-900">
            Arbocensus
          </span>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          <SyncStatus />
          <GpsStatus position={position} />
          <UserMenu />
        </div>
      </div>

      <div className="flex items-center justify-between gap-3 px-4 pb-2 pt-1">
        {routes.length > 1 ? (
          <RouteSelector
            routes={routes}
            activeRouteId={activeRouteId}
            onSelect={onSelectRoute}
          />
        ) : (
          <h1 className="text-lg font-bold text-slate-900">
            Ruta {activeIndex + 1}
          </h1>
        )}
        <span className="shrink-0 text-sm font-bold tabular-nums text-slate-700">
          {resolvedCount}/{stopsCount} censados
        </span>
      </div>

      <div
        role="progressbar"
        aria-valuenow={resolvedCount}
        aria-valuemin={0}
        aria-valuemax={stopsCount}
        aria-label="Progreso del censo"
        className="h-1.5 w-full bg-slate-200"
      >
        <div
          className="h-full bg-primary transition-all"
          style={{ width: `${progress}%` }}
        />
      </div>
    </header>
  );
}
