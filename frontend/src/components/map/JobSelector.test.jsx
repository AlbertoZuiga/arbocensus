import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import JobSelector from "./JobSelector.jsx";

const jobs = [
  { id: "j2", status: "completed", started_at: "2026-07-20T14:00:00Z" },
  { id: "j1", status: "failed", started_at: "2026-07-18T09:00:00Z" },
];

describe("JobSelector", () => {
  it("renders nothing when the dataset has no optimizations", () => {
    const { container } = render(
      <JobSelector jobs={[]} value={undefined} onChange={() => {}} />,
    );

    expect(container).toBeEmptyDOMElement();
  });

  it("lists every optimization with its status", async () => {
    const user = userEvent.setup();
    render(<JobSelector jobs={jobs} value="j2" onChange={() => {}} />);

    await user.click(screen.getByRole("combobox", { name: "Optimización" }));

    const options = screen.getAllByRole("option");
    expect(options).toHaveLength(2);
    expect(options[0]).toHaveTextContent("Completado");
    expect(options[1]).toHaveTextContent("Fallido");
  });

  it("reports the selected optimization", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<JobSelector jobs={jobs} value="j2" onChange={onChange} />);

    await user.click(screen.getByRole("combobox", { name: "Optimización" }));
    await user.click(screen.getAllByRole("option")[1]);

    expect(onChange).toHaveBeenCalledWith("j1");
  });
});
