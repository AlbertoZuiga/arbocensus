import { Fragment, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CircleMarker, Polyline, Popup } from "react-leaflet";

import { fetchRoutesGeojson } from "@/api/routes.js";
import { formatDurationBreakdown } from "@/lib/optimization.js";
import { cn } from "@/lib/utils";
import BaseMap from "./BaseMap.jsx";
import { geojsonToRoutes } from "./routeGeojson.js";

export default function DatasetMap({ markers, solutionId }) {
  const [selectedRoute, setSelectedRoute] = useState(null);

  const { data } = useQuery({
    queryKey: ["routes-geojson", solutionId],
    queryFn: () => fetchRoutesGeojson(solutionId),
    enabled: !!solutionId,
    staleTime: Infinity,
  });

  const routes = useMemo(() => geojsonToRoutes(data), [data]);
  const hasRoutes = routes.length > 0;

  const bounds = useMemo(() => {
    if (hasRoutes) return routes.flatMap((route) => route.positions);
    return markers.map((m) => m.position);
  }, [hasRoutes, routes, markers]);

  return (
    <div className="relative h-full w-full">
      <BaseMap bounds={bounds}>
        {!hasRoutes &&
          markers.map((marker) => (
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
                  opacity: active ? 0.85 : 0.15,
                }}
              />
              {route.stops.map((position, index) => (
                <CircleMarker
                  key={index}
                  center={position}
                  radius={6}
                  pathOptions={{
                    color: "#fff",
                    weight: 2,
                    fillColor: route.color,
                    fillOpacity: active ? 0.9 : 0.15,
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

      {hasRoutes && (
        <div className="absolute bottom-3 left-3 z-[1000] max-h-[45%] w-56 overflow-y-auto rounded-lg border bg-background/90 p-2 shadow-md backdrop-blur">
          {routes.map((route) => {
            const active = selectedRoute === route.routeNumber;
            return (
              <button
                key={route.routeNumber}
                type="button"
                onMouseEnter={() => setSelectedRoute(route.routeNumber)}
                onMouseLeave={() => setSelectedRoute(null)}
                onClick={() =>
                  setSelectedRoute(active ? null : route.routeNumber)
                }
                className={cn(
                  "flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm",
                  active ? "bg-muted" : "hover:bg-muted/50",
                )}
              >
                <span
                  className="h-3 w-3 shrink-0 rounded-full"
                  style={{ backgroundColor: route.color }}
                />
                <span className="font-medium">Ruta {route.routeNumber}</span>
                <span className="ml-auto text-xs text-muted-foreground">
                  {route.totalTrees} ·{" "}
                  {formatDurationBreakdown(
                    route.travelTimeSec,
                    route.totalServiceTimeSec,
                  )}
                </span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
