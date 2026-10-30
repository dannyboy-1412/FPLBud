import { NextResponse, type NextRequest } from "next/server";
import { updateSession } from "@/lib/supabase/middleware";

const SECTION_IDS = new Set(["squad", "season", "market", "insights"]);

export async function proxy(request: NextRequest) {
  const url = request.nextUrl;
  if (url.pathname === "/dashboard") {
    const section = url.searchParams.get("section");
    if (section && SECTION_IDS.has(section)) {
      const dest = url.clone();
      dest.pathname = `/dashboard/${section}`;
      dest.searchParams.delete("section");
      if (section !== "insights") dest.searchParams.delete("pos");
      return NextResponse.redirect(dest);
    }
  }
  return updateSession(request);
}

export const config = {
  matcher: ["/dashboard/:path*", "/onboarding/:path*", "/settings/:path*", "/login"],
};
