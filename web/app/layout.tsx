import type { Metadata } from "next";
import { Fraunces, Instrument_Sans, Newsreader } from "next/font/google";
import { EditionPreference } from "@/components/EditionPreference";
import { EDITION_BOOT_SCRIPT } from "@/lib/edition";
import "./globals.css";

const fraunces = Fraunces({
  variable: "--font-fraunces",
  subsets: ["latin"],
  axes: ["opsz", "SOFT"],
});

const newsreader = Newsreader({
  variable: "--font-newsreader",
  subsets: ["latin"],
  axes: ["opsz"],
  style: ["normal", "italic"],
});

const instrument = Instrument_Sans({
  variable: "--font-instrument",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "FPLBud",
  description: "Your transfers, captain and chips, worked out.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${fraunces.variable} ${newsreader.variable} ${instrument.variable} h-full`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: EDITION_BOOT_SCRIPT }} />
      </head>
      <body className="min-h-full bg-paper text-ink">
        <EditionPreference />
        {children}
      </body>
    </html>
  );
}
