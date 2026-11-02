"use client";

import { ArrowsLeftRight, CalendarBlank, Crown, Ticket } from "@phosphor-icons/react";
import { DeadlineClock } from "@/components/programme/DeadlineClock";
import { londonStamp } from "@/components/chat/stamps";

const PROMPTS = [
  { kicker: "Captaincy", question: "Who should I captain?", icon: Crown },
  { kicker: "Transfers", question: "Is a hit worth it?", icon: ArrowsLeftRight },
  { kicker: "Chips", question: "Should I use a chip this week?", icon: Ticket },
  { kicker: "Fixtures", question: "Which of my players have the best fixtures?", icon: CalendarBlank },
] as const;

export function EmptyBriefing({
  event,
  missing,
  onAsk,
}: {
  event: { id: number; name: string; deadline_time: string } | null;
  missing: boolean;
  onAsk: (question: string) => void;
}) {
  return (
    <section className="chat-brief">
      {missing ? <p className="chat-missing">That conversation isn&apos;t in the notebook.</p> : null}
      <p className="kicker">Today&apos;s briefing</p>
      <h2 className="chat-brief-title">{event ? `Gameweek ${event.id}` : "The desk is open"}</h2>
      {event ? (
        <p className="chat-brief-deadline">
          <span>Deadline {londonStamp(event.deadline_time)}</span>
          <DeadlineClock iso={event.deadline_time} />
        </p>
      ) : (
        <p className="chat-brief-deadline">Ask about your squad, a player, or the deadline.</p>
      )}
      <div className="chat-prompts">
        {PROMPTS.map((prompt) => {
          const Icon = prompt.icon;
          return (
            <button key={prompt.kicker} type="button" className="chat-prompt" onClick={() => onAsk(prompt.question)}>
              <span className="chat-prompt-kicker">
                <Icon size={16} weight="bold" />
                <span className="kicker">{prompt.kicker}</span>
              </span>
              <span className="chat-prompt-q">{prompt.question}</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
