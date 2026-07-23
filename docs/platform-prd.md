# Product Requirements Document — Theater-Maschine Plattform 2.0

**Status:** Entwurf  
**Stand:** 2026-07-23  
**Bezug:** [platform-audit.md](platform-audit.md) · [architektur.md](architektur.md) · [PLAN.md](../PLAN.md) · [active-production.md](active-production.md) · `.cursor/rules/platform-architecture.mdc`

---

## 1. Vision

Die Theater-Maschine ist eine **produktionsunabhängige Live-Regie-Plattform** für Theater: Medien und Cues verwalten, technische Geräte konfigurieren, dramaturgische Regeln anwenden und Signale an Bühnenhardware senden — mit einem Menschen am Operator-Pult.

Version 2.0 löst die enge Kopplung an die Burgtheater-Produktion *Unter Tieren* und macht **Production**, **Asset**, **Cue**, **Device**, **Rule** und **PerformanceSession** zu ersten Domänenobjekten.

Bestehende Burgtheater-Funktionalität bleibt während der Migration als Referenz und Importquelle erhalten; der Kernel (Director-Pipeline, Safety, Adapter) wird erweitert, nicht ersetzt.

**Kernprinzip (unverändert):**

```text
DialogueEvent → DramaturgyDecision → ScheduledCue → Adapter (OSC / MIDI / TCP) / Log
     dramaturgisch      abstrakte Cues              Technik
```

Dramaturgische Entscheidungen erzeugen **keine** direkten Netzwerk- oder Hardwarebefehle.

---

## 2. Produktziel MVP

Im MVP kann ein Operator ohne Login:

1. Produktionen anlegen, bearbeiten, duplizieren und archivieren  
2. eine aktive Produktion auswählen  
3. Video-, Audio-, Bild-, Text-, JSON- und CSV-Dateien hochladen  
4. Assets mit Metadaten und Tags verwalten  
5. Cues erstellen und Assets zuordnen  
6. technische Geräte konfigurieren  
7. Cues im Dry-Run oder real ausführen  
8. bestehende Dramaturgie-Regeln zunächst weiterverwenden  
9. die Burgtheater-Konfiguration importieren  
10. den Operator-Modus mit Emergency Stop nutzen  

Erfolgskriterium: Eine neue Produktion ist ohne Code-Änderung an Projektor-IDs oder Venue-IPs bedienbar; die Burgtheater-Show lässt sich als Production importieren und im Dry-Run abspielen.

---

## 3. MVP-Funktionen (Detail)

### 3.1 Produktionen anlegen, bearbeiten, duplizieren, archivieren

| Anforderung | Beschreibung |
|-------------|--------------|
| Anlegen | Name, optionale Beschreibung, Status `draft` |
| Bearbeiten | Metadaten ändern; Inhalt (Assets/Cues/Devices/Rules) gehört zur Production |
| Duplizieren | Tiefe Kopie der Metadaten + Verweise; Assets optional mitkopieren oder referenzieren (MVP: Metadaten + Cue-/Device-/Rule-Struktur; Binärdateien teilen oder kopieren — Implementierung dokumentiert) |
| Archivieren | Status `archived`; nicht mehr als aktive Production wählbar; Daten bleiben lesbar |
| Löschen | Im MVP **kein** Hard-Delete produktiver Daten; nur Archivieren |

Jede production-bezogene Entität trägt `production_id`.

### 3.2 Aktive Produktion auswählen

- Genau **eine** aktive Production pro Backend-Instanz (Runtime-Kontext).  
- UI und API zeigen/setzen die aktive Production.  
- Alle Cue-Ausführungen, Uploads und Device-Operationen gelten im Kontext der aktiven Production (außer explizit production-scoped Admin-Listen).  
- Wechsel der aktiven Production während einer laufenden PerformanceSession erfordert Bestätigung und bricht/stoppt die Session sicher (Emergency-äquivalent oder Pause + Clear).

### 3.3 Dateien hochladen

Unterstützte Typen (MVP):

