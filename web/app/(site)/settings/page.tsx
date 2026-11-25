import { Suspense, type ReactNode } from "react";
import { ChatHistory } from "@/components/chat/ChatHistory";
import { SettingsForm } from "@/components/programme/SettingsForm";
import { AssistantSettingsSkeleton, SettingsSkeleton } from "@/components/programme/Skeletons";
import SectionError from "@/components/programme/SectionError";
import { api, ApiError } from "@/lib/api";
import { renderApi } from "@/lib/server/render-api";
import { getMe, loadMeta } from "@/lib/server/data";
import { getAccessToken } from "@/lib/server/session";

export default function SettingsPage() {
  const assistantSection = (
    <Suspense fallback={<AssistantSettingsSkeleton />}>
      <ChatHistoryLoader />
    </Suspense>
  );

  return (
    <div className="settings-page">
      <header className="settings-header">
        <h1>Settings</h1>
        <p className="settings-lede">
          Tune how FPLBud scores players, plans transfers, and looks in this browser.
        </p>
      </header>
      <Suspense fallback={<SettingsSkeleton />}>
        <SectionError>
          <SettingsLoader assistantSection={assistantSection} />
        </SectionError>
      </Suspense>
    </div>
  );
}

async function ChatHistoryLoader() {
  const token = await getAccessToken();
  if (!token) return null;
  let memory: { key: string; value: string }[] = [];
  let note: string | null = null;
  try {
    const body = await api<{ memory: { key: string; value: string }[] }>("/chat/memory", { token });
    memory = body.memory;
  } catch (err) {
    note =
      err instanceof ApiError && err.status === 503
        ? "Chat is turned off for this account."
        : "Chat preferences could not be loaded.";
  }
  return <ChatHistory memory={memory} note={note} />;
}

async function SettingsLoader({ assistantSection }: { assistantSection: ReactNode }) {
  return renderApi(async () => {
    const [me, meta] = await Promise.all([getMe(), loadMeta()]);
    return <SettingsForm profile={me.profile} meta={meta} assistantSection={assistantSection} />;
  });
}
