import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { HealthStatus } from "./health-status";

describe("HealthStatus", () => {
  it("renders status values when health data is provided", () => {
    render(
      <HealthStatus
        health={{ status: "ok", postgres: "ok", banner: "mock" }}
      />,
    );
    const okElements = screen.getAllByText("ok");
    expect(okElements).toHaveLength(2);
    expect(screen.getByText("mock")).toBeInTheDocument();
  });

  it("renders unavailable message when health is null", () => {
    render(<HealthStatus health={null} />);
    expect(screen.getByText("Backend unavailable")).toBeInTheDocument();
  });
});
