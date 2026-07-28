import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import SolutionsComparisonTable from "./SolutionsComparisonTable.jsx";
import {
  fetchSolutionsForDataset,
  publishSolution,
} from "@/api/optimization.js";

vi.mock("@/api/optimization.js", () => ({
  fetchSolutionsForDataset: vi.fn(),
  publishSolution: vi.fn(),
}));

function renderTable(props) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <SolutionsComparisonTable datasetId="d1" {...props} />
    </QueryClientProvider>,
  );
}

const baseSolution = {
  id: "s1",
  strategy: "global",
  config_preset_label: "Producción (default)",
  total_routes: 3,
  total_travel_time_sec: 900,
  total_service_time_sec: 300,
  total_time_sec: 1200,
  balance_score: 0.8,
  dropped_trees: 0,
  degenerate_routes: 0,
  sum_max_radius_m: 100,
  interleave_total: 0,
  interleave_per_route: 0,
  worst_pair_iou: 0,
  published_at: null,
  recommended: false,
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("SolutionsComparisonTable", () => {
  it("renders nothing while there are no solutions", async () => {
    fetchSolutionsForDataset.mockResolvedValue([]);

    const { container } = renderTable();

    await waitFor(() => expect(fetchSolutionsForDataset).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("highlights the recommended solution among the full comparison", async () => {
    fetchSolutionsForDataset.mockResolvedValue([
      { ...baseSolution, id: "s1", total_travel_time_sec: 900 },
      {
        ...baseSolution,
        id: "s2",
        strategy: "spatial_term",
        total_travel_time_sec: 100,
        recommended: true,
      },
    ]);

    renderTable();

    expect(await screen.findByText("★ Recomendada")).toBeInTheDocument();
  });

  it("publishes the chosen solution when its button is clicked", async () => {
    fetchSolutionsForDataset.mockResolvedValue([
      { ...baseSolution, id: "s1" },
    ]);
    publishSolution.mockResolvedValue({ id: "s1", published_at: "now" });

    renderTable();

    const button = await screen.findByRole("button", { name: "Publicar" });
    fireEvent.click(button);

    await waitFor(() => expect(publishSolution).toHaveBeenCalledWith("s1"));
  });

  it("shows a published badge instead of a button for the published solution", async () => {
    fetchSolutionsForDataset.mockResolvedValue([
      { ...baseSolution, id: "s1", published_at: "2026-01-01" },
    ]);

    renderTable();

    expect(await screen.findByText("✓ Publicada")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Publicar" }),
    ).not.toBeInTheDocument();
  });

  it("confirms before replacing an already published plan", async () => {
    fetchSolutionsForDataset.mockResolvedValue([
      { ...baseSolution, id: "s1", published_at: null },
      { ...baseSolution, id: "s2", published_at: "2026-01-01" },
    ]);
    vi.spyOn(window, "confirm").mockReturnValue(false);

    renderTable();

    const buttons = await screen.findAllByRole("button", { name: "Publicar" });
    fireEvent.click(buttons[0]);

    expect(window.confirm).toHaveBeenCalledWith(
      expect.stringContaining("reemplazará el plan vigente"),
    );
    expect(publishSolution).not.toHaveBeenCalled();
  });
});
