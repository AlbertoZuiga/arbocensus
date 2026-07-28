import { useDatasetSolutions } from "@/hooks/useDatasetSolutions";
import { usePublishSolution } from "@/hooks/usePublishSolution";
import { COMPARISON_METRICS, bestValue, strategyLabel } from "@/lib/optimization";
import { getErrorMessage } from "@/lib/errors";
import { cn } from "@/lib/utils";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
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

const REPLACE_WARNING =
  "Ya hay un plan publicado para este dataset. Publicar esta solución " +
  "reemplazará el plan vigente. ¿Continuar?";

export default function SolutionsComparisonTable({ datasetId }) {
  const { data: solutions = [], isLoading, error } =
    useDatasetSolutions(datasetId);
  const publish = usePublishSolution();

  if (isLoading) return null;

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription>
          {getErrorMessage(error, "No se pudieron cargar las soluciones.")}
        </AlertDescription>
      </Alert>
    );
  }

  if (solutions.length === 0) return null;

  const publishedElsewhere = solutions.some((s) => s.published_at);

  const handlePublish = (solutionId) => {
    if (publishedElsewhere && !window.confirm(REPLACE_WARNING)) return;
    publish.mutate(solutionId);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Comparación de configuraciones</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Métrica</TableHead>
              {solutions.map((solution) => (
                <TableHead key={solution.id} className="text-right">
                  <div className="flex flex-col items-end gap-1">
                    <span>
                      {strategyLabel(solution.strategy)} ·{" "}
                      {solution.config_preset_label}
                    </span>
                    {solution.recommended && (
                      <Badge variant="success">★ Recomendada</Badge>
                    )}
                  </div>
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {COMPARISON_METRICS.map((metric) => {
              const values = solutions.map((s) => s[metric.key]);
              const best = bestValue(values, metric.better);
              return (
                <TableRow key={metric.key}>
                  <TableCell className="text-muted-foreground">
                    {metric.label}
                  </TableCell>
                  {solutions.map((solution, i) => {
                    const isBest = best !== null && values[i] === best;
                    return (
                      <TableCell
                        key={solution.id}
                        className={cn(
                          "text-right tabular-nums",
                          isBest && "font-semibold text-primary",
                          solution.recommended && "bg-emerald-500/10",
                        )}
                      >
                        {metric.format(values[i])}
                      </TableCell>
                    );
                  })}
                </TableRow>
              );
            })}
            <TableRow>
              <TableCell className="text-muted-foreground">Plan</TableCell>
              {solutions.map((solution) => (
                <TableCell
                  key={solution.id}
                  className={cn(
                    "text-right",
                    solution.recommended && "bg-emerald-500/10",
                  )}
                >
                  {solution.published_at ? (
                    <Badge variant="secondary">✓ Publicada</Badge>
                  ) : (
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={publish.isPending}
                      onClick={() => handlePublish(solution.id)}
                    >
                      Publicar
                    </Button>
                  )}
                </TableCell>
              ))}
            </TableRow>
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