| Kategorie | Beispiele | Speicherung |
|-----------|-----------|-------------|
| Video | mp4, mov, webm | Storage-Service (lokal) |
| Audio | wav, mp3, aiff | Storage-Service |
| Bild | png, jpg, webp | Storage-Service |
| Text | txt, md | Storage-Service |
| JSON | Kataloge, Regeln, Exporte | Storage-Service + ggf. parse → DB-Metadaten |
| CSV | Cue-Listen, Avatar-Zuordnung | Storage-Service + ggf. Import-Job |

- Binärdaten **nicht** in PostgreSQL.  
- Metadaten und Verweise in PostgreSQL.  
- Erster Storage: lokales Dateisystem hinter austauschbarem Storage-Service.  
- Upload-Pfade niemals ungeprüft verwenden (siehe Sicherheit).

### 3.4 Assets mit Metadaten und Tags

Ein **Asset** ist eine registrierte Datei inkl. Metadaten:

- `id`, `production_id`, `kind` (video|audio|image|text|json|csv|other)  
- `original_filename`, `content_type`, `size_bytes`, `checksum`  
- `storage_key` (interner Schlüssel, kein User-Pfad)  
- `title`, `description`, `tags[]`  
- optionale fachliche Felder (z. B. `duration_ms`, `pixera_name`) als JSON-Extension  
- `created_at`, `updated_at`

CRUD + Filter nach Tag/Kind/Textsuche in der aktiven Production.

### 3.5 Cues erstellen und Assets zuordnen

Ein **Cue** ist eine ausführbare Anweisung:

- referenziert optional ein oder mehrere Assets  
- referenziert optional ein Device (oder Device-Gruppe / Output-Slot)  
- trägt abstrakte Aktion (z. B. `play_clip`, `trigger_cue`, `set_scene`) und Parameter  
- gehört zu `production_id`

MVP: manuelles Anlegen/Bearbeiten; Ausführung über Director/Adapter. Bestehende Cue-Modelle (`VisualCue` / `SoundCue` / `LightCue`) bleiben die technische Zielstruktur der Adapter-Schicht.

### 3.6 Technische Geräte konfigurieren

Ein **Device** beschreibt eine Ausgabe oder Verbindung:

- Typ: z. B. `pixera_osc`, `touchdesigner_osc`, `midi`, `light_tcp`, `light_osc`, `qlab_relay`  
- Verbindungsparameter (Host, Port, Kanal) — **nur** in DB/Env, nicht im Git  
- Output-Slots (ehemals hart kodierte Projektoren `adam`/`eva`/`rz21`/`led`) als konfigurierbare Liste  
- Enable/Disable pro Device  

Adapter implementieren die Protokollkommunikation; die Domäne kennt nur Device-IDs und abstrakte Befehle.

### 3.7 Cues Dry-Run oder real ausführen

- **Dry-Run:** Befehle werden geloggt/getraced, **kein** reales Senden (entspricht `OSC_DRY_RUN` / Probebetrieb).  
- **Real:** Adapter senden an konfigurierte Devices.  
- Umschalten nur bewusst (Operator-UI / Safety); Default in Dev-Dokumentation: Dry-Run.  
- Signal-Trace und OSC-Log bleiben Pflicht für beide Modi.

### 3.8 Bestehende Dramaturgie-Regeln weiterverwenden

- MVP importiert und nutzt die bestehenden Regeldateien (`dramaturgy_rules.json` und Engine-Verhalten aus `docs/dramaturgy_rules.md`).  
- Kein neuer Rule-Editor im MVP (nur Laden, Anzeigen, Zuordnung zur Production).  
- Pipeline: Rules → DramaturgyDecision → Scheduler → Adapter.

### 3.9 Burgtheater-Konfiguration importieren

Import-Job erzeugt eine Production (z. B. `unter-tieren`) aus:

- `data/video_cues.json`, `sound_cues.json`, `light_scenes.json`, `light_inventory.json`  
- `avatar_speech.json`, `dramaturgy_rules.json`  
- Geräte-Defaults aus dokumentierter Venue-Config (Hosts nur aus Env/Import-Overlay, nicht hardcodiert committen)  
- optional Stücktext / CSV aus `Stücktext/` und `media/`

Nach Import: Production wählbar, Cues/Assets/Devices befüllt, Dry-Run ausführbar. Bestehende Teil-1/Teil-2-Flows bleiben parallel lauffähig, bis sie auf Production-Kontext umgestellt sind.

