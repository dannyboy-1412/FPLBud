import { ChatPanel } from "@/components/chat/ChatPanel";

export default function ChatPage() {
  return (
    <>
      <p className="kicker">Assistant</p>
      <h1>Ask about your team</h1>
      <p className="text-ink-soft max-w-2xl">
        Answers use your saved squad and FPLBud&apos;s projections. Nothing here is a bet, and the numbers are estimates.
        Chat is off unless it has been turned on for your account.
      </p>
      <ChatPanel />
    </>
  );
}
