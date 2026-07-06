import { Link } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";

import { useOptimizationJobs } from "@/hooks/useOptimizationJobs";
import { formatElapsed, formatTimestamp, strategySummary } from "@/lib/optimization";
import { getErrorMessage } from "@/lib/errors";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import JobStatusBadge from "./JobStatusBadge";
import RoutingConfigForm from "./RoutingConfigForm";

export default function OptimizationPanel({ datasetId }) {
  const queryClient = useQueryClient();

  const { data: jobs = [], error } = useOptimizationJobs(datasetId);

  const latest = jobs[0];
  const isActive =
    latest && ["queued", "running"].includes(latest.status);

  const handleJobCreated = () => {
    queryClient.invalidateQueries({
      queryKey: ["optimization-jobs", datasetId],
    });
  };

  return (
    <div className="flex flex-col gap-4">
      <RoutingConfigForm datasetId={datasetId} onJobCreated={handleJobCreated} />

      {error && (
        <Alert variant="destructive">
          <AlertDescription>
            {getErrorMessage(error, "No se pudieron cargar los trabajos.")}
          </AlertDescription>
        </Alert>
      )}

      {latest && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0">
            <CardTitle>Última optimización</CardTitle>
            <JobStatusBadge status={latest.status} />
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              {isActive
                ? formatElapsed(latest.created_at)
                : formatTimestamp(latest.started_at)}
            </p>
            {latest.error_message ? (
              <Alert variant="destructive">
                <AlertDescription>{latest.error_message}</AlertDescription>
              </Alert>
            ) : (
              <p className="text-sm">{strategySummary(latest)}</p>
            )}
            <Button asChild size="sm">
              <Link to={`/admin/datasets/${datasetId}/jobs/${latest.id}`}>
                Ver detalle
              </Link>
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
