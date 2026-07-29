import { useMemo, useState } from "react";
import { useMutation, useQueries, useQuery } from "@tanstack/react-query";

import { fetchSolution } from "@/api/optimization.js";
import { fetchRoutes, suggestAssignment } from "@/api/routes.js";
import { fetchSurveyors } from "@/api/surveyors.js";
import { useAssignRoute } from "@/hooks/useAssignRoute";
import { useSurveyorWorkload } from "@/hooks/useSurveyorWorkload";
import {
  formatDuration,
  formatDurationSplit,
  totalDurationSec,
} from "@/lib/optimization.js";
import { getErrorMessage } from "@/lib/errors";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
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

function formatUtil(value) {
  return `${value.toFixed(2)}×`;
}

function WorkloadTable({ workload, surveyors }) {
  const surveyorById = useMemo(
    () => Object.fromEntries(surveyors.map((s) => [s.id, s])),
    [surveyors],
  );

  if (!workload.length) return null;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-muted-foreground">
            <th className="py-1 text-left font-medium">Censista</th>
            <th className="py-1 text-right font-medium">Censos</th>
            <th className="py-1 text-right font-medium">Util. acum.</th>
            <th className="py-1 text-right font-medium">Saldo</th>
          </tr>
        </thead>
        <tbody>
          {workload.map((entry) => {
            const surveyor = surveyorById[entry.surveyor_id];
            const label = surveyor ? surveyorLabel(surveyor) : entry.username;
            const deficit = entry.cumulative_deficit;
            return (
              <tr key={entry.surveyor_id} className="border-b last:border-0">
                <td className="py-1">{label}</td>
                <td className="py-1 text-right text-muted-foreground">
                  {entry.census_count}
                </td>
                <td className="py-1 text-right text-muted-foreground">
                  {formatUtil(entry.total_utilization)}
                </td>
                <td
                  className={`py-1 text-right ${
                    deficit > 0.001
                      ? "text-green-600 dark:text-green-400"
                      : deficit < -0.001
                        ? "text-red-600 dark:text-red-400"
                        : "text-muted-foreground"
                  }`}
                >
                  {deficit > 0 ? "+" : ""}
                  {formatUtil(deficit)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="mt-2 text-xs text-muted-foreground">
        Utilización calculada sobre tiempos estimados por el solver. Una ruta
        abandonada cuenta como carga completa.
      </p>
    </div>
  );
}

export default function RouteAssignmentPanel({ datasetSolutionIds = [] }) {
  const [selectedParticipants, setSelectedParticipants] = useState(new Set());
  const [pending, setPending] = useState(null);

  const solutionResults = useQueries({
    queries: datasetSolutionIds.map((id) => ({
      queryKey: ["solution-metrics", id],
      queryFn: () => fetchSolution(id),
      enabled: !!id,
      staleTime: Infinity,
    })),
  });

  const publishedSolution = solutionResults
    .map((result) => result.data)
    .find((solution) => solution?.published_at);
  const solutionId = publishedSolution?.id ?? null;

  const {
    data: routes = [],
    isLoading: routesLoading,
    error: routesError,
  } = useQuery({
    queryKey: ["routes", solutionId],
    queryFn: () => fetchRoutes(solutionId),
    enabled: !!solutionId,
  });

  const { data: surveyors = [] } = useQuery({
    queryKey: ["surveyors"],
    queryFn: fetchSurveyors,
    enabled: !!solutionId,
  });

  const { data: workload = [] } = useSurveyorWorkload({ enabled: !!solutionId });

  const assign = useAssignRoute();

  const suggestMutation = useMutation({
    mutationFn: () =>
      suggestAssignment(solutionId, [...selectedParticipants]),
    onSuccess: (data) => {
      const map = new Map(
        data.assignments.map((a) => [a.route_id, a.surveyor_id]),
      );
      setPending(map);
    },
  });

  const published = !!solutionId;

  const workloadBySurveyor = useMemo(
    () => Object.fromEntries(workload.map((e) => [e.surveyor_id, e])),
    [workload],
  );

  function handleParticipantToggle(surveyorId) {
    setSelectedParticipants((prev) => {
      const next = new Set(prev);
      if (next.has(surveyorId)) {
        next.delete(surveyorId);
      } else {
        next.add(surveyorId);
      }
      return next;
    });
  }

  function selectValue(route) {
    if (pending && pending.has(route.id)) {
      return pending.get(route.id) ?? UNASSIGNED;
    }
    return route.surveyor ?? UNASSIGNED;
  }

  function handleSelectChange(routeId, nextValue) {
    const surveyorId = nextValue === UNASSIGNED ? null : nextValue;
    if (pending) {
      setPending((prev) => new Map(prev).set(routeId, surveyorId));
    } else {
      assign.mutate({ routeId, surveyorId });
    }
  }

  function handleConfirm() {
    if (!pending) return;
    for (const [routeId, surveyorId] of pending) {
      assign.mutate({ routeId, surveyorId });
    }
    setPending(null);
  }

  function handleDiscard() {
    setPending(null);
  }

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-lg font-semibold">Asignación de rutas</h2>

      {!published && (
        <p className="text-sm text-muted-foreground">
          Publica una solución para asignar censadores a las rutas.
        </p>
      )}

      {routesError && (
        <Alert variant="destructive">
          <AlertDescription>
            {getErrorMessage(routesError, "No se pudieron cargar las rutas.")}
          </AlertDescription>
        </Alert>
      )}

      {published && workload.length > 0 && (
        <div className="rounded-md border p-3">
          <h3 className="mb-2 text-sm font-medium">Carga histórica</h3>
          <WorkloadTable workload={workload} surveyors={surveyors} />
        </div>
      )}

      {published && (
        <div className="rounded-md border p-3">
          <h3 className="mb-2 text-sm font-medium">
            Participantes en este censo
          </h3>
          <div className="flex flex-col gap-1">
            {surveyors.map((surveyor) => {
              const wl = workloadBySurveyor[surveyor.id];
              return (
                <label
                  key={surveyor.id}
                  className="flex cursor-pointer items-center gap-2 text-sm"
                >
                  <input
                    type="checkbox"
                    aria-label={surveyorLabel(surveyor)}
                    checked={selectedParticipants.has(surveyor.id)}
                    onChange={() => handleParticipantToggle(surveyor.id)}
                    className="h-4 w-4"
                  />
                  {surveyorLabel(surveyor)}
                  {wl && (
                    <span className="text-xs text-muted-foreground">
                      saldo {wl.cumulative_deficit > 0 ? "+" : ""}
                      {formatUtil(wl.cumulative_deficit)}
                    </span>
                  )}
                </label>
              );
            })}
          </div>

          <div className="mt-3 flex flex-wrap gap-2">
            <Button
              size="sm"
              disabled={
                selectedParticipants.size === 0 || suggestMutation.isPending
              }
              onClick={() => suggestMutation.mutate()}
            >
              Sugerir asignación
            </Button>
            {pending && (
              <>
                <Button size="sm" onClick={handleConfirm}>
                  Confirmar
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleDiscard}
                >
                  Descartar
                </Button>
              </>
            )}
          </div>

          {suggestMutation.isError && (
            <Alert variant="destructive" className="mt-2">
              <AlertDescription>
                {getErrorMessage(
                  suggestMutation.error,
                  "No se pudo generar la propuesta.",
                )}
              </AlertDescription>
            </Alert>
          )}
        </div>
      )}

      {routesLoading && (
        <p className="text-sm text-muted-foreground">Cargando rutas…</p>
      )}

      {routes.map((route) => {
        const total = route.total_trees;
        const resolved = route.visited_count + route.skipped_count;
        const progress = total ? (resolved / total) * 100 : 0;
        return (
          <div key={route.id} className="rounded-md border p-3">
            <div className="flex items-center justify-between">
              <span className="font-medium">Ruta {route.route_number}</span>
              <span className="text-xs text-muted-foreground">
                {route.total_trees} árboles ·{" "}
                {formatDuration(
                  totalDurationSec(
                    route.travel_time_sec,
                    route.total_service_time_sec,
                  ),
                )}
              </span>
            </div>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {formatDurationSplit(
                route.travel_time_sec,
                route.total_service_time_sec,
              )}
            </p>

            <Select
              value={selectValue(route)}
              disabled={!published}
              onValueChange={(next) => handleSelectChange(route.id, next)}
            >
              <SelectTrigger
                className="mt-2"
                aria-label={`Censador ruta ${route.route_number}`}
              >
                <SelectValue placeholder="Sin asignar" />
              </SelectTrigger>
              <SelectContent className="z-[1100]">
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
                <span>
                  {route.skipped_count > 0 && (
                    <span className="mr-2">{route.skipped_count} omitidos</span>
                  )}
                  {route.pending_count} pendientes
                </span>
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
