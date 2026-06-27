import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export default function AdminHome() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-2xl">Panel de administración</CardTitle>
      </CardHeader>
      <CardContent>
        <Button asChild>
          <Link to="/admin/datasets">Ir a Datasets</Link>
        </Button>
      </CardContent>
    </Card>
  );
}
