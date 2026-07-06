import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Censadores from "./Censadores.jsx";
import { fetchSurveyors } from "@/api/surveyors.js";
import { fetchRoutes } from "@/api/routes.js";

vi.mock("@/api/surveyors.js", () => ({
  fetchSurveyors: vi.fn(),
}));

vi.mock("@/api/routes.js", () => ({
  fetchRoutes: vi.fn().mockResolvedValue([]),
}));

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Censadores />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  fetchSurveyors.mockReset();
  fetchRoutes.mockReset();
  fetchRoutes.mockResolvedValue([]);
});

describe("Censadores", () => {
  it("renders a row per surveyor with name, email and role", async () => {
    fetchSurveyors.mockResolvedValue([
      {
        id: "s1",
        username: "alovelace",
        first_name: "Ada",
        last_name: "Lovelace",
        email: "ada@example.com",
        role: "surveyor",
        role_display: "Surveyor",
      },
    ]);
    renderPage();

    expect(await screen.findByText("Ada Lovelace")).toBeInTheDocument();
    expect(screen.getByText("ada@example.com")).toBeInTheDocument();
    expect(screen.getByText("Surveyor")).toBeInTheDocument();
  });

  it("falls back to username when the name is empty", async () => {
    fetchSurveyors.mockResolvedValue([
      {
        id: "s2",
        username: "ghopper",
        first_name: "",
        last_name: "",
        email: "grace@example.com",
        role: "surveyor",
        role_display: "Surveyor",
      },
    ]);
    renderPage();

    expect(await screen.findByText("ghopper")).toBeInTheDocument();
  });

  it("shows the assigned route and progress from the published plan", async () => {
    fetchSurveyors.mockResolvedValue([
      {
        id: "s1",
        username: "alovelace",
        first_name: "Ada",
        last_name: "Lovelace",
        email: "ada@example.com",
        role: "surveyor",
        role_display: "Surveyor",
      },
    ]);
    fetchRoutes.mockResolvedValue([
      {
        id: "r1",
        route_number: 3,
        surveyor: "s1",
        visited_count: 2,
        pending_count: 5,
      },
    ]);
    renderPage();

    expect(await screen.findByText("Ruta 3")).toBeInTheDocument();
    expect(screen.getByText("2/7 visitados")).toBeInTheDocument();
  });

  it("shows an empty message when there are no surveyors", async () => {
    fetchSurveyors.mockResolvedValue([]);
    renderPage();

    expect(await screen.findByText("Aún no hay censadores.")).toBeInTheDocument();
  });

  it("shows an error alert when the request fails", async () => {
    fetchSurveyors.mockRejectedValue(new Error("boom"));
    renderPage();

    await waitFor(() =>
      expect(screen.getByText(/No se pudieron cargar/)).toBeInTheDocument(),
    );
  });
});
