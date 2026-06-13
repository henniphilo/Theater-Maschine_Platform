import "./globals.css";
import { ReactNode } from "react";

export const metadata = {
  title: "Theatermaschine",
  description: "Dramaturgie, Stücktext und Live-Aufführung"
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="de">
      <body>{children}</body>
    </html>
  );
}
