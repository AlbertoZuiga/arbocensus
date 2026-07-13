import { describe, it, expect } from "vitest";

import {
  PROGRESS_POLL_MS,
  isCensusComplete,
  progressPercent,
  progressPollInterval,
  statusSegments,
  stopsPollInterval,
} from "./progress.js";

const totals = { total: 10, visited: 4, skipped: 1, pending: 5 };

const query = (state) => ({ state: { status: "success", ...state } });

describe("progressPercent", () => {
  it("counts visited and skipped as resolved", () => {
    expect(progressPercent(totals)).toBe(50);
  });

  it("returns 0 without stops", () => {
    expect(progressPercent({ total: 0, visited: 0, skipped: 0, pending: 0 })).toBe(0);
  });
});

describe("statusSegments", () => {
  it("splits the bar by status share", () => {
    expect(statusSegments(totals)).toEqual([
      { status: "visited", count: 4, percent: 40 },
      { status: "skipped", count: 1, percent: 10 },
      { status: "pending", count: 5, percent: 50 },
    ]);
  });
});

describe("isCensusComplete", () => {
  it("is complete when nothing is pending", () => {
    expect(
      isCensusComplete({
        solution: { id: "s1" },
        totals: { total: 5, visited: 4, skipped: 1, pending: 0 },
      }),
    ).toBe(true);
  });

  it("is not complete without a published solution", () => {
    expect(isCensusComplete({ solution: null, totals })).toBe(false);
  });
});

describe("progressPollInterval", () => {
  it("polls while stops are pending", () => {
    expect(
      progressPollInterval(query({ data: { solution: { id: "s1" }, totals } })),
    ).toBe(PROGRESS_POLL_MS);
  });

  it("stops on error", () => {
    expect(
      progressPollInterval(
        query({ status: "error", data: { solution: { id: "s1" }, totals } }),
      ),
    ).toBe(false);
  });

  it("stops without a published solution", () => {
    expect(progressPollInterval(query({ data: { solution: null, totals } }))).toBe(
      false,
    );
  });

  it("stops when the census is complete", () => {
    expect(
      progressPollInterval(
        query({
          data: {
            solution: { id: "s1" },
            totals: { total: 5, visited: 5, skipped: 0, pending: 0 },
          },
        }),
      ),
    ).toBe(false);
  });
});

describe("stopsPollInterval", () => {
  it("polls only while live", () => {
    expect(stopsPollInterval(query({}), true)).toBe(PROGRESS_POLL_MS);
    expect(stopsPollInterval(query({}), false)).toBe(false);
  });

  it("stops on error", () => {
    expect(stopsPollInterval(query({ status: "error" }), true)).toBe(false);
  });
});
