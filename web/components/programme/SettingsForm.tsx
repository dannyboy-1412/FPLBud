"use client";

import { useEffect, useState, useTransition } from "react";
import { SelectionCriteria } from "@/components/programme/SelectionCriteria";
import { deleteAccount, saveSettings } from "@/lib/server/actions";
import { createClient } from "@/lib/supabase/client";
import type { Meta, Profile, Weights } from "@/lib/api";

export function SettingsForm({ profile, meta }: { profile: Profile; meta: Meta }) {
  const [weights, setWeights] = useState<Weights>(profile.weights);
  const [horizon, setHorizon] = useState(profile.default_horizon);
  const [maxHits, setMaxHits] = useState(profile.max_hits);
  const [edition, setEdition] = useState<"morning" | "evening">("morning");
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [confirm, setConfirm] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, startSave] = useTransition();
  const [signingOut, startSignOut] = useTransition();
  const [deleting, startDelete] = useTransition();

  useEffect(() => {
    const stored = window.localStorage.getItem("edition");
    if (stored === "evening") {
      document.documentElement.dataset.edition = "evening";
      setEdition("evening");
    }
  }, []);

  return (
    <>
      <section className="mt-8">
        <p className="kicker">Selection criteria</p>
        <SelectionCriteria
          weights={weights}
          labels={meta.metric_labels}
          descriptions={meta.metric_descriptions}
          onChange={setWeights}
        />
        <button
          type="button"
          className="btn btn-primary mt-4"
          disabled={saving}
          onClick={() => {
            setError(null);
            setMessage(null);
            startSave(async () => {
              const result = await saveSettings({
                weights,
                default_horizon: horizon,
                max_hits: maxHits,
              });
              if (result.error) {
                setError(result.error);
                return;
              }
              setMessage("Saved, re-running your agent");
            });
          }}
        >
          {saving ? "Saving..." : "Save"}
        </button>
        {message ? <p className="caption mt-2">{message}</p> : <p className="caption mt-2">Saving re-runs your agent.</p>}
        {error ? <p className="caption text-claret mt-2">{error}</p> : null}
      </section>
      <div className="double-rule my-10" />
      <section>
        <p className="kicker">Defaults</p>
        <div className="flex gap-4 mt-4">
          {[1, 3, 5].map((h) => (
            <button
              key={h}
              type="button"
              className={`btn ${horizon === h ? "btn-primary" : "btn-secondary"}`}
              onClick={() => setHorizon(h)}
            >
              {h}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-4 mt-4">
          <span className="kicker">Max hits</span>
          <button type="button" className="btn btn-secondary" onClick={() => setMaxHits(Math.max(0, maxHits - 1))}>
            −
          </button>
          <span className="stat">{maxHits}</span>
          <button type="button" className="btn btn-secondary" onClick={() => setMaxHits(Math.min(3, maxHits + 1))}>
            +
          </button>
        </div>
      </section>
      <div className="double-rule my-10" />
      <section>
        <p className="kicker">Appearance</p>
        <div className="flex gap-3 mt-4">
          {(["morning", "evening"] as const).map((e) => (
            <button
              key={e}
              type="button"
              className={`btn ${edition === e ? "btn-primary" : "btn-secondary"}`}
              onClick={() => {
                setEdition(e);
                document.documentElement.dataset.edition = e === "evening" ? "evening" : "";
                window.localStorage.setItem("edition", e);
              }}
            >
              {e === "morning" ? "Morning edition" : "Evening edition"}
            </button>
          ))}
        </div>
      </section>
      <div className="double-rule my-10" />
      <section>
        <p className="kicker">Account</p>
        <div className="flex gap-3 mt-4">
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
            {signingOut ? "Signing out…" : "Sign out"}
          </button>
          <button type="button" className="btn btn-destructive" onClick={() => setDeleteOpen(true)}>
            Delete account
          </button>
        </div>
      </section>
      {deleteOpen ? (
        <div className="fixed inset-0 grid place-items-center bg-[rgba(22,20,18,0.4)]">
          <div className="bg-paper-bright border border-ink shadow-[6px_6px_0_#161412] p-8 max-w-md">
            <h2>Delete account</h2>
            <p className="prose-body mt-3">
              This deletes your profile, saved team and plans. It can&apos;t be undone.
            </p>
            <input
              className="w-full mt-4 border-b-2 border-ink bg-transparent h-12"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              placeholder="Type DELETE"
            />
            <div className="flex gap-3 mt-4">
              <button
                type="button"
                className="btn btn-destructive"
                disabled={confirm !== "DELETE" || deleting}
                onClick={() => {
                  startDelete(async () => {
                    const result = await deleteAccount();
                    if (result.error) {
                      setError(result.error);
                      return;
                    }
                    await createClient().auth.signOut();
                    window.location.href = "/";
                  });
                }}
              >
                {deleting ? "Deleting…" : "Delete"}
              </button>
              <button type="button" className="btn btn-secondary" onClick={() => setDeleteOpen(false)}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
