import { DeadlineClock } from "@/components/programme/DeadlineClock";
import { loadMeta } from "@/lib/server/data";

function formatDeadline(iso: string) {
  return new Date(iso).toLocaleString("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/London",
  });
}

export async function GameweekLine() {
  const meta = await loadMeta().catch(() => null);
  const event = meta?.next_event ?? meta?.current_event;
  if (!event) return <span className="kicker">The FPL tactics column</span>;
  return (
    <div className="edition kicker text-center">
      Gameweek {event.id} · {formatDeadline(event.deadline_time)}
      <DeadlineClock iso={event.deadline_time} />
    </div>
  );
}
