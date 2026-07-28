import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown } from "lucide-react";

import { fetchTreeObservations } from "@/api/datasets.js";
import { Badge } from "@/components/ui/badge";
import TreeHistoryPopup from "@/components/map/TreeHistoryPopup.jsx";
import {
  STATUS_LABELS,
  STATUS_STYLES,
  dateFormatter,
} from "@/lib/observations";
import { cn } from "@/lib/utils";

export default function PreviousCensusCard({ treeId }) {
  const [expanded, setExpanded] = useState(false);
  const { data } = useQuery({
    queryKey: ["tree-observations", treeId],
    queryFn: () => fetchTreeObservations(treeId),
  });

  const latest = data?.[0];
  if (!latest) return null;

  const photoSrc = latest.photo || latest.photo_url;
  const observedAt = new Date(latest.observed_at);
  const formattedDate = dateFormatter.format(observedAt);
  const statusLabel = STATUS_LABELS[latest.status] ?? latest.status;

  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-2">
      <div className="flex items-center gap-3">
        {photoSrc && (
          <a
            href={photoSrc}
            target="_blank"
            rel="noreferrer"
            className="shrink-0"
            title="Ver foto completa"
          >
            <img
              src={photoSrc}
              alt={`Foto del censo anterior · ${statusLabel} · ${formattedDate}`}
              className="h-16 w-16 rounded border object-cover"
            />
          </a>
        )}
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold text-slate-500">Censo anterior</p>
          <p className="text-sm font-bold text-slate-900">{formattedDate}</p>
          <Badge
            variant="outline"
            className={cn(
              "mt-0.5 px-1.5 py-0 text-[11px]",
              STATUS_STYLES[latest.status],
            )}
          >
            {statusLabel}
          </Badge>
        </div>
        <button
          type="button"
          onClick={() => setExpanded((value) => !value)}
          aria-expanded={expanded}
          className="flex shrink-0 items-center gap-1 rounded-full px-2 py-1.5 text-xs font-bold text-slate-600"
        >
          Historial
          <ChevronDown
            className={cn(
              "h-4 w-4 transition-transform",
              expanded && "rotate-180",
            )}
            aria-hidden="true"
          />
        </button>
      </div>

      {expanded && (
        <div className="mt-2 border-t pt-2">
          <TreeHistoryPopup treeId={treeId} className="w-full" />
        </div>
      )}
    </div>
  );
}
