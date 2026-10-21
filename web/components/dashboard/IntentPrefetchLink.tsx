"use client";

import Link from "next/link";
import { useState, type ComponentProps } from "react";

type PrefetchOnIntent = "shell" | "full";

type IntentPrefetchLinkProps = Omit<ComponentProps<typeof Link>, "prefetch"> & {
  prefetchOnIntent: PrefetchOnIntent;
};

export function IntentPrefetchLink({
  prefetchOnIntent,
  onMouseEnter,
  onFocus,
  onTouchStart,
  ...props
}: IntentPrefetchLinkProps) {
  const [armed, setArmed] = useState(false);

  const arm = () => {
    if (!armed) setArmed(true);
  };

  return (
    <Link
      {...props}
      prefetch={armed ? (prefetchOnIntent === "full" ? true : null) : false}
      onMouseEnter={(event) => {
        arm();
        onMouseEnter?.(event);
      }}
      onFocus={(event) => {
        arm();
        onFocus?.(event);
      }}
      onTouchStart={(event) => {
        arm();
        onTouchStart?.(event);
      }}
    />
  );
}
