import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("@/api/datasets.js", () => ({
  fetchTreeObservations: vi.fn(),
}));

import { fetchTreeObservations } from "@/api/datasets.js";
import TreeHistoryPopup from "./TreeHistoryPopup.jsx";

function renderPopup(treeId = "t1") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <TreeHistoryPopup treeId={treeId} />
    </QueryClientProvider>,
  );
}

describe("TreeHistoryPopup", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders each observation with date, status, source, notes and author", async () => {
    fetchTreeObservations.mockResolvedValue([
      {
        id: "o1",
        status: "alive",
        source: "legacy_api",
        photo: "",
        photo_url: "https://example.com/photo.jpg",
        notes: "Poda pendiente",
        created_by_username: "ana",
        observed_at: "2026-05-01T10:00:00Z",
      },
    ]);
    const { container } = renderPopup();

    expect(await screen.findByText("Vivo")).toBeInTheDocument();
    expect(screen.getByText("API")).toBeInTheDocument();
    expect(screen.getByText("Poda pendiente")).toBeInTheDocument();
    expect(screen.getByText("por ana")).toBeInTheDocument();
    expect(screen.getByText("1 observación")).toBeInTheDocument();
    expect(container.querySelector("img")).toHaveAttribute(
      "src",
      "https://example.com/photo.jpg",
    );
    expect(container.querySelector("a")).toHaveAttribute(
      "href",
      "https://example.com/photo.jpg",
    );
  });

  it("shows an empty state when there are no observations", async () => {
    fetchTreeObservations.mockResolvedValue([]);
    renderPopup();

    expect(
      await screen.findByText(
        "Este árbol aún no tiene observaciones registradas.",
      ),
    ).toBeInTheDocument();
  });

  it("shows a loading placeholder while the history is fetched", () => {
    fetchTreeObservations.mockReturnValue(new Promise(() => {}));
    renderPopup();

    expect(screen.getByLabelText("Cargando historial")).toBeInTheDocument();
  });

  it("labels a blank source as field-collected", async () => {
    fetchTreeObservations.mockResolvedValue([
      {
        id: "o1",
        status: "removed",
        source: "",
        photo: "",
        photo_url: "",
        observed_at: "2026-05-01T10:00:00Z",
      },
    ]);
    renderPopup();

    expect(await screen.findByText("Campo")).toBeInTheDocument();
  });
});
