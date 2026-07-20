import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { fetchDatasets } from "@/api/datasets.js";
import { useCensusProgress } from "@/hooks/useCensusProgress.js";
import { useOptimizationJobs } from "@/hooks/useOptimizationJobs.js";
import { getErrorMessage } from "@/lib/errors";
import ProgressSummary from "@/components/progress/ProgressSummary.jsx";
import JobHistoryList from "@/components/optimization/JobHistoryList.jsx";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";

const RECENT_JOBS_LIMIT = 5;

function StatCard({ label, value }) {
  return (
    <Card>
      <CardContent className="p-4">
        <p className="text-sm text-muted-foreground">{label}</p>
        <p className="text-3xl font-semibold tabular-nums">{value}</p>
      </CardContent>
    </Card>
  );
}

function CensusProgressCard({ datasetId, progress, isLoading, error }) {
  if (isLoading) return <Skeleton className="h-40" />;

  if (error)
    return (
      <Alert variant="destructive">
        <AlertDescription>
          {getErrorMessage(error, "No se pudo cargar el avance del censo.")}
        </AlertDescription>
      </Alert>
    );

  if (!progress) return null;

  if (!progress.solution)
    return (
      <Alert>
        <AlertDescription>
          Este dataset no tiene una solución publicada. Publica una solución
          para seguir el avance del censo.
        </AlertDescription>
      </Alert>
    );

  return (
    <div className="flex flex-col gap-2">
      <ProgressSummary totals={progress.totals} />
      <Button variant="outline" size="sm" className="self-start" asChild>
        <Link to={`/admin/datasets/${datasetId}/progress`}>
          Ver avance detallado
        </Link>
      </Button>
    </div>
  );
}

function RecentJobsCard({ datasetId, jobs, isLoading, error }) {
  if (isLoading) return <Skeleton className="h-40" />;

  if (error)
    return (
      <Alert variant="destructive">
        <AlertDescription>
          {getErrorMessage(error, "No se pudieron cargar los trabajos.")}
        </AlertDescription>
      </Alert>
    );

  if (!jobs || jobs.length === 0)
    return (
      <p className="text-muted-foreground">
        Este dataset no tiene trabajos de optimización.
      </p>
    );

  return (
    <JobHistoryList
      datasetId={datasetId}
      jobs={jobs.slice(0, RECENT_JOBS_LIMIT)}
    />
  );
}

export default function AdminHome() {
  const [selectedDatasetId, setSelectedDatasetId] = useState(null);

  const {
    data: datasets,
    isLoading: datasetsLoading,
    error: datasetsError,
  } = useQuery({
    queryKey: ["datasets"],
    queryFn: fetchDatasets,
  });

  const datasetId = selectedDatasetId ?? datasets?.[0]?.id ?? null;
  const dataset = datasets?.find((d) => d.id === datasetId);

  const {
    data: progress,
    isLoading: progressLoading,
    error: progressError,
  } = useCensusProgress(datasetId);

  const {
    data: jobs,
    isLoading: jobsLoading,
    error: jobsError,
  } = useOptimizationJobs(datasetId);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">Panel de administración</h1>
        {datasets && datasets.length > 0 && (
          <Select value={datasetId ?? ""} onValueChange={setSelectedDatasetId}>
            <SelectTrigger
              className="w-64"
              aria-label="Seleccionar dataset"
            >
              <SelectValue placeholder="Selecciona un dataset" />
            </SelectTrigger>
            <SelectContent>
              {datasets.map((d) => (
                <SelectItem key={d.id} value={d.id}>
                  {d.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </div>

      {datasetsError && (
        <Alert variant="destructive">
          <AlertDescription>
            {getErrorMessage(datasetsError, "No se pudieron cargar los datasets.")}
          </AlertDescription>
        </Alert>
      )}

      {datasetsLoading && (
        <div className="grid gap-4 sm:grid-cols-3">
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
        </div>
      )}

      {datasets && datasets.length === 0 && (
        <Alert>
          <AlertDescription>
            Aún no hay datasets. Sube un archivo o importa desde Arbocensus para
            comenzar.
          </AlertDescription>
        </Alert>
      )}

      {datasets && datasets.length > 0 && (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <StatCard label="Datasets" value={datasets.length} />
            <StatCard
              label="Árboles del dataset"
              value={dataset?.total_trees ?? dataset?.tree_count ?? 0}
            />
            <StatCard
              label="Trabajos de optimización"
              value={jobs?.length ?? "—"}
            />
          </div>

          <div className="grid items-start gap-4 lg:grid-cols-2">
            <CensusProgressCard
              datasetId={datasetId}
              progress={progress}
              isLoading={progressLoading}
              error={progressError}
            />

            <Card>
              <CardHeader>
                <CardTitle>Trabajos recientes</CardTitle>
              </CardHeader>
              <CardContent>
                <RecentJobsCard
                  datasetId={datasetId}
                  jobs={jobs}
                  isLoading={jobsLoading}
                  error={jobsError}
                />
              </CardContent>
            </Card>
          </div>
        </>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Accesos directos</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          <Button asChild>
            <Link to="/admin/datasets">Datasets</Link>
          </Button>
          <Button variant="outline" asChild>
            <Link to="/admin/usuarios">Usuarios</Link>
          </Button>
          {datasetId && (
            <>
              <Button variant="outline" asChild>
                <Link to={`/admin/datasets/${datasetId}`}>
                  Ver dataset seleccionado
                </Link>
              </Button>
              <Button variant="outline" asChild>
                <Link to={`/admin/datasets/${datasetId}/progress`}>
                  Avance del censo
                </Link>
              </Button>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
