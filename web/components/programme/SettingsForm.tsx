"use client";

import Link from "next/link";
import { useEffect, useRef, useState, useTransition, type ReactNode } from "react";
import { Check, Minus, Plus, SignOut } from "@phosphor-icons/react";
import { SelectionCriteria } from "@/components/programme/SelectionCriteria";
import {
  hasUnsavedSettings,
  hitLimitNote,
  HORIZON_OPTIONS,
  MAX_HITS,
  metricTotal,
  MIN_HITS,
  weightsEqual,
  type PlanningSettings,
} from "@/components/programme/settings-model";
import { deleteAccount, saveSettings } from "@/lib/server/actions";
import { createClient } from "@/lib/supabase/client";
import type { Meta, Profile, Weights } from "@/lib/api";

type Edition = "morning" | "evening";

const EDITIONS: ReadonlyArray<{
  id: Edition;
  label: string;
  caption: string;
}> = [
  { id: "morning", label: "Morning edition", caption: "Daylight paper and forest ink" },
  { id: "evening", label: "Evening edition", caption: "Dark pitch paper for low light" },
];

function applyEdition(next: Edition) {
  if (next === "evening") {
    document.documentElement.setAttribute("data-edition", "evening");
    return;
  }
  document.documentElement.removeAttribute("data-edition");
}

function readStoredEdition(): Edition {
  try {
    return window.localStorage.getItem("edition") === "evening" ? "evening" : "morning";
  } catch {
    return "morning";
  }
}