### 3.10 Operator-Modus mit Emergency Stop

Erhalten und an Production-Kontext binden:

- Autopilot / Visuals / Sound / Lights Toggles (`SafetyState`)  
- Emergency Stop: alle Ausgaben stoppen / Blackout-Pfad, Queue leeren, Epoch erhöhen  
- Emergency Clear  
- Events/Status SSE  
- Technik-Test und manuelle Cue-Ausführung  

Emergency Stop muss auch bei fehlgeschlagenen Adaptern fail-closed agieren (so weit technisch möglich).

---

## 4. Nicht-Ziele des MVP

Ausdrücklich **nicht** im MVP:

1. Benutzer-Login, OAuth, Mehrbenutzer-Rechteverwaltung  
2. Cloud-Object-Storage (S3 o. ä.) — nur lokaler Storage-Adapter  
3. Neuer visueller Rule-Editor / vollständige LLM-Dramaturgie-Neuentwicklung  
4. Framework-Wechsel (kein anderes Backend/Frontend-Stack)  
5. Vollständige Neuschreibung von Teil-1-Workshop oder Teil-2-Text-Sync  
6. Art-Net/sACN-Produktion (Stub darf bleiben)  
7. Multi-Tenant / mehrere parallele aktive Productions pro Instanz  
8. Hard-Delete von Productions inkl. aller Medien  
9. Mobile Native Apps (Remote-Webseite darf bleiben)  
10. Automatisches Deployment auf Theater-Server / CI-CD-Show-Pipeline  
11. Lizenz-/Rechteverwaltung für Medieninhalte  
12. Ersetzen von Pixera/Ableton/EOS durch proprietäre Player im Kern  

Post-MVP-Kandidaten: Auth, Multi-Operator, Rule-UI, Pack-Export/Import als ZIP, Cloud-Storage, generischer Teil-2 ohne Burgtheater-Kanon.

---

## 5. Benutzerrollen (zunächst ohne Login)

Kein Authentifizierungs-Flow im MVP. Rollen sind **logische Nutzungsmodi** (UI-Konvention / Dokumentation), nicht durchgesetzte Accounts:

| Rolle | Typische Aufgaben | UI-Schwerpunkt |
|-------|-------------------|----------------|
| **Operator** | Aktive Production, Dry-Run/Real, Safety, Emergency Stop, Cue feuern | `/director`, Aufführung |
| **Regie / Dramaturgie** | Assets/Tags, Cues, Regeln laden, Import prüfen | Production- und Asset-UI |
| **Technik** | Devices, Hosts/Ports, Verbindungstests | Technik / Device-Config |
| **Gast / Remote** | Transport Play/Pause/Stop (bestehend) | `/remote` |

Durchsetzung im MVP: lokales Netzwerkvertrauen + Rate-Limits; sensible Hosts nur in `.env`. Echte Auth ist Post-MVP.

---

## 6. Domänenmodell

### 6.1 Kernobjekte

```text
Production 1──* Asset
Production 1──* Cue
Production 1──* Device
Production 1──* RuleSet
Production 1──* PerformanceSession

Cue *──* Asset          (Zuordnung)
Cue *──o Device         (Zielausgabe / Slot)
RuleSet ──► Cue         (Auswahl / Trigger, abstrakt)
PerformanceSession ──► ExecutionLog / SignalTrace
```

| Objekt | Kurzdefinition |
|--------|----------------|
| **Production** | Eigenständige Theaterproduktion mit Assets, Cues, Regeln, Geräten und Sessions |
| **Asset** | Hochgeladene oder registrierte Datei inkl. Metadaten |
| **Cue** | Ausführbare Anweisung; kann Asset und/oder Device referenzieren |
| **Device** | Konfigurierte technische Ausgabe oder Verbindung |
| **Adapter** | Implementiert Protokollkommunikation für einen Device-Typ (kein Domänen-Persistenzobjekt, Runtime) |
| **Rule / RuleSet** | Bedingungen für Cue-Auswahl/-Auslösung; MVP = importierte bestehende Regeln |
| **PerformanceSession** | Konkrete Probe oder Aufführung mit Protokollierung |

### 6.2 Wichtige Attribute (MVP)

