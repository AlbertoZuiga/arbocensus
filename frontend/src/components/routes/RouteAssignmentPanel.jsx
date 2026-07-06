import { useQuery } from "@tanstack/react-query";

import { fetchSolution } from "@/api/optimization.js";
import { fetchRoutes } from "@/api/routes.js";
import { fetchSurveyors } from "@/api/surveyors.js";
import { useAssignRoute } from "@/hooks/useAssignRoute";
import { formatDuration } from "@/lib/optimization.js";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const UNASSIGNED = "none";

function surveyorLabel(surveyor) {
  const name = [surveyor.first_name, surveyor.last_name]
    .filter(Boolean)
    .join(" ")
    .trim();
  return name || surveyor.username;
}

export default function RouteAssignmentPanel({ solutionId }) {
  const { data: solution } = useQuery({
    queryKey: ["solution-metrics", solutionId],
    queryFn: () => fetchSolution(solutionId),
    enabled: !!solutionId,
    staleTime: Infinity,
  });

  const { data: routes = [] } = useQuery({
    queryKey: ["routes", solutionId],
    queryFn: () => fetchRoutes(solutionId),
    enabled: !!solutionId,
  });

  const { data: surveyors = [] } = useQuery({
    queryKey: ["surveyors"],
    queryFn: fetchSurveyors,
    enabled: !!solutionId,
  });

  const assign = useAssignRoute();

  if (!solutionId) return null;

  const published = !!solution?.published_at;

  return (
    <div className="flex flex-col gap-3">
      <h2 className="text-lg font-semibold">Asignación de rutas</h2>
      {!published && (
        <p className="text-sm text-muted-foreground">
          Publica esta solución para asignar censadores a las rutas.
        </p>
      )}

      {routes.map((route) => {
        const total = route.visited_count + route.pending_count;
        const progress = total ? (route.visited_count / total) * 100 : 0;
        return (
          <div key={route.id} className="rounded-md border p-3">
            <div className="flex items-center justify-between">
              <span className="font-medium">Ruta {route.route_number}</span>
              <span className="text-xs text-muted-foreground">
                {route.total_trees} árboles ·{" "}
                {formatDuration(route.travel_time_sec)}
              </span>
            </div>

            <Select
              value={route.surveyor ?? UNASSIGNED}
              disabled={!published}
              onValueChange={(next) =>
                assign.mutate({
                  routeId: route.id,
                  surveyorId: next === UNASSIGNED ? null : next,
                })
              }
            >
              <SelectTrigger
                className="mt-2"
                aria-label={`Censador ruta ${route.route_number}`}
              >
                <SelectValue placeholder="Sin asignar" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={UNASSIGNED}>Sin asignar</SelectItem>
                {surveyors.map((surveyor) => (
                  <SelectItem key={surveyor.id} value={surveyor.id}>
                    {surveyorLabel(surveyor)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <div className="mt-2">
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>
                  {route.visited_count}/{total} visitados
                </span>
                <span>{route.pending_count} pendientes</span>
              </div>
              <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-primary"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
