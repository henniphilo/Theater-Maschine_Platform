import Link from "next/link";

import { OscTestPanel } from "@/components/technik/OscTestPanel";

export default function TechnikPage() {
  return (
    <main className="container col">
      <div className="pageHeader">
        <h1>Technik-Test</h1>
      </div>
      <p className="textMuted">
        Video, Sound und Licht jeweils einzeln testen — getrennte Bereiche wie am Licht-Pult.{" "}
        Betriebsmodus, Dry-Run und Prepare-Optionen:{" "}
        <Link href="/einstellungen">Einstellungen →</Link>
      </p>
      <OscTestPanel />
    </main>
  );
}
