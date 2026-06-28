import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Datasets from "./Datasets.jsx";
import { Toaster } from "@/components/ui/toaster";
import { fetchDatasets, uploadDataset } from "@/api/datasets.js";

vi.mock("@/api/datasets.js", () => ({
  fetchDatasets: vi.fn(),
  uploadDataset: vi.fn(),
}));

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Datasets />
        <Toaster />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  fetchDatasets.mockReset();
  uploadDataset.mockReset();
});

describe("Datasets", () => {
  it("renders a row per dataset linking to its detail page", async () => {
    fetchDatasets.mockResolvedValue([
      {
        id: "d1",
        name: "Providencia 2025",
        tree_count: 42,
        imported_at: "2025-06-01T10:00:00Z",
      },
    ]);
    renderPage();

    const link = await screen.findByRole("link", { name: "Providencia 2025" });
    expect(link).toHaveAttribute("href", "/admin/datasets/d1");
    expect(screen.getByText("42")).toBeInTheDocument();
  });

  it("falls back to total_trees when tree_count is absent", async () => {
    fetchDatasets.mockResolvedValue([
      { id: "d2", name: "Ñuñoa", total_trees: 7, imported_at: null },
    ]);
    renderPage();

    expect(await screen.findByText("7")).toBeInTheDocument();
  });

  it("shows an empty message when there are no datasets", async () => {
    fetchDatasets.mockResolvedValue([]);
    renderPage();

    expect(await screen.findByText("Aún no hay datasets.")).toBeInTheDocument();
  });

  it("shows an error alert when the request fails", async () => {
    fetchDatasets.mockRejectedValue(new Error("boom"));
    renderPage();

    await waitFor(() =>
      expect(screen.getByText(/No se pudieron cargar/)).toBeInTheDocument(),
    );
  });

  it("uploads a CSV and shows a toast with the imported tree count", async () => {
    const user = userEvent.setup();
    fetchDatasets.mockResolvedValue([]);
    uploadDataset.mockResolvedValue({ id: "d9", name: "Nuevo", tree_count: 128 });
    renderPage();

    const file = new File(["lat,lon\n1,2"], "trees.csv", { type: "text/csv" });
    await user.upload(screen.getByLabelText("Subir CSV"), file);

    expect(uploadDataset.mock.calls[0][0]).toBe(file);
    expect(
      await screen.findByText("Importados 128 árboles"),
    ).toBeInTheDocument();
  });
});
