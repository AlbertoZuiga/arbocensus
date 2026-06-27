import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient } from "@tanstack/react-query";
import { PersistQueryClientProvider } from "@tanstack/react-query-persist-client";
import { createSyncStoragePersister } from "@tanstack/query-sync-storage-persister";
import { BrowserRouter } from "react-router-dom";
import App from "./App.jsx";
import { visitStop } from "./api/routes.js";
import "./index.css";

const DAY_MS = 1000 * 60 * 60 * 24;

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      gcTime: DAY_MS,
      staleTime: 1000 * 30,
    },
  },
});

queryClient.setMutationDefaults(["visitStop"], {
  mutationFn: (stopId) => visitStop(stopId),
});

const persister = createSyncStoragePersister({
  storage: window.localStorage,
  key: "arbocensus.query-cache",
});

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <PersistQueryClientProvider
      client={queryClient}
      persistOptions={{ persister, maxAge: DAY_MS }}
      onSuccess={() => queryClient.resumePausedMutations()}
    >
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </PersistQueryClientProvider>
  </StrictMode>
);
