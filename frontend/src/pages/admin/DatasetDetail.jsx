import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { fetchDataset, fetchDatasetTrees, updateDataset } from "@/api/datasets.js";
import { useDatasetSolutions } from "@/hooks/useDatasetSolutions";
import { strategyLabel } from "@/lib/optimization";
import { getErrorMessage } from "@/lib/errors";
import DatasetMap from "@/components/map/DatasetMap.jsx";
import RouteAssignmentPanel from "@/components/routes/RouteAssignmentPanel.jsx";
import OptimizationPanel from "@/components/optimization/OptimizationPanel.jsx";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "@/store/toastStore.js";
import { cn } from "@/lib/utils";

function toLeafletPositions(featureCollection) {
  const features = featureCollection?.features ?? [];
  return features.map((feature) => {
    // GeoJSON Point coordinates are [lon, lat]; Leaflet expects [lat, lon].
    const [lon, lat] = feature.geometry.coordinates;
    return {
      id: feature.id ?? feature.properties?.id,
      position: [lat, lon],
    };
  });
}

export default function DatasetDetail() {
  const { id } = useParams();
  const queryClient = useQueryClient();
  const [selectedSolutionId, setSelectedSolutionId] = useState(null);
  const [openPanel, setOpenPanel] = useState(null);
  const [editOpen, setEditOpen] = useState(false);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");

  const togglePanel = (panel) =>
    setOpenPanel((current) => (current === panel ? null : panel));

  const { data: dataset } = useQuery({
    queryKey: ["dataset", id],
    queryFn: () => fetchDataset(id),
  });

  const {
    data: trees,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["dataset-trees", id],
    queryFn: () => fetchDatasetTrees(id),
  });

  const markers = useMemo(() => toLeafletPositions(trees), [trees]);

  // The API orders best-first across every sweep of the dataset, but the
  // recommendation is scoped to the latest one — so the map defaults to the
  // recommended solution, not to the globally cheapest of some older sweep.
  const { data: solutions = [] } = useDatasetSolutions(id);
  const displaySolution =
    solutions.find((s) => s.id === selectedSolutionId) ??
    solutions.find((s) => s.recommended) ??
    solutions[0] ??
    null;
  const solutionId = displaySolution?.id ?? null;
  const datasetSolutionIds = useMemo(
    () => solutions.map((s) => s.id),
    [solutions],
  );

  const edit = useMutation({
    mutationFn: ({ name, description }) => updateDataset(id, { name, description }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dataset", id] });
      queryClient.invalidateQueries({ queryKey: ["datasets"] });
      setEditOpen(false);
      toast.success("Dataset actualizado");
    },
    onError: (err) => {
      toast.error(getErrorMessage(err, "No se pudo actualizar el dataset"));
    },
  });

  const handleOpenEdit = () => {
    setEditName(dataset?.name ?? "");
    setEditDescription(dataset?.description ?? "");
    setEditOpen(true);
  };

  const handleViewSolution = (solution) => {
    setSelectedSolutionId(solution.id);
    setOpenPanel(null);
  };

  return (
    <>
      <div className="flex h-[calc(100vh-6rem)] flex-col gap-4">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" asChild>
            <Link to="/admin/datasets">← Datasets</Link>
          </Button>
          <h1 className="text-2xl font-semibold">{dataset?.name ?? "Dataset"}</h1>
          <Button
            variant="outline"
            size="sm"
            className="ml-auto"
            onClick={handleOpenEdit}
            disabled={!dataset}
          >
            Editar
          </Button>
          <Button variant="outline" size="sm" asChild>
            <Link to={`/admin/datasets/${id}/progress`}>📊 Avance</Link>
          </Button>
          <Button
            variant={openPanel === "assign" ? "secondary" : "outline"}
            size="sm"
            disabled={!solutionId}
            onClick={() => togglePanel("assign")}
          >
            👤 Asignación
          </Button>
          <Button
            variant={openPanel === "optimization" ? "secondary" : "outline"}
            size="sm"
            onClick={() => togglePanel("optimization")}
          >
            ⚙ Optimización
          </Button>
        </div>

        {error && (
          <Alert variant="destructive">
            <AlertDescription>
              {getErrorMessage(error, "No se pudieron cargar los árboles.")}
            </AlertDescription>
          </Alert>
        )}

        <div className="relative flex-1 overflow-hidden rounded-md border">
          {isLoading && (
            <div className="flex h-full items-center justify-center text-muted-foreground">
              Cargando árboles…
            </div>
          )}
          {trees && <DatasetMap markers={markers} solutionId={solutionId} />}

          <div className="absolute left-3 top-3 z-[1000] flex flex-col gap-2">
            {displaySolution ? (
              <div className="flex flex-wrap items-center gap-1.5 rounded-md border bg-background/90 px-3 py-1.5 text-sm shadow-md backdrop-blur">
                <span>
                  {displaySolution.config_preset_label} ·{" "}
                  {strategyLabel(displaySolution.strategy)}
                </span>
                {displaySolution.recommended && (
                  <Badge variant="success">★ Recomendada</Badge>
                )}
                {displaySolution.published_at && (
                  <Badge variant="secondary">✓ Publicada</Badge>
                )}
              </div>
            ) : (
              <span className="rounded-md border bg-background/90 px-3 py-1.5 text-sm text-muted-foreground shadow-md backdrop-blur">
                Optimiza el dataset para ver rutas
              </span>
            )}
          </div>

          <div
            className={cn(
              "absolute right-0 top-0 z-[1001] h-full w-full max-w-sm overflow-y-auto border-l bg-background p-4 shadow-xl transition-transform",
              openPanel === "optimization" ? "translate-x-0" : "translate-x-full",
            )}
          >
            <OptimizationPanel
              key={id}
              datasetId={id}
              activeSolutionId={solutionId}
              onViewSolution={handleViewSolution}
            />
          </div>

          <div
            className={cn(
              "absolute right-0 top-0 z-[1001] h-full w-full max-w-sm overflow-y-auto border-l bg-background p-4 shadow-xl transition-transform",
              openPanel === "assign" ? "translate-x-0" : "translate-x-full",
            )}
          >
            <RouteAssignmentPanel datasetSolutionIds={datasetSolutionIds} />
          </div>
        </div>
      </div>

      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Editar dataset</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="edit-name">Nombre</Label>
              <Input
                id="edit-name"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                disabled={edit.isPending}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="edit-description">Descripción</Label>
              <textarea
                id="edit-description"
                value={editDescription}
                onChange={(e) => setEditDescription(e.target.value)}
                disabled={edit.isPending}
                rows={3}
                className="flex w-full rounded-md border border-input bg-transparent px-3 py-2 text-base shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 md:text-sm"
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setEditOpen(false)}
              disabled={edit.isPending}
            >
              Cancelar
            </Button>
            <Button
              onClick={() =>
                edit.mutate({
                name: editName.trim(),
                description: editDescription.trim(),
              })
              }
              disabled={edit.isPending || !editName.trim()}
            >
              {edit.isPending ? "Guardando…" : "Guardar"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
