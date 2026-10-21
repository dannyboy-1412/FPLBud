import type { ReactNode } from "react";
import { Masthead } from "@/components/programme/Masthead";

export default function SiteLayout({ children }: { children: ReactNode }) {
  return (
    <div className="page">
      <Masthead />
      {children}
    </div>
  );
}
