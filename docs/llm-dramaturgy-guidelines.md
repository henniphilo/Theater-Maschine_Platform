# Guidelines für erklärbare LLM-Dramaturgie und professionelles Medienmischen

**Status:** Referenz · Post-MVP  
**Implementierung:** inkrementell (siehe Meilensteine M0–M5 im Code)

---

## 1. Grundprinzip

Die Theater-Maschine löst Cues aus, die präzise, dramaturgisch nachvollziehbare und künstlerisch interessante Begleitung erzeugen. Musik, Sound und Video sind eigenständige theatrale Ebenen — sie unterstützen, kontrastieren, kommentieren, irritieren oder setzen bewusst aus.

Die Maschine verhält sich wie eine professionelle Live-Dramaturgin: aufmerksam, präzise in Übergängen, abwechslungsreich, mutig aber nicht beliebig, überraschend aber begründbar, sensibel für Wiederholung, Dichte und Überforderung.

## 2. Jede Cue-Entscheidung muss erklärbar sein

Für jeden vorgeschlagenen oder ausgelösten Cue erzeugt die LLM-Dramaturgie eine kurze Begründung (`reason_short`), die in der Textübersicht beim Cue angezeigt wird.

- Maximal ein kurzer Stichpunkt / ein Satz
- Dramaturgische Funktion benennen
- Keine technischen Implementierungsdetails
- Konkret auf die aktuelle Textstelle reagieren

**Gute Beispiele:** „Verstärkt die zunehmende Bedrohung.“ · „Setzt einen ruhigen Kontrapunkt zum hektischen Text.“ · „Lässt die Stimme bewusst allein stehen.“

**Schlechte Beispiele:** „Das Modell hält diesen Cue für passend.“ · „Sound passt zur Szene.“ · lange Absätze

## 3. Datenmodell

Jede Entscheidung wird als Dramaturgie-Ereignis protokolliert (`DramaturgyDecisionEvent`):

- `decision_id`, `session_id`, `text_event_id`, `cue_id`
- `decision`: execute | modify | stop | hold | none
- `reason_short`, `dramaturgical_function`, `confidence`
- optional: `intensity_before/after`, `alternatives_considered`

Operator-UI (kompakt):

```text
▶ VIDEO: Langsamer Wald
  – Setzt einen ruhigen Kontrapunkt zur sprachlichen Eskalation.
```

## 4. Dramaturgische Funktionen

| Funktion | Bedeutung |
|----------|-----------|
| `support` | Unterstützt Stimmung, Rhythmus oder Inhalt |
| `contrast` | Bewusster Gegensatz |
| `intensification` | Steigert vorhandene Bewegung |
| `release` | Reduziert Dichte, beendet Ebene |
| `transition` | Bereitet Wechsel vor |
| `recall` | Nimmt früheres Motiv wieder auf |
| `disruption` | Unterbricht etabliertes Muster |
| `foreshadowing` | Deutet kommende Entwicklung an |
| `space` | Bewusstes Nichtstun / Leerstelle |

## 5. Stille und Leerstelle

Nicht jede Stimmung erzeugt einen Cue. „Kein Cue“ (`decision: none`, `dramaturgical_function: space`) ist eine reguläre Entscheidung mit Begründung.

## 6. Gemeinsamer Dramaturgiezustand

Musik- und Videomischung teilen einen `DramaturgyState`: Dichte pro Medium, aktive Layer, Zeit seit letztem Cue, Wiederholungen. Vor Ausführung prüft `ConflictCheck` Dichte, Überlagerung und Wiederholung.

## 7–8. Musik- und Videomischung

Über Zeit entwickeln, nicht playlist-artig. Aktionen: start/stop/fade/layer/volume. Sprache hat Priorität. Schwarzbild und Stille sind aktive Cues. Keine automatische Schlüsselwort-Illustration.

## 9. Zusammenspiel Musik/Video

Strategien: gemeinsame Unterstützung (sparsam), geteilte Rollen, Vorder-/Hintergrund, Ablösung, Asynchronität, Leerstelle.

## 10. Dichte-Regeln

Skala 0.0–1.0. Normalbetrieb 0.2–0.6. Über 0.75 kein weiterer Layer außer replace/stop. Bei hoher Textdichte Medien reduzieren.

## 11–12. Überraschung und Kandidatenauswahl

Überraschung durch Kontrast, Timing, Wiederaufnahme, Reduktion — nicht durch Zufall. Ablauf: Text analysieren → Funktion → Dichte → Kandidaten → Konflikte → Auswahl → `reason_short`.

## 13. Cooldowns

Pro Cue/Asset: `minimum_play_duration`, `cooldown_seconds`, `maximum_repetitions_per_session`.

## 14. Autonomie und Operator

Entscheidungsmodi: `suggested`, `scheduled`, `executed`, `rejected`, `overridden`, `cancelled`. Operator kann stoppen, überschreiben, Autopilot pausieren, Emergency Stop.

## 15. Trennung Auswahl / Ausführung

```text
TextEvent → DramaturgyAnalysis → CueProposal → ConflictCheck → Scheduler → CueExecutionService → DeviceAdapter
```

LLM erzeugt abstrakte Proposals — keine OSC/MIDI/TCP-Befehle.

## 16–17. LLM-Prompt und Ausgabeformat

Systemprompt: professionelle Theaterdramaturgin, Stille erlaubt, keine Illustrationspflicht, nur vorhandene Cue-IDs.

```json
{
  "decision": "execute",
  "cue_id": "video_forest_02",
  "dramaturgical_function": "recall",
  "reason_short": "Nimmt das frühere Waldmotiv wieder auf.",
  "confidence": 0.81
}
```

## 18. Textübersicht

Chronologische Verbindung von Text und Cues mit kompakter Begründung.

## 19. Post-Show-Analyse

Alle Entscheidungen speicherbar und auswertbar (Timeline, Dichte, Operator-Eingriffe).

## 20. Akzeptanzkriterien

1. Jeder LLM-Cue hat sichtbare `reason_short`
2. Begründung mit Textstelle gespeichert
3. „Kein Cue“ ist regulär
4. Gemeinsamer Dramaturgiezustand
5. Laufende Cues veränderbar/beendbar
6. Nicht nur Startaktionen
7. Kontrollierte Layer
8. Wiederholung und Dichte bewusst
9. Sprachverständlichkeit
10. Keine Keyword-Illustration
11. Operator-Override
12. LLM-Validierung vor Ausführung
13. Nur bestehende Cue-IDs
14. Nachvollziehbarkeit nach Aufführung
15. Überraschung aus Variation, nicht Zufall

---

Siehe auch: [dramaturgy_rules.md](dramaturgy_rules.md) · [platform-prd.md](platform-prd.md)
