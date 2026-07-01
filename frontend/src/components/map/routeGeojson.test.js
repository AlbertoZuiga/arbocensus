import { describe, it, expect } from "vitest";
import { geojsonToRoutes } from "./routeGeojson.js";

const collection = {
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
      properties: { route_number: 1, total_trees: 2, travel_time_sec: 600 },
    },
    {
      type: "Feature",
      geometry: { type: "LineString", coordinates: [[-70.7, -33.5]] },
      properties: { route_number: 2, total_trees: 1, travel_time_sec: 120 },
    },
  ],
};

describe("geojsonToRoutes", () => {
  it("inverts [lon, lat] geojson coordinates to [lat, lon] for Leaflet", () => {
    const routes = geojsonToRoutes(collection);
    expect(routes[0].positions).toEqual([
      [-33.45, -70.65],
      [-33.46, -70.66],
    ]);
    expect(routes[1].positions).toEqual([[-33.5, -70.7]]);
  });

  it("maps route properties and assigns distinct colors per route", () => {
    const routes = geojsonToRoutes(collection);
    expect(routes[0]).toMatchObject({
      routeNumber: 1,
      totalTrees: 2,
      travelTimeSec: 600,
    });
    expect(routes[0].color).not.toBe(routes[1].color);
  });

  it("returns an empty array for a missing feature collection", () => {
    expect(geojsonToRoutes(undefined)).toEqual([]);
    expect(geojsonToRoutes({ features: [] })).toEqual([]);
  });
});