export function SettingsForm({
  profile,
  meta,
  assistantSection,
}: {
  profile: Profile;
  meta: Meta;
  assistantSection?: ReactNode;
}) {
  const [saved, setSaved] = useState<PlanningSettings>({
    weights: profile.weights,
    default_horizon: profile.default_horizon,
    max_hits: profile.max_hits,
  });
  const [weights, setWeights] = useState<Weights>(profile.weights);
  const [horizon, setHorizon] = useState(profile.default_horizon);
  const [maxHits, setMaxHits] = useState(profile.max_hits);
  const [edition, setEdition] = useState<Edition>("morning");
  const [message, setMessage] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [confirm, setConfirm] = useState("");
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [saving, startSave] = useTransition();
  const [signingOut, startSignOut] = useTransition();
  const [deleting, startDelete] = useTransition();
  const confirmInputRef = useRef<HTMLInputElement>(null);

  const isDirty = hasUnsavedSettings(
    { weights, default_horizon: horizon, max_hits: maxHits },
    saved,
  );
  const isDefaultWeights = weightsEqual(weights, meta.default_weights);
  const canSave = isDirty && metricTotal(weights) > 0 && !saving;

  useEffect(() => {
    const stored = readStoredEdition();
    applyEdition(stored);
    if (stored === "evening") {
      setEdition("evening");
    }
  }, []);

  useEffect(() => {
    if (!deleteOpen) return;
    confirmInputRef.current?.focus();
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && !deleting) {
        setDeleteOpen(false);
        setConfirm("");
        setDeleteError(null);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [deleteOpen, deleting]);

  function updateWeights(next: Weights) {
    setWeights(next);
    setMessage(null);
    setSaveError(null);
  }

  function updateHorizon(next: number) {
    setHorizon(next);
    setMessage(null);
    setSaveError(null);
  }

  function updateMaxHits(next: number) {
    setMaxHits(Math.min(MAX_HITS, Math.max(MIN_HITS, next)));
    setMessage(null);
    setSaveError(null);
  }

  function discardChanges() {
    setWeights(saved.weights);
    setHorizon(saved.default_horizon);
    setMaxHits(saved.max_hits);
    setMessage(null);
    setSaveError(null);
  }

  function handleSave() {
    if (!canSave) return;
    setSaveError(null);
    setMessage(null);
    const next: PlanningSettings = {
      weights: { ...weights },
      default_horizon: horizon,
      max_hits: maxHits,
    };
    startSave(async () => {
      const result = await saveSettings(next);
      if (result.error) {
        setSaveError(result.error);
        return;
      }
      setSaved(next);
      setMessage("Changes saved. Your agent is updating your plans.");
    });
  }

  function selectEdition(next: Edition) {
    setEdition(next);
    applyEdition(next);
    try {
      window.localStorage.setItem("edition", next);
    } catch {
      /* ignore unavailable storage */
    }
  }

  function closeDeleteModal() {
    if (deleting) return;
    setDeleteOpen(false);
    setConfirm("");
    setDeleteError(null);
  }

  return (
    <div className="settings-stack">
      <section className="settings-chapter" aria-labelledby="scoring-heading">
        <div className="settings-aside">
          <h2 id="scoring-heading" className="settings-heading">
            Scoring blend
          </h2>
          <p className="settings-copy">
            Choose how much weight each signal carries in your projected points and transfer rankings.
          </p>
          {!isDefaultWeights ? (
            <button
              type="button"
              className="settings-link-action"
              onClick={() => updateWeights({ ...meta.default_weights })}
            >
              Reset to default blend
            </button>
          ) : null}
        </div>

        <div className="settings-panel">
          <SelectionCriteria
            weights={weights}
            labels={meta.metric_labels}
            descriptions={meta.metric_descriptions}
            onChange={updateWeights}
          />
        </div>
      </section>

      <section className="settings-chapter" aria-labelledby="defaults-heading">
        <div className="settings-aside">
          <h2 id="defaults-heading" className="settings-heading">
            Planning defaults
          </h2>
          <p className="settings-copy">
            The horizon and hit tolerance used when building transfer plans.
          </p>
        </div>

        <div className="settings-panel">
          <div className="settings-control-list">
            <div className="settings-control-row">
              <div className="settings-control-label">
                <p id="horizon-label" className="settings-row-title">
                  Default horizon
                </p>
                <p className="settings-row-note">
                  How many gameweeks ahead your plans look by default.
                </p>
              </div>
              <div
                className="settings-segments"
                role="radiogroup"
                aria-labelledby="horizon-label"
              >
                {HORIZON_OPTIONS.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    role="radio"
                    aria-checked={horizon === option.value}
                    className={`settings-segment ${horizon === option.value ? "is-selected" : ""}`}
                    onClick={() => updateHorizon(option.value)}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="settings-control-row">
              <div className="settings-control-label">
                <p id="hits-label" className="settings-row-title">
                  Max transfer hits
                </p>
                <p className="settings-row-note">{hitLimitNote(maxHits)}</p>
              </div>
              <div className="settings-stepper" role="group" aria-labelledby="hits-label">
                <button
                  type="button"
                  className="settings-step-btn"
                  aria-label="Decrease max transfer hits"
                  disabled={maxHits <= MIN_HITS}
                  onClick={() => updateMaxHits(maxHits - 1)}
                >
                  <Minus size={16} weight="bold" />
                </button>
                <span className="settings-step-value nums" aria-live="polite">
                  {maxHits}
                </span>
                <button
                  type="button"
                  className="settings-step-btn"
                  aria-label="Increase max transfer hits"
                  disabled={maxHits >= MAX_HITS}
                  onClick={() => updateMaxHits(maxHits + 1)}
                >
                  <Plus size={16} weight="bold" />
                </button>
              </div>
            </div>
          </div>

          <div className={`settings-savebar ${isDirty ? "is-dirty" : ""}`}>
            <div className="settings-savebar-status" aria-live="polite">
              {saveError ? (
                <p className="settings-status-error" role="alert">
                  {saveError}
                </p>
              ) : message ? (
                <p className="settings-status-ok">{message}</p>
              ) : isDirty ? (
                <p className="settings-status-dirty">
                  Unsaved changes. Saving re-runs your agent.
                </p>
              ) : (
                <p className="settings-status-idle">
                  All scoring and planning settings are saved.
                </p>
              )}
            </div>

            <div className="settings-savebar-actions">
              {isDirty ? (
                <button
                  type="button"
                  className="settings-quiet-btn"
                  disabled={saving}
                  onClick={discardChanges}
                >
                  Discard
                </button>
              ) : null}
              <button
                type="button"
                className="btn btn-primary"
                disabled={!canSave}
                onClick={handleSave}
              >
                {saving ? "Saving changes..." : "Save changes"}
              </button>
            </div>
          </div>
        </div>
      </section>

      <section className="settings-chapter" aria-labelledby="appearance-heading">
        <div className="settings-aside">
          <h2 id="appearance-heading" className="settings-heading">
            Appearance
          </h2>
          <p className="settings-copy">
            Switch between daylight and evening paper. Applies immediately in this browser.
          </p>
        </div>

        <div className="settings-panel">
          <div
            className="edition-grid"
            role="radiogroup"
            aria-labelledby="appearance-heading"
          >
            {EDITIONS.map((item) => {
              const selected = edition === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  className={`edition-card ${selected ? "is-selected" : ""}`}
                  onClick={() => selectEdition(item.id)}
                >
                  <div className={`edition-specimen is-${item.id}`} aria-hidden="true">
                    <div className="edition-specimen-bar">
                      <span className="edition-specimen-word" />
                      <span className="edition-specimen-dot" />
                    </div>
                    <div className="edition-specimen-sheet">
                      <span className="edition-specimen-line is-title" />
                      <span className="edition-specimen-line is-body" />
                      <span className="edition-specimen-accent" />
                    </div>
                  </div>
                  <div className="edition-meta">
                    <span className="edition-title">{item.label}</span>
                    <span className="edition-caption">{item.caption}</span>
                  </div>
                  <span className={`edition-check ${selected ? "is-selected" : ""}`} aria-hidden="true">
                    {selected ? <Check size={14} weight="bold" /> : null}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </section>

      {assistantSection}

      <section className="settings-chapter" aria-labelledby="account-heading">
        <div className="settings-aside">
          <h2 id="account-heading" className="settings-heading">
            Account
          </h2>
          <p className="settings-copy">
            Your linked Fantasy Premier League team, session, and account data.
          </p>
        </div>

        <div className="settings-panel settings-account-stack">
          <div className="settings-account-row">
            <div className="settings-account-identity">
              <p className="settings-row-title">
                {profile.display_name || "Signed-in manager"}
              </p>
              {profile.fpl_entry_id ? (
                <p className="settings-row-note">
                  {profile.fpl_team_name ? `${profile.fpl_team_name} ` : "Team "}
                  <span className="nums">(#{profile.fpl_entry_id})</span>{" "}
                  <Link href="/dashboard" className="settings-inline-link">
                    Open team
                  </Link>
                </p>
              ) : (
                <p className="settings-row-note">
                  No FPL team linked yet.{" "}
                  <Link href="/onboarding" className="settings-inline-link">
                    Link a team
                  </Link>
                </p>
              )}
            </div>

            <button
              type="button"
              className="btn btn-secondary"
              disabled={signingOut}
              onClick={() => {
                startSignOut(async () => {
                  await createClient().auth.signOut();
                  window.location.href = "/";
                });
              }}
            >
              <SignOut size={16} weight="bold" aria-hidden="true" />
              {signingOut ? "Signing out..." : "Sign out"}
            </button>
          </div>

          <div className="settings-danger">
            <div>
              <p className="settings-danger-title">Delete account</p>
              <p className="settings-danger-copy">
                Permanently remove your profile, linked team, saved plans, and chat history. This
                cannot be undone.
              </p>
            </div>
            <button
              type="button"
              className="btn btn-destructive"
              onClick={() => {
                setConfirm("");
                setDeleteError(null);
                setDeleteOpen(true);
              }}
            >
              Delete account
            </button>
          </div>
        </div>
      </section>

      {deleteOpen ? (
        <div
          className="settings-modal-backdrop"
          onClick={(event) => {
            if (event.target === event.currentTarget) closeDeleteModal();
          }}
        >
          <div
            className="settings-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-account-title"
          >
            <h2 id="delete-account-title" className="settings-modal-title">
              Delete account
            </h2>
            <p className="settings-modal-copy">
              This deletes your profile, linked team, plans, and chat history. It cannot be undone.
            </p>
            <label htmlFor="delete-confirm-input" className="settings-modal-label">
              Type <strong>DELETE</strong> to confirm
            </label>
            <input
              ref={confirmInputRef}
              id="delete-confirm-input"
              className="settings-modal-input"
              value={confirm}
              autoComplete="off"
              onChange={(e) => setConfirm(e.target.value)}
              placeholder="DELETE"
            />
            {deleteError ? (
              <p className="settings-status-error mt-3" role="alert">
                {deleteError}
              </p>
            ) : null}
            <div className="settings-modal-actions">
              <button
                type="button"
                className="btn btn-secondary"
                disabled={deleting}
                onClick={closeDeleteModal}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-destructive"
                disabled={confirm !== "DELETE" || deleting}
                onClick={() => {
                  setDeleteError(null);
                  startDelete(async () => {
                    const result = await deleteAccount();
                    if (result.error) {
                      setDeleteError(result.error);
                      return;
                    }
                    await createClient().auth.signOut();
                    window.location.href = "/";
                  });
                }}
              >
                {deleting ? "Deleting..." : "Delete account"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
