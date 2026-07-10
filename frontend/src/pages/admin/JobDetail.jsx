import { Link, useParams } from "react-router-dom";
import { useQueries } from "@tanstack/react-query";

import { fetchSolution } from "@/api/optimization";
import { useOptimizationJob } from "@/hooks/useOptimizationJob";
import {
  COMPARISON_METRICS,
  bestValue,
  formatTimestamp,
  strategyLabel,
} from "@/lib/optimization";
import { cn } from "@/lib/utils";
import JobStatusBadge from "@/components/optimization/JobStatusBadge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const STRATEGY_ORDER = ["global", "spatial_term", "cluster_first"];

function ComparisonTable({ strategies, solutionsByStrategy }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Métrica</TableHead>
          {strategies.map((s) => (
            <TableHead key={s} className="text-right">
              {strategyLabel(s)}
            </TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {COMPARISON_METRICS.map((metric) => {
          const values = strategies.map(
            (s) => solutionsByStrategy[s][metric.key],
          );
          const best = bestValue(values, metric.better);
          return (
            <TableRow key={metric.key}>
              <TableCell className="text-muted-foreground">
                {metric.label}
              </TableCell>
              {strategies.map((s, i) => {
                const isBest = best !== null && values[i] === best;
                return (
                  <TableCell
                    key={s}
                    className={cn(
                      "text-right tabular-nums",
                      isBest && "font-semibold text-primary",
                    )}
                  >
                    {metric.format(values[i])}
                  </TableCell>
                );
              })}
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}

export default function JobDetail() {
  const { id: datasetId, jobId } = useParams();
  const { data: job, isLoading: jobLoading, error: jobError } =
    useOptimizationJob(jobId);

  const solutionEntries = Object.entries(job?.solution_ids ?? {});
  const solutionQueries = useQueries({
    queries: solutionEntries.map(([, solutionId]) => ({
      queryKey: ["optimization-solution", solutionId],
      queryFn: () => fetchSolution(solutionId),
      enabled: !!solutionId,
    })),
  });

  const backLink = (
    <Button variant="ghost" size="sm" asChild>
      <Link to={`/admin/datasets/${datasetId}`}>← Volver al dataset</Link>
    </Button>
  );

  if (jobLoading)
    return (
      <div className="flex flex-col gap-4">
        {backLink}
        <p className="text-muted-foreground">Cargando trabajo…</p>
      </div>
    );

  if (jobError || !job)
    return (
      <div className="flex flex-col gap-4">
        {backLink}
        <Alert variant="destructive">
          <AlertDescription>No se pudo cargar el trabajo.</AlertDescription>
        </Alert>
      </div>
    );

  const solutionsByStrategy = {};
  solutionEntries.forEach(([strategy], i) => {
    const solution = solutionQueries[i].data;
    if (solution) solutionsByStrategy[strategy] = solution;
  });
  const droppedTrees = job.metrics?.dropped_trees ?? [];
  const strategies = STRATEGY_ORDER.filter((s) => solutionsByStrategy[s]);
  const solutionsLoading = solutionQueries.some((q) => q.isLoading);
  const solutionsError = solutionQueries.some((q) => q.error);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          {backLink}
          <div>
            <h1 className="text-2xl font-semibold">
              {formatTimestamp(job.started_at)}
            </h1>
          </div>
        </div>
        <JobStatusBadge status={job.status} />
      </div>

      {job.error_message && (
        <Alert variant="destructive">
          <AlertDescription>{job.error_message}</AlertDescription>
        </Alert>
      )}

      {droppedTrees.length > 0 && (
        <Alert className="border-amber-500/50 text-amber-700 dark:text-amber-500">
          <AlertDescription>
            {droppedTrees.length === 1
              ? "1 árbol quedó fuera de las rutas."
              : `${droppedTrees.length} árboles quedaron fuera de las rutas.`}
          </AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Comparación de estrategias</CardTitle>
        </CardHeader>
        <CardContent>
          {solutionsError && (
            <Alert variant="destructive">
              <AlertDescription>
                No se pudieron cargar todas las soluciones.
              </AlertDescription>
            </Alert>
          )}
          {!solutionsError && solutionsLoading && (
            <p className="text-muted-foreground">Cargando soluciones…</p>
          )}
          {!solutionsError && !solutionsLoading && strategies.length === 0 && (
            <p className="text-muted-foreground">
              Este trabajo no tiene soluciones.
            </p>
          )}
          {!solutionsError && !solutionsLoading && strategies.length > 0 && (
            <ComparisonTable
              strategies={strategies}
              solutionsByStrategy={solutionsByStrategy}
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
