"use client";

import { Suspense, use } from "react";
import { ArrowsLeftRight, CalendarBlank, Crown, FirstAid, Ticket } from "@phosphor-icons/react";
import {
  GENERIC_PROMPTS,
  greetingName,
  squadPrompts,
  statusLine,
  type BriefingEvent,
  type BriefingSquad,
  type SquadPrompt,
} from "@/components/chat/briefing";

const ICONS = {
  captain: Crown,
  fitness: FirstAid,
  transfer: ArrowsLeftRight,
  chip: Ticket,
  fixtures: CalendarBlank,
} as const;

export function EmptyBriefing({
  teamPromise,
  event,
  missing,
}: {
  teamPromise: Promise<BriefingSquad | null>;
  event: BriefingEvent;
  missing: boolean;
}) {
  return (
    <section className="chat-brief">
      {missing ? <p className="chat-missing">That chat isn&apos;t here.</p> : null}
      <Suspense fallback={<Greeting team={null} event={event} />}>
        <ResolvedGreeting teamPromise={teamPromise} event={event} />
      </Suspense>
    </section>
  );
}

export function PromptChips({
  teamPromise,
  onAsk,
}: {
  teamPromise: Promise<BriefingSquad | null>;
  onAsk: (question: string) => void;
}) {
  return (
    <Suspense fallback={<PromptRow prompts={GENERIC_PROMPTS} onAsk={onAsk} />}>
      <ResolvedPrompts teamPromise={teamPromise} onAsk={onAsk} />
    </Suspense>
  );
}

function ResolvedGreeting({ teamPromise, event }: { teamPromise: Promise<BriefingSquad | null>; event: BriefingEvent }) {
  return <Greeting team={use(teamPromise)} event={event} />;
}

function Greeting({ team, event }: { team: BriefingSquad | null; event: BriefingEvent }) {
  const now = new Date();
  return (
    <>
      <h2 className="chat-brief-title" suppressHydrationWarning>
        {greetingName(team, event, now)}
      </h2>
      <p className="chat-brief-deadline" suppressHydrationWarning>
        {statusLine(team, event, now)}
      </p>
    </>
  );
}

function ResolvedPrompts({
  teamPromise,
  onAsk,
}: {
  teamPromise: Promise<BriefingSquad | null>;
  onAsk: (question: string) => void;
}) {
  return <PromptRow prompts={squadPrompts(use(teamPromise))} onAsk={onAsk} />;
}

function PromptRow({ prompts, onAsk }: { prompts: SquadPrompt[]; onAsk: (question: string) => void }) {
  return (
    <div className="chat-prompts">
      {prompts.map((prompt) => {
        const Icon = ICONS[prompt.icon];
        return (
          <button key={`${prompt.icon}-${prompt.question}`} type="button" className="chat-prompt" onClick={() => onAsk(prompt.question)}>
            <Icon size={16} weight="bold" />
            {prompt.question}
          </button>
        );
      })}
    </div>
  );
}
