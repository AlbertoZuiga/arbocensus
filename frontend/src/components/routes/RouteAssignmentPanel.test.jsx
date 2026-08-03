import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("@/api/routes.js", () => ({
  assignRoute: vi.fn(),
  fetchRoutes: vi.fn(),
  fetchWorkload: vi.fn(),
  suggestAssignment: vi.fn(),
  setSolutionParticipants: vi.fn(),
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

import {
  assignRoute,
  fetchRoutes,
  fetchWorkload,
  setSolutionParticipants,
  suggestAssignment,
} from "@/api/routes.js";
import { fetchSolution } from "@/api/optimization.js";
import { fetchSurveyors } from "@/api/surveyors.js";
import { useToastStore } from "@/store/toastStore.js";
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
  {
    id: SURVEYOR_ID,
    username: "ana",
    first_name: "Ana",
    last_name: "",
    is_active: true,
  },
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
    useToastStore.setState({ toasts: [] });
    fetchSolution.mockResolvedValue(SOLUTION);
    fetchRoutes.mockResolvedValue(ROUTES);
    fetchSurveyors.mockResolvedValue(SURVEYORS);
    fetchWorkload.mockResolvedValue(WORKLOAD);
    setSolutionParticipants.mockResolvedValue({ participant_count: 1 });
    assignRoute.mockResolvedValue({ id: ROUTE_ID, surveyor: SURVEYOR_ID });
  });

  it("shows 'Asignación automática' button when solution is published", async () => {
    renderPanel();
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Asignación automática" }),
      ).toBeInTheDocument(),
    );
  });

  it("opens modal with surveyor list on button click", async () => {
    renderPanel();
    const btn = await screen.findByRole("button", { name: "Asignación automática" });
    await userEvent.click(btn);

    await waitFor(() =>
      expect(screen.getByRole("checkbox", { name: "Ana" })).toBeInTheDocument(),
    );
  });

  it("'Siguiente' disabled until surveyor selected in modal", async () => {
    renderPanel();
    await userEvent.click(
      await screen.findByRole("button", { name: "Asignación automática" }),
    );

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Siguiente" }),
      ).toBeDisabled(),
    );

    await userEvent.click(screen.getByRole("checkbox", { name: "Ana" }));
    expect(
      screen.getByRole("button", { name: "Siguiente" }),
    ).not.toBeDisabled();
  });

  it("calls API and shows per-surveyor preview on suggest", async () => {
    suggestAssignment.mockResolvedValue(SUGGESTION);
    renderPanel();

    await userEvent.click(
      await screen.findByRole("button", { name: "Asignación automática" }),
    );
    await waitFor(() => screen.getByRole("checkbox", { name: "Ana" }));

    await userEvent.click(screen.getByRole("checkbox", { name: "Ana" }));
    await userEvent.click(screen.getByRole("button", { name: "Siguiente" }));

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Confirmar asignación" }),
      ).toBeInTheDocument(),
    );
    expect(suggestAssignment).toHaveBeenCalledWith(SOLUTION_ID, [SURVEYOR_ID]);
    expect(screen.getByText(/Ruta 1 \(0\.42×\)/)).toBeInTheDocument();
    expect(mockAssignMutate).not.toHaveBeenCalled();
  });

  async function confirmSuggestion() {
    await userEvent.click(
      await screen.findByRole("button", { name: "Asignación automática" }),
    );
    await waitFor(() => screen.getByRole("checkbox", { name: "Ana" }));
    await userEvent.click(screen.getByRole("checkbox", { name: "Ana" }));
    await userEvent.click(screen.getByRole("button", { name: "Siguiente" }));
    await waitFor(() =>
      screen.getByRole("button", { name: "Confirmar asignación" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Confirmar asignación" }),
    );
  }

  it("confirmar asignación assigns each route in bulk and closes modal", async () => {
    suggestAssignment.mockResolvedValue(SUGGESTION);
    renderPanel();

    await confirmSuggestion();

    await waitFor(() =>
      expect(setSolutionParticipants).toHaveBeenCalledWith(SOLUTION_ID, [
        SURVEYOR_ID,
      ]),
    );
    await waitFor(() =>
      expect(assignRoute).toHaveBeenCalledWith(ROUTE_ID, SURVEYOR_ID),
    );
    expect(mockAssignMutate).not.toHaveBeenCalled();
    await waitFor(() =>
      expect(useToastStore.getState().toasts).toContainEqual(
        expect.objectContaining({
          variant: "success",
          message: "Rutas asignadas",
        }),
      ),
    );
    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: "Confirmar asignación" }),
      ).not.toBeInTheDocument(),
    );
  });

  it("shows partial failure toast when some bulk assignments fail", async () => {
    suggestAssignment.mockResolvedValue({
      assignments: [
        {
          route_id: ROUTE_ID,
          route_number: 1,
          surveyor_id: SURVEYOR_ID,
          utilization: 0.42,
        },
        {
          route_id: "route-dddd-4444",
          route_number: 2,
          surveyor_id: SURVEYOR_ID,
          utilization: 0.3,
        },
      ],
      balance: { [SURVEYOR_ID]: -0.12 },
    });
    assignRoute
      .mockResolvedValueOnce({ id: ROUTE_ID, surveyor: SURVEYOR_ID })
      .mockRejectedValueOnce(new Error("boom"));
    renderPanel();

    await confirmSuggestion();

    await waitFor(() =>
      expect(useToastStore.getState().toasts).toContainEqual(
        expect.objectContaining({
          variant: "error",
          message: "1 de 2 asignaciones fallaron",
        }),
      ),
    );
  });

  it("disables the button and selects while bulk assignment is pending", async () => {
    suggestAssignment.mockResolvedValue(SUGGESTION);
    assignRoute.mockReturnValue(new Promise(() => {}));
    renderPanel();

    await confirmSuggestion();

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Asignación automática" }),
      ).toBeDisabled(),
    );
    expect(
      screen.getByRole("combobox", { name: "Censista ruta 1" }),
    ).toBeDisabled();
  });

  it("'Volver' regresa a paso 1 sin llamar mutate", async () => {
    suggestAssignment.mockResolvedValue(SUGGESTION);
    renderPanel();

    await userEvent.click(
      await screen.findByRole("button", { name: "Asignación automática" }),
    );
    await waitFor(() => screen.getByRole("checkbox", { name: "Ana" }));
    await userEvent.click(screen.getByRole("checkbox", { name: "Ana" }));
    await userEvent.click(screen.getByRole("button", { name: "Siguiente" }));
    await waitFor(() => screen.getByRole("button", { name: "Volver" }));

    await userEvent.click(screen.getByRole("button", { name: "Volver" }));

    expect(mockAssignMutate).not.toHaveBeenCalled();
    await waitFor(() =>
      expect(screen.getByRole("checkbox", { name: "Ana" })).toBeInTheDocument(),
    );
  });
});
