import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { PersistQueryClientProvider } from "@tanstack/react-query-persist-client";
import { BrowserRouter } from "react-router-dom";
import App from "./App.jsx";
import {
  createAppQueryClient,
  dehydrateOptions,
  DAY_MS,
  PERSIST_KEY,
} from "./lib/queryClient.js";
import { createIdbPersister } from "./lib/idbPersister.js";
import "./index.css";

const queryClient = createAppQueryClient();

const persister = createIdbPersister(PERSIST_KEY);

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
