import { useRef } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchDatasets, uploadDataset } from "@/api/datasets.js";
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

  const { data, isLoading, error } = useQuery({
    queryKey: ["datasets"],
    queryFn: fetchDatasets,
  });

  const upload = useMutation({
    mutationFn: uploadDataset,
    onSuccess: (dataset) => {
      queryClient.invalidateQueries({ queryKey: ["datasets"] });
      toast.success(`Importados ${treeCount(dataset)} árboles`);
    },
    onError: (err) => {
      toast.error(err.response?.data?.detail ?? "No se pudo importar el CSV");
    },
    onSettled: () => {
      if (fileInputRef.current) fileInputRef.current.value = "";
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
          <Input
            ref={fileInputRef}
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            onChange={handleFileChange}
            aria-label="Subir CSV"
          />
          <Button
            onClick={() => fileInputRef.current?.click()}
            disabled={upload.isPending}
          >
            {upload.isPending ? "Importando…" : "Subir CSV"}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading && <p className="text-muted-foreground">Cargando…</p>}
        {error && (
          <Alert variant="destructive">
            <AlertDescription>
              No se pudieron cargar los datasets: {error.message}
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
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
