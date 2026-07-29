import { useQuery } from "@tanstack/react-query";
import { fetchSolutionsForDataset } from "../api/optimization.js";

export function useDatasetSolutions(datasetId, hasActiveJob = false) {
  return useQuery({
    queryKey: ["dataset-solutions", datasetId],
    queryFn: () => fetchSolutionsForDataset(datasetId),
    enabled: !!datasetId,
    refetchInterval: () => (hasActiveJob ? 3000 : false),
  });
}
