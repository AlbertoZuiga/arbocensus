import { describe, it, expect } from "vitest";
import { pollInterval, MAX_POLL_MS } from "./optimization.js";

describe("pollInterval", () => {
  it.each([
    ["queued", 3000],
    ["running", 3000],
  ])("keeps polling while %s", (status, expected) => {
    expect(pollInterval(status)).toBe(expected);
  });

  it.each([["completed"], ["failed"], ["error"]])(
    "stops polling once %s (terminal)",
    (status) => {
      expect(pollInterval(status)).toBe(false);
    }
  );

  it("stops polling when status is undefined", () => {
    expect(pollInterval(undefined)).toBe(false);
  });

  it("keeps polling an active job before the 15 min cutoff", () => {
    const now = Date.now();
    const createdAt = new Date(now - (MAX_POLL_MS - 60000)).toISOString();
    expect(pollInterval("running", createdAt, now)).toBe(3000);
  });

  it("stops polling once an active job passes the 15 min cutoff", () => {
    const now = Date.now();
    const createdAt = new Date(now - MAX_POLL_MS).toISOString();
    expect(pollInterval("queued", createdAt, now)).toBe(false);
  });
});
