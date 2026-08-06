import Link from "next/link";

export default function Page() {
  return (
    <main className="container homeHero">
      <p className="textMuted" style={{ margin: 0, letterSpacing: "0.08em", textTransform: "uppercase", fontSize: "0.75rem" }}>
        Live-Regie
      </p>
      <h1 className="homeHeroBrand">Theater-Maschine</h1>
      <p className="homeHeroLead">
        Dramaturgie schreiben, Inszenierung vorbereiten, Aufführung steuern — mit einem Menschen am Regiepult.
      </p>
      <div className="homeModeGrid">
        <Link className="homeModeCard" href="/dramaturgie">
          <h2>Teil 1</h2>
          <p>Workshop, Stücktext und dramaturgische Cues.</p>
        </Link>
        <Link className="homeModeCard" href="/inszenierung">
          <h2>Teil 2</h2>
          <p>Korpus vorbereiten, Avatare und Atmosphäre synchronisieren.</p>
        </Link>
        <Link className="homeModeCard" href="/auffuehrung">
          <h2>Aufführung</h2>
          <p>Show steuern — Play, Pause, Timeline.</p>
        </Link>
        <Link className="homeModeCard" href="/director">
          <h2>Operator</h2>
          <p>Safety, Emergency Stop, Regievorschläge.</p>
        </Link>
      </div>
    </main>
  );
}