**Production:** `id`, `slug`, `title`, `description`, `status` (`draft`|`active_eligible`|`archived`), `created_at`, `updated_at`, optional `source` (`manual`|`import:unter-tieren`)

**Runtime:** `ActiveProduction` (Singleton pro Instanz) → `production_id`

**Device:** `id`, `production_id`, `type`, `name`, `enabled`, `connection` (strukturiert), `outputs[]` (`id`, `label`, `lock_policy`, vendor-mapping)

### 6.3 Persistenz-Prinzipien

- PostgreSQL = **primäre** Datenbank für Domänenobjekte und Metadaten.  
- Große Medien = Storage-Service (lokal zuerst).  
- Redis nur bei klarem Zweck (sonst nicht ausbauen).  
- Schemaänderungen über Migrationen (Alembic).  
- Bestehende JSON-Dateien bleiben Import-/Übergangsquelle, nicht langfristige Single Source of Truth.

### 6.4 Schichtentrennung

```text
UI → API → Domain Services → Director/Scheduler → Adapters → Hardware
                ↑
         Rules (dramaturgisch, keine Sockets)
```

---

## 7. Zentrale Workflows

### 7.1 Neue Production von Null

1. Production anlegen  
2. Als aktiv setzen  
3. Devices konfigurieren (oder Template)  
4. Assets hochladen, Tags setzen  
5. Cues anlegen und Assets/Devices zuordnen  
6. RuleSet laden (Default-Regeln)  
7. Dry-Run einzelner Cues  
8. Optional Real-Test mit Safety-Toggles  

### 7.2 Burgtheater importieren

1. Import starten („Unter Tieren“ / vorhandene `data/`+`media/`-Quellen)  
2. System erzeugt Production + Assets + Cues + Devices + RuleSet  
3. Operator prüft Diff/Warnungen (fehlende Dateien, unbekannte Hosts)  
4. Active Production = Import  
5. Dry-Run / bestehende Teil-1-/Teil-2-Pfade gegen neuen Kontext validieren  

### 7.3 Cue ausführen

1. Operator wählt Cue (oder Dramaturgie entscheidet abstrakt)  
2. Scheduler prüft Safety / Gaps / Emergency  
3. Bei Dry-Run: Trace + Log, kein Send  
4. Bei Real: Adapter mappt abstrakten Cue → Protokollbefehl  
5. Signal-Trace korreliert `run_epoch`, `cue_id`, `bridge`, Status  

### 7.4 Emergency Stop

1. Operator löst Emergency aus  
2. Safety: `emergency_stop_active`  
3. Queue stoppen, Stop/Blackout an enabled Devices (best effort)  
4. Neue Befehle blockiert bis Clear  
5. Session/Trace vermerken  

### 7.5 Production wechseln

1. Keine offene Session — oder Session beenden  
2. Neue Production aktivieren  
3. Kataloge/Devices neu laden  
4. UI aktualisieren  

### 7.6 Duplizieren

1. Quell-Production wählen  
2. Duplikat mit neuem `slug`/`title`  
3. Struktur kopieren; Storage-Strategie dokumentiert anwenden  
4. Duplikat bleibt `draft`, nicht automatisch aktiv  

---

## 8. Akzeptanzkriterien

### A. Produktionen

- [ ] Production anlegen, umbenennen, archivieren über API und UI  
- [ ] Duplikat erzeugt neue `production_id`; Quelldaten unverändert  
- [ ] Archivierte Production nicht als aktiv setzbar  

### B. Aktive Production

- [ ] Genau eine aktive Production; Wechsel über API/UI  
- [ ] Upload und Cue-Create landden unter aktiver `production_id`  
- [ ] Listen sind production-gefiltert  

### C. Uploads & Assets

- [ ] Video/Audio/Bild/Text/JSON/CSV uploadbar  
- [ ] Metadaten + Tags editierbar; Suche/Filter nach Tag  
- [ ] Datei liegt im Storage; DB hält nur Metadaten + `storage_key`  
- [ ] Path-Traversal und absolute Pfade in Dateinamen werden abgewiesen  

### D. Cues

- [ ] Cue CRUD in aktiver Production  
- [ ] Cue kann Asset und Device referenzieren  
- [ ] Ungültige Referenzen (andere Production) werden abgewiesen  

### E. Devices

