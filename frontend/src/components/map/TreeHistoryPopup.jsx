import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { fetchTreeObservations } from "@/api/datasets.js";
import { Badge } from "@/components/ui/badge";
import { getErrorMessage } from "@/lib/errors";
import { cn } from "@/lib/utils";

const SOURCE_LABELS = {
  legacy_api: "API",
  legacy_app: "App",
  "": "Campo",
};

const STATUS_LABELS = {
  alive: "Vivo",
  removed: "Removido",
  not_found: "No encontrado",
  other: "Otro",
  unknown: "Desconocido",
};

const STATUS_STYLES = {
  alive: "border-green-600/30 bg-green-600/10 text-green-700",
  removed: "border-destructive/30 bg-destructive/10 text-destructive",
  not_found: "border-amber-600/30 bg-amber-600/10 text-amber-700",
  other: "border-muted-foreground/30 bg-muted text-muted-foreground",
  unknown: "border-muted-foreground/30 bg-muted text-muted-foreground",
};

const dateFormatter = new Intl.DateTimeFormat("es-CL", {
  day: "numeric",
  month: "short",
  year: "numeric",
});

const timeFormatter = new Intl.DateTimeFormat("es-CL", {
  hour: "2-digit",
  minute: "2-digit",
});

const relativeFormatter = new Intl.RelativeTimeFormat("es-CL", {
  numeric: "auto",
});

const RELATIVE_UNITS = [
  ["year", 365 * 24 * 3600],
  ["month", 30 * 24 * 3600],
  ["day", 24 * 3600],
  ["hour", 3600],
  ["minute", 60],
];

function formatRelative(date) {
  const seconds = (date.getTime() - Date.now()) / 1000;
  for (const [unit, unitSeconds] of RELATIVE_UNITS) {
    if (Math.abs(seconds) >= unitSeconds) {
      return relativeFormatter.format(Math.round(seconds / unitSeconds), unit);
    }
  }
  return relativeFormatter.format(0, "minute");
}

function ObservationEntry({ observation, isLatest, isLast }) {
  const [photoFailed, setPhotoFailed] = useState(false);
  const photoSrc = observation.photo || observation.photo_url;
  const observedAt = new Date(observation.observed_at);
  const statusLabel = STATUS_LABELS[observation.status] ?? observation.status;
  const sourceLabel = SOURCE_LABELS[observation.source] ?? observation.source;

  return (
    <li className="relative flex gap-2.5 pb-3 pl-4 last:pb-0">
      {!isLast && (
        <span
          className="absolute left-[3px] top-1.5 h-full w-px bg-border"
          aria-hidden="true"
        />
      )}
      <span
        className={cn(
          "absolute left-0 top-1.5 h-[7px] w-[7px] rounded-full ring-2 ring-background",
          isLatest ? "bg-primary" : "bg-muted-foreground/40",
        )}
        aria-hidden="true"
      />

      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex flex-wrap items-center gap-x-1.5 gap-y-0.5">
          <time
            dateTime={observation.observed_at}
            className="text-xs font-medium leading-none"
            title={`${dateFormatter.format(observedAt)} · ${timeFormatter.format(observedAt)}`}
          >
            {dateFormatter.format(observedAt)}
          </time>
          <span className="text-[10px] leading-none text-muted-foreground">
            {formatRelative(observedAt)}
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-1">
          <Badge
            variant="outline"
            className={cn(
              "px-1.5 py-0 text-[10px] font-medium",
              STATUS_STYLES[observation.status],
            )}
          >
            {statusLabel}
          </Badge>
          <Badge
            variant="outline"
            className="px-1.5 py-0 text-[10px] font-normal text-muted-foreground"
          >
            {sourceLabel}
          </Badge>
        </div>

        {observation.notes && (
          <p className="text-[11px] leading-snug text-muted-foreground">
            {observation.notes}
          </p>
        )}
        {observation.created_by_username && (
          <p className="text-[10px] leading-none text-muted-foreground">
            por {observation.created_by_username}
          </p>
        )}
      </div>

      {photoSrc && !photoFailed && (
        <a
          href={photoSrc}
          target="_blank"
          rel="noreferrer"
          className="shrink-0 rounded ring-offset-background transition hover:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          title="Ver foto completa"
        >
          <img
            src={photoSrc}
            alt={`Foto del árbol · ${statusLabel} · ${dateFormatter.format(observedAt)}`}
            loading="lazy"
            onError={() => setPhotoFailed(true)}
            className="h-14 w-14 rounded border object-cover"
          />
        </a>
      )}
    </li>
  );
}

function EntrySkeleton() {
  return (
    <li className="flex gap-2.5 pb-3 pl-4">
      <div className="flex-1 space-y-1.5">
        <div className="h-3 w-24 rounded bg-muted" />
        <div className="h-3.5 w-16 rounded bg-muted" />
      </div>
      <div className="h-14 w-14 shrink-0 rounded bg-muted" />
    </li>
  );
}

export default function TreeHistoryPopup({ treeId }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["tree-observations", treeId],
    queryFn: () => fetchTreeObservations(treeId),
  });

  return (
    <section className="w-60 space-y-2">
      <header className="flex items-baseline justify-between gap-2 border-b pb-1.5">
        <h3 className="text-sm font-semibold leading-none">Historial</h3>
        {data && data.length > 0 && (
          <span className="text-[11px] text-muted-foreground">
            {data.length} {data.length === 1 ? "observación" : "observaciones"}
          </span>
        )}
      </header>

      {isLoading && (
        <ul
          className="animate-pulse list-none"
          aria-busy="true"
          aria-label="Cargando historial"
        >
          <EntrySkeleton />
          <EntrySkeleton />
        </ul>
      )}

      {error && (
        <p className="text-xs text-destructive" role="alert">
          {getErrorMessage(error, "No se pudo cargar el historial.")}
        </p>
      )}

      {data && data.length === 0 && (
        <p className="text-xs text-muted-foreground">
          Este árbol aún no tiene observaciones registradas.
        </p>
      )}

      {data && data.length > 0 && (
        <ul className="-mr-2 max-h-64 list-none overflow-y-auto pr-2">
          {data.map((observation, index) => (
            <ObservationEntry
              key={observation.id}
              observation={observation}
              isLatest={index === 0}
              isLast={index === data.length - 1}
            />
          ))}
        </ul>
      )}
    </section>
  );
}
