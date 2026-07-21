import { useIsMutating } from "@tanstack/react-query";
import {
  Check,
  CloudCheck,
  CloudOff,
  LoaderCircle,
  SkipForward,
} from "lucide-react";
import { useOnlineStatus } from "../../hooks/useOnlineStatus.js";

function SyncConfirmation() {
  const online = useOnlineStatus();
  const pendingMutations = useIsMutating();

  if (!online) {
    return (
      <p
        role="status"
        className="flex items-center justify-center gap-2 rounded-lg bg-red-50 px-4 py-3 text-sm font-semibold text-red-700"
      >
        <CloudOff className="h-4 w-4 shrink-0" aria-hidden="true" />
        Sin conexión: los datos se sincronizarán al recuperar señal.
      </p>
    );
  }
  if (pendingMutations > 0) {
    return (
      <p
        role="status"
        className="flex items-center justify-center gap-2 rounded-lg bg-amber-50 px-4 py-3 text-sm font-semibold text-amber-800"
      >
        <LoaderCircle
          className="h-4 w-4 shrink-0 animate-spin"
          aria-hidden="true"
        />
        Sincronizando los últimos registros…
      </p>
    );
  }
  return (
    <p
      role="status"
      className="flex items-center justify-center gap-2 rounded-lg bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-700"
    >
      <CloudCheck className="h-4 w-4 shrink-0" aria-hidden="true" />
      Todos los registros están sincronizados.
    </p>
  );
}

export default function RouteCompletionScreen({ stops }) {
  const visitedCount = stops.filter((stop) => stop.status === "visited").length;
  const skippedCount = stops.filter((stop) => stop.status === "skipped").length;

  return (
    <section
      aria-label="Ruta completada"
      className="flex flex-1 flex-col items-center justify-center gap-6 overflow-y-auto px-6 py-8 text-center"
    >
      <span className="flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
        <Check className="h-8 w-8 text-primary" aria-hidden="true" />
      </span>

      <div className="space-y-1">
        <h2 className="text-2xl font-extrabold tracking-tight text-slate-900">
          ¡Ruta completada!
        </h2>
        <p className="text-muted-foreground">
          Terminaste todos los árboles de esta ruta.
        </p>
      </div>

      <dl className="flex w-full max-w-xs justify-center gap-3">
        <div className="flex-1 rounded-xl border bg-white px-4 py-3 shadow-sm">
          <dt className="flex items-center justify-center gap-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
            <Check className="h-3.5 w-3.5" aria-hidden="true" />
            Visitados
          </dt>
          <dd className="text-2xl font-extrabold tabular-nums text-slate-900">
            {visitedCount}
          </dd>
        </div>
        <div className="flex-1 rounded-xl border bg-white px-4 py-3 shadow-sm">
          <dt className="flex items-center justify-center gap-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
            <SkipForward className="h-3.5 w-3.5" aria-hidden="true" />
            Omitidos
          </dt>
          <dd className="text-2xl font-extrabold tabular-nums text-slate-900">
            {skippedCount}
          </dd>
        </div>
      </dl>

      <SyncConfirmation />
    </section>
  );
}
