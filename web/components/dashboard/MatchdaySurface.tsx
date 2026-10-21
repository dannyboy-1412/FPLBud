"use client";

import { useEffect } from "react";

export function MatchdaySurface() {
  useEffect(() => {
    document.body.dataset.surface = "matchday";
    return () => {
      delete document.body.dataset.surface;
    };
  }, []);
  return null;
}
