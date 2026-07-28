import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("@/api/datasets.js", () => ({
  fetchTreeObservations: vi.fn(),
  fetchLegacyTreeObservations: vi.fn(),
}));

import { fetchTreeObservations } from "@/api/datasets.js";
import TreePhotoGallery from "./TreePhotoGallery.jsx";
import useTreePhotos from "@/hooks/useTreePhotos.js";

const DEAD_PHOTO = "https://example.com/dead.jpg";
const originalImage = globalThis.Image;

function mockImageLoading() {
  globalThis.Image = class {
    set src(value) {
      queueMicrotask(() =>
        value === DEAD_PHOTO ? this.onerror?.() : this.onload?.(),
      );
    }
  };
}

function Harness({ treeId }) {
  const photos = useTreePhotos(treeId);
  return (
    <TreePhotoGallery
      open
      onOpenChange={() => {}}
      title="Árbol 3"
      photos={photos}
    />
  );
}

function renderGallery() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <Harness treeId="t1" />
    </QueryClientProvider>,
  );
}

describe("TreePhotoGallery", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockImageLoading();
  });

  afterEach(() => {
    globalThis.Image = originalImage;
  });

  it("drops photos whose URL does not load and navigates the rest", async () => {
    fetchTreeObservations.mockResolvedValue([
      {
        id: "o1",
        photo: "",
        photo_url: "https://example.com/a.jpg",
        photo_urls: ["https://example.com/a.jpg", DEAD_PHOTO],
      },
      { id: "o2", photo: "", photo_url: "https://example.com/b.jpg" },
    ]);
    renderGallery();

    const photo = await screen.findByRole("img", { name: "Árbol 3" });
    expect(photo).toHaveAttribute("src", "https://example.com/a.jpg");
    expect(
      screen.queryByRole("button", { name: "Foto anterior" }),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Foto siguiente" }));
    expect(screen.getByRole("img", { name: "Árbol 3" })).toHaveAttribute(
      "src",
      "https://example.com/b.jpg",
    );
    expect(
      screen.queryByRole("button", { name: "Foto siguiente" }),
    ).not.toBeInTheDocument();
  });

  it("shows no photo and no arrows when every URL is dead", async () => {
    fetchTreeObservations.mockResolvedValue([
      { id: "o1", photo: "", photo_url: DEAD_PHOTO, photo_urls: [DEAD_PHOTO] },
    ]);
    renderGallery();

    await waitFor(() => expect(fetchTreeObservations).toHaveBeenCalled());
    expect(await screen.findByText("Árbol 3")).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Foto siguiente" }),
    ).not.toBeInTheDocument();
  });
});
