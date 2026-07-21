# Avatar-Done-Gate: Erzähler wartet auf Video-Ende

Ziel: **Avatar-Performance-Clips** blockieren den Erzählertext und den nächsten Avatar, bis das Video fertig ist. **Atmosphäre / Loops** bleiben unabhängig und können weiterlaufen.

```
Avatar-OSC start  →  Video spielt  →  Done-Signal  →  TTS weiter / nächster Avatar
```

---

## Status

| Pfad | Stand |
|------|--------|
| **QLab (lokaler Test via Relay)** | implementiert |
| **Pixera (Bühne)** | vorbereitet, noch nicht verdrahtet — siehe unten |

Feature-Flag (Backend `.env`):

```env
AVATAR_DONE_GATE_ENABLED=true
AVATAR_DONE_OSC_HOST=127.0.0.1
AVATAR_DONE_OSC_PORT=8991
AVATAR_DONE_TIMEOUT_GRACE_MS=2000
```

Ohne Flag (`false`, Default): Verhalten wie bisher — TTS läuft durch, Beamer-Sperren nur über geschätzte CSV-Dauer.

---

## Ablauf (QLab-Test)

```
Theatermaschine  →  /pixera/args/cue/apply  →  Relay :8990  →  QLab /cue/{name}/start
                                                                      │
                                                                      │ Video endet
                                                                      ▼
Theatermaschine  ←  /avatar/done {name}  ←  Relay  ←  QLab show-control cue/stop
     :8991
```

1. Teil-2 feuert Avatar-OSC und pausiert die TTS.
2. Frontend ruft `POST /api/v1/director/avatar-done/wait` mit den Pixera-Cue-Namen.
3. Relay empfängt QLab Show-Control `…/cue/stop` und sendet `/avatar/done <cue_number>`.
4. Backend löst den Wait → TTS läuft weiter → nächster Avatar erst danach.

Timeout: max. Clip-`duration_ms` (CSV) + `AVATAR_DONE_TIMEOUT_GRACE_MS` (sonst 120 s + Grace). Bei Timeout geht die Aufführung weiter (Warnung in der Konsole).

Atmosphäre-Stops werden vom Gate **ignoriert**, solange sie nicht in der Wait-Liste stehen.

---

## Setup QLab

Voraussetzungen wie in [qlab_setup.md](qlab_setup.md): Workspace, Video-Cues, `make qlab-relay`, Backend nativ.

Zusätzlich:

```env
# backend/.env — lokal
AVATAR_DONE_GATE_ENABLED=true
AVATAR_DONE_OSC_HOST=127.0.0.1
AVATAR_DONE_OSC_PORT=8991
PIXERA_OSC_HOST=127.0.0.1
PIXERA_OSC_PORT=8990
```

1. Backend neu starten (`make run`), damit der Listener auf `:8991` läuft.
2. `make qlab-relay` — aktiviert standardmäßig QLab-Feedback (`/listen` + `/listen/cue/stop` + Keepalive).
3. QLab nach der Checkliste unten einstellen.

### QLab-Checkliste (wichtig)

Ohne diese Punkte kommt **kein** Done-Signal — die Stimme wartet dann bis zum Timeout (CSV-Dauer) oder hängt optisch „zu lange“.

| # | Einstellung | Warum |
|---|-------------|--------|
| 1 | **Workspace Settings → Network → OSC Access**: Haken bei **View** und **Control** | Sonst akzeptiert QLab `/listen` nicht zuverlässig |
| 2 | OSC Listening Port **53000** | Relay spricht QLab dort an |
| 3 | Avatar-**Video-Cues enden** (kein Loop / keine unendliche Duration) | Nur wenn der Cue „ausläuft“, sendet QLab `cue/stop` |
| 4 | Cue-**Nummer** = exakter Pixera-Name (`KI_RZ21.BK1_Caro`, …) | Start und Stop müssen denselben Namen tragen |
| 5 | Relay läuft (`make qlab-relay`) und loggt `qlab feedback: …` | Abonniert Show-Control und leitet Stops weiter |

**Kein extra Workspace-Schalter** für OSC Show-Control nötig: Der Client (Relay) schickt `/listen` / `/listen/cue/stop`, QLab antwortet dann mit Events an denselben UDP-Absender.

### Show-Control (Standardpfad)

Der Relay erwartet Events der Form:

```
/qlab/event/workspace/cue/stop  {cue number}  {cue name}  {uniqueID}  {cue type}
```

Cue number muss dem gestarteten Video-Cue entsprechen (z. B. `KI_RZ21.BK1_Caro`).

Im Relay-Log sollte bei Clip-Ende erscheinen:

```
relay qlab stop …/cue/stop -> /avatar/done KI_RZ21.…
```

