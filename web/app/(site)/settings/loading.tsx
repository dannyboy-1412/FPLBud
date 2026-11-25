import { SettingsSkeleton } from "@/components/programme/Skeletons";

export default function Loading() {
  return (
    <div className="settings-page">
      <header className="settings-header">
        <h1>Settings</h1>
        <p className="settings-lede">
          Tune how FPLBud scores players, plans transfers, and looks in this browser.
        </p>
      </header>
      <SettingsSkeleton />
    </div>
  );
}
