import { useCallback, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createDatasetFromLegacySelection,
  fetchLegacyAreas,
  fetchLegacyTrees,
} from "@/api/datasets.js";
import {
  addTrees,
  removeKey,
  selectionPayload,
  toggleTree,
  toggleTrees,
  treeKey,
} from "@/lib/legacySelection.js";
import LegacySelectionMap from "@/components/map/LegacySelectionMap.jsx";
import { getErrorMessage } from "@/lib/errors";
import { toast } from "@/store/toastStore.js";
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

const SOURCE_LABELS = { legacy_api: "API", legacy_app: "App" };

function treeLabel(tree) {
  const species = tree.species?.trim();
  return species ? `${species} · #${tree.external_id}` : `#${tree.external_id}`;
}

export default function LegacyImport() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [selectedKeys, setSelectedKeys] = useState(() => new Set());
  const [bboxMode, setBboxMode] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [datasetName, setDatasetName] = useState("");

  const bboxModeRef = useRef(bboxMode);
  bboxModeRef.current = bboxMode;

  const {
    data: trees,
    isLoading: treesLoading,
    error: treesError,
  } = useQuery({
    queryKey: ["legacy-trees"],
    queryFn: fetchLegacyTrees,
    staleTime: 5 * 60 * 1000,
  });

  const { data: areas, error: areasError } = useQuery({
    queryKey: ["legacy-areas"],
    queryFn: fetchLegacyAreas,
    staleTime: 5 * 60 * 1000,
  });

  const treesByArea = useMemo(() => {
    const byArea = new Map();
    for (const tree of trees ?? []) {
      if (tree.area_id === null) continue;
      if (!byArea.has(tree.area_id)) byArea.set(tree.area_id, []);
      byArea.get(tree.area_id).push(tree);
    }
    return byArea;
  }, [trees]);

  const treesByKey = useMemo(
    () => new Map((trees ?? []).map((tree) => [treeKey(tree), tree])),
    [trees],
  );

  const handleToggleTree = useCallback((tree) => {
    if (bboxModeRef.current) return;
    setSelectedKeys((prev) => toggleTree(prev, tree));
  }, []);

  const handleToggleArea = useCallback(
    (area) => {
      if (bboxModeRef.current) return;
      const areaTrees = treesByArea.get(area.id) ?? [];
      setSelectedKeys((prev) => toggleTrees(prev, areaTrees));
    },
    [treesByArea],
  );

  const handleBboxSelect = useCallback(
    (bounds) => {
      const inside = (trees ?? []).filter((tree) =>
        bounds.contains([tree.lat, tree.lon]),
      );
      setSelectedKeys((prev) => addTrees(prev, inside));
    },
    [trees],
  );

  const createDataset = useMutation({
    mutationFn: createDatasetFromLegacySelection,
    onSuccess: (dataset) => {
      queryClient.invalidateQueries({ queryKey: ["datasets"] });
      queryClient.invalidateQueries({ queryKey: ["legacy-trees"] });
      toast.success(
        `Dataset "${dataset.name}" creado con ${dataset.total_trees} árboles`,
      );
      navigate(`/admin/datasets/${dataset.id}`);
    },
    onError: (err) => {
      toast.error(getErrorMessage(err, "No se pudo crear el dataset"));
    },
  });

  const handleConfirm = (event) => {
    event.preventDefault();
    const name = datasetName.trim();
    if (!name || selectedKeys.size === 0) return;
    createDataset.mutate({ name, trees: selectionPayload(selectedKeys) });
  };

  const error = treesError ?? areasError;
  const selectedList = [...selectedKeys];

  return (
    <div className="flex h-[calc(100vh-6rem)] flex-col gap-4">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" asChild>
          <Link to="/admin/datasets">← Datasets</Link>
        </Button>
        <h1 className="text-2xl font-semibold">Importar desde Arbocensus</h1>
        <Button
          variant={bboxMode ? "secondary" : "outline"}
          size="sm"
          className="ml-auto"
          onClick={() => setBboxMode((mode) => !mode)}
        >
          ▭ Selección por rectángulo
        </Button>
        <Button
          size="sm"
          disabled={selectedKeys.size === 0 || createDataset.isPending}
          onClick={() => setDialogOpen(true)}
        >
          Importar {selectedKeys.size > 0 ? `(${selectedKeys.size})` : ""}
        </Button>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>
            {getErrorMessage(error, "No se pudieron cargar los árboles legacy.")}
          </AlertDescription>
        </Alert>
      )}

      <div className="flex flex-1 gap-4 overflow-hidden">
        <div className="relative isolate flex-1 overflow-hidden rounded-md border">
          {treesLoading && (
            <div className="flex h-full items-center justify-center text-muted-foreground">
              Cargando árboles legacy…
            </div>
          )}
          {trees && (
            <LegacySelectionMap
              trees={trees}
              areas={areas ?? []}
              selectedKeys={selectedKeys}
              bboxMode={bboxMode}
              onToggleTree={handleToggleTree}
              onToggleArea={handleToggleArea}
              onBboxSelect={handleBboxSelect}
            />
          )}
          <div className="absolute bottom-3 left-3 z-[1000] flex flex-col gap-1 rounded-md border bg-background/90 px-3 py-2 text-xs shadow-md backdrop-blur">
            <span className="flex items-center gap-2">
              <span className="h-3 w-3 rounded-full bg-green-600" /> Disponible
            </span>
            <span className="flex items-center gap-2">
              <span className="h-3 w-3 rounded-full bg-blue-600" /> Seleccionado
            </span>
            <span className="flex items-center gap-2">
              <span className="h-3 w-3 rounded-full bg-slate-400" /> Ya importado
            </span>
          </div>
          {bboxMode && (
            <div className="absolute left-1/2 top-3 z-[1000] -translate-x-1/2 rounded-md border bg-background/90 px-3 py-1.5 text-sm shadow-md backdrop-blur">
              Arrastra un rectángulo para seleccionar
            </div>
          )}
        </div>

        <aside className="flex w-72 shrink-0 flex-col rounded-md border bg-white">
          <div className="flex items-center justify-between border-b px-3 py-2">
            <span className="text-sm font-medium">
              {selectedKeys.size} seleccionados
            </span>
            {selectedKeys.size > 0 && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSelectedKeys(new Set())}
              >
                Limpiar
              </Button>
            )}
          </div>
          <ul className="flex-1 overflow-y-auto p-2">
            {selectedList.length === 0 && (
              <li className="px-1 py-2 text-sm text-muted-foreground">
                Haz clic en árboles, áreas o usa el rectángulo para
                seleccionar.
              </li>
            )}
            {selectedList.map((key) => {
              const tree = treesByKey.get(key);
              if (!tree) return null;
              return (
                <li
                  key={key}
                  className="flex items-center gap-2 rounded-md px-1 py-1 text-sm hover:bg-muted/50"
                >
                  <Badge variant="outline">{SOURCE_LABELS[tree.source]}</Badge>
                  <span className="truncate">{treeLabel(tree)}</span>
                  <button
                    type="button"
                    aria-label={`Quitar ${treeLabel(tree)}`}
                    className="ml-auto rounded px-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                    onClick={() =>
                      setSelectedKeys((prev) => removeKey(prev, key))
                    }
                  >
                    ×
                  </button>
                </li>
              );
            })}
          </ul>
        </aside>
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <form onSubmit={handleConfirm} className="grid gap-4">
            <DialogHeader>
              <DialogTitle>Crear dataset</DialogTitle>
            </DialogHeader>
            <div className="grid gap-2">
              <Label htmlFor="dataset-name">Nombre del dataset</Label>
              <Input
                id="dataset-name"
                value={datasetName}
                onChange={(event) => setDatasetName(event.target.value)}
                placeholder="Ej: Selección campus 2026"
                autoFocus
              />
            </div>
            <p className="text-sm text-muted-foreground">
              Se importarán {selectedKeys.size} árboles.
            </p>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setDialogOpen(false)}
              >
                Cancelar
              </Button>
              <Button
                type="submit"
                disabled={!datasetName.trim() || createDataset.isPending}
              >
                {createDataset.isPending ? "Creando…" : "Crear dataset"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
