import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const formatDuration = (seconds) => {
  const total = Math.round(seconds ?? 0);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  return hours > 0 ? `${hours} h ${minutes} min` : `${minutes} min`;
};

export default function RouteListPanel({ routes, selectedRoute, onSelectRoute }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Rutas</CardTitle>
      </CardHeader>
      <CardContent className="space-y-1">
        {routes.map((route) => {
          const active = selectedRoute === route.routeNumber;
          return (
            <button
              key={route.routeNumber}
              type="button"
              onMouseEnter={() => onSelectRoute(route.routeNumber)}
              onMouseLeave={() => onSelectRoute(null)}
              onClick={() => onSelectRoute(active ? null : route.routeNumber)}
              className={cn(
                "flex w-full items-center gap-3 rounded-md px-2 py-2 text-left text-sm",
                active ? "bg-muted" : "hover:bg-muted/50",
              )}
            >
              <span
                className="h-3 w-3 shrink-0 rounded-full"
                style={{ backgroundColor: route.color }}
              />
              <span className="font-medium">Ruta {route.routeNumber}</span>
              <span className="ml-auto text-muted-foreground">
                {route.totalTrees} árboles · {formatDuration(route.travelTimeSec)}
              </span>
            </button>
          );
        })}
      </CardContent>
    </Card>
  );
}
