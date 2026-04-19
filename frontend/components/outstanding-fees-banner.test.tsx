import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { OutstandingFeesBanner } from "./outstanding-fees-banner";

describe("OutstandingFeesBanner", () => {
  it("renders nothing when balanceCents is null", () => {
    const { container } = render(<OutstandingFeesBanner balanceCents={null} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders nothing when balanceCents is 0", () => {
    const { container } = render(<OutstandingFeesBanner balanceCents={0} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders nothing when balanceCents is negative", () => {
    const { container } = render(<OutstandingFeesBanner balanceCents={-100} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders the banner with formatted amount when balanceCents is positive", () => {
    render(<OutstandingFeesBanner balanceCents={150000} />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText(/outstanding fees/i)).toBeInTheDocument();
    expect(screen.getByText(/1,500\.00/)).toBeInTheDocument();
    expect(screen.getByText("Make a payment")).toHaveAttribute("href", "/pay");
  });
});
