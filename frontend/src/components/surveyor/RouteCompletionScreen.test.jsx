import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import RouteCompletionScreen from "./RouteCompletionScreen.jsx";
import { useOnlineStatus } from "../../hooks/useOnlineStatus.js";

vi.mock("../../hooks/useOnlineStatus.js", () => ({
  useOnlineStatus: vi.fn(() => true),
}));

const stops = [
  { id: "s1", visited: true, status: "visited" },
  { id: "s2", visited: true, status: "visited" },
  { id: "s3", visited: false, status: "skipped" },
];

function renderScreen() {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <RouteCompletionScreen stops={stops} />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  useOnlineStatus.mockReturnValue(true);
});

describe("RouteCompletionScreen", () => {
  it("shows the completion title and visited/skipped counts", () => {
    renderScreen();

    expect(screen.getByText("¡Ruta completada!")).toBeInTheDocument();
    expect(screen.getByText("Visitados").nextSibling).toHaveTextContent("2");
    expect(screen.getByText("Omitidos").nextSibling).toHaveTextContent("1");
  });

  it("confirms sync when online with no pending mutations", () => {
    renderScreen();

    expect(screen.getByRole("status")).toHaveTextContent(
      "Todos los registros están sincronizados.",
    );
  });

  it("warns about pending sync when offline", () => {
    useOnlineStatus.mockReturnValue(false);
    renderScreen();

    expect(screen.getByRole("status")).toHaveTextContent(
      "Sin conexión: los datos se sincronizarán al recuperar señal.",
    );
  });
});
