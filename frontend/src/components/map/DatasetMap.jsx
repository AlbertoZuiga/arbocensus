import { Fragment, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CircleMarker, Polyline, Popup } from "react-leaflet";

import { fetchRoutesGeojson } from "@/api/routes.js";
import {
  formatDuration,
  formatDurationSplit,
  totalDurationSec,
} from "@/lib/optimization.js";
import { cn } from "@/lib/utils";
import BaseMap from "./BaseMap.jsx";
import { geojsonToRoutes } from "./routeGeojson.js";
import TreeHistoryPopup from "./TreeHistoryPopup.jsx";

export default function DatasetMap({ markers, solutionId }) {
  const [selectedRoute, setSelectedRoute] = useState(null);
  const [openTreeId, setOpenTreeId] = useState(null);

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
          markers.map((marker) => {
            const open = openTreeId === marker.id;
            return (
              <CircleMarker
                key={marker.id}
                center={marker.position}
                radius={open ? 7 : 5}
                pathOptions={{
                  className: "cursor-pointer",
                  color: open ? "#fff" : "#16a34a",
                  weight: open ? 2 : 1,
                  fillColor: "#16a34a",
                  fillOpacity: open ? 1 : 0.7,
                }}
                eventHandlers={{
                  popupopen: () => setOpenTreeId(marker.id),
                  popupclose: () =>
                    setOpenTreeId((id) => (id === marker.id ? null : id)),
                }}
              >
                <Popup minWidth={248} maxWidth={280} keepInView>
                  {open && <TreeHistoryPopup treeId={marker.id} />}
                </Popup>
              </CircleMarker>
            );
          })}

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
                  "w-full rounded-md px-2 py-1.5 text-left text-sm",
                  active ? "bg-muted" : "hover:bg-muted/50",
                )}
              >
                <span className="flex items-center gap-2">
                  <span
                    className="h-3 w-3 shrink-0 rounded-full"
                    style={{ backgroundColor: route.color }}
                  />
                  <span className="font-medium">Ruta {route.routeNumber}</span>
                  <span className="ml-auto text-xs text-muted-foreground">
                    {route.totalTrees} ·{" "}
                    {formatDuration(
                      totalDurationSec(
                        route.travelTimeSec,
                        route.totalServiceTimeSec,
                      ),
                    )}
                  </span>
                </span>
                {active && (
                  <span className="mt-0.5 block pl-5 text-xs text-muted-foreground">
                    {formatDurationSplit(
                      route.travelTimeSec,
                      route.totalServiceTimeSec,
                    )}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
