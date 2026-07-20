import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { fetchDatasets } from "@/api/datasets.js";
import { fetchUsers } from "@/api/users.js";
import { useCensusProgress } from "@/hooks/useCensusProgress.js";
import { useOptimizationJobs } from "@/hooks/useOptimizationJobs.js";
import { ROLES } from "@/constants/roles.js";
import { getErrorMessage } from "@/lib/errors";
import { progressPercent, resolvedCount } from "@/lib/progress.js";
import ProgressBar from "@/components/progress/ProgressBar.jsx";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

const DATASET_CARDS_LIMIT = 6;

const numberFormat = new Intl.NumberFormat("es-CL");

const treeCount = (dataset) => dataset.total_trees ?? 0;

function formatDate(value) {
  if (!value) return "sin fecha";
  return new Date(value).toLocaleDateString("es-CL", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function StatCard({ label, value, hint }) {
  return (
    <Card>
      <CardContent className="p-4">
        <p className="text-sm text-muted-foreground">{label}</p>
        <p className="text-3xl font-semibold tabular-nums">{value}</p>
        {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      </CardContent>
    </Card>
  );
}

function datasetState(progress, jobs) {
  if (progress?.solution) return { variant: "success", label: "Publicado" };
  const latest = jobs?.[0];
  if (latest && ["queued", "running"].includes(latest.status))
    return { variant: "default", label: "Optimizando" };
  if (latest?.status === "completed")
    return { variant: "secondary", label: "Sin publicar" };
  return { variant: "outline", label: "Sin optimizar" };
}

function DatasetCard({ dataset }) {
  const { data: progress } = useCensusProgress(dataset.id);
  const { data: jobs } = useOptimizationJobs(dataset.id);

  const state = datasetState(progress, jobs);
  const totals = progress?.solution ? progress.totals : null;

  return (
    <Card>
      <CardContent className="flex flex-col gap-3 p-4">
        <div className="flex items-start justify-between gap-2">
          <Link
            to={`/admin/datasets/${dataset.id}`}
            className="font-medium text-primary hover:underline"
          >
            {dataset.name}
          </Link>
          <Badge variant={state.variant}>{state.label}</Badge>
        </div>

        <p className="text-sm text-muted-foreground">
          {numberFormat.format(treeCount(dataset))} árboles · importado{" "}
          {formatDate(dataset.imported_at)}
        </p>

        {totals ? (
          <div className="flex flex-col gap-1">
            <ProgressBar totals={totals} />
            <p className="text-sm">
              <span className="font-semibold tabular-nums">
                {progressPercent(totals)}%
              </span>{" "}
              <span className="text-muted-foreground">
                censado · {numberFormat.format(resolvedCount(totals))} de{" "}
                {numberFormat.format(totals.total)}
              </span>
            </p>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            Sin solución publicada. Optimiza el dataset y publica una solución
            para seguir el avance del censo.
          </p>
        )}

        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" asChild>
            <Link to={`/admin/datasets/${dataset.id}`}>Abrir dataset</Link>
          </Button>
          {totals && (
            <Button size="sm" asChild>
              <Link to={`/admin/datasets/${dataset.id}/progress`}>
                Ver avance
              </Link>
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function EmptyState() {
  return (
    <Card>
      <CardContent className="flex flex-col items-start gap-3 p-6">
        <div>
          <p className="font-medium">Aún no hay datasets</p>
          <p className="text-sm text-muted-foreground">
            Sube un archivo con árboles o importa desde la base de Arbocensus
            para comenzar.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button asChild>
            <Link to="/admin/datasets">Subir archivo</Link>
          </Button>
          <Button variant="outline" asChild>
            <Link to="/admin/datasets/legacy-import">
              Importar desde Arbocensus
            </Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export default function AdminHome() {
  const {
    data: datasets,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["datasets"],
    queryFn: fetchDatasets,
  });

  const { data: users, error: usersError } = useQuery({
    queryKey: ["users"],
    queryFn: fetchUsers,
  });

  const surveyors = users?.filter(
    (user) => user.role === ROLES.SURVEYOR && user.is_active,
  );

  const visible = datasets ? datasets.slice(0, DATASET_CARDS_LIMIT) : [];

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Panel de administración</h1>
        <p className="text-sm text-muted-foreground">
          Resumen de todos los datasets del censo.
        </p>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>
            {getErrorMessage(error, "No se pudieron cargar los datasets.")}
          </AlertDescription>
        </Alert>
      )}

      {isLoading && (
        <div className="grid gap-4 sm:grid-cols-3">
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
        </div>
      )}

      {datasets && (
        <div className="grid gap-4 sm:grid-cols-3">
          <StatCard label="Datasets" value={datasets.length} />
          <StatCard
            label="Árboles cargados"
            value={numberFormat.format(
              datasets.reduce((sum, d) => sum + treeCount(d), 0),
            )}
            hint="En todos los datasets"
          />
          <StatCard
            label="Censadores activos"
            value={surveyors ? surveyors.length : "—"}
            hint={usersError ? "No se pudieron cargar los usuarios." : undefined}
          />
        </div>
      )}

      {datasets && datasets.length === 0 && <EmptyState />}

      {visible.length > 0 && (
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between gap-2">
            <div>
              <h2 className="text-lg font-semibold">Datasets recientes</h2>
              <p className="text-sm text-muted-foreground">
                {datasets.length > DATASET_CARDS_LIMIT
                  ? `Los ${DATASET_CARDS_LIMIT} importados más recientemente.`
                  : "Ordenados por fecha de importación."}
              </p>
            </div>
            <Button variant="ghost" size="sm" asChild>
              <Link to="/admin/datasets">Ver todos ({datasets.length})</Link>
            </Button>
          </div>
          <div className="grid items-start gap-4 lg:grid-cols-2">
            {visible.map((dataset) => (
              <DatasetCard key={dataset.id} dataset={dataset} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
