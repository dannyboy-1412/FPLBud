"use client";

import { useLayoutEffect } from "react";
import { applyEdition, persistEdition, readStoredEdition } from "@/lib/edition";

export function EditionPreference() {
  useLayoutEffect(() => {
    const stored = readStoredEdition();
    if (!stored) return;
    applyEdition(stored);
    persistEdition(stored);
  }, []);
  return null;
}
