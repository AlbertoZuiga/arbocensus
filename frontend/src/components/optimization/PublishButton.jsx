import { useQueries } from "@tanstack/react-query";

import { fetchSolution } from "@/api/optimization.js";
import { usePublishSolution } from "@/hooks/usePublishSolution";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

const REPLACE_WARNING =
  "Ya hay un plan publicado para este dataset. Publicar esta solución " +
  "reemplazará el plan vigente. ¿Continuar?";

export default function PublishButton({ solutionId, datasetSolutionIds = [] }) {
  const results = useQueries({
    queries: datasetSolutionIds.map((id) => ({
      queryKey: ["solution-metrics", id],
      queryFn: () => fetchSolution(id),
      enabled: !!id,
      staleTime: Infinity,
    })),
  });
  const publish = usePublishSolution();

  if (!solutionId) return null;

  const loading = results.some((result) => result.isLoading);
  const solutions = results.map((result) => result.data).filter(Boolean);
  const active = solutions.find((solution) => solution.id === solutionId);
  const publishedElsewhere = solutions.find(
    (solution) => solution.published_at && solution.id !== solutionId,
  );

  if (active?.published_at) {
    return (
      <Badge
        variant="secondary"
        className="w-fit shadow-md backdrop-blur"
      >
        ✓ Plan publicado
      </Badge>
    );
  }

  const onClick = () => {
    if (publishedElsewhere && !window.confirm(REPLACE_WARNING)) return;
    publish.mutate(solutionId);
  };

  return (
    <Button
      size="sm"
      className="w-fit shadow-md"
      onClick={onClick}
      disabled={loading || publish.isPending}
    >
      Publicar esta solución
    </Button>
  );
}
