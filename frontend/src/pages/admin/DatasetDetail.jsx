import { useMemo } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { CircleMarker } from "react-leaflet";
import { fetchDataset, fetchDatasetTrees } from "@/api/datasets.js";
import BaseMap from "@/components/map/BaseMap.jsx";
import OptimizationPanel from "@/components/optimization/OptimizationPanel.jsx";
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
                  No se pudieron cargar los árboles: {error.message}
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

        <OptimizationPanel datasetId={id} />
      </div>
    </div>
  );
}
