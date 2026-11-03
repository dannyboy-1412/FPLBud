import { AnswerActions } from "@/components/chat/AnswerActions";
import { SafeMarkdown } from "@/components/chat/SafeMarkdown";
import { SourcesLedger } from "@/components/chat/SourcesLedger";
import { clockTime, londonStamp } from "@/components/chat/stamps";
import type { ChatBubble, WorkStep } from "@/lib/chat";

export function DeskByline({ createdAt, stopped }: { createdAt: string | null; stopped?: boolean }) {
  const time = clockTime(createdAt);
  return (
    <header className="chat-byline">
      <span className="chat-mark" aria-hidden>
        F
      </span>
      <span className="chat-name">FPLBud</span>
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

export function LiveStep({ steps }: { steps: WorkStep[] }) {
  const current = [...steps].reverse().find((step) => !step.done) ?? steps[steps.length - 1];
  if (!current) return null;
  return <p className="chat-live-step">{current.label}</p>;
}

export function AssistantAnswer({
  message,
  latest,
  arrive,
}: {
  message: ChatBubble;
  latest: boolean;
  arrive: boolean;
}) {
  const className = ["chat-answer", latest ? "is-latest" : "", arrive ? "chat-arrive" : ""].filter(Boolean).join(" ");
  return (
    <article className={className}>
      <DeskByline createdAt={message.createdAt} stopped={message.stopped} />
      <Checked message={message} />
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
      <AnswerActions text={message.text} messageId={message.messageId} feedback={message.feedback} />
    </article>
  );
}

function Checked({ message }: { message: ChatBubble }) {
  if (message.toolsUsed.length > 0) {
    const count = message.toolsUsed.length;
    return (
      <details className="chat-checked">
        <summary>
          Checked {count} {count === 1 ? "source" : "sources"}
        </summary>
        <SourcesLedger tools={message.toolsUsed} />
      </details>
    );
  }
  if (message.steps.length === 0) return null;
  const count = message.steps.length;
  return (
    <details className="chat-checked">
      <summary>
        Checked {count} {count === 1 ? "step" : "steps"}
      </summary>
      <WorkSteps steps={message.steps.map((step) => ({ ...step, done: true }))} />
    </details>
  );
}
