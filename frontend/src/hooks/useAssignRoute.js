import { useMutation, useQueryClient } from "@tanstack/react-query";
import { assignRoute } from "../api/routes.js";
import { toast } from "../store/toastStore.js";
import { getErrorMessage } from "../lib/errors.js";

export function useAssignRoute() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ routeId, surveyorId }) => assignRoute(routeId, surveyorId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["routes"] });
      queryClient.invalidateQueries({ queryKey: ["surveyors"] });
      queryClient.invalidateQueries({ queryKey: ["surveyor-workload"] });
      queryClient.invalidateQueries({ queryKey: ["census-progress"] });
      queryClient.invalidateQueries({ queryKey: ["census-progress-stops"] });
    },
    onError: (err) => {
      toast.error(getErrorMessage(err, "No se pudo asignar la ruta"));
    },
  });
}
