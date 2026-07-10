import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("@/api/optimization.js", () => ({
  fetchSolution: vi.fn(() =>
    Promise.resolve({
      total_routes: 3,
      total_travel_time_sec: 3600,
      total_service_time_sec: 1800,
    }),
  ),
}));

import StrategyTabs from "./StrategyTabs.jsx";

function renderWithClient(ui) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>{ui}</QueryClientProvider>,
  );
}

describe("StrategyTabs", () => {
  it("renders nothing when there are no strategies", () => {
    const { container } = renderWithClient(
      <StrategyTabs strategies={[]} value={null} onChange={vi.fn()} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders a static chip with no other tabs when only one strategy ran", async () => {
    renderWithClient(
      <StrategyTabs
        strategies={[{ key: "global", label: "Global", solutionId: "s1" }]}
        value="global"
        onChange={vi.fn()}
      />,
    );

    expect(screen.getByText("Global")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    const metrics = await screen.findByText("3 rutas · 1 h 30 min");
    expect(metrics.closest("[title]")).toHaveAttribute(
      "title",
      "Total 1 h 30 min · Caminata 1 h 0 min · Censo 30 min",
    );
  });

  it("renders a toggle with a tab per strategy when more than one ran", () => {
    renderWithClient(
      <StrategyTabs
        strategies={[
          { key: "global", label: "Global", solutionId: "s1" },
          { key: "spatial_term", label: "Término espacial", solutionId: "s2" },
        ]}
        value="global"
        onChange={vi.fn()}
      />,
    );

    expect(screen.getAllByRole("button")).toHaveLength(2);
  });
});
