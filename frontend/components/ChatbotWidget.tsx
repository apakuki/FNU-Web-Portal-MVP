"use client";


import { useState, useRef, useEffect } from "react";
import { ChatBubbleLeftEllipsisIcon, XMarkIcon, ExclamationTriangleIcon } from "@heroicons/react/24/outline";

export default function ChatbotWidget() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<
    { role: "user" | "assistant"; content: string }[]
  >([
    {
      role: "assistant",
      content: "How can I help you today?",
    },
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [escalated, setEscalated] = useState<null | string>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open && messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, open]);

  const handleSend = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!input.trim() || sending) return;
    const userMsg = input.trim();
    setMessages((msgs) => [...msgs, { role: "user", content: userMsg }]);
    setInput("");
    setSending(true);

    // Simulate escalation detection (replace with real logic after API integration)
    if (/human|staff|escalate/i.test(userMsg)) {
      setTimeout(() => {
        setMessages((msgs) => [
          ...msgs,
          {
            role: "assistant",
            content:
              "I've flagged your enquiry for a human staff member. Someone will follow up soon.",
          },
        ]);
        setEscalated("Your conversation has been escalated to staff.");
        setSending(false);
      }, 800);
      return;
    }

    // Simulate assistant reply (replace with API call)
    setTimeout(() => {
      setMessages((msgs) => [
        ...msgs,
        {
          role: "assistant",
          content: "(This is a placeholder response. API integration coming soon.)",
        },
      ]);
      setSending(false);
    }, 1000);
  };

  return (
    <div className="fixed bottom-6 right-6 z-50">
      {open ? (
        <div className="w-80 h-96 bg-white shadow-xl rounded-lg flex flex-col border border-gray-200">
          <div className="flex items-center justify-between px-4 py-2 border-b border-gray-100 bg-[#003A70] rounded-t-lg">
            <span className="text-white font-semibold">Ask FNU</span>
            <button
              aria-label="Close chatbot"
              onClick={() => setOpen(false)}
              className="text-white hover:text-[#FFB81C]"
            >
              <XMarkIcon className="h-5 w-5" />
            </button>
          </div>
          {escalated && (
            <div className="flex items-center gap-2 bg-[#FFB81C] text-[#0A1F33] text-xs px-3 py-2 border-b border-[#F9A825]">
              <ExclamationTriangleIcon className="h-4 w-4" />
              <span>{escalated}</span>
            </div>
          )}
          <div className="flex-1 p-4 overflow-y-auto text-gray-800 bg-[#F4F6F9]">
            <div className="flex flex-col gap-3">
              {messages.map((msg, i) => (
                <div
                  key={i}
                  className={
                    msg.role === "user"
                      ? "self-end max-w-[80%] bg-[#003A70] text-white rounded-lg px-3 py-2 text-sm shadow"
                      : "self-start max-w-[80%] bg-white border border-gray-200 text-[#0A1F33] rounded-lg px-3 py-2 text-sm shadow"
                  }
                >
                  {msg.content}
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
          </div>
          <form
            className="p-2 border-t border-gray-100 bg-white"
            onSubmit={handleSend}
            autoComplete="off"
          >
            <div className="flex gap-2">
              <input
                type="text"
                className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#003A70]"
                placeholder="Type your question..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                disabled={sending}
                maxLength={400}
                aria-label="Chatbot message input"
              />
              <button
                type="submit"
                className="bg-[#003A70] hover:bg-[#FFB81C] text-white font-semibold rounded px-4 py-2 text-sm disabled:opacity-60"
                disabled={sending || !input.trim()}
                aria-label="Send message"
              >
                Send
              </button>
            </div>
          </form>
        </div>
      ) : (
        <button
          aria-label="Open chatbot"
          onClick={() => setOpen(true)}
          className="bg-[#003A70] hover:bg-[#FFB81C] text-white rounded-full shadow-lg p-4 flex items-center justify-center focus:outline-none focus:ring-2 focus:ring-[#FFB81C]"
        >
          <ChatBubbleLeftEllipsisIcon className="h-7 w-7" />
        </button>
      )}
    </div>
  );
}
