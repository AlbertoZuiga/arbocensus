import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClientProvider, dehydrate, hydrate, onlineManager } from "@tanstack/react-query";
import { createAppQueryClient, dehydrateOptions } from "../lib/queryClient.js";
import { useVisitStop } from "./useVisitStop.js";
import { useSkipStop } from "./useSkipStop.js";
import client from "../api/client.js";

vi.mock("../api/client.js", () => ({
  default: { post: vi.fn(() => Promise.resolve({ data: {} })) },
}));

const STOP_ID = "3f2b1c66-0000-4000-8000-000000000001";
const POSITION = { lat: -33.4569, lon: -70.6483 };

function wrapper(queryClient) {
  return function Wrapper({ children }) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  };
}

function formEntries(body) {
  if (body instanceof FormData) return Object.fromEntries(body.entries());
  return body;
}

async function queuePausedMutation(hookFactory, variables) {
  const queryClient = createAppQueryClient();
  const { result, unmount } = renderHook(hookFactory, {
    wrapper: wrapper(queryClient),
  });

  result.current.mutate(variables);

  await waitFor(() => {
    expect(queryClient.getMutationCache().getAll()).toHaveLength(1);
    expect(queryClient.getMutationCache().getAll()[0].state.isPaused).toBe(true);
  });

  const dehydrated = dehydrate(queryClient, dehydrateOptions);

  unmount();
  queryClient.getMutationCache().clear();
  queryClient.clear();

  return dehydrated;
}

async function resume(dehydrated) {
  const restored = createAppQueryClient();
  hydrate(restored, dehydrated);
  onlineManager.setOnline(true);
  await restored.resumePausedMutations();
  return restored;
}

describe("offline mutation queue", () => {
  beforeEach(() => {
    client.post.mockClear();
    onlineManager.setOnline(false);
  });

  afterEach(() => {
    onlineManager.setOnline(true);
  });

  it("resumes a paused visit with the real stop id and the full observation", async () => {
    const photo = new File(["jpeg-bytes"], "tree.jpg", { type: "image/jpeg" });
    const dehydrated = await queuePausedMutation(
      () => useVisitStop("route-1", POSITION),
      { stopId: STOP_ID, status: "alive", notes: "árbol sano", photo }
    );

    await resume(dehydrated);

    expect(client.post).toHaveBeenCalledTimes(1);
    const [url, body] = client.post.mock.calls[0];
    expect(url).toBe(`/routes/stops/${STOP_ID}/visit/`);

    const fields = formEntries(body);
    expect(fields.status).toBe("alive");
    expect(fields.notes).toBe("árbol sano");
    expect(fields.photo).toBeInstanceOf(File);
    expect(Number(fields.lat)).toBeCloseTo(POSITION.lat);
    expect(Number(fields.lon)).toBeCloseTo(POSITION.lon);
  });

  it("resumes a paused skip with the real stop id and its reason", async () => {
    const dehydrated = await queuePausedMutation(() => useSkipStop("route-1"), {
      stopId: STOP_ID,
      reason: "Acceso bloqueado",
      status: "blocked",
      notes: "reja cerrada",
    });

    await resume(dehydrated);

    expect(client.post).toHaveBeenCalledTimes(1);
    const [url, body] = client.post.mock.calls[0];
    expect(url).toBe(`/routes/stops/${STOP_ID}/skip/`);

    const fields = formEntries(body);
    expect(fields.reason).toBe("Acceso bloqueado");
    expect(fields.status).toBe("blocked");
    expect(fields.notes).toBe("reja cerrada");
  });
});
