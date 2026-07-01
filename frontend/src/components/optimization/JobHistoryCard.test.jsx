import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("@/api/optimization", () => ({
  fetchJobs: vi.fn().mockResolvedValue([]),
}));

import { fetchJobs } from "@/api/optimization";
import JobHistoryCard from "./JobHistoryCard.jsx";

function renderCard() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <JobHistoryCard datasetId="d1" />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("JobHistoryCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchJobs.mockResolvedValue([]);
  });

  it("renders nothing when there are no jobs", async () => {
    renderCard();
    expect(screen.queryByText("Historial de trabajos")).not.toBeInTheDocument();
  });

  it("links each history row to its job detail page", async () => {
    fetchJobs.mockResolvedValue([
      {
        id: "j2",
        status: "completed",
        solution_ids: { global: "s1" },
        started_at: "2026-06-30T10:00:00Z",
      },
      {
        id: "j1",
        status: "failed",
        solution_ids: {},
        started_at: "2026-06-29T10:00:00Z",
      },
    ]);
    renderCard();

    expect(await screen.findByText("Historial de trabajos")).toBeInTheDocument();

    const failedRow = screen.getByText("Fallido").closest("a");
    expect(failedRow).toHaveAttribute("href", "/admin/datasets/d1/jobs/j1");
  });
});
