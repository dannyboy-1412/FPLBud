import { Suspense } from "react";
import { SettingsForm } from "@/components/programme/SettingsForm";
import { SettingsSkeleton } from "@/components/programme/Skeletons";
import SectionError from "@/components/programme/SectionError";
import { getMe, loadMeta } from "@/lib/server/data";

export default function SettingsPage() {
  return (
    <>
      <h1>Settings</h1>
      <Suspense fallback={<SettingsSkeleton />}>
        <SectionError>
          <SettingsLoader />
        </SectionError>
      </Suspense>
    </>
  );
}

async function SettingsLoader() {
  const [me, meta] = await Promise.all([getMe(), loadMeta()]);
  return <SettingsForm profile={me.profile} meta={meta} />;
}
