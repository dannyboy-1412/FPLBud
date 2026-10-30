"use client";

import { ApiNotice } from "@/components/programme/ApiNotice";

const RECOVERABLE =
  /minified react error #441|server components render|bad gateway|service unavailable|gateway timeout|fetch failed|econnrefused/i;

function readable(error: Error): string | null {
  const message = error.message?.trim() ?? "";
  if (!message || RECOVERABLE.test(message)) return null;
  if (/^minified react error #\d+/i.test(message)) {
    return "Something went wrong while putting this page together.";
  }
  return message;
}

export function RouteError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  const message = readable(error);
  if (message == null) return <ApiNotice retry={reset} />;
  return <ApiNotice message={message} retry={reset} />;
}