### Fallback: Network-Cue (wenn Show-Control nicht ankommt)

Zuverlässigste Variante zum Testen — **einmal pro Avatar-Video** (oder als Vorlage kopieren):

1. Nach dem Video-Cue einen **Network Cue** anlegen (Group „fire first child, then next“ oder Auto-continue nach dem Video).
2. Network-Patch: UDP an `127.0.0.1`, Port **`8991`** (direkt Backend).
3. OSC-Nachricht:
   - Adresse: `/avatar/done`
   - Argument (String): dieselbe Cue-Nummer wie das Video, z. B. `KI_RZ21.BK1_Caro`

So umgehst du Show-Control komplett. Atmosphäre-Videos brauchen **keinen** Network-Cue.

### Schnell prüfen

1. Gate an, Relay + Backend laufen.
2. In QLab einen Avatar-Video-Cue manuell starten und auslaufen lassen.
3. Relay-Log: `relay qlab stop … → /avatar/done …` **oder** Network-Cue feuert.
4. Optional manuell:

```bash
cd backend && .venv/bin/python - <<'PY'
from pythonosc.udp_client import SimpleUDPClient
SimpleUDPClient("127.0.0.1", 8991).send_message("/avatar/done", ["KI_RZ21.BK1_Caro"])
print("sent")
PY
```

Wenn das manuelle `/avatar/done` die pausierte Stimme sofort weiterlaufen lässt, ist Theatermaschine ok — dann fehlt nur noch QLab→Relay.

---

## API / Code

| Stück | Ort |
|-------|-----|
| Gate-Zustand | `backend/app/director/avatar_done_gate.py` |
| OSC-Listener | `backend/app/director/outputs/avatar_done_listener.py` |
| Wait-API | `POST /api/v1/director/avatar-done/wait` |
| Status-Flag | `GET /api/v1/director/status` → `avatar_done_gate_enabled` |
| Relay-Feedback | `tools/pixera_qlab_relay.py` (`--no-qlab-feedback` zum Abschalten) |
| TTS-Pause | `frontend/features/inszenierung/avatarCuePlayback.ts` |

Während einer Wait-Anfrage: Signal-Trace `avatar.done_received` / `avatar.done_wait`.

---

## Pixera (Bühne) — vorbereitet, noch offen

Pixera-OSC (`/pixera/args/cue/apply`) ist **fire-and-forget** und liefert **kein** Clip-Ende. Für die Bühne brauchen wir einen der folgenden Wege (noch nicht implementiert):

### Option A — Cue sendet OSC/String selbst (empfohlen prüfen)

In der Pixera-Timeline am Ende jedes Avatar-Clips (oder via Control / CueAppliedActions / String-Output am Cue):

```
/avatar/done  "KI_Adam.BK1_Caro"
```

an `AVATAR_DONE_OSC_HOST:AVATAR_DONE_OSC_PORT` der Theatermaschine.

Vorteil: gleiche Adresse wie QLab-Pfad, Backend bleibt unverändert.  
Aufwand: einmalig Cue-Programmierung / Modul in Pixera.

### Option B — JSON/TCP Monitoring

Pixera Native API per JSON/TCP: Transport-Status / Monitoring pollen oder Events empfangen, Backend mappt „Clip fertig“ → `AvatarDoneGate.signal_done`.

Vorteil: keine Cue-seitige Verdrahtung.  
Aufwand: neuer Bridge-Client, Handles/Timeline-Mapping, robuste Reconnect-Logik.

### Option C — Dauer-Timer (Fallback)

Weiterhin CSV-`duration_ms` als Timeout (schon im Gate als Sicherheitsnetz). Nicht frame-genau, aber ohne Pixera-Feedback nutzbar.

### Checkliste Bühne

- [ ] Entscheidung A vs. B mit Technik/Pixera-Operator
- [ ] Netz: Show-Rechner erreicht Pixera; Rückkanal zur Maschine erlaubt (Firewall/UDP)
- [ ] Nur **Avatar**-Clips senden Done — Atmosphäre nicht
- [ ] `AVATAR_DONE_GATE_ENABLED=true` auf dem Show-Rechner
- [ ] Probe: ein Avatar-Clip → Wait endet → TTS setzt fort; Atmosphäre parallel ungestört
- [ ] Docs hier + `.env.example` aktualisieren, sobald der Pixera-Pfad feststeht

---

## Abgrenzung

- Gate gilt für Avatar-Segmente (Teil 2 Text-Sync / Avatar-Moment-Cues).
- Licht, Sound, Atmosphäre-Videos: **kein** Done-Gate.
- Stop / Emergency: Gate wird zurückgesetzt (`reset`), hängende Waits enden.
