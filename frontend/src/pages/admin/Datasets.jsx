import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchDatasets } from "@/api/datasets.js";
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

function formatDate(value) {
  if (!value) return "—";
  return new Date(value).toLocaleString("es-CL");
}

function treeCount(dataset) {
  return dataset.tree_count ?? dataset.total_trees ?? 0;
}

export default function Datasets() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["datasets"],
    queryFn: fetchDatasets,
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-2xl">Datasets</CardTitle>
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
