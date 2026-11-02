import { AnswerActions } from "@/components/chat/AnswerActions";
import { SafeMarkdown } from "@/components/chat/SafeMarkdown";
import { clockTime, londonStamp } from "@/components/chat/stamps";
import type { ChatBubble, WorkStep } from "@/lib/chat";

export function DeskByline({ createdAt, stopped }: { createdAt: string | null; stopped?: boolean }) {
  const time = clockTime(createdAt);
  return (
    <header className="chat-byline">
      <span className="chat-mark" aria-hidden>
        F
      </span>
      <span className="kicker">FPLBud desk</span>
      {stopped ? <span className="chat-stopped">Stopped</span> : null}
      {time ? <time dateTime={createdAt ?? undefined}>{time}</time> : null}
    </header>
  );
}

export function WorkSteps({ steps }: { steps: WorkStep[] }) {
  if (steps.length === 0) return null;
  return (
    <ol className="chat-steps">
      {steps.map((step, index) => (
        <li key={`${step.label}-${index}`} className={step.done ? "is-done" : "is-live"}>
          <span className="chat-step-mark" aria-hidden />
          <span>{step.label}</span>
        </li>
      ))}
    </ol>
  );
}

export function AssistantAnswer({ message }: { message: ChatBubble }) {
  return (
    <article className="chat-answer">
      <DeskByline createdAt={message.createdAt} stopped={message.stopped} />
      {message.stopped ? <WorkSteps steps={message.steps} /> : null}
      {message.text ? <SafeMarkdown text={message.text} citations={message.citations} /> : null}
      {message.disclaimers.length > 0 || message.dataAsOf ? (
        <footer className="chat-footnotes">
          {message.disclaimers.map((line) => (
            <p key={line} className="caption">
              {line}
            </p>
          ))}
          {message.dataAsOf ? <p className="caption">Data as of {londonStamp(message.dataAsOf)}</p> : null}
        </footer>
      ) : null}
      <AnswerActions
        text={message.text}
        messageId={message.messageId}
        feedback={message.feedback}
        tools={message.toolsUsed}
      />
    </article>
  );
}
