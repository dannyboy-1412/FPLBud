"use client";

import { useRef, type KeyboardEvent } from "react";

export type TabOption<T extends string> = { id: T; label: string };

export function tabTriggerId(name: string, id: string) {
  return `${name}-tab-${id}`;
}

export function tabPanelId(name: string) {
  return `${name}-panel`;
}

export function Tabs<T extends string>({
  name,
  label,
  tabs,
  value,
  onChange,
  wide = false,
}: {
  name: string;
  label: string;
  tabs: readonly TabOption<T>[];
  value: T;
  onChange: (id: T) => void;
  wide?: boolean;
}) {
  const refs = useRef<Array<HTMLButtonElement | null>>([]);
  const selected = tabs.findIndex((tab) => tab.id === value);
  const current = selected === -1 ? 0 : selected;

  function move(event: KeyboardEvent<HTMLDivElement>) {
    const last = tabs.length - 1;
    let next = current;
    if (event.key === "ArrowRight" && current < last) next = current + 1;
    else if (event.key === "ArrowLeft" && current > 0) next = current - 1;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = last;
    else return;
    event.preventDefault();
    onChange(tabs[next].id);
    refs.current[next]?.focus();
  }

  return (
    <div role="tablist" aria-label={label} className={`insight-tabs${wide ? " is-wide" : ""}`} onKeyDown={move}>
      {tabs.map((tab, index) => {
        const active = tab.id === value;
        return (
          <button
            key={tab.id}
            ref={(node) => {
              refs.current[index] = node;
            }}
            type="button"
            role="tab"
            id={tabTriggerId(name, tab.id)}
            className={`insight-tab${active ? " is-selected" : ""}`}
            aria-selected={active}
            aria-controls={tabPanelId(name)}
            tabIndex={index === current ? 0 : -1}
            onClick={() => onChange(tab.id)}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
