import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { fetchDataset } from "@/api/datasets.js";
import {
  useCensusProgress,
  useCensusProgressStops,
  useRouteLines,
} from "@/hooks/useCensusProgress.js";
import { isCensusComplete, UNASSIGNED_KEY } from "@/lib/progress.js";
import { formatTimestamp } from "@/lib/optimization.js";
import { getErrorMessage } from "@/lib/errors";
import ProgressSummary from "@/components/progress/ProgressSummary.jsx";
import ProgressBreakdown from "@/components/progress/ProgressBreakdown.jsx";
import ProgressMap from "@/components/progress/ProgressMap.jsx";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

export default function CensusProgress() {
  const { id } = useParams();
  const [dimension, setDimension] = useState("routes");
  const [selectedKey, setSelectedKey] = useState(null);
  const [showRoutes, setShowRoutes] = useState(false);

  const { data: dataset } = useQuery({
    queryKey: ["dataset", id],
    queryFn: () => fetchDataset(id),
  });

  const { data: progress, isLoading, error } = useCensusProgress(id);
  const hasSolution = !!progress?.solution;
  const live = hasSolution && !isCensusComplete(progress);
  const { data: stops } = useCensusProgressStops(id, {
    enabled: hasSolution,
    live,
  });
  const { data: routeLines } = useRouteLines(progress?.solution?.id, showRoutes);

  const routeRows = useMemo(
    () =>
      (progress?.routes ?? []).map((route) => ({
        key: route.id,
        label: `Ruta ${route.route_number}`,
        sublabel: route.surveyor_name ?? "Sin asignar",
        totals: route,
      })),
    [progress],
  );

  const surveyorRows = useMemo(
    () =>
      (progress?.surveyors ?? []).map((surveyor) => ({
        key: surveyor.surveyor_id ?? UNASSIGNED_KEY,
        label: surveyor.surveyor_name,
        sublabel: `${surveyor.route_count} ${
          surveyor.route_count === 1 ? "ruta" : "rutas"
        }`,
        totals: surveyor,
      })),
    [progress],
  );

  const visibleRouteNumbers = useMemo(() => {
    if (!selectedKey) return null;
    const matches = (progress?.routes ?? []).filter((route) =>
      dimension === "routes"
        ? route.id === selectedKey
        : (route.surveyor_id ?? UNASSIGNED_KEY) === selectedKey,
    );
    return new Set(matches.map((route) => route.route_number));
  }, [progress, dimension, selectedKey]);

  const selectDimension = (next) => {
    setDimension(next);
    setSelectedKey(null);
  };

  return (
    <div className="flex flex-col gap-4 lg:h-[calc(100vh-6rem)]">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <Button variant="ghost" size="sm" asChild>
          <Link to={`/admin/datasets/${id}`}>
            ← {dataset?.name ?? "Dataset"}
          </Link>
        </Button>
        <h1 className="text-xl font-semibold sm:text-2xl">Avance del censo</h1>
        {progress?.solution && (
          <span className="w-full text-xs text-muted-foreground sm:ml-auto sm:w-auto sm:text-sm">
            Solución publicada el{" "}
            {formatTimestamp(progress.solution.published_at, "medium")}
          </span>
        )}
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>
            {getErrorMessage(error, "No se pudo cargar el avance del censo.")}
          </AlertDescription>
        </Alert>
      )}

      {isLoading && <p className="text-muted-foreground">Cargando avance…</p>}

      {progress && !progress.solution && (
        <Alert>
          <AlertDescription>
            Este dataset no tiene una solución publicada. Publica una solución
            para seguir el avance del censo.
          </AlertDescription>
        </Alert>
      )}

      {progress?.solution && (
        <>
          <ProgressSummary totals={progress.totals} />

          <div className="grid gap-4 lg:min-h-0 lg:flex-1 lg:grid-cols-[2fr_1fr]">
            <div className="h-[60vh] overflow-hidden rounded-md border lg:h-auto lg:min-h-[20rem]">
              <ProgressMap
                stops={stops}
                routeLines={routeLines}
                visibleRouteNumbers={visibleRouteNumbers}
                showRoutes={showRoutes}
                onToggleRoutes={() => setShowRoutes((current) => !current)}
              />
            </div>

            <ProgressBreakdown
              dimension={dimension}
              onDimensionChange={selectDimension}
              rows={dimension === "routes" ? routeRows : surveyorRows}
              selectedKey={selectedKey}
              onSelect={setSelectedKey}
              emptyMessage={
                dimension === "routes"
                  ? "La solución publicada no tiene rutas."
                  : "Ninguna ruta tiene censista asignado."
              }
            />
          </div>
        </>
      )}
    </div>
  );
}
