import { useMutation, useQueryClient } from "@tanstack/react-query";
import { assignRoute } from "../api/routes.js";

export function useAssignRoute() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ routeId, surveyorId }) => assignRoute(routeId, surveyorId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["routes"] });
      queryClient.invalidateQueries({ queryKey: ["surveyors"] });
    },
  });
}
