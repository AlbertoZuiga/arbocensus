import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RouteSelector from "./RouteSelector.jsx";
import { routeOptionLabel } from "../../utils/routes.js";

window.HTMLElement.prototype.hasPointerCapture ??= () => false;
window.HTMLElement.prototype.releasePointerCapture ??= () => {};
window.HTMLElement.prototype.scrollIntoView ??= () => {};

const routes = [
  { id: "r1", total_trees: 30, visited_count: 30, skipped_count: 0 },
  { id: "r2", total_trees: 40, visited_count: 10, skipped_count: 4 },
];

describe("routeOptionLabel", () => {
  it("formats progress as resolved over total", () => {
    expect(routeOptionLabel(routes[1], 1)).toBe("Ruta 2 · 14/40");
  });

  it("counts visited and skipped stops as resolved", () => {
    expect(routeOptionLabel(routes[0], 0)).toBe("Ruta 1 · 30/30");
  });

  it("treats missing counts as zero", () => {
    expect(routeOptionLabel({ id: "r3", total_trees: 12 }, 2)).toBe(
      "Ruta 3 · 0/12",
    );
  });
});

describe("RouteSelector", () => {
  it("lists every route with its progress", async () => {
    const user = userEvent.setup();
    render(
      <RouteSelector routes={routes} activeRouteId="r2" onSelect={() => {}} />,
    );

    await user.click(screen.getByRole("combobox"));

    expect(
      screen.getByRole("option", { name: "Ruta 1 · 30/30" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("option", { name: "Ruta 2 · 14/40" }),
    ).toBeInTheDocument();
  });
});
