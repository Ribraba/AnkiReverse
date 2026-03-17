import type { Metadata, Viewport } from "next";
import Script from "next/script";
import { Providers } from "@/components/providers";
import { DemoBanner } from "@/components/DemoBanner";
import "./globals.css";

export const metadata: Metadata = {
  title: "AnkiReverse",
  description: "Révisez vos fiches Anki sur mobile",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "AnkiReverse",
  },
};

export const viewport: Viewport = {
  themeColor: "#6366f1",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <head>
        <link rel="apple-touch-icon" href="/icon-192.png" />
      </head>
      <body className="bg-slate-950 text-white min-h-screen">
        <Providers>{children}</Providers>
        <DemoBanner />
        {/* MathJax — rendu \[...\] et \(...\) dans les cartes Anki */}
        <Script id="mathjax-config" strategy="beforeInteractive">{`
          window.MathJax = {
            tex: {
              inlineMath: [['\\\\(', '\\\\)']],
              displayMath: [['\\\\[', '\\\\]']],
              packages: {'[+]': ['ams']}
            },
            svg: { fontCache: 'global' },
            startup: { typeset: false }
          };
        `}</Script>
        <Script
          id="mathjax"
          src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"
          strategy="afterInteractive"
        />
      </body>
    </html>
  );
}
