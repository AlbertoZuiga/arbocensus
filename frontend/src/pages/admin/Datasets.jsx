import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { deleteDataset, fetchDatasets, uploadDataset } from "@/api/datasets.js";
import { getErrorMessage } from "@/lib/errors";
import { toast } from "@/store/toastStore.js";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

function formatDate(value) {
  if (!value) return "—";
  return new Date(value).toLocaleString("es-CL");
}

function treeCount(dataset) {
  return dataset.tree_count ?? dataset.total_trees ?? 0;
}

export default function Datasets() {
  const queryClient = useQueryClient();
  const fileInputRef = useRef(null);
  const [datasetToDelete, setDatasetToDelete] = useState(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["datasets"],
    queryFn: fetchDatasets,
  });

  const upload = useMutation({
    mutationFn: uploadDataset,
    onSuccess: (dataset) => {
      queryClient.invalidateQueries({ queryKey: ["datasets"] });
      const imported = treeCount(dataset);
      const skipped = dataset.skipped_rows ?? 0;
      toast.success(
        skipped > 0
          ? `${imported} importados (${skipped} filas sin coordenadas)`
          : `Importados ${imported} árboles`,
      );
    },
    onError: (err) => {
      toast.error(getErrorMessage(err, "No se pudo importar el archivo"));
    },
    onSettled: () => {
      if (fileInputRef.current) fileInputRef.current.value = "";
    },
  });

  const remove = useMutation({
    mutationFn: deleteDataset,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["datasets"] });
      toast.success("Dataset eliminado");
    },
    onError: (err) => {
      toast.error(getErrorMessage(err, "No se pudo eliminar el dataset"));
    },
    onSettled: () => {
      setDatasetToDelete(null);
    },
  });

  const handleFileChange = (event) => {
    const file = event.target.files?.[0];
    if (file) upload.mutate(file);
  };

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle className="text-2xl">Datasets</CardTitle>
        <div className="flex items-center gap-2">
          <Button variant="outline" asChild>
            <Link to="/admin/datasets/legacy-import">
              Importar desde Arbocensus
            </Link>
          </Button>
          <Input
            ref={fileInputRef}
            type="file"
            accept=".csv,.json,text/csv,application/json"
            className="hidden"
            onChange={handleFileChange}
            aria-label="Subir archivo"
          />
          <Button
            onClick={() => fileInputRef.current?.click()}
            disabled={upload.isPending}
          >
            {upload.isPending ? "Importando…" : "Subir archivo"}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading && <p className="text-muted-foreground">Cargando…</p>}
        {error && (
          <Alert variant="destructive">
            <AlertDescription>
              {getErrorMessage(error, "No se pudieron cargar los datasets.")}
            </AlertDescription>
          </Alert>
        )}
        {data && data.length === 0 && (
          <p className="text-muted-foreground">Aún no hay datasets.</p>
        )}
        {data && data.length > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Nombre</TableHead>
                <TableHead>Árboles</TableHead>
                <TableHead>Importado</TableHead>
                <TableHead className="text-right">Acciones</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((dataset) => (
                <TableRow key={dataset.id}>
                  <TableCell className="font-medium">
                    <Link
                      to={`/admin/datasets/${dataset.id}`}
                      className="text-primary hover:underline"
                    >
                      {dataset.name}
                    </Link>
                  </TableCell>
                  <TableCell>{treeCount(dataset)}</TableCell>
                  <TableCell>{formatDate(dataset.imported_at)}</TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => setDatasetToDelete(dataset)}
                    >
                      Eliminar
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
      <Dialog
        open={!!datasetToDelete}
        onOpenChange={(open) => !open && setDatasetToDelete(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Eliminar dataset</DialogTitle>
            <DialogDescription>
              ¿Eliminar &quot;{datasetToDelete?.name}&quot;? Se eliminarán también sus
              árboles y optimizaciones asociadas. Esta acción no se puede
              deshacer.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDatasetToDelete(null)}
              disabled={remove.isPending}
            >
              Cancelar
            </Button>
            <Button
              variant="destructive"
              onClick={() => remove.mutate(datasetToDelete.id)}
              disabled={remove.isPending}
            >
              {remove.isPending ? "Eliminando…" : "Eliminar"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
