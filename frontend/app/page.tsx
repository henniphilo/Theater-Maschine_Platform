import Link from "next/link";

export default function Page() {
  return (
    <main className="container homeHero">
      <h1 className="homeHeroBrand">AutoPlay</h1>
      <p className="textMuted" style={{ margin: 0, fontSize: "0.95rem", letterSpacing: "0.04em" }}>
        theater-maschine
      </p>
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
