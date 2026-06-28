import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { fetchSolution } from "@/api/optimization";
import { getErrorMessage } from "@/lib/errors";
import { useOptimizationJob } from "@/hooks/useOptimizationJob";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import JobStatusBadge from "./JobStatusBadge";
import RoutingConfigForm from "./RoutingConfigForm";

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
    <div className="space-y-2">
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
      </dl>
      <p className="text-xs text-muted-foreground">
        Balance de carga: 1.00 indica rutas con duraciones equilibradas; valores
        más bajos, rutas más dispares.
      </p>
    </div>
  );
}

export default function OptimizationPanel({ datasetId }) {
  const [jobId, setJobId] = useState(null);
  const { data: job } = useOptimizationJob(jobId);

  useEffect(() => {
    setJobId(null);
  }, [datasetId]);

  return (
    <div className="flex flex-col gap-4">
      <RoutingConfigForm
        datasetId={datasetId}
        onJobCreated={(created) => setJobId(created.id)}
      />

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
            {job.solution_id && (
              <SolutionSummary solutionId={job.solution_id} />
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
