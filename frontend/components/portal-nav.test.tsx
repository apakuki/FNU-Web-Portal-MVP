import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
}));

import { PortalNav } from "./portal-nav";

afterEach(() => {
  cleanup();
});

describe("PortalNav", () => {
  it("renders all student navigation links", () => {
    render(<PortalNav />);
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Register")).toBeInTheDocument();
    expect(screen.getByText("Timetable")).toBeInTheDocument();
    expect(screen.getByText("My Courses")).toBeInTheDocument();
    expect(screen.getByText("My Grades")).toBeInTheDocument();
    expect(screen.getByText("Invoices")).toBeInTheDocument();
    expect(screen.getByText("Make a Payment")).toBeInTheDocument();
    expect(screen.getByText("Student ID")).toBeInTheDocument();
    expect(screen.getByText("Profile")).toBeInTheDocument();
  });

  it("marks the active link with aria-current", () => {
    render(<PortalNav />);
    const dashboardLinks = screen.getAllByText("Dashboard");
    expect(dashboardLinks[0]).toHaveAttribute("aria-current", "page");
    const registerLinks = screen.getAllByText("Register");
    expect(registerLinks[0]).not.toHaveAttribute("aria-current");
  });

  it("has accessible navigation landmark", () => {
    render(<PortalNav />);
    const navs = screen.getAllByRole("navigation", {
      name: /portal navigation/i,
    });
    expect(navs.length).toBeGreaterThan(0);
  });
});