- [ ] Mindestens OSC-Visual-, MIDI/Sound- und Light-Device-Typen konfigurierbar  
- [ ] Output-Slots ohne hart kodierte `adam`/`eva`/`rz21`/`led`-Literals in neuer Production  
- [ ] Disabled Device empfängt keine Real-Befehle  

### F. Ausführung

- [ ] Dry-Run erzeugt Trace/Log ohne Netzwerk-Send (verifizierbar mit Fake-Receiver / Log-Assertion)  
- [ ] Real-Modus sendet nur an konfigurierte, enabled Devices  
- [ ] Default-Dev-Pfad dokumentiert Dry-Run  

### G. Regeln

- [ ] Bestehende `dramaturgy_rules` einer Production zuordenbar und von der Engine nutzbar  
- [ ] Rules lösen keine Sockets direkt aus  

### H. Burgtheater-Import

- [ ] Import erzeugt lauffähige Production mit Cues/Assets/Devices/Rules  
- [ ] Nach Import: Dry-Run mindestens eines Video-, Sound- und Light-Cues  
- [ ] Keine Secrets/IPs aus Import ins Git geschrieben  

### I. Operator / Emergency

- [ ] `/director` (oder Nachfolger) zeigt Safety-Toggles der aktiven Production  
- [ ] Emergency Stop blockiert weitere Ausführungen und triggert Stop/Blackout-Pfad  
- [ ] Emergency Clear stellt Bedienung wieder her  

### J. Regression

- [ ] Bestehende Backend- und Frontend-Tests der Pipeline bleiben grün oder sind bewusst migriert  
- [ ] `OSC_DRY_RUN=true` in Test-Runner unverändert  

---

## 9. Technische Einschränkungen

| Bereich | Einschränkung |
|---------|----------------|
| Backend | FastAPI / Python 3.11+ |
| Frontend | Next.js / TypeScript |
| DB | PostgreSQL primär; Änderungen via Migrationen |
| Cache/Queue | Redis nur bei nachgewiesenem Nutzen |
| Storage | Austauschbarer Service; MVP = lokales FS |
| Hardware | Nur über Adapter; bestehende Bridges (Pixera, TD, MIDI, Light TCP/EOS) wiederverwenden |
| Frameworks | Kein Stack-Wechsel |
| Parallelbetrieb | Alte JSON-Stores und neue Domäne dürfen übergangsweise koexistieren; Feature-Flag / Active Production |
| Native vs Docker | MIDI und macOS `say` weiter native Backend-Vorteile; Docker für Infra |
| Skalierung | Eine aktive Production pro Instanz; kein Cluster-MVP |
| LLM | Optional für Dramaturgie; MVP verpflichtet nicht zu neuen LLM-Features |

---

## 10. Sicherheitsanforderungen

### 10.1 Uploads

- Allowlist für Content-Types und/oder Dateiendungen  
- Maximale Dateigröße konfigurierbar  
- Dateiname sanitizen; Speicherung nur unter generiertem `storage_key`  
- Keine Verwendung von Client-Pfaden für `open()`/`send_file`  
- JSON/CSV nach Upload parsen in isoliertem Import-Pfad; fehlerhafte Dateien nicht als ausführbare Config übernehmen ohne Validierung  
- Keine Ausführung hochgeladener Skripte  

### 10.2 Hardwareausgaben

- Dry-Run als sicherer Default in Entwicklung  
- Real-Send erfordert expliziten Modus + enabled Devices  
- Emergency Stop fail-closed  
- Hosts/Ports/Credentials nur Env oder DB, nie Commit  
- Safety-Toggles serverseitig erzwingen (nicht nur UI)  
- Rate-Limits auf Execute-/Emergency-Endpunkten beibehalten/erweitern  
- Tests niemals mit Live-`OSC_DRY_RUN=false` ohne Fake-Receiver  

### 10.3 Allgemein

- Kein Login im MVP ⇒ Deployment nur in vertrauenswürdigem Netz annehmen; in Docs klarstellen  
- API-Keys (OpenAI/Anthropic) nur `backend/.env`  
- Logs ohne Secrets/PII  

---

## 11. Migrationsstrategie

