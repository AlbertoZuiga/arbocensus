import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("@/api/routes.js", () => ({
  fetchRoutes: vi.fn(),
  fetchWorkload: vi.fn(),
  suggestAssignment: vi.fn(),
}));

vi.mock("@/api/optimization.js", () => ({
  fetchSolution: vi.fn(),
}));

vi.mock("@/api/surveyors.js", () => ({
  fetchSurveyors: vi.fn(),
}));

const mockAssignMutate = vi.fn();
vi.mock("@/hooks/useAssignRoute", () => ({
  useAssignRoute: () => ({ mutate: mockAssignMutate }),
}));

import { fetchRoutes, fetchWorkload, suggestAssignment } from "@/api/routes.js";
import { fetchSolution } from "@/api/optimization.js";
import { fetchSurveyors } from "@/api/surveyors.js";
import RouteAssignmentPanel from "./RouteAssignmentPanel.jsx";

const SOLUTION_ID = "sol-aaaa-1111";
const ROUTE_ID = "route-bbbb-2222";
const SURVEYOR_ID = "surv-cccc-3333";

const SOLUTION = { id: SOLUTION_ID, published_at: "2026-01-01T00:00:00Z" };
const ROUTES = [
  {
    id: ROUTE_ID,
    route_number: 1,
    total_trees: 3,
    surveyor: null,
    visited_count: 0,
    pending_count: 3,
    skipped_count: 0,
    travel_time_sec: 600,
    total_service_time_sec: 900,
    total_estimated_time_sec: 1500,
  },
];
const SURVEYORS = [
  { id: SURVEYOR_ID, username: "ana", first_name: "Ana", last_name: "" },
];
const WORKLOAD = [
  {
    surveyor_id: SURVEYOR_ID,
    username: "ana",
    total_utilization: 1.5,
    census_count: 2,
    cumulative_deficit: 0.3,
  },
];
const SUGGESTION = {
  assignments: [
    {
      route_id: ROUTE_ID,
      route_number: 1,
      surveyor_id: SURVEYOR_ID,
      utilization: 0.42,
    },
  ],
  balance: { [SURVEYOR_ID]: -0.12 },
};

function renderPanel() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <RouteAssignmentPanel datasetSolutionIds={[SOLUTION_ID]} />
    </QueryClientProvider>,
  );
}

describe("RouteAssignmentPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchSolution.mockResolvedValue(SOLUTION);
    fetchRoutes.mockResolvedValue(ROUTES);
    fetchSurveyors.mockResolvedValue(SURVEYORS);
    fetchWorkload.mockResolvedValue(WORKLOAD);
  });

  it("shows participant checkboxes when solution is published", async () => {
    renderPanel();
    await waitFor(() =>
      expect(screen.getByRole("checkbox", { name: "Ana" })).toBeInTheDocument(),
    );
  });

  it("suggest button disabled until participant selected", async () => {
    renderPanel();
    await waitFor(() =>
      expect(screen.getByRole("checkbox", { name: "Ana" })).toBeInTheDocument(),
    );
    expect(screen.getByText("Sugerir asignación")).toBeDisabled();

    await userEvent.click(screen.getByRole("checkbox", { name: "Ana" }));
    expect(screen.getByText("Sugerir asignación")).not.toBeDisabled();
  });

  it("sugerir calls API and shows confirm/discard without persisting", async () => {
    suggestAssignment.mockResolvedValue(SUGGESTION);
    renderPanel();

    await waitFor(() =>
      expect(screen.getByRole("checkbox", { name: "Ana" })).toBeInTheDocument(),
    );
    await userEvent.click(screen.getByRole("checkbox", { name: "Ana" }));
    await userEvent.click(screen.getByText("Sugerir asignación"));

    await waitFor(() =>
      expect(screen.getByText("Confirmar")).toBeInTheDocument(),
    );
    expect(screen.getByText("Descartar")).toBeInTheDocument();
    expect(mockAssignMutate).not.toHaveBeenCalled();
    expect(suggestAssignment).toHaveBeenCalledWith(SOLUTION_ID, [SURVEYOR_ID]);
  });

  it("confirmar dispara assign.mutate para cada ruta sugerida", async () => {
    suggestAssignment.mockResolvedValue(SUGGESTION);
    renderPanel();

    await waitFor(() =>
      expect(screen.getByRole("checkbox", { name: "Ana" })).toBeInTheDocument(),
    );
    await userEvent.click(screen.getByRole("checkbox", { name: "Ana" }));
    await userEvent.click(screen.getByText("Sugerir asignación"));
    await waitFor(() =>
      expect(screen.getByText("Confirmar")).toBeInTheDocument(),
    );

    await userEvent.click(screen.getByText("Confirmar"));

    expect(mockAssignMutate).toHaveBeenCalledWith({
      routeId: ROUTE_ID,
      surveyorId: SURVEYOR_ID,
    });
    await waitFor(() =>
      expect(screen.queryByText("Confirmar")).not.toBeInTheDocument(),
    );
  });

  it("descartar oculta confirm/discard sin llamar mutate", async () => {
    suggestAssignment.mockResolvedValue(SUGGESTION);
    renderPanel();

    await waitFor(() =>
      expect(screen.getByRole("checkbox", { name: "Ana" })).toBeInTheDocument(),
    );
    await userEvent.click(screen.getByRole("checkbox", { name: "Ana" }));
    await userEvent.click(screen.getByText("Sugerir asignación"));
    await waitFor(() =>
      expect(screen.getByText("Descartar")).toBeInTheDocument(),
    );

    await userEvent.click(screen.getByText("Descartar"));

    expect(mockAssignMutate).not.toHaveBeenCalled();
    await waitFor(() =>
      expect(screen.queryByText("Confirmar")).not.toBeInTheDocument(),
    );
  });

  it("muestra carga histórica cuando hay datos de workload", async () => {
    renderPanel();
    await waitFor(() =>
      expect(screen.getByText("Carga histórica")).toBeInTheDocument(),
    );
    expect(screen.getByText("1.50×")).toBeInTheDocument();
  });
});
