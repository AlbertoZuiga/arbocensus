import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import SolutionCandidatesList from "./SolutionCandidatesList.jsx";
import {
  fetchSolutionsForDataset,
  publishSolution,
} from "@/api/optimization.js";

vi.mock("@/api/optimization.js", () => ({
  fetchSolutionsForDataset: vi.fn(),
  publishSolution: vi.fn(),
}));

function renderList(props) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <SolutionCandidatesList datasetId="d1" {...props} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const baseSolution = {
  id: "s1",
  job: "j1",
  strategy: "global",
  config_preset_label: "Equilibrada",
  total_routes: 3,
  total_travel_time_sec: 900,
  total_service_time_sec: 300,
  total_time_sec: 1200,
  balance_score: 0.8,
  balance_below_gate: false,
  dropped_trees: 0,
  degenerate_routes: 0,
  sum_max_radius_m: 100,
  interleave_total: 0,
  interleave_per_route: 0,
  worst_pair_iou: 0,
  generated_at: "2026-07-28T12:00:00Z",
  published_at: null,
  recommended: false,
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("SolutionCandidatesList", () => {
  it("renders nothing while there are no solutions", async () => {
    fetchSolutionsForDataset.mockResolvedValue([]);

    const { container } = renderList();

    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });

  it("marks the recommended candidate", async () => {
    fetchSolutionsForDataset.mockResolvedValue([
      { ...baseSolution, id: "s1", recommended: true },
      { ...baseSolution, id: "s2", strategy: "spatial_term" },
    ]);

    renderList();

    expect(await screen.findByText("★ Recomendada")).toBeInTheDocument();
    expect(screen.getByText(/Equilibrada · Global/)).toBeInTheDocument();
  });

  it("warns about dropped trees and degenerate routes", async () => {
    fetchSolutionsForDataset.mockResolvedValue([
      { ...baseSolution, dropped_trees: 2, degenerate_routes: 1 },
    ]);

    renderList();

    expect(
      await screen.findByText(/2 árboles fuera de ruta · 1 ruta muy corta/),
    ).toBeInTheDocument();
  });

  it("warns about balance from the backend gate, not from a local threshold", async () => {
    fetchSolutionsForDataset.mockResolvedValue([
      { ...baseSolution, balance_score: 0.9, balance_below_gate: true },
    ]);

    renderList();

    expect(
      await screen.findByText(/carga desbalanceada/),
    ).toBeInTheDocument();
  });

  it("hides candidates beyond the first three behind a toggle", async () => {
    fetchSolutionsForDataset.mockResolvedValue(
      ["s1", "s2", "s3", "s4"].map((id) => ({ ...baseSolution, id })),
    );

    renderList({ onViewSolution: vi.fn() });

    const toggle = await screen.findByRole("button", { name: "Ver 1 más" });
    expect(screen.getAllByText("Ver en el mapa")).toHaveLength(3);

    fireEvent.click(toggle);
    expect(screen.getAllByText("Ver en el mapa")).toHaveLength(4);
  });

  it("hides solutions from another sweep when viewedConfig is given", async () => {
    fetchSolutionsForDataset.mockResolvedValue([
      { ...baseSolution, id: "s1", config: "c2" },
      { ...baseSolution, id: "s2", config: "c1" },
    ]);

    renderList({ viewedConfig: "c2", onViewSolution: vi.fn() });

    await screen.findByText("Ver en el mapa");
    expect(screen.getAllByText("Ver en el mapa")).toHaveLength(1);
  });

  it("shows a sweep switcher and lets the admin pick a past sweep", async () => {
    fetchSolutionsForDataset.mockResolvedValue([
      { ...baseSolution, id: "s1", config: "c2" },
      { ...baseSolution, id: "s2", config: "c1" },
    ]);
    const sweeps = [
      { config: "c2", label: "28 jul 2026" },
      { config: "c1", label: "27 jul 2026" },
    ];

    renderList({
      viewedConfig: "c2",
      sweeps,
      onChangeViewedConfig: vi.fn(),
      onViewSolution: vi.fn(),
    });

    expect(
      await screen.findByRole("combobox", { name: "Corrida" }),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Ver en el mapa")).toHaveLength(1);
  });

  it("hands the picked candidate back for map viewing", async () => {
    fetchSolutionsForDataset.mockResolvedValue([baseSolution]);
    const onViewSolution = vi.fn();

    renderList({ onViewSolution });

    fireEvent.click(await screen.findByText("Ver en el mapa"));
    expect(onViewSolution).toHaveBeenCalledWith(
      expect.objectContaining({ id: "s1", job: "j1", strategy: "global" }),
    );
  });

  it("publishes without confirmation when no plan is published yet", async () => {
    fetchSolutionsForDataset.mockResolvedValue([baseSolution]);
    publishSolution.mockResolvedValue({});

    renderList();

    fireEvent.click(await screen.findByText("Publicar"));
    await waitFor(() => expect(publishSolution).toHaveBeenCalledWith("s1"));
  });

  it("asks for confirmation before replacing a published plan", async () => {
    fetchSolutionsForDataset.mockResolvedValue([
      { ...baseSolution, id: "s1" },
      { ...baseSolution, id: "s2", published_at: "2026-07-28T13:00:00Z" },
    ]);
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);

    renderList();

    fireEvent.click(await screen.findByText("Publicar"));
    expect(confirm).toHaveBeenCalled();
    expect(publishSolution).not.toHaveBeenCalled();
    confirm.mockRestore();
  });
});
