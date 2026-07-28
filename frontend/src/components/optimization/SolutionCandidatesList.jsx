import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { useDatasetSolutions } from "@/hooks/useDatasetSolutions";
import { usePublishSolution } from "@/hooks/usePublishSolution";
import {
  KEY_METRICS,
  bestValue,
  solutionWarnings,
  strategyLabel,
} from "@/lib/optimization";
import { getErrorMessage } from "@/lib/errors";
import { cn } from "@/lib/utils";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";

const REPLACE_WARNING =
  "Ya hay un plan publicado para este dataset. Publicar esta solución " +
  "reemplazará el plan vigente. ¿Continuar?";

const COLLAPSED_COUNT = 3;

function MetricGrid({ metrics, solution, bestByKey }) {
  return (
    <dl className="grid grid-cols-2 gap-x-3 gap-y-1">
      {metrics.map((metric) => {
        const value = solution[metric.key];
        const isBest = bestByKey[metric.key] != null &&
          value === bestByKey[metric.key];
        return (
          <div key={metric.key} className="flex items-baseline justify-between gap-2">
            <dt className="text-xs text-muted-foreground">{metric.label}</dt>
            <dd
              className={cn(
                "text-sm tabular-nums",
                isBest && "font-semibold text-primary",
              )}
            >
              {metric.format(value)}
            </dd>
          </div>
        );
      })}
    </dl>
  );
}

function CandidateCard({
  datasetId,
  solution,
  bestByKey,
  isActive,
  onView,
  onPublish,
  publishDisabled,
}) {
  const warnings = solutionWarnings(solution);

  return (
    <div
      className={cn(
        "rounded-md border p-3",
        solution.recommended && "border-emerald-500/60 bg-emerald-500/5",
        isActive && "ring-2 ring-primary",
      )}
    >
      <div className="flex flex-wrap items-center gap-1.5">
        {solution.recommended && <Badge variant="success">★ Recomendada</Badge>}
        {solution.published_at && <Badge variant="secondary">✓ Publicada</Badge>}
        {isActive && <Badge variant="outline">En el mapa</Badge>}
      </div>

      <p className="mt-1.5 text-sm font-medium">
        {solution.config_preset_label} · {strategyLabel(solution.strategy)}
      </p>

      <div className="mt-2">
        <MetricGrid
          metrics={KEY_METRICS}
          solution={solution}
          bestByKey={bestByKey}
        />
      </div>

      {warnings.length > 0 && (
        <p className="mt-2 text-xs text-amber-700 dark:text-amber-500">
          ⚠ {warnings.join(" · ")}
        </p>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {onView && (
          <Button size="sm" variant="outline" onClick={() => onView(solution)}>
            Ver en el mapa
          </Button>
        )}
        {!solution.published_at && (
          <Button
            size="sm"
            variant={solution.recommended ? "default" : "secondary"}
            disabled={publishDisabled}
            onClick={() => onPublish(solution.id)}
          >
            Publicar
          </Button>
        )}
        <Link
          to={`/admin/datasets/${datasetId}/jobs/${solution.job}`}
          className="ml-auto text-xs text-muted-foreground underline"
        >
          Ver detalle
        </Link>
      </div>
    </div>
  );
}

export default function SolutionCandidatesList({
  datasetId,
  hasActiveJob = false,
  viewedConfig = null,
  sweeps = [],
  onChangeViewedConfig,
  activeSolutionId = null,
  onViewSolution,
}) {
  const [expanded, setExpanded] = useState(false);
  const { data: allSolutions = [], isLoading, error } = useDatasetSolutions(
    datasetId,
    hasActiveJob,
  );
  // Solutions from a different RoutingConfig aren't comparable to each other
  // (different min/max/service time), so the list only shows one sweep at a
  // time — the switcher below lets the admin pick which one.
  const solutions = viewedConfig
    ? allSolutions.filter((s) => s.config === viewedConfig)
    : allSolutions;
  const publish = usePublishSolution();

  useEffect(() => {
    setExpanded(false);
  }, [viewedConfig]);

  if (isLoading) {
    return <Skeleton className="h-40 w-full" />;
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription>
          {getErrorMessage(error, "No se pudieron cargar las soluciones.")}
        </AlertDescription>
      </Alert>
    );
  }

  if (solutions.length === 0 && sweeps.length <= 1) return null;

  const bestByKey = Object.fromEntries(
    KEY_METRICS.map((metric) => [
      metric.key,
      bestValue(
        solutions.map((solution) => solution[metric.key]),
        metric.better,
      ),
    ]),
  );

  // The published plan is one per dataset, so the replace warning has to look at
  // every sweep, not only the one currently on screen.
  const publishedElsewhere = allSolutions.some((s) => s.published_at);
  const handlePublish = (solutionId) => {
    if (publishedElsewhere && !window.confirm(REPLACE_WARNING)) return;
    publish.mutate(solutionId);
  };

  const visible = expanded ? solutions : solutions.slice(0, COLLAPSED_COUNT);
  const hidden = solutions.length - visible.length;

  return (
    <Card>
      <CardHeader className="space-y-1">
        <div className="flex items-center justify-between gap-2">
          Ejecución
          {sweeps.length > 1 && (
            <Select value={viewedConfig ?? undefined} onValueChange={onChangeViewedConfig}>
              <SelectTrigger className="h-8 w-auto text-xs" aria-label="Corrida">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {sweeps.map((sweep, index) => (
                  <SelectItem key={sweep.config} value={sweep.config}>
                    <strong>{index + 1}</strong>: {sweep.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>
        <CardTitle>Candidatos a plan</CardTitle>
        <p className="text-xs text-muted-foreground">
          Ordenados de mejor a peor. Se recomienda la que no deja árboles
          fuera de ruta ni rutas muy cortas, mantiene la carga balanceada y
          camina menos.
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        {solutions.length === 0 && (
          <p className="text-sm text-muted-foreground">
            Esta corrida todavía no tiene soluciones.
          </p>
        )}
        {visible.map((solution) => (
          <CandidateCard
            key={solution.id}
            datasetId={datasetId}
            solution={solution}
            bestByKey={bestByKey}
            isActive={solution.id === activeSolutionId}
            onView={onViewSolution}
            onPublish={handlePublish}
            publishDisabled={publish.isPending}
          />
        ))}
        {(hidden > 0 || expanded) && (
          <Button
            variant="ghost"
            size="sm"
            className="w-full"
            onClick={() => setExpanded((value) => !value)}
          >
            {expanded ? "Ver solo los mejores" : `Ver ${hidden} más`}
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
