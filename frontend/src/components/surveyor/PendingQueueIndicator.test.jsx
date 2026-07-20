import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClientProvider, onlineManager } from "@tanstack/react-query";
import { createAppQueryClient } from "../../lib/queryClient.js";
import PendingQueueIndicator from "./PendingQueueIndicator.jsx";

vi.mock("../../api/client.js", () => ({
  default: { post: vi.fn(() => Promise.resolve({ data: {} })) },
}));

function renderIndicator(queryClient) {
  return render(
    <QueryClientProvider client={queryClient}>
      <PendingQueueIndicator />
    </QueryClientProvider>
  );
}

function queueVisit(queryClient, stopId) {
  const mutation = queryClient
    .getMutationCache()
    .build(queryClient, { mutationKey: ["visitStop"] });
  return mutation.execute({ stopId, status: "alive" });
}

function goOffline() {
  vi.spyOn(navigator, "onLine", "get").mockReturnValue(false);
  onlineManager.setOnline(false);
}

afterEach(() => {
  vi.restoreAllMocks();
  onlineManager.setOnline(true);
});

describe("PendingQueueIndicator", () => {
  it("stays hidden while online with nothing queued", () => {
    const { container } = renderIndicator(createAppQueryClient());
    expect(container).toBeEmptyDOMElement();
  });

  it("counts the observations waiting for signal", async () => {
    goOffline();
    const queryClient = createAppQueryClient();
    queueVisit(queryClient, "stop-1");
    queueVisit(queryClient, "stop-2");

    renderIndicator(queryClient);

    await waitFor(() => {
      expect(
        screen.getByText("Sin conexión · 2 observaciones en espera")
      ).toBeInTheDocument();
    });
  });

  it("ignores paused mutations that are not observations", () => {
    goOffline();
    const queryClient = createAppQueryClient();
    queryClient
      .getMutationCache()
      .build(queryClient, {
        mutationKey: ["assignRoute"],
        mutationFn: () => Promise.resolve({}),
      })
      .execute({});

    renderIndicator(queryClient);

    expect(
      screen.getByText("Sin conexión · se guardará en el dispositivo")
    ).toBeInTheDocument();
  });

  it("announces the offline state even with an empty queue", () => {
    goOffline();
    renderIndicator(createAppQueryClient());

    expect(
      screen.getByText("Sin conexión · se guardará en el dispositivo")
    ).toBeInTheDocument();
  });
});
