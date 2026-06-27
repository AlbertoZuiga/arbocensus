import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import client from "../api/client.js";
import { useAuthStore } from "../store/authStore.js";

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
    <main className="flex min-h-screen items-center justify-center bg-slate-50">
      <form
        onSubmit={handleSubmit}
        className="flex w-80 flex-col gap-4 rounded-lg bg-white p-8 shadow"
      >
        <h1 className="text-2xl font-bold text-emerald-700">Arbocensus</h1>
        <input
          type="text"
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          placeholder="Usuario"
          autoComplete="username"
          className="rounded border border-slate-300 px-3 py-2"
        />
        <input
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          placeholder="Contraseña"
          autoComplete="current-password"
          className="rounded border border-slate-300 px-3 py-2"
        />
        {mutation.isError && (
          <p className="text-sm text-red-600">
            Usuario o contraseña incorrectos.
          </p>
        )}
        <button
          type="submit"
          disabled={mutation.isPending}
          className="rounded bg-emerald-700 py-2 font-semibold text-white disabled:opacity-50"
        >
          {mutation.isPending ? "Ingresando…" : "Ingresar"}
        </button>
      </form>
    </main>
  );
}
