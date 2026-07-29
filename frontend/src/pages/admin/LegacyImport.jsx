import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createDatasetFromLegacySelection,
  fetchLegacyAreas,
  fetchLegacyTrees,
  partitionLegacySelection,
} from "@/api/datasets.js";
import {
  deselectKeys,
  keysInRing,
  pruneExclusions,
  resolveSelection,
  selectionPayload,
  toggleKeys,
  treeKey,
  treeKeys,
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
const EMPTY_SELECTION = { manualKeys: new Set(), excludedKeys: new Set() };
const NO_AREAS = [];
// Mirrors MIN_TREES_PER_DATASET in apps/datasets/partition.py, which validates it.
const MIN_TREES_PER_DATASET = 51;

function treeLabel(tree) {
  const species = tree.species?.trim();
  return species ? `${species} · #${tree.external_id}` : `#${tree.external_id}`;
}

export default function LegacyImport() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [selection, setSelection] = useState(EMPTY_SELECTION);
  const [shapes, setShapes] = useState([]);
  const [selectionMode, setSelectionMode] = useState(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [datasetName, setDatasetName] = useState("");
  const [partitionBy, setPartitionBy] = useState("single");
  const [clusterCount, setClusterCount] = useState("2");
  const [importFilter, setImportFilter] = useState("all");
  const [datasetFilter, setDatasetFilter] = useState(new Set());

  const nextShapeId = useRef(1);
  const selectionModeRef = useRef(selectionMode);
  selectionModeRef.current = selectionMode;

  const toggleSelectionMode = (mode) =>
    setSelectionMode((current) => (current === mode ? null : mode));

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

  const treesByKey = useMemo(
    () => new Map((trees ?? []).map((tree) => [treeKey(tree), tree])),
    [trees],
  );

  const allDatasets = useMemo(() => {
    const seen = new Map();
    for (const tree of trees ?? []) {
      for (const ds of tree.datasets ?? []) {
        if (!seen.has(ds.id)) seen.set(ds.id, ds.name);
      }
    }
    return [...seen.entries()].map(([id, name]) => ({ id, name }));
  }, [trees]);

  const filteredTrees = useMemo(() => {
    let result = trees ?? [];
    if (importFilter === "available") result = result.filter((t) => !t.already_imported);
    else if (importFilter === "imported") result = result.filter((t) => t.already_imported);
    if (datasetFilter.size > 0) {
      result = result.filter((t) =>
        t.datasets?.some((d) => datasetFilter.has(d.id)),
      );
    }
    return result;
  }, [trees, importFilter, datasetFilter]);

  const keysByShape = useMemo(
    () => shapes.map((shape) => keysInRing(filteredTrees, shape.ring)),
    [filteredTrees, shapes],
  );

  const coveredKeys = useMemo(() => new Set(keysByShape.flat()), [keysByShape]);

  useEffect(() => {
    setSelection((prev) => pruneExclusions(prev, coveredKeys));
  }, [coveredKeys]);

  const selectedKeys = useMemo(
    () => resolveSelection({ coveredKeys, ...selection }),
    [coveredKeys, selection],
  );

  const coveredKeysRef = useRef(coveredKeys);
  coveredKeysRef.current = coveredKeys;

  const toggle = useCallback((keys) => {
    const coveredKeysNow = coveredKeysRef.current;
    setSelection((prev) => toggleKeys(prev, keys, coveredKeysNow));
  }, []);

  const handleToggleTree = useCallback(
    (tree) => {
      if (selectionModeRef.current) return;
      toggle(treeKeys([tree]));
    },
    [toggle],
  );

  const handleToggleArea = useCallback(
    (keys) => {
      if (selectionModeRef.current) return;
      toggle(keys);
    },
    [toggle],
  );

  const handleShapeCreate = useCallback((ring) => {
    setShapes((prev) => [...prev, { id: nextShapeId.current++, ring }]);
    setSelectionMode(null);
  }, []);

  const handleShapeChange = useCallback((id, ring) => {
    setShapes((prev) =>
      prev.map((shape) => (shape.id === id ? { ...shape, ring } : shape)),
    );
  }, []);

  const handleShapeRemove = (id) =>
    setShapes((prev) => prev.filter((shape) => shape.id !== id));

  const handleClear = () => {
    setShapes([]);
    setSelection(EMPTY_SELECTION);
    setSelectionMode(null);
  };

  const handleClearFilters = () => {
    setImportFilter("all");
    setDatasetFilter(new Set());
  };

  const filtersActive = importFilter !== "all" || datasetFilter.size > 0;

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

  const partitionDatasets = useMutation({
    mutationFn: partitionLegacySelection,
    onSuccess: (datasets) => {
      queryClient.invalidateQueries({ queryKey: ["datasets"] });
      queryClient.invalidateQueries({ queryKey: ["legacy-trees"] });
      const total = datasets.reduce(
        (sum, dataset) => sum + dataset.total_trees,
        0,
      );
      toast.success(
        `${datasets.length} datasets creados con ${total} árboles en total`,
      );
      navigate("/admin/datasets");
    },
    onError: (err) => {
      toast.error(getErrorMessage(err, "No se pudieron crear los datasets"));
    },
  });

  const reimportCount = useMemo(
    () =>
      [...selectedKeys].filter((key) => treesByKey.get(key)?.already_imported)
        .length,
    [selectedKeys, treesByKey],
  );

  const k = Number(clusterCount);
  const maxK = Math.floor(selectedKeys.size / MIN_TREES_PER_DATASET);
  const invalidK =
    partitionBy === "kmeans" && (!Number.isInteger(k) || k < 2 || k > maxK);
  const pending = createDataset.isPending || partitionDatasets.isPending;

  const handleConfirm = (event) => {
    event.preventDefault();
    const name = datasetName.trim();
    if (!name || selectedKeys.size === 0 || invalidK) return;
    const trees = selectionPayload(selectedKeys);
    if (partitionBy === "single") {
      createDataset.mutate({ name, trees });
      return;
    }
    partitionDatasets.mutate({ name, trees, k });
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
          variant={selectionMode === "bbox" ? "secondary" : "outline"}
          size="sm"
          className="ml-auto"
          onClick={() => toggleSelectionMode("bbox")}
        >
          ▭ Selección por rectángulo
        </Button>
        <Button
          variant={selectionMode === "polygon" ? "secondary" : "outline"}
          size="sm"
          onClick={() => toggleSelectionMode("polygon")}
        >
          ⬠ Selección por polígono
        </Button>
        <Button
          size="sm"
          disabled={selectedKeys.size === 0 || pending}
          onClick={() => {
            setPartitionBy("single");
            setDialogOpen(true);
          }}
        >
          Importar {selectedKeys.size > 0 ? `(${selectedKeys.size})` : ""}
        </Button>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>
            {getErrorMessage(
              error,
              "No se pudieron cargar los árboles legacy.",
            )}
          </AlertDescription>
        </Alert>
      )}

      <div className="flex flex-1 gap-4 overflow-hidden">
        <div className="flex flex-1 flex-col overflow-hidden rounded-md border">
          <div className="flex shrink-0 items-center gap-2 border-b px-3 py-2 text-sm">
            <select
              aria-label="Estado de importación"
              className="rounded border px-1 py-0.5 text-sm"
              value={importFilter}
              onChange={(e) => setImportFilter(e.target.value)}
            >
              <option value="all">Todos</option>
              <option value="available">Solo disponibles</option>
              <option value="imported">Solo ya importados</option>
            </select>
            {allDatasets.length > 0 && (
              <select
                aria-label="Dataset de origen"
                className="rounded border px-1 py-0.5 text-sm"
                multiple
                size={Math.min(allDatasets.length, 3)}
                value={[...datasetFilter]}
                onChange={(e) =>
                  setDatasetFilter(
                    new Set(
                      [...e.target.options]
                        .filter((o) => o.selected)
                        .map((o) => o.value),
                    ),
                  )
                }
              >
                {allDatasets.map((ds) => (
                  <option key={ds.id} value={ds.id}>
                    {ds.name}
                  </option>
                ))}
              </select>
            )}
            <span className="ml-auto text-muted-foreground">
              {filteredTrees.length} de {trees?.length ?? 0} árboles
            </span>
            {filtersActive && (
              <Button variant="ghost" size="sm" onClick={handleClearFilters}>
                Limpiar filtros
              </Button>
            )}
          </div>
          <div className="relative isolate flex-1 overflow-hidden">
            {treesLoading && (
              <div className="flex h-full items-center justify-center text-muted-foreground">
                Cargando árboles legacy…
              </div>
            )}
            {trees && (
              <LegacySelectionMap
                trees={filteredTrees}
                areas={areas ?? NO_AREAS}
                selectedKeys={selectedKeys}
                shapes={shapes}
                selectionMode={selectionMode}
                onToggleTree={handleToggleTree}
                onToggleArea={handleToggleArea}
                onShapeCreate={handleShapeCreate}
                onShapeChange={handleShapeChange}
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
                <span className="h-3 w-3 rounded-full bg-slate-400" /> Ya en otro
                dataset
              </span>
            </div>
            {(selectionMode || shapes.length > 0) && (
              <div className="absolute left-1/2 top-3 z-[1000] -translate-x-1/2 rounded-md border bg-background/90 px-3 py-1.5 text-sm shadow-md backdrop-blur">
                {selectionMode === "bbox" &&
                  "Arrastra un rectángulo para seleccionar"}
                {selectionMode === "polygon" &&
                  "Haz clic para marcar vértices y cierra sobre el primero"}
                {!selectionMode &&
                  "Arrastra un vértice para moverlo, clic en un punto medio para añadir, clic derecho para borrar"}
              </div>
            )}
          </div>
        </div>

        <aside className="flex w-72 shrink-0 flex-col rounded-md border bg-white">
          <div className="flex items-center justify-between border-b px-3 py-2">
            <span className="text-sm font-medium">
              {selectedKeys.size} seleccionados
            </span>
            {(selectedKeys.size > 0 || shapes.length > 0) && (
              <Button variant="ghost" size="sm" onClick={handleClear}>
                Limpiar
              </Button>
            )}
          </div>
          {shapes.length > 0 && (
            <ul className="border-b p-2">
              {shapes.map((shape, index) => (
                <li
                  key={shape.id}
                  className="flex items-center gap-2 rounded-md px-1 py-1 text-sm hover:bg-muted/50"
                >
                  <span className="truncate">
                    Polígono {index + 1} — {keysByShape[index].length} árboles
                  </span>
                  <button
                    type="button"
                    aria-label={`Borrar polígono ${index + 1}`}
                    className="ml-auto rounded px-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                    onClick={() => handleShapeRemove(shape.id)}
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          )}
          <ul className="flex-1 overflow-y-auto p-2">
            {selectedList.length === 0 && (
              <li className="px-1 py-2 text-sm text-muted-foreground">
                Haz clic en árboles, áreas o usa el rectángulo o el polígono
                para seleccionar.
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
                      setSelection((prev) =>
                        deselectKeys(prev, [key], coveredKeys),
                      )
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
              <DialogTitle>
                {partitionBy === "single" ? "Crear dataset" : "Crear datasets"}
              </DialogTitle>
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
            <fieldset className="grid gap-2">
              <legend className="mb-2 text-sm font-medium">Partición</legend>
              {[
                ["single", "Un solo dataset"],
                ["kmeans", "Dividir en k grupos por cercanía"],
              ].map(([value, label]) => (
                <Label
                  key={value}
                  htmlFor={`partition-${value}`}
                  className="flex items-center gap-2 font-normal"
                >
                  <input
                    id={`partition-${value}`}
                    type="radio"
                    name="partition-by"
                    value={value}
                    checked={partitionBy === value}
                    disabled={value === "kmeans" && maxK < 2}
                    onChange={() => setPartitionBy(value)}
                  />
                  {label}
                </Label>
              ))}
              {maxK < 2 && (
                <p className="text-sm text-muted-foreground">
                  La selección necesita al menos {MIN_TREES_PER_DATASET * 2}{" "}
                  árboles para dividirse: cada dataset debe alcanzar para una
                  jornada completa.
                </p>
              )}
            </fieldset>
            {partitionBy === "kmeans" && (
              <div className="grid gap-2">
                <Label htmlFor="cluster-count">Cantidad de grupos (k)</Label>
                <Input
                  id="cluster-count"
                  type="number"
                  min={2}
                  max={maxK}
                  value={clusterCount}
                  onChange={(event) => setClusterCount(event.target.value)}
                />
                {invalidK ? (
                  <p className="text-sm text-destructive">
                    k debe ser un entero entre 2 y {maxK}: cada dataset necesita
                    al menos {MIN_TREES_PER_DATASET} árboles.
                  </p>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    ≈ {Math.round(selectedKeys.size / k)} árboles por grupo.
                  </p>
                )}
              </div>
            )}
            <p className="text-sm text-muted-foreground">
              Se importarán {selectedKeys.size} árboles.
            </p>
            {reimportCount > 0 && (
              <p className="text-sm text-amber-600">
                {reimportCount} de {selectedKeys.size}{" "}
                {reimportCount === 1
                  ? "árbol ya pertenece"
                  : "árboles ya pertenecen"}{" "}
                a otro dataset.
              </p>
            )}
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
                disabled={!datasetName.trim() || invalidK || pending}
              >
                {pending
                  ? "Creando…"
                  : partitionBy === "single"
                    ? "Crear dataset"
                    : "Crear datasets"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
