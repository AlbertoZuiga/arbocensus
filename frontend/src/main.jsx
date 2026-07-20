import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { PersistQueryClientProvider } from "@tanstack/react-query-persist-client";
import { createSyncStoragePersister } from "@tanstack/query-sync-storage-persister";
import { BrowserRouter } from "react-router-dom";
import App from "./App.jsx";
import {
  createAppQueryClient,
  dehydrateOptions,
  DAY_MS,
  PERSIST_KEY,
} from "./lib/queryClient.js";
import "./index.css";

const queryClient = createAppQueryClient();

const persister = createSyncStoragePersister({
  storage: window.localStorage,
  key: PERSIST_KEY,
});

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <PersistQueryClientProvider
      client={queryClient}
      persistOptions={{
        persister,
        maxAge: DAY_MS,
        buster: "v1",
        dehydrateOptions,
      }}
      onSuccess={() => queryClient.resumePausedMutations()}
    >
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </PersistQueryClientProvider>
  </StrictMode>
);
