import { DeadlineClock } from "@/components/programme/DeadlineClock";
import { loadMeta } from "@/lib/server/data";

function deadlineLabels(iso: string) {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/London",
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date(iso));
  const value = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((part) => part.type === type)?.value ?? "";
  const day = `${value("weekday")} ${value("day")} ${value("month")}`;
  const time = `${value("hour")}:${value("minute")}`;
  return { long: `${day}, ${time}`, short: `${day} ${time}` };
}

export async function GameweekLine() {
  const meta = await loadMeta().catch(() => null);
  const event = meta?.next_event ?? meta?.current_event;
  if (!event) return <span className="kicker">The FPL tactics column</span>;
  const labels = deadlineLabels(event.deadline_time);
  return (
    <div className="edition kicker masthead-deadline">
      <span className="masthead-deadline-long">
        Gameweek {event.id} · <time dateTime={event.deadline_time}>{labels.long}</time>
      </span>
      <span className="masthead-deadline-short">
        GW{event.id} · <time dateTime={event.deadline_time}>{labels.short}</time>
      </span>
      <DeadlineClock iso={event.deadline_time} />
    </div>
  );
}
