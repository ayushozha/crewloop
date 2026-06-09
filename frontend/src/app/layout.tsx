import type { Metadata } from "next";
import { Geist, Geist_Mono, Instrument_Serif } from "next/font/google";

import { PasswordGate } from "@/components/PasswordGate";

import "./globals.css";

const geist = Geist({
  subsets: ["latin"],
  variable: "--font-geist",
  display: "swap",
});

const geistMono = Geist_Mono({
  subsets: ["latin"],
  variable: "--font-geist-mono",
  display: "swap",
});

const instrumentSerif = Instrument_Serif({
  subsets: ["latin"],
  weight: "400",
  variable: "--font-instrument-serif",
  display: "swap",
});

export const metadata: Metadata = {
  title: "CrewLoop — The action OS for small business",
  description:
    "CrewLoop turns small business requests into finished operations: source evidence, texts, calls, emails, payment rules, proof, and an audit timeline.",
  icons: {
    icon: [
      { url: "/favicon.ico", sizes: "any" },
      { url: "/icon.svg", type: "image/svg+xml" },
    ],
    shortcut: "/favicon.ico",
    apple: "/apple-icon.png",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${geist.variable} ${geistMono.variable} ${instrumentSerif.variable}`}
    >
      <body>
        {/* Event-only gate (no probe): any page whose API call answers 401
            swaps to the unlock card, so legacy operator pages work behind
            APP_PASSWORD too. The public landing page never hits the API. */}
        <PasswordGate probe={false}>{children}</PasswordGate>
      </body>
    </html>
  );
}
