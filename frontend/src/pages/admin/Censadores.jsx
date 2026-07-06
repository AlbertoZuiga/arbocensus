import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchSurveyors } from "@/api/surveyors.js";
import { fetchRoutes } from "@/api/routes.js";
import { getErrorMessage } from "@/lib/errors";
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

function fullName(surveyor) {
  const name = [surveyor.first_name, surveyor.last_name]
    .filter(Boolean)
    .join(" ")
    .trim();
  return name || surveyor.username || "—";
}

export default function Censadores() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["surveyors"],
    queryFn: fetchSurveyors,
  });

  const { data: routes = [] } = useQuery({
    queryKey: ["routes", "assigned"],
    queryFn: () => fetchRoutes(),
  });

  const routeBySurveyor = useMemo(() => {
    const map = new Map();
    for (const route of routes) {
      if (route.surveyor) map.set(route.surveyor, route);
    }
    return map;
  }, [routes]);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-2xl">Censadores</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading && <p className="text-muted-foreground">Cargando…</p>}
        {error && (
          <Alert variant="destructive">
            <AlertDescription>
              {getErrorMessage(error, "No se pudieron cargar los censadores.")}
            </AlertDescription>
          </Alert>
        )}
        {data && data.length === 0 && (
          <p className="text-muted-foreground">Aún no hay censadores.</p>
        )}
        {data && data.length > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Nombre</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Rol</TableHead>
                <TableHead>Ruta asignada</TableHead>
                <TableHead>Progreso</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((surveyor) => {
                const route = routeBySurveyor.get(surveyor.id);
                const total = route
                  ? route.visited_count + route.pending_count
                  : 0;
                return (
                  <TableRow key={surveyor.id}>
                    <TableCell className="font-medium">
                      {fullName(surveyor)}
                    </TableCell>
                    <TableCell>{surveyor.email || "—"}</TableCell>
                    <TableCell>{surveyor.role_display}</TableCell>
                    <TableCell>
                      {route ? `Ruta ${route.route_number}` : "—"}
                    </TableCell>
                    <TableCell>
                      {route
                        ? `${route.visited_count}/${total} visitados`
                        : "—"}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
