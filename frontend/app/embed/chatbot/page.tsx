import type { Metadata } from "next";
import ChatbotWidget from "@/components/ChatbotWidget";

export const metadata: Metadata = {
  title: "Ask FNU",
  description: "FNU chatbot",
  robots: { index: false, follow: false },
};

export default function EmbeddedChatbotPage() {
  return <ChatbotWidget variant="embed" />;
}
