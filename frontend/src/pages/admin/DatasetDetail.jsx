import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { fetchDataset, fetchDatasetTrees } from "@/api/datasets.js";
import { useOptimizationJobs } from "@/hooks/useOptimizationJobs";
import { getErrorMessage } from "@/lib/errors";
import DatasetMap from "@/components/map/DatasetMap.jsx";
import StrategyTabs from "@/components/map/StrategyTabs.jsx";
import OptimizationPanel from "@/components/optimization/OptimizationPanel.jsx";
import JobHistoryCard from "@/components/optimization/JobHistoryCard.jsx";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const STRATEGY_LABELS = [
  { key: "global", label: "Global" },
  { key: "spatial_term", label: "Término espacial" },
  { key: "cluster_first", label: "Cluster first" },
];

function toLeafletPositions(featureCollection) {
  const features = featureCollection?.features ?? [];
  return features.map((feature) => {
    // GeoJSON Point coordinates are [lon, lat]; Leaflet expects [lat, lon].
    const [lon, lat] = feature.geometry.coordinates;
    return {
      id: feature.id ?? feature.properties?.id,
      position: [lat, lon],
    };
  });
}

export default function DatasetDetail() {
  const { id } = useParams();
  const [strategy, setStrategy] = useState(null);
  const [panelOpen, setPanelOpen] = useState(false);

  const { data: dataset } = useQuery({
    queryKey: ["dataset", id],
    queryFn: () => fetchDataset(id),
  });

  const {
    data: trees,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["dataset-trees", id],
    queryFn: () => fetchDatasetTrees(id),
  });

  const markers = useMemo(() => toLeafletPositions(trees), [trees]);

  const { data: jobs = [] } = useOptimizationJobs(id);
  const latestJob = jobs[0];

  const strategies = useMemo(() => {
    if (latestJob?.status !== "completed") return [];
    const ids = latestJob.solution_ids ?? {};
    return STRATEGY_LABELS.filter((s) => ids[s.key]).map((s) => ({
      ...s,
      solutionId: ids[s.key],
    }));
  }, [latestJob]);

  const activeStrategy =
    strategies.find((s) => s.key === strategy)?.key ??
    strategies[0]?.key ??
    null;
  const solutionId =
    strategies.find((s) => s.key === activeStrategy)?.solutionId ?? null;

  return (
    <div className="flex h-[calc(100vh-6rem)] flex-col gap-4">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" asChild>
          <Link to="/admin/datasets">← Datasets</Link>
        </Button>
        <h1 className="text-2xl font-semibold">{dataset?.name ?? "Dataset"}</h1>
        <Button
          variant={panelOpen ? "secondary" : "outline"}
          size="sm"
          className="ml-auto"
          onClick={() => setPanelOpen((open) => !open)}
        >
          ⚙ Optimización
        </Button>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>
            {getErrorMessage(error, "No se pudieron cargar los árboles.")}
          </AlertDescription>
        </Alert>
      )}

      <div className="relative flex-1 overflow-hidden rounded-md border">
        {isLoading && (
          <div className="flex h-full items-center justify-center text-muted-foreground">
            Cargando árboles…
          </div>
        )}
        {trees && <DatasetMap markers={markers} solutionId={solutionId} />}

        <div className="absolute left-3 top-3 z-[1000]">
          {strategies.length > 0 ? (
            <StrategyTabs
              strategies={strategies}
              value={activeStrategy}
              onChange={setStrategy}
            />
          ) : (
            <span className="rounded-md border bg-background/90 px-3 py-1.5 text-sm text-muted-foreground shadow-md backdrop-blur">
              Optimiza el dataset para ver rutas
            </span>
          )}
        </div>

        <div
          className={cn(
            "absolute right-0 top-0 z-[1001] h-full w-full max-w-sm overflow-y-auto border-l bg-background p-4 shadow-xl transition-transform",
            panelOpen ? "translate-x-0" : "translate-x-full",
          )}
        >
          <div className="flex flex-col gap-4">
            <OptimizationPanel key={id} datasetId={id} />
            <JobHistoryCard datasetId={id} />
          </div>
        </div>
      </div>
    </div>
  );
}
