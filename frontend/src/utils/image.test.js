import { afterEach, describe, expect, it, vi } from "vitest";
import {
  MAX_PHOTO_SIDE,
  PHOTO_JPEG_QUALITY,
  captureJpegFrame,
  fitWithin,
} from "./image.js";

describe("fitWithin", () => {
  it("keeps dimensions already within the limit", () => {
    expect(fitWithin(1200, 900)).toEqual({ width: 1200, height: 900 });
  });

  it("keeps dimensions exactly at the limit", () => {
    expect(fitWithin(1600, 1200)).toEqual({ width: 1600, height: 1200 });
  });

  it("scales landscape down to the max side preserving aspect ratio", () => {
    expect(fitWithin(4000, 3000)).toEqual({ width: 1600, height: 1200 });
  });

  it("scales portrait down to the max side preserving aspect ratio", () => {
    expect(fitWithin(3000, 4000)).toEqual({ width: 1200, height: 1600 });
  });

  it("rounds scaled dimensions to whole pixels", () => {
    const { width, height } = fitWithin(3333, 2000);
    expect(width).toBe(1600);
    expect(height).toBe(960);
    expect(Number.isInteger(height)).toBe(true);
  });

  it("respects a custom max side", () => {
    expect(fitWithin(2000, 1000, 500)).toEqual({ width: 500, height: 250 });
  });
});

describe("captureJpegFrame", () => {
  function stubCanvas(blob) {
    const canvas = {
      width: 0,
      height: 0,
      getContext: vi.fn(() => ({ drawImage: vi.fn() })),
      toBlob: vi.fn((callback) => callback(blob)),
    };
    vi.spyOn(document, "createElement").mockReturnValue(canvas);
    return canvas;
  }

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("downscales the frame and encodes it as JPEG at the target quality", async () => {
    const blob = new Blob(["photo"], { type: "image/jpeg" });
    const canvas = stubCanvas(blob);
    const video = { videoWidth: 4000, videoHeight: 3000 };

    const file = await captureJpegFrame(video, "tree-1.jpg");

    expect(canvas.width).toBe(MAX_PHOTO_SIDE);
    expect(canvas.height).toBe(1200);
    expect(canvas.getContext("2d").drawImage).toBeDefined();
    expect(canvas.toBlob).toHaveBeenCalledWith(
      expect.any(Function),
      "image/jpeg",
      PHOTO_JPEG_QUALITY
    );
    expect(file).toBeInstanceOf(File);
    expect(file.name).toBe("tree-1.jpg");
    expect(file.type).toBe("image/jpeg");
  });

  it("keeps small frames at their original size", async () => {
    const canvas = stubCanvas(new Blob([""], { type: "image/jpeg" }));
    const video = { videoWidth: 640, videoHeight: 480 };

    await captureJpegFrame(video, "tree-2.jpg");

    expect(canvas.width).toBe(640);
    expect(canvas.height).toBe(480);
  });

  it("resolves null when encoding fails", async () => {
    stubCanvas(null);
    const video = { videoWidth: 1000, videoHeight: 1000 };

    await expect(captureJpegFrame(video, "tree-3.jpg")).resolves.toBeNull();
  });
});
