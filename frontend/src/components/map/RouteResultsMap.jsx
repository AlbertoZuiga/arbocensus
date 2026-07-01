import { Fragment, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Polyline, CircleMarker, Popup } from "react-leaflet";

import { fetchRoutesGeojson } from "@/api/routes.js";
import { getErrorMessage } from "@/lib/errors";
import BaseMap from "./BaseMap.jsx";
import RouteListPanel from "./RouteListPanel.jsx";
import { geojsonToRoutes } from "./routeGeojson.js";
import { Alert, AlertDescription } from "@/components/ui/alert";

export default function RouteResultsMap({ solutionId }) {
  const [selectedRoute, setSelectedRoute] = useState(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["routes-geojson", solutionId],
    queryFn: () => fetchRoutesGeojson(solutionId),
    enabled: !!solutionId,
  });

  const routes = useMemo(() => geojsonToRoutes(data), [data]);
  const bounds = useMemo(() => routes.flatMap((route) => route.positions), [
    routes,
  ]);

  if (isLoading)
    return <p className="text-muted-foreground">Cargando rutas…</p>;
  if (error)
    return (
      <Alert variant="destructive">
        <AlertDescription>
          {getErrorMessage(error, "No se pudieron cargar las rutas.")}
        </AlertDescription>
      </Alert>
    );
  if (routes.length === 0)
    return <p className="text-muted-foreground">La solución no tiene rutas.</p>;

  return (
    <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
      <div className="h-[520px] w-full overflow-hidden rounded-md border">
        <BaseMap bounds={bounds}>
          {routes.map((route) => {
            const active =
              selectedRoute === null || selectedRoute === route.routeNumber;
            return (
              <Fragment key={route.routeNumber}>
                <Polyline
                  positions={route.positions}
                  pathOptions={{
                    color: route.color,
                    weight: 4,
                    opacity: active ? 0.85 : 0.2,
                  }}
                />
                {route.positions.map((position, index) => (
                  <CircleMarker
                    key={index}
                    center={position}
                    radius={6}
                    pathOptions={{
                      color: "#fff",
                      weight: 2,
                      fillColor: route.color,
                      fillOpacity: active ? 0.9 : 0.2,
                    }}
                  >
                    <Popup>
                      Ruta {route.routeNumber} · Parada {index + 1}
                    </Popup>
                  </CircleMarker>
                ))}
              </Fragment>
            );
          })}
        </BaseMap>
      </div>
      <RouteListPanel
        routes={routes}
        selectedRoute={selectedRoute}
        onSelectRoute={setSelectedRoute}
      />
    </div>
  );
}
