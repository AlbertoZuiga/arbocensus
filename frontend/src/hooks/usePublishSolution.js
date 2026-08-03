import { useMutation, useQueryClient } from "@tanstack/react-query";
import { publishSolution } from "../api/optimization.js";
import { toast } from "../store/toastStore.js";
import { getErrorMessage } from "../lib/errors.js";

export function usePublishSolution() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (solutionId) => publishSolution(solutionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["solution-metrics"] });
      queryClient.invalidateQueries({ queryKey: ["dataset-solutions"] });
      queryClient.invalidateQueries({ queryKey: ["routes"] });
      queryClient.invalidateQueries({ queryKey: ["census-progress"] });
      queryClient.invalidateQueries({ queryKey: ["census-progress-stops"] });
    },
    onError: (err) => {
      toast.error(getErrorMessage(err, "No se pudo publicar la solución"));
    },
  });
}
