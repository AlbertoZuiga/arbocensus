import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import SurveyorRoutePage from "./SurveyorRoutePage.jsx";
import { useMyRoute, useRouteDetail } from "../../hooks/useMyRoute.js";

vi.mock("../../hooks/useMyRoute.js", () => ({
  useMyRoute: vi.fn(),
  useRouteDetail: vi.fn(),
  useRoutePath: vi.fn(() => ({ data: null })),
}));
vi.mock("../../hooks/useWatchPosition.js", () => ({
  useWatchPosition: () => ({ position: null }),
}));
vi.mock("../../hooks/useWakeLock.js", () => ({
  useWakeLock: () => {},
}));
vi.mock("../../components/surveyor/RouteMap.jsx", () => ({
  default: () => <div data-testid="route-map" />,
}));
vi.mock("../../components/UserMenu.jsx", () => ({ default: () => null }));

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
    <QueryClientProvider client={queryClient}>
      <SurveyorRoutePage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  useMyRoute.mockReturnValue({
    data: [route],
    isLoading: false,
    isError: false,
  });
});

describe("SurveyorRoutePage", () => {
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
