document.querySelectorAll("[data-tabs]").forEach((root) => {
  const tabs = [...root.querySelectorAll('[role="tab"]')];
  const panels = [...root.querySelectorAll('[role="tabpanel"]')];
  function activate(id) {
    tabs.forEach((t) => {
      const on = t.id === id;
      t.setAttribute("aria-selected", on ? "true" : "false");
      t.tabIndex = on ? 0 : -1;
    });
    panels.forEach((p) => {
      p.hidden = p.getAttribute("aria-labelledby") !== id;
    });
  }
  tabs.forEach((t) => {
    t.addEventListener("click", () => activate(t.id));
    t.addEventListener("keydown", (e) => {
      const i = tabs.indexOf(t);
      if (e.key === "ArrowRight") tabs[(i + 1) % tabs.length].focus();
      if (e.key === "ArrowLeft") tabs[(i - 1 + tabs.length) % tabs.length].focus();
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        activate(t.id);
      }
    });
  });
});
