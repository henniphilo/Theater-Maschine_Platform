import "./globals.css";
import { Source_Sans_3 } from "next/font/google";
import { ReactNode } from "react";

import { AppShell } from "@/components/layout/AppShell";

const sourceSans = Source_Sans_3({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-source-sans"
});

export const metadata = {
  title: "AutoPlay",
  description: "theater-maschine — Dramaturgie. Automation. Bühne."
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="de" className={sourceSans.variable} suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem("autoplay-theme");if(t==="light"||t==="dark"){document.documentElement.setAttribute("data-theme",t);document.documentElement.style.colorScheme=t;}}catch(e){}})();`
          }}
        />
      </head>
      <body className={sourceSans.className}>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
