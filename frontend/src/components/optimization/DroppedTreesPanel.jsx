import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { deactivateDatasetTrees } from "@/api/datasets.js";
import { getErrorMessage } from "@/lib/errors";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "@/store/toastStore.js";

export default function DroppedTreesPanel({
  datasetId,
  droppedTreeIds,
  onReoptimize,
}) {
  const queryClient = useQueryClient();
  const [confirming, setConfirming] = useState(false);

  const deactivate = useMutation({
    mutationFn: () => deactivateDatasetTrees(datasetId, droppedTreeIds),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dataset", datasetId] });
      queryClient.invalidateQueries({ queryKey: ["dataset-trees", datasetId] });
      queryClient.invalidateQueries({ queryKey: ["dataset-solutions", datasetId] });
      setConfirming(false);
      toast.success(
        `${droppedTreeIds.length} árbol${droppedTreeIds.length !== 1 ? "es" : ""} excluido${droppedTreeIds.length !== 1 ? "s" : ""} del dataset`,
      );
    },
    onError: (err) => {
      toast.error(getErrorMessage(err, "No se pudo excluir los árboles"));
    },
  });

  if (droppedTreeIds.length === 0) return null;

  return (
    <div className="rounded-md border border-red-200 bg-red-50 p-3 dark:border-red-900 dark:bg-red-950/30">
      <p className="mb-2 text-sm font-medium text-red-700 dark:text-red-400">
        {droppedTreeIds.length} árbol{droppedTreeIds.length !== 1 ? "es" : ""} fuera
        de ruta
      </p>
      <p className="mb-3 text-xs text-red-600 dark:text-red-500">
        El solver no pudo incluirlos. Normalmente indica que el presupuesto de
        tiempo de las rutas es demasiado ajustado, no que los árboles sean el
        problema.
      </p>
      <div className="flex flex-col gap-2">
        <Button size="sm" onClick={onReoptimize}>
          Re-optimizar con otra configuración
        </Button>
        <Button
          size="sm"
          variant="outline"
          className="border-red-300 text-red-700 hover:bg-red-100 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-900/30"
          onClick={() => setConfirming(true)}
        >
          Excluir del dataset
        </Button>
        <Dialog open={confirming} onOpenChange={setConfirming}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Excluir árboles del dataset</DialogTitle>
              <DialogDescription>
                Esto marcará {droppedTreeIds.length} árbol
                {droppedTreeIds.length !== 1 ? "es" : ""} como inactivo
                {droppedTreeIds.length !== 1 ? "s" : ""}. La acción es
                reversible reimportando desde la selección legacy.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setConfirming(false)}
                disabled={deactivate.isPending}
              >
                Cancelar
              </Button>
              <Button
                className="bg-red-600 hover:bg-red-700"
                onClick={() => deactivate.mutate()}
                disabled={deactivate.isPending}
              >
                {deactivate.isPending ? "Excluyendo…" : "Confirmar exclusión"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}
