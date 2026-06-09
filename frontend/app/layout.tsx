import "./globals.css";
import { ReactNode } from "react";

export const metadata = {
  title: "AI Debate",
  description: "GPT vs Claude — live AI debate"
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