Leitlinie aus Audit + Architecture-Rule: **bestehende Funktionen nicht löschen, bevor Ersatz implementiert und getestet ist**; kein Big-Bang.

| Phase | Inhalt | Ergebnis |
|-------|--------|----------|
| **M0 — Doku** | Audit + dieses PRD + Architecture-Rule | Gemeinsames Zielbild |
| **M1 — Domäne Foundation** | Production/Asset/Cue/Device Tabellen + Migrationen + Active Production API | Leere Production CRUD |
| **M2 — Storage & Upload** | Local Storage-Service, Asset-Metadaten, Tagging | Upload-MVP |
| **M3 — Devices & Adapter-Bindung** | Device-Config; bestehende Bridges hinter Device-IDs; Dry-Run/Real | Cue execute ohne Hardcode-Projektoren in neuer Production |
| **M4 — Rules anbinden** | RuleSet aus bestehender Engine/JSON | Dramaturgie auf Production-Kontext |
| **M5 — Burgtheater-Import** | Import-Job aus `data/`/`media/` | Reference Production |
| **M6 — Operator & Safety** | Director-UI an Active Production; Emergency unverändert robust | Operator-MVP komplett |
| **M7 — Entkopplung Legacy** | JSON-Kataloge nur noch Import/Fallback; Projektor-Literals entfernen | Plattform ohne Venue-Hardcode |
| **M8 — Aufräumen** | Naming (`aidebatte`→neutral), Compose-Defaults, Redis-Entscheidung | Wartbarer Stand |

Rollback: Feature-Flags / parallele Pfade; Import-Production löschbar (archivierbar), Kernel unverändert startbar im Legacy-Modus bis M7.

---

## 12. Meilensteine

| Meilenstein | Lieferumfang | Akzeptanz (Kurz) |
|-------------|--------------|------------------|
| **MS0** | PRD + Audit abgestimmt | Stakeholder-OK auf Nicht-Ziele |
| **MS1** | Production CRUD + Active Production | Kriterien A–B |
| **MS2** | Asset-Upload + Tags | Kriterien C |
| **MS3** | Cue CRUD + Asset/Device-Zuordnung | Kriterien D |
| **MS4** | Device-Config + Dry-Run/Real Execute | Kriterien E–F |
| **MS5** | RuleSet-Weiterverwendung | Kriterium G |
| **MS6** | Burgtheater-Import | Kriterium H |
| **MS7** | Operator + Emergency auf neuem Kontext | Kriterium I |
| **MS8** | Regression grün; Legacy-Hardcodes dokumentiert entfernt oder isoliert | Kriterium J |

Empfohlene Bearbeitungsweise (Architecture-Rule): **pro Aufgabe nur einen Meilenstein**; vor Implementierung Dateiplan nennen; danach Backend-Tests, Frontend-Lint und TypeScript-Check.

---

## 13. Offene Produktentscheidungen

1. Duplikat: Assets physisch kopieren oder Storage teilen (Copy-on-Write)?  
2. Bleiben Teil-1 und Teil-2 im MVP als First-Class-UI oder nur als Legacy-Flows neben der neuen Production-UI?  
3. Device-Hosts: nur Env, nur DB, oder DB mit Env-Override?  
4. Soll der Burgtheater-Import einmalig (Seed) oder wiederholbar (Re-Import mit Merge) sein?  
5. Wann wird Auth nachgezogen (direkt nach MVP vs. erst bei Multi-Operator)?  

---

## 14. Referenzen

- [docs/platform-audit.md](platform-audit.md) — Ist-Zustand und Migrationsrisiken  
- [docs/architektur.md](architektur.md) — Signal- und Schichtmodell  
- [docs/dramaturgy_rules.md](dramaturgy_rules.md) — bestehende Regie-Regeln  
- [docs/teil2_inszenierung.md](teil2_inszenierung.md) — Text-Sync-Referenzproduktion  
- [docs/remote_transport.md](remote_transport.md) — Remote-Operator  
- [AGENTS.md](../AGENTS.md) — Dev- und Sicherheitswarnungen  
- [PLAN.md](../PLAN.md) — historischer Entwicklungsplan  
- `.cursor/rules/platform-architecture.mdc` — verbindliche Plattformregeln  

---

*Ende PRD — Theater-Maschine Plattform 2.0 MVP.*
