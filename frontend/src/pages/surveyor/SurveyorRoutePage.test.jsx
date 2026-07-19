import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import SurveyorRoutePage from "./SurveyorRoutePage.jsx";
import { useAuthStore } from "../../store/authStore.js";
import { useMyRoute, useRouteDetail, useRoutePath } from "../../hooks/useMyRoute.js";

vi.mock("../../hooks/useMyRoute.js", () => ({
  EMPTY_ROUTES_POLL_MS: 30_000,
  useMyRoute: vi.fn(),
  useRouteDetail: vi.fn(),
  useRoutePath: vi.fn(() => ({ data: null })),
}));
vi.mock("../../hooks/useWatchPosition.js", () => ({
  useWatchPosition: () => ({ position: null }),
}));
vi.mock("../../hooks/useWakeLock.js", () => ({ useWakeLock: () => {} }));
vi.mock("../../hooks/useLogout.js", () => ({ useLogout: () => vi.fn() }));
vi.mock("../../components/surveyor/RouteMap.jsx", () => ({
  default: () => <div data-testid="route-map" />,
}));

const mutationStub = {
  mutate: vi.fn(),
  reset: vi.fn(),
  isPending: false,
  isError: false,
  error: null,
};
vi.mock("../../hooks/useVisitStop.js", () => ({
  useVisitStop: () => mutationStub,
}));
vi.mock("../../hooks/useSkipStop.js", () => ({
  useSkipStop: () => mutationStub,
}));

const idleQuery = { data: undefined, isLoading: false, isError: false, isFetching: false };

const route = { id: "r1", route_number: 1 };

function stop(id, overrides = {}) {
  return {
    id,
    sequence: 1,
    tree_id: `tree-${id}`,
    lat: -33.45,
    lon: -70.65,
    status: "pending",
    visited: false,
    ...overrides,
  };
}

function renderPage() {
  const queryClient = new QueryClient();
  return render(
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <SurveyorRoutePage />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  useAuthStore.setState({
    user: { username: "alice", role: "surveyor", role_display: "Censador" },
  });
  useRouteDetail.mockReturnValue({ ...idleQuery });
  useRoutePath.mockReturnValue({ ...idleQuery });
});

describe("SurveyorRoutePage status screens", () => {
  it("shows the header with the user menu while loading", () => {
    useMyRoute.mockReturnValue({ ...idleQuery, isLoading: true });
    renderPage();
    expect(screen.getByText("Cargando ruta…")).toBeInTheDocument();
    expect(screen.getByText("Arbocensus")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /alice/ })).toBeInTheDocument();
  });

  it("shows the error message with a retry button that refetches", () => {
    const refetch = vi.fn();
    useMyRoute.mockReturnValue({ ...idleQuery, isError: true, refetch });
    renderPage();
    expect(screen.getByText("No se pudo cargar tu ruta.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /alice/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Reintentar/ }));
    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it("shows a friendly empty state with an update button when no routes are assigned", () => {
    const refetch = vi.fn();
    useMyRoute.mockReturnValue({ ...idleQuery, data: [], refetch });
    renderPage();
    expect(screen.getByText("Aún no tienes rutas asignadas")).toBeInTheDocument();
    expect(screen.getByText(/actualiza sola cada 30 segundos/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /alice/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Actualizar/ }));
    expect(refetch).toHaveBeenCalledTimes(1);
  });
});

describe("SurveyorRoutePage core flow", () => {
  beforeEach(() => {
    useMyRoute.mockReturnValue({
      data: [route],
      isLoading: false,
      isError: false,
    });
  });

  it("shows the map and stop list while stops remain pending", () => {
    useRouteDetail.mockReturnValue({
      data: {
        ...route,
        stops: [stop("s1", { visited: true, status: "visited" }), stop("s2")],
      },
      isLoading: false,
    });
    renderPage();

    expect(screen.getByTestId("route-map")).toBeInTheDocument();
    expect(screen.queryByText("¡Ruta completada!")).not.toBeInTheDocument();
  });

  it("shows the completion screen when every stop is resolved", () => {
    useRouteDetail.mockReturnValue({
      data: {
        ...route,
        stops: [
          stop("s1", { visited: true, status: "visited" }),
          stop("s2", { status: "skipped" }),
        ],
      },
      isLoading: false,
    });
    renderPage();

    expect(screen.getByText("¡Ruta completada!")).toBeInTheDocument();
    expect(screen.queryByTestId("route-map")).not.toBeInTheDocument();
    expect(screen.getByText("Visitados").nextSibling).toHaveTextContent("1");
    expect(screen.getByText("Omitidos").nextSibling).toHaveTextContent("1");
  });

  it("keeps showing the map when the route has no stops", () => {
    useRouteDetail.mockReturnValue({
      data: { ...route, stops: [] },
      isLoading: false,
    });
    renderPage();

    expect(screen.getByTestId("route-map")).toBeInTheDocument();
    expect(screen.queryByText("¡Ruta completada!")).not.toBeInTheDocument();
  });
});
