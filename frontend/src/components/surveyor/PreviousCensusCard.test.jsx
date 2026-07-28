import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("@/api/datasets.js", () => ({
  fetchTreeObservations: vi.fn(),
  fetchLegacyTreeObservations: vi.fn(),
}));

import { fetchTreeObservations } from "@/api/datasets.js";
import PreviousCensusCard from "./PreviousCensusCard.jsx";

function renderCard() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <PreviousCensusCard treeId="t1" />
    </QueryClientProvider>,
  );
}

describe("PreviousCensusCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows the latest photo, date and status", async () => {
    fetchTreeObservations.mockResolvedValue([
      {
        id: "o1",
        status: "alive",
        source: "legacy_api",
        photo: "",
        photo_url: "https://example.com/photo.jpg",
        observed_at: "2025-05-01T10:00:00Z",
      },
      {
        id: "o2",
        status: "removed",
        source: "legacy_app",
        photo: "",
        photo_url: "",
        observed_at: "2021-10-29T00:06:00Z",
      },
    ]);
    renderCard();

    expect(await screen.findByText("Censo anterior")).toBeInTheDocument();
    expect(screen.getByText("Vivo")).toBeInTheDocument();
    const photo = screen.getByRole("img");
    expect(photo).toHaveAttribute("src", "https://example.com/photo.jpg");
    expect(photo.getAttribute("alt")).toContain("censo anterior");
  });

  it("reveals the full timeline behind the toggle", async () => {
    fetchTreeObservations.mockResolvedValue([
      {
        id: "o1",
        status: "alive",
        source: "legacy_api",
        photo: "",
        photo_url: "",
        observed_at: "2025-05-01T10:00:00Z",
      },
    ]);
    renderCard();

    const toggle = await screen.findByRole("button", { name: /Historial/ });
    expect(screen.queryByText("1 observación")).not.toBeInTheDocument();
    fireEvent.click(toggle);
    expect(await screen.findByText("1 observación")).toBeInTheDocument();
  });

  it("renders nothing when there is no history", async () => {
    fetchTreeObservations.mockResolvedValue([]);
    const { container } = renderCard();

    await waitFor(() => expect(fetchTreeObservations).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when the request fails", async () => {
    fetchTreeObservations.mockRejectedValue(new Error("network"));
    const { container } = renderCard();

    await waitFor(() => expect(fetchTreeObservations).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });
});
