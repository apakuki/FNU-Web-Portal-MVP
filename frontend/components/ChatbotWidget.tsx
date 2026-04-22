"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type Role = "user" | "assistant" | "system";

interface Message {
  role: Role;
  content: string;
}

interface Source {
  title: string;
}

interface ChatResponse {
  session_key: string;
  reply: string;
  escalated: boolean;
  escalation_reason: string | null;
  sources: Source[];
}

interface ChatbotWidgetProps {
  accessToken?: string | null;
  apiBase?: string;
  storageKey?: string;
  initialOpen?: boolean;
  greeting?: string;
  variant?: "fixed" | "embed";
}

const DEFAULT_GREETING =
  "Hi! I'm the FNU chatbot. Ask me about admissions, fees, timetables, or payments.";

export default function ChatbotWidget({
  accessToken = null,
  apiBase = "",
  storageKey = "fnu_chatbot_session",
  initialOpen = false,
  greeting = DEFAULT_GREETING,
  variant = "fixed",
}: ChatbotWidgetProps) {
  const embedMode = variant === "embed";
  const [open, setOpen] = useState(embedMode ? true : initialOpen);
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", content: greeting },
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [escalated, setEscalated] = useState<string | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const sessionKeyRef = useRef<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      sessionKeyRef.current = window.sessionStorage.getItem(storageKey);
    } catch {
      sessionKeyRef.current = null;
    }
  }, [storageKey]);

  useEffect(() => {
    if (open) {
      messagesEndRef.current?.scrollIntoView?.({ behavior: "smooth" });
    }
  }, [messages, open]);

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || sending) return;

      setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
      setInput("");
      setSending(true);
      setError(null);

      try {
        const res = await fetch(`${apiBase}/api/chat`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
          },
          body: JSON.stringify({
            message: trimmed,
            session_key: sessionKeyRef.current ?? undefined,
          }),
        });

        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.detail ?? `Chat failed (${res.status})`);
        }

        const data = (await res.json()) as ChatResponse;
        sessionKeyRef.current = data.session_key;
        try {
          window.sessionStorage.setItem(storageKey, data.session_key);
        } catch {
          // sessionStorage may be unavailable (Safari private mode); ignore.
        }
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: data.reply },
        ]);
        setSources(data.sources ?? []);
        if (data.escalated) {
          setEscalated(
            data.escalation_reason
              ? `This enquiry has been flagged for staff (${data.escalation_reason}).`
              : "This enquiry has been flagged for staff follow-up.",
          );
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Chat unavailable");
      } finally {
        setSending(false);
      }
    },
    [accessToken, apiBase, sending, storageKey],
  );

  const panelClass = embedMode
    ? "flex h-screen w-full flex-col overflow-hidden bg-white"
    : "flex h-[480px] w-[min(360px,calc(100vw-2rem))] flex-col overflow-hidden rounded-lg border border-gray-200 bg-white shadow-xl";

  const wrapperClass = embedMode
    ? "h-screen w-full"
    : "fixed bottom-6 right-6 z-50";

  return (
    <div className={wrapperClass}>
      {open ? (
        <div
          role="dialog"
          aria-label="FNU chatbot"
          className={panelClass}
        >
          <div className="flex items-center justify-between border-b bg-[#003A70] px-4 py-3">
            <span className="font-semibold text-white">Ask FNU</span>
            {!embedMode && (
              <button
                type="button"
                aria-label="Close chatbot"
                onClick={() => setOpen(false)}
                className="rounded p-1 text-white hover:bg-white/15"
              >
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  aria-hidden="true"
                >
                  <path d="M6 6l12 12M6 18L18 6" />
                </svg>
              </button>
            )}
          </div>

          {escalated && (
            <div
              role="status"
              className="border-b bg-[#FFB81C]/30 px-3 py-2 text-xs text-[#0A1F33]"
            >
              {escalated}
            </div>
          )}

          <div
            className="flex-1 overflow-y-auto bg-[#F4F6F9] px-3 py-3"
            data-testid="chatbot-messages"
          >
            <div className="flex flex-col gap-2">
              {messages.map((msg, i) => (
                <div
                  key={i}
                  className={
                    msg.role === "user"
                      ? "max-w-[85%] self-end rounded-lg bg-[#003A70] px-3 py-2 text-sm text-white shadow-sm"
                      : "max-w-[85%] self-start rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-[#0A1F33] shadow-sm"
                  }
                >
                  {msg.content}
                </div>
              ))}
              {sending && (
                <div className="self-start rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs text-gray-500">
                  Typing…
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
            {sources.length > 0 && !sending && (
              <p className="mt-2 text-[11px] text-gray-500">
                Sources: {sources.map((s) => s.title).join(", ")}
              </p>
            )}
            {error && (
              <p className="mt-2 text-[11px] text-red-700">{error}</p>
            )}
          </div>

          <form
            className="flex gap-2 border-t bg-white p-2"
            onSubmit={(e) => {
              e.preventDefault();
              sendMessage(input);
            }}
            autoComplete="off"
          >
            <input
              type="text"
              className="min-h-[40px] w-full rounded border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#003A70]"
              placeholder="Type a question…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={sending}
              maxLength={1000}
              aria-label="Chatbot message"
            />
            <button
              type="submit"
              disabled={sending || !input.trim()}
              className="min-h-[40px] rounded bg-[#003A70] px-4 py-2 text-sm font-semibold text-white hover:bg-[#002d57] disabled:opacity-60"
            >
              Send
            </button>
          </form>
        </div>
      ) : (
        <button
          type="button"
          aria-label="Open chatbot"
          onClick={() => setOpen(true)}
          className="flex h-14 w-14 items-center justify-center rounded-full bg-[#003A70] text-white shadow-lg hover:bg-[#002d57] focus:outline-none focus:ring-2 focus:ring-[#FFB81C]"
        >
          <svg
            width="26"
            height="26"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            aria-hidden="true"
          >
            <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
          </svg>
        </button>
      )}
    </div>
  );
}
