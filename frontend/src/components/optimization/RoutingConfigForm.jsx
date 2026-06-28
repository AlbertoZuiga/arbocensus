import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { createJob } from "@/api/optimization";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const DEFAULTS = {
  minRouteTimeHours: 2,
  maxRouteTimeHours: 3,
  serviceTimeSec: 300,
};

const hoursToSeconds = (hours) => Math.round(Number(hours) * 3600);

export default function RoutingConfigForm({ datasetId, onJobCreated }) {
  const [minRouteTimeHours, setMinRouteTimeHours] = useState(
    DEFAULTS.minRouteTimeHours
  );
  const [maxRouteTimeHours, setMaxRouteTimeHours] = useState(
    DEFAULTS.maxRouteTimeHours
  );
  const [serviceTimeSec, setServiceTimeSec] = useState(
    DEFAULTS.serviceTimeSec
  );

  const mutation = useMutation({
    mutationFn: () =>
      createJob({
        dataset: datasetId,
        minRouteTimeSec: hoursToSeconds(minRouteTimeHours),
        maxRouteTimeSec: hoursToSeconds(maxRouteTimeHours),
        serviceTimeSec: Number(serviceTimeSec),
      }),
    onSuccess: (job) => {
      onJobCreated?.(job);
    },
  });

  const handleSubmit = (event) => {
    event.preventDefault();
    mutation.mutate();
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Configuración de rutas</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="min-route-time">Tiempo mínimo por ruta (h)</Label>
            <Input
              id="min-route-time"
              type="number"
              min="0"
              step="0.25"
              value={minRouteTimeHours}
              onChange={(e) => setMinRouteTimeHours(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="max-route-time">Tiempo máximo por ruta (h)</Label>
            <Input
              id="max-route-time"
              type="number"
              min="0"
              step="0.25"
              value={maxRouteTimeHours}
              onChange={(e) => setMaxRouteTimeHours(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="service-time">Tiempo de servicio (s)</Label>
            <Input
              id="service-time"
              type="number"
              min="0"
              step="1"
              value={serviceTimeSec}
              onChange={(e) => setServiceTimeSec(e.target.value)}
            />
          </div>

          {mutation.isError && (
            <p className="text-sm text-destructive">
              {mutation.error?.response?.data?.detail ??
                "No se pudo crear el trabajo de optimización"}
            </p>
          )}

          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? "Generando…" : "Generar rutas"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
