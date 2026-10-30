import "server-only";
import { unstable_rethrow } from "next/navigation";
import { cache, type ReactNode } from "react";
import { ApiNotice } from "@/components/programme/ApiNotice";
import { ApiError, isTransientApiError, type MeResponse, type Meta } from "@/lib/api";
import { getMe, loadMeta } from "@/lib/server/data";

type Account =
  | { ok: true; me: MeResponse; meta: Meta | null }
  | { ok: false; unavailable: true }
  | { ok: false; unavailable: false; message: string; status: number };

/** One shared profile read per request, so a sleeping API does not fail the layout and the page separately. */
export const loadAccount = cache(async (): Promise<Account> => {
  try {
    const [me, meta] = await Promise.all([getMe(), loadMeta().catch(() => null)]);
    return { ok: true, me, meta };
  } catch (err) {
    unstable_rethrow(err);
    if (isTransientApiError(err)) return { ok: false, unavailable: true };
    if (err instanceof ApiError) return { ok: false, unavailable: false, message: err.message, status: err.status };
    throw err;
  }
});

export function accountNotice(account: Extract<Account, { ok: false }>) {
  if (account.unavailable) return <ApiNotice />;
  return <ApiNotice message={account.message} status={account.status} />;
}

/** Catch an API failure inside a Server Component.
 * An uncaught server error reaches the browser as a minified React error, with the real message removed.
 */
export async function renderApi(render: () => Promise<ReactNode>): Promise<ReactNode> {
  try {
    return await render();
  } catch (err) {
    unstable_rethrow(err);
    if (isTransientApiError(err)) return <ApiNotice />;
    if (err instanceof ApiError) return <ApiNotice message={err.message} status={err.status} />;
    throw err;
  }
}
