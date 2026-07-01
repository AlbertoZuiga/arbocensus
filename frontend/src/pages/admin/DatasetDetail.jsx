import { useMemo } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { CircleMarker } from "react-leaflet";
import { fetchDataset, fetchDatasetTrees } from "@/api/datasets.js";
import { fetchLatestJob } from "@/api/optimization";
import { getErrorMessage } from "@/lib/errors";
import BaseMap from "@/components/map/BaseMap.jsx";
import RouteResultsMap from "@/components/map/RouteResultsMap.jsx";
import OptimizationPanel from "@/components/optimization/OptimizationPanel.jsx";
import JobHistoryCard from "@/components/optimization/JobHistoryCard.jsx";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

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
  const bounds = useMemo(() => markers.map((m) => m.position), [markers]);

  const { data: latestJob } = useQuery({
    queryKey: ["optimization-latest-job", id],
    queryFn: () => fetchLatestJob(id),
  });

  const solutionId = useMemo(() => {
    if (latestJob?.status !== "completed") return null;
    const ids = latestJob.solution_ids ?? {};
    return ids.global ?? Object.values(ids)[0] ?? null;
  }, [latestJob]);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" asChild>
          <Link to="/admin/datasets">← Datasets</Link>
        </Button>
        <h1 className="text-2xl font-semibold">
          {dataset?.name ?? "Dataset"}
        </h1>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Árboles</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading && (
              <p className="text-muted-foreground">Cargando árboles…</p>
            )}
            {error && (
              <Alert variant="destructive">
                <AlertDescription>
                  {getErrorMessage(error, "No se pudieron cargar los árboles.")}
                </AlertDescription>
              </Alert>
            )}
            {trees && (
              <div className="h-[520px] w-full overflow-hidden rounded-md border">
                <BaseMap bounds={bounds}>
                  {markers.map((marker) => (
                    <CircleMarker
                      key={marker.id}
                      center={marker.position}
                      radius={5}
                      pathOptions={{
                        color: "#16a34a",
                        fillColor: "#16a34a",
                        fillOpacity: 0.7,
                      }}
                    />
                  ))}
                </BaseMap>
              </div>
            )}
          </CardContent>
        </Card>

        <OptimizationPanel key={id} datasetId={id} />
      </div>

      <JobHistoryCard datasetId={id} />

      {solutionId && (
        <Card>
          <CardHeader>
            <CardTitle>Rutas optimizadas</CardTitle>
          </CardHeader>
          <CardContent>
            <RouteResultsMap solutionId={solutionId} />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
