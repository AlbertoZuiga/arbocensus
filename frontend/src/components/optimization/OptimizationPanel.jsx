import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { fetchJobs, fetchSolution } from "@/api/optimization";
import { getErrorMessage } from "@/lib/errors";
import { useOptimizationJob } from "@/hooks/useOptimizationJob";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import JobHistoryList from "./JobHistoryList";
import JobStatusBadge from "./JobStatusBadge";
import RoutingConfigForm from "./RoutingConfigForm";

const ACTIVE_STATUSES = ["queued", "running"];

const STRATEGY_LABELS = {
  global: "Global",
  spatial_term: "Término espacial",
  cluster_first: "Clustering primero",
};

const formatDuration = (seconds) => {
  const total = Math.round(seconds);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  return hours > 0 ? `${hours} h ${minutes} min` : `${minutes} min`;
};

function SolutionSummary({ solutionId }) {
  const {
    data: solution,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["optimization-solution", solutionId],
    queryFn: () => fetchSolution(solutionId),
    enabled: !!solutionId,
  });

  if (isLoading)
    return <p className="text-muted-foreground">Cargando solución…</p>;
  if (error)
    return (
      <Alert variant="destructive">
        <AlertDescription>
          {getErrorMessage(error, "No se pudo cargar la solución.")}
        </AlertDescription>
      </Alert>
    );
  if (!solution) return null;

  return (
    <dl className="grid grid-cols-2 gap-2 text-sm">
      <dt className="text-muted-foreground">Rutas</dt>
      <dd className="text-right font-medium">{solution.total_routes}</dd>
      <dt className="text-muted-foreground">Tiempo total de viaje</dt>
      <dd className="text-right font-medium">
        {formatDuration(solution.total_travel_time_sec)}
      </dd>
      <dt className="text-muted-foreground">Balance de carga</dt>
      <dd className="text-right font-medium">
        {solution.balance_score.toFixed(2)}
      </dd>
      <dt className="text-muted-foreground">Radio máx. (suma)</dt>
      <dd className="text-right font-medium">{solution.sum_max_radius_m} m</dd>
      <dt className="text-muted-foreground">Solapamiento por ruta</dt>
      <dd className="text-right font-medium">
        {solution.interleave_per_route.toFixed(2)}
      </dd>
      <dt className="text-muted-foreground">IoU peor par</dt>
      <dd className="text-right font-medium">
        {solution.worst_pair_iou.toFixed(2)}
      </dd>
    </dl>
  );
}

export default function OptimizationPanel({ datasetId }) {
  const queryClient = useQueryClient();
  const [selectedJobId, setSelectedJobId] = useState(null);

  const { data: jobs = [] } = useQuery({
    queryKey: ["optimization-jobs", datasetId],
    queryFn: () => fetchJobs(datasetId),
    enabled: !!datasetId,
    refetchInterval: (query) =>
      (query.state.data ?? []).some((j) => ACTIVE_STATUSES.includes(j.status))
        ? 3000
        : false,
  });

  const jobId = selectedJobId ?? jobs[0]?.id ?? null;
  const { data: job } = useOptimizationJob(jobId);

  const handleJobCreated = (created) => {
    setSelectedJobId(created.id);
    queryClient.invalidateQueries({
      queryKey: ["optimization-jobs", datasetId],
    });
  };

  return (
    <div className="flex flex-col gap-4">
      <RoutingConfigForm datasetId={datasetId} onJobCreated={handleJobCreated} />

      {jobs.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Historial de trabajos</CardTitle>
          </CardHeader>
          <CardContent>
            <JobHistoryList
              jobs={jobs}
              selectedJobId={jobId}
              onSelect={setSelectedJobId}
            />
          </CardContent>
        </Card>
      )}

      {job && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0">
            <CardTitle>Trabajo de optimización</CardTitle>
            <JobStatusBadge status={job.status} />
          </CardHeader>
          <CardContent className="space-y-4">
            {job.error_message && (
              <Alert variant="destructive">
                <AlertDescription>{job.error_message}</AlertDescription>
              </Alert>
            )}
            {job.solution_ids &&
              Object.keys(job.solution_ids).length > 0 && (
                <div className="space-y-4 divide-y">
                  {Object.entries(job.solution_ids).map(
                    ([strategy, solutionId]) => (
                      <div key={strategy} className="pt-4 first:pt-0 space-y-2">
                        <p className="text-sm font-medium">
                          {STRATEGY_LABELS[strategy] ?? strategy}
                        </p>
                        <SolutionSummary solutionId={solutionId} />
                      </div>
                    )
                  )}
                </div>
              )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
