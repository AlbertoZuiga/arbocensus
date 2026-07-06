import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import PublishButton from "./PublishButton.jsx";
import { fetchSolution, publishSolution } from "@/api/optimization.js";

vi.mock("@/api/optimization.js", () => ({
  fetchSolution: vi.fn(),
  publishSolution: vi.fn(),
}));

function renderButton(props) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <PublishButton {...props} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("PublishButton", () => {
  it("publishes without confirmation when no other plan is published", async () => {
    fetchSolution.mockImplementation((id) =>
      Promise.resolve({ id, published_at: null }),
    );
    publishSolution.mockResolvedValue({ id: "s1", published_at: "now" });

    renderButton({ solutionId: "s1", datasetSolutionIds: ["s1", "s2"] });

    const button = await screen.findByRole("button", {
      name: "Publicar esta solución",
    });
    await waitFor(() => expect(button).toBeEnabled());
    fireEvent.click(button);

    await waitFor(() => expect(publishSolution).toHaveBeenCalledWith("s1"));
  });

  it("confirms before replacing an already published plan", async () => {
    fetchSolution.mockImplementation((id) =>
      Promise.resolve({
        id,
        published_at: id === "s2" ? "2026-01-01" : null,
      }),
    );
    publishSolution.mockResolvedValue({});
    const confirmSpy = vi
      .spyOn(window, "confirm")
      .mockReturnValue(true);

    renderButton({ solutionId: "s1", datasetSolutionIds: ["s1", "s2"] });

    const button = await screen.findByRole("button", {
      name: "Publicar esta solución",
    });
    await waitFor(() => expect(button).toBeEnabled());
    fireEvent.click(button);

    expect(confirmSpy).toHaveBeenCalledWith(
      expect.stringContaining("reemplazará el plan vigente"),
    );
    await waitFor(() => expect(publishSolution).toHaveBeenCalledWith("s1"));
  });

  it("does not publish when the replace confirmation is cancelled", async () => {
    fetchSolution.mockImplementation((id) =>
      Promise.resolve({
        id,
        published_at: id === "s2" ? "2026-01-01" : null,
      }),
    );
    vi.spyOn(window, "confirm").mockReturnValue(false);

    renderButton({ solutionId: "s1", datasetSolutionIds: ["s1", "s2"] });

    const button = await screen.findByRole("button", {
      name: "Publicar esta solución",
    });
    await waitFor(() => expect(button).toBeEnabled());
    fireEvent.click(button);

    expect(publishSolution).not.toHaveBeenCalled();
  });

  it("shows a published badge and no button when the solution is published", async () => {
    fetchSolution.mockImplementation((id) =>
      Promise.resolve({ id, published_at: id === "s1" ? "2026-01-01" : null }),
    );

    renderButton({ solutionId: "s1", datasetSolutionIds: ["s1"] });

    expect(await screen.findByText("✓ Plan publicado")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Publicar esta solución" }),
    ).not.toBeInTheDocument();
  });
});
