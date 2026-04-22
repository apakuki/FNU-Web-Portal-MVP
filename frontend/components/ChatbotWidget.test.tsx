import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ChatbotWidget from "./ChatbotWidget";

type FetchMock = ReturnType<typeof vi.fn>;

function mockFetchOnce(body: Record<string, unknown>, status = 200) {
  const fetchMock = global.fetch as FetchMock;
  fetchMock.mockResolvedValueOnce({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response);
}

describe("ChatbotWidget", () => {
  let originalFetch: typeof global.fetch;

  beforeEach(() => {
    originalFetch = global.fetch;
    global.fetch = vi.fn();
    window.sessionStorage.clear();
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("starts minimised and shows launcher button", () => {
    render(<ChatbotWidget />);
    expect(
      screen.getByRole("button", { name: /open chatbot/i }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("opens dialog on launcher click and shows greeting", () => {
    render(<ChatbotWidget />);
    fireEvent.click(screen.getByRole("button", { name: /open chatbot/i }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText(/ask me about admissions/i)).toBeInTheDocument();
  });

  it("sends a message to /api/chat and renders the reply", async () => {
    mockFetchOnce({
      session_key: "sess-abc",
      reply: "Applications open in April.",
      escalated: false,
      escalation_reason: null,
      sources: [{ title: "Admissions FAQ" }],
    });

    render(<ChatbotWidget />);
    fireEvent.click(screen.getByRole("button", { name: /open chatbot/i }));
    fireEvent.change(screen.getByLabelText(/chatbot message/i), {
      target: { value: "When does semester start?" },
    });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() =>
      expect(screen.getByText(/applications open in april/i)).toBeInTheDocument(),
    );
    expect(screen.getByText(/admissions faq/i)).toBeInTheDocument();
    expect(window.sessionStorage.getItem("fnu_chatbot_session")).toBe("sess-abc");

    const fetchMock = global.fetch as FetchMock;
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/chat");
    const body = JSON.parse((init as RequestInit).body as string);
    expect(body.message).toBe("When does semester start?");
  });

  it("attaches Bearer token when provided", async () => {
    mockFetchOnce({
      session_key: "s1",
      reply: "ok",
      escalated: false,
      escalation_reason: null,
      sources: [],
    });

    render(<ChatbotWidget accessToken="tok_123" />);
    fireEvent.click(screen.getByRole("button", { name: /open chatbot/i }));
    fireEvent.change(screen.getByLabelText(/chatbot message/i), {
      target: { value: "hi" },
    });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() => expect(screen.getByText("ok")).toBeInTheDocument());
    const fetchMock = global.fetch as FetchMock;
    const [, init] = fetchMock.mock.calls[0];
    const headers = (init as RequestInit).headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer tok_123");
  });

  it("shows escalation banner when response is escalated", async () => {
    mockFetchOnce({
      session_key: "s2",
      reply: "A staff member will follow up.",
      escalated: true,
      escalation_reason: "finance",
      sources: [],
    });

    render(<ChatbotWidget initialOpen />);
    fireEvent.change(screen.getByLabelText(/chatbot message/i), {
      target: { value: "I need a refund" },
    });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent(/finance/i),
    );
  });

  it("surfaces an error message when the API call fails", async () => {
    mockFetchOnce({ detail: "rate limited" }, 429);

    render(<ChatbotWidget initialOpen />);
    fireEvent.change(screen.getByLabelText(/chatbot message/i), {
      target: { value: "hi" },
    });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() =>
      expect(screen.getByText(/rate limited/i)).toBeInTheDocument(),
    );
  });

  it("renders embed variant expanded with no close button", () => {
    render(<ChatbotWidget variant="embed" />);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /close chatbot/i }),
    ).not.toBeInTheDocument();
  });
});
