import { useQuery } from "@tanstack/react-query";
import { fetchSurveyors } from "@/api/surveyors.js";
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
  return name || surveyor.username;
}

export default function Censadores() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["surveyors"],
    queryFn: fetchSurveyors,
  });

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
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((surveyor) => (
                <TableRow key={surveyor.id}>
                  <TableCell className="font-medium">
                    {fullName(surveyor)}
                  </TableCell>
                  <TableCell>{surveyor.email || "—"}</TableCell>
                  <TableCell>{surveyor.role_display ?? surveyor.role}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
