import { DeskByline, LiveStep } from "@/components/chat/AssistantAnswer";
import { SafeMarkdown } from "@/components/chat/SafeMarkdown";
import type { LiveTurn } from "@/lib/chat";

export function LiveAnswer({
  live,
  busy,
  onRetry,
}: {
  live: LiveTurn;
  busy: boolean;
  onRetry: (() => void) | null;
}) {
  const steps =
    live.steps.length > 0 ? live.steps : busy && !live.draft ? [{ label: "Reading the brief", done: false }] : [];
  const caret = busy ? <span className="chat-caret" aria-hidden /> : null;

  return (
    <article className="chat-answer is-live chat-arrive" aria-busy={busy}>
      <DeskByline createdAt={null} />
      {live.draft ? null : <LiveStep steps={steps} />}
      {live.draft ? <SafeMarkdown text={live.draft} citations={[]} trailing={caret} /> : null}
      {live.error ? (
        <div className="chat-error" role="alert">
          <p>{live.error}</p>
          {onRetry ? (
            <button type="button" className="chat-retry" onClick={onRetry}>
              Retry
            </button>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}
