import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import client from "../api/client.js";
import { useAuthStore } from "../store/authStore.js";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";

export default function Login() {
  const navigate = useNavigate();
  const setTokens = useAuthStore((state) => state.setTokens);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const mutation = useMutation({
    mutationFn: async (credentials) => {
      const { data } = await client.post("/auth/token/", credentials);
      return data;
    },
    onSuccess: (data) => {
      setTokens({ access: data.access, refresh: data.refresh });
      navigate("/");
    },
  });

  const handleSubmit = (event) => {
    event.preventDefault();
    mutation.mutate({ username, password });
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <Card className="w-80">
        <CardHeader>
          <CardTitle className="text-2xl text-primary">Arbocensus</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="username">Usuario</Label>
              <Input
                id="username"
                type="text"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                placeholder="Usuario"
                autoComplete="username"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="password">Contraseña</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Contraseña"
                autoComplete="current-password"
              />
            </div>
            {mutation.isError && (
              <Alert variant="destructive">
                <AlertDescription>
                  Usuario o contraseña incorrectos.
                </AlertDescription>
              </Alert>
            )}
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "Ingresando…" : "Ingresar"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}
