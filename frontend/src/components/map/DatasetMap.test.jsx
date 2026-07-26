import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
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
  CircleMarker: ({ center, eventHandlers, children }) => (
    <div data-testid="marker" data-center={JSON.stringify(center)}>
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
