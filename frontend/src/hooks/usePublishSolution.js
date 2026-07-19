import { useMutation, useQueryClient } from "@tanstack/react-query";
import { publishSolution } from "../api/optimization.js";

export function usePublishSolution() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (solutionId) => publishSolution(solutionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["solution-metrics"] });
      queryClient.invalidateQueries({ queryKey: ["routes"] });
      queryClient.invalidateQueries({ queryKey: ["census-progress"] });
      queryClient.invalidateQueries({ queryKey: ["census-progress-stops"] });
    },
  });
}
