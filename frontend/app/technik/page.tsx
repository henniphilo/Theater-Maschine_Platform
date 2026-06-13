import { AppNav } from "@/components/layout/AppNav";
import { OscTestPanel } from "@/components/technik/OscTestPanel";

export default function TechnikPage() {
  return (
    <main className="container col">
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <h1 style={{ margin: 0 }}>Technik-Test</h1>
        <AppNav />
      </div>
      <p className="textMuted">
        OSC-Signale an TouchDesigner prüfen — einzeln oder kombiniert wie in der Aufführung.
      </p>
      <OscTestPanel />
    </main>
  );
}
