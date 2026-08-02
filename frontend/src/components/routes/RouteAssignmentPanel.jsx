import { useMemo, useState } from "react";
import {
  useMutation,
  useQueries,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { fetchSolution } from "@/api/optimization.js";
import { fetchRoutes, setSolutionParticipants, suggestAssignment } from "@/api/routes.js";
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
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
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

function deficitClass(value) {
  if (value > 0.001) return "text-green-600 dark:text-green-400";
  if (value < -0.001) return "text-red-600 dark:text-red-400";
  return "text-muted-foreground";
}

function AssignmentModal({ open, onOpenChange, surveyors, solutionId, onApply }) {
  const [step, setStep] = useState(1);
  const [selected, setSelected] = useState(new Set());
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState("cumulative_deficit");
  const [sortDir, setSortDir] = useState("desc");
  const [suggestion, setSuggestion] = useState(null);

  const queryClient = useQueryClient();
  const { data: workload = [] } = useSurveyorWorkload({ enabled: open });

  const workloadById = useMemo(
    () => Object.fromEntries(workload.map((e) => [e.surveyor_id, e])),
    [workload],
  );

  function handleOpenChange(val) {
    if (!val) {
      setStep(1);
      setSelected(new Set());
      setSearch("");
      setSuggestion(null);
    }
    onOpenChange(val);
  }

  function toggleSelected(id) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleSort(key) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(key === "name" ? "asc" : "desc");
    }
  }

  const displayed = useMemo(() => {
    const filtered = surveyors.filter((s) => {
      if (s.is_active === false) return false;
      return surveyorLabel(s).toLowerCase().includes(search.toLowerCase());
    });
    return [...filtered].sort((a, b) => {
      const wa = workloadById[a.id];
      const wb = workloadById[b.id];
      let aVal, bVal;
      switch (sortKey) {
        case "name":
          aVal = surveyorLabel(a);
          bVal = surveyorLabel(b);
          break;
        case "census_count":
          aVal = wa?.census_count ?? 0;
          bVal = wb?.census_count ?? 0;
          break;
        case "total_utilization":
          aVal = wa?.total_utilization ?? 0;
          bVal = wb?.total_utilization ?? 0;
          break;
        default:
          aVal = wa?.cumulative_deficit ?? 0;
          bVal = wb?.cumulative_deficit ?? 0;
      }
      const order = sortDir === "asc" ? 1 : -1;
      return typeof aVal === "string"
        ? aVal.localeCompare(bVal) * order
        : (aVal - bVal) * order;
    });
  }, [surveyors, search, sortKey, sortDir, workloadById]);

  const suggestMutation = useMutation({
    mutationFn: () => suggestAssignment(solutionId, [...selected]),
    onSuccess: (data) => {
      setSuggestion(data);
      setStep(2);
    },
  });

  const participantsMutation = useMutation({
    mutationFn: () => setSolutionParticipants(solutionId, [...selected]),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["surveyor-workload"] }),
  });

  const previewBySurveyor = useMemo(() => {
    if (!suggestion) return [];
    const grouped = {};
    for (const a of suggestion.assignments) {
      if (!grouped[a.surveyor_id]) grouped[a.surveyor_id] = [];
      grouped[a.surveyor_id].push(a);
    }
    return Object.entries(grouped)
      .map(([sid, assignments]) => {
        const s = surveyors.find((u) => u.id === sid);
        return {
          surveyorId: sid,
          name: s ? surveyorLabel(s) : sid,
          assignments,
          balance: suggestion.balance[sid] ?? 0,
        };
      })
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [suggestion, surveyors]);

  function sortArrow(key) {
    if (sortKey !== key) return null;
    return sortDir === "asc" ? " ↑" : " ↓";
  }

  async function handleConfirm() {
    try {
      await participantsMutation.mutateAsync();
    } catch {
      return;
    }
    onApply(suggestion.assignments);
    handleOpenChange(false);
  }

  const COLUMNS = [
    ["Censista", "name", "text-left"],
    ["Censos", "census_count", "text-right"],
    ["Carga acum.", "total_utilization", "text-right"],
    ["Saldo", "cumulative_deficit", "text-right"],
  ];

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="flex max-h-[80vh] max-w-2xl flex-col">
        <DialogHeader>
          <DialogTitle>
            {step === 1
              ? "Seleccionar censistas"
              : "Previsualización de asignación"}
          </DialogTitle>
        </DialogHeader>

        {step === 1 && (
          <>
            <Input
              placeholder="Buscar censista…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="flex-shrink-0"
            />
            <div className="min-h-0 flex-1 overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-background">
                  <tr className="border-b text-muted-foreground">
                    <th className="w-8 py-1" />
                    {COLUMNS.map(([label, key, align]) => (
                      <th
                        key={key}
                        className={`cursor-pointer select-none py-1 font-medium ${align}`}
                        onClick={() => toggleSort(key)}
                      >
                        {label}
                        {sortArrow(key)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {displayed.map((surveyor) => {
                    const wl = workloadById[surveyor.id];
                    const deficit = wl?.cumulative_deficit ?? 0;
                    return (
                      <tr
                        key={surveyor.id}
                        className="cursor-pointer border-b last:border-0 hover:bg-muted/50"
                        onClick={() => toggleSelected(surveyor.id)}
                      >
                        <td className="py-1.5">
                          <input
                            type="checkbox"
                            aria-label={surveyorLabel(surveyor)}
                            checked={selected.has(surveyor.id)}
                            onChange={() => toggleSelected(surveyor.id)}
                            onClick={(e) => e.stopPropagation()}
                            className="h-4 w-4"
                          />
                        </td>
                        <td className="py-1.5">{surveyorLabel(surveyor)}</td>
                        <td className="py-1.5 text-right text-muted-foreground">
                          {wl?.census_count ?? "—"}
                        </td>
                        <td className="py-1.5 text-right text-muted-foreground">
                          {wl ? formatUtil(wl.total_utilization) : "—"}
                        </td>
                        <td
                          className={`py-1.5 text-right ${deficitClass(deficit)}`}
                        >
                          {wl
                            ? `${deficit > 0 ? "+" : ""}${formatUtil(deficit)}`
                            : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <p className="mt-2 text-xs text-muted-foreground">
                Carga acum. = sumatoria de (tiempo de ruta / T_máx) en todos los
                censos anteriores. Saldo positivo = le corresponde más trabajo
                que el promedio; negativo = ya tiene más. Una ruta abandonada
                cuenta como carga completa.
              </p>
            </div>

            {suggestMutation.isError && (
              <Alert variant="destructive" className="flex-shrink-0">
                <AlertDescription>
                  {getErrorMessage(
                    suggestMutation.error,
                    "No se pudo generar la propuesta.",
                  )}
                </AlertDescription>
              </Alert>
            )}

            <DialogFooter className="flex-shrink-0">
              <Button
                disabled={selected.size === 0 || suggestMutation.isPending}
                onClick={() => suggestMutation.mutate()}
              >
                {suggestMutation.isPending ? "Calculando…" : "Siguiente"}
              </Button>
            </DialogFooter>
          </>
        )}

        {step === 2 && suggestion && (
          <>
            <div className="min-h-0 flex-1 space-y-3 overflow-y-auto">
              {previewBySurveyor.map(({ surveyorId, name, assignments, balance }) => (
                <div key={surveyorId} className="rounded-md border p-3">
                  <div className="mb-1 flex items-center justify-between">
                    <span className="text-sm font-medium">{name}</span>
                    <span className={`text-xs ${deficitClass(balance)}`}>
                      Saldo resultante:{" "}
                      {balance > 0 ? "+" : ""}
                      {formatUtil(balance)}
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {assignments.map((a) => (
                      <span
                        key={a.route_id}
                        className="rounded bg-muted px-1.5 py-0.5 text-xs"
                      >
                        Ruta {a.route_number} ({formatUtil(a.utilization)})
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            {participantsMutation.isError && (
              <Alert variant="destructive" className="flex-shrink-0">
                <AlertDescription>
                  {getErrorMessage(
                    participantsMutation.error,
                    "No se pudo registrar a los censistas participantes.",
                  )}
                </AlertDescription>
              </Alert>
            )}

            <DialogFooter className="flex-shrink-0">
              <Button variant="outline" onClick={() => setStep(1)}>
                Volver
              </Button>
              <Button
                disabled={participantsMutation.isPending}
                onClick={handleConfirm}
              >
                Confirmar asignación
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default function RouteAssignmentPanel({ datasetSolutionIds = [] }) {
  const [modalOpen, setModalOpen] = useState(false);

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

  const assign = useAssignRoute();

  const published = !!solutionId;

  function handleSelectChange(routeId, nextValue) {
    const surveyorId = nextValue === UNASSIGNED ? null : nextValue;
    assign.mutate({ routeId, surveyorId });
  }

  function handleApply(assignments) {
    for (const a of assignments) {
      assign.mutate({ routeId: a.route_id, surveyorId: a.surveyor_id });
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-lg font-semibold">Asignación de rutas</h2>

      {!published && (
        <p className="text-sm text-muted-foreground">
          Publica una solución para asignar censistas a las rutas.
        </p>
      )}

      {routesError && (
        <Alert variant="destructive">
          <AlertDescription>
            {getErrorMessage(routesError, "No se pudieron cargar las rutas.")}
          </AlertDescription>
        </Alert>
      )}

      {published && (
        <Button
          className="self-start bg-green-600 text-white hover:bg-green-700"
          onClick={() => setModalOpen(true)}
        >
          Asignación automática
        </Button>
      )}

      <AssignmentModal
        open={modalOpen}
        onOpenChange={setModalOpen}
        surveyors={surveyors}
        solutionId={solutionId}
        onApply={handleApply}
      />

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
              value={route.surveyor ?? UNASSIGNED}
              disabled={!published}
              onValueChange={(next) => handleSelectChange(route.id, next)}
            >
              <SelectTrigger
                className="mt-2"
                aria-label={`Censista ruta ${route.route_number}`}
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
