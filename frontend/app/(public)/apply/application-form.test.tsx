import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApplicationForm } from "./application-form";

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
  }: {
    children: React.ReactNode;
    href: string;
  }) => <a href={href}>{children}</a>,
}));

afterEach(() => {
  cleanup();
});

describe("ApplicationForm", () => {
  it("renders the contact step first", () => {
    render(<ApplicationForm />);
    expect(screen.getByText("Contact Information")).toBeDefined();
    expect(screen.getByText("Email Address")).toBeDefined();
  });

  it("shows validation error for empty email on next", () => {
    render(<ApplicationForm />);
    const nextBtn = screen.getByText("Next");
    fireEvent.click(nextBtn);
    expect(screen.getByText("Email is required")).toBeDefined();
  });

  it("advances to personal details after valid contact", () => {
    render(<ApplicationForm />);
    const emailInput = document.querySelector('input[type="email"]')!;
    fireEvent.change(emailInput, { target: { value: "test@email.com" } });
    fireEvent.click(screen.getByText("Next"));
    expect(screen.getByText("Personal Details")).toBeDefined();
  });

  it("shows step indicators", () => {
    render(<ApplicationForm />);
    expect(screen.getByText("Contact")).toBeDefined();
    expect(screen.getByText("Personal")).toBeDefined();
    expect(screen.getByText("Qualifications")).toBeDefined();
    expect(screen.getByText("Programme")).toBeDefined();
    expect(screen.getByText("Review")).toBeDefined();
  });

  it("can go back from personal details to contact", () => {
    render(<ApplicationForm />);
    const emailInput = document.querySelector('input[type="email"]')!;
    fireEvent.change(emailInput, { target: { value: "test@email.com" } });
    fireEvent.click(screen.getByText("Next"));
    expect(screen.getByText("Personal Details")).toBeDefined();
    fireEvent.click(screen.getByText("Back"));
    expect(screen.getByText("Contact Information")).toBeDefined();
  });

  it("validates personal details before advancing", () => {
    render(<ApplicationForm />);
    // Go to step 2
    const emailInput = document.querySelector('input[type="email"]')!;
    fireEvent.change(emailInput, { target: { value: "test@email.com" } });
    fireEvent.click(screen.getByText("Next"));
    // Try to advance without filling fields
    fireEvent.click(screen.getByText("Next"));
    expect(screen.getByText("First name is required")).toBeDefined();
  });
});
