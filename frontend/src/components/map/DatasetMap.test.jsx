import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import DatasetMap from "./DatasetMap.jsx";
import { fetchRoutesGeojson } from "@/api/routes.js";
import { fetchTreeObservations } from "@/api/datasets.js";

vi.mock("@/api/routes.js", () => ({
  fetchRoutesGeojson: vi.fn(),
}));

vi.mock("@/api/datasets.js", () => ({
  fetchTreeObservations: vi.fn().mockResolvedValue([]),
}));

vi.mock("./BaseMap.jsx", () => ({
  default: ({ children }) => <div>{children}</div>,
}));

vi.mock("react-leaflet", () => ({
  CircleMarker: ({ center, pathOptions, eventHandlers, children }) => (
    <div
      data-testid="marker"
      data-center={JSON.stringify(center)}
      data-fill={pathOptions?.fillColor}
      data-fill-opacity={pathOptions?.fillOpacity}
    >
      <button onClick={() => eventHandlers?.popupopen?.()}>abrir</button>
      {children}
    </div>
  ),
  Polyline: () => <div data-testid="route-line" />,
  Popup: ({ children }) => <div>{children}</div>,
}));

const ROUTES_GEOJSON = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      geometry: {
        type: "LineString",
        coordinates: [
          [-70.65, -33.45],
          [-70.66, -33.46],
        ],
      },
      properties: {
        route_number: 1,
        total_trees: 2,
        travel_time_sec: 600,
        total_service_time_sec: 600,
        stops: [
          { tree_id: "t1", coordinates: [-70.65, -33.45] },
          { tree_id: "t2", coordinates: [-70.66, -33.46] },
        ],
      },
    },
  ],
};

function renderMap(props) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <DatasetMap markers={[]} solutionId="s1" {...props} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  fetchTreeObservations.mockClear();
  fetchRoutesGeojson.mockReset().mockResolvedValue(ROUTES_GEOJSON);
});

describe("DatasetMap dropped markers", () => {
  it("renders only dropped markers with hollow red style when solution is active", async () => {
    const markers = [
      { id: "t1", position: [-33.45, -70.65] },
      { id: "t2", position: [-33.46, -70.66] },
    ];
    renderMap({ markers, droppedIds: new Set(["t1"]) });

    // Wait for routes to load (which also triggers dropped markers to render)
    await screen.findByTestId("route-line");

    await waitFor(() => {
      const allMarkers = screen.getAllByTestId("marker");
      const droppedMarkers = allMarkers.filter(
        (m) => m.getAttribute("data-fill-opacity") === "0.4",
      );
      expect(droppedMarkers).toHaveLength(1);
      expect(droppedMarkers[0].getAttribute("data-fill")).toBe("#dc2626");
    });
  });

  it("renders no dropped markers when droppedIds is empty", async () => {
    const markers = [{ id: "t9", position: [-33.4, -70.6] }];
    renderMap({ markers, droppedIds: new Set() });

    await screen.findByTestId("route-line");

    const allMarkers = screen.getAllByTestId("marker");
    const droppedMarkers = allMarkers.filter(
      (m) => m.getAttribute("data-fill-opacity") === "0.4",
    );
    expect(droppedMarkers).toHaveLength(0);
  });

  it("shows fuera de ruta label in dropped marker popup", async () => {
    const markers = [{ id: "t1", position: [-33.45, -70.65] }];
    renderMap({ markers, droppedIds: new Set(["t1"]) });

    // Wait for routes to load, then dropped marker appears
    await screen.findByTestId("route-line");

    const buttons = screen.getAllByRole("button", { name: "abrir" });
    await userEvent.click(buttons[buttons.length - 1]);

    expect(await screen.findByText("Fuera de ruta")).toBeInTheDocument();
  });
});

describe("DatasetMap routes error", () => {
  it("shows a retry overlay when the geojson fails and refetches on click", async () => {
    fetchRoutesGeojson.mockRejectedValue(new Error("boom"));
    const markers = [{ id: "t9", position: [-33.4, -70.6] }];
    renderMap({ markers });

    const retry = await screen.findByRole(
      "button",
      { name: "Reintentar" },
      { timeout: 4000 },
    );
    expect(screen.getByText("No se pudieron cargar las rutas.")).toBeInTheDocument();
    expect(screen.getAllByTestId("marker")).toHaveLength(1);

    const callsBefore = fetchRoutesGeojson.mock.calls.length;
    fetchRoutesGeojson.mockResolvedValue(ROUTES_GEOJSON);
    await userEvent.click(retry);

    await waitFor(() =>
      expect(fetchRoutesGeojson.mock.calls.length).toBeGreaterThan(callsBefore),
    );
    expect(await screen.findByTestId("route-line")).toBeInTheDocument();
  });
});

describe("DatasetMap stop popups", () => {
  it("keeps the tree history of a stop out of the network until its popup opens", async () => {
    renderMap();

    const markers = await screen.findAllByTestId("marker");
    expect(markers).toHaveLength(2);
    expect(fetchTreeObservations).not.toHaveBeenCalled();

    await userEvent.click(screen.getAllByRole("button", { name: "abrir" })[1]);

    expect(fetchTreeObservations).toHaveBeenCalledTimes(1);
    expect(fetchTreeObservations).toHaveBeenCalledWith("t2");
    expect(await screen.findByText("Historial")).toBeInTheDocument();
    expect(screen.getByText(/Ruta 1 · Parada 2/)).toBeInTheDocument();
  });

  it("shows the tree history on the dataset markers when there are no routes", async () => {
    fetchRoutesGeojson.mockResolvedValue({
      type: "FeatureCollection",
      features: [],
    });
    renderMap({ markers: [{ id: "t9", position: [-33.4, -70.6] }] });

    await userEvent.click(await screen.findByRole("button", { name: "abrir" }));

    expect(fetchTreeObservations).toHaveBeenCalledWith("t9");
  });
});
