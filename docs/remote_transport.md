# Remote-Transport (Handy → Aufführung)

Play/Pause/Stop vom Handy, während **TTS und Cue-Takt auf dem Bühnen-Mac** bleiben.

## Warum nicht einfach die Aufführungsseite auf dem Handy öffnen?

Der ▶-Button startet die Show **im Browser-Tab**, der den Button drückt. TTS läuft dort als HTML-Audio; bei Teil 2 ist TTS der Taktgeber. Würde man Play auf dem Handy starten, käme die Stimme vom Handy — für die Bühne falsch.

Deshalb: Aufführungs-Tab auf dem Mac offen lassen; Handy schickt nur Steuerbefehle.

```text
Handy /remote  →  POST play/pause/stop  →  Backend-Mailbox
Mac-Aufführung  →  pollt Mailbox  →  führt lokale handlePlay/Pause/Stop aus
```

## Ablauf vor der Show

1. Auf dem **Bühnen-Mac**: `make run` (oder Stack wie gewohnt).
2. Aufführung vorbereiten und Tab offen lassen:
   - Teil 1: http://localhost:3003/auffuehrung
   - Teil 2: http://localhost:3003/inszenierung/auffuehrung
3. Mac-IP im LAN ermitteln (siehe unten).
4. Handy (gleiches WLAN/LAN): `http://<Mac-IP>:3003/remote`
5. Status **„Mac live“** abwarten, dann Play / Pause / Stop.

Nur **ein** Mac-Tab sollte die Aufführung laufen lassen. Bei zwei offenen Listener-Tabs gewinnt der erste, der den Befehl abholt.

## Mac-IP im LAN finden

Die Adresse brauchst du für die Handy-URL (`http://…:3003/remote`). Das ist die **IPv4-Adresse im lokalen Netz**, nicht die MAC-Hardwareadresse.

### Terminal (schnell)

```bash
ipconfig getifaddr en0
```

- Oft die **WLAN**-IP.
- Bei Ethernet leer? Dann `en1` versuchen:

```bash
ipconfig getifaddr en1
```

Beispiel-Ausgabe: `192.168.1.42` → Handy öffnet `http://192.168.1.42:3003/remote`.

Alle Interfaces auflisten:

```bash
ifconfig | grep "inet "
```

(Typisch lokal: `192.168.…` oder `10.…`; `127.0.0.1` ist nur der Mac selbst.)

### Systemeinstellungen

**Systemeinstellungen → Netzwerk →** aktives Interface (**WLAN** oder **Ethernet**) → **Details…** / Status → **IPv4-Adresse**.

### Hinweise

- Handy und Mac müssen im **gleichen Netz** sein (gleicher Router / gleiches WLAN; Gast-WLAN oft isoliert).
- Frontend-Port ist **3003** (wie bei `make run` / Docker).
- Firewall: eingehende Verbindungen auf Port 3003 vom LAN erlauben, falls die Seite nicht lädt.
- Mac eingeschlafen / Display aus: Audio kann stoppen — Energy Saver / „Display ausschalten“ für Show-Betrieb prüfen.

## UI

| Ort | Rolle |
|-----|--------|
| `/remote` | Große Play / Pause / Stop-Buttons, Status „Mac live“ / „Kein Mac“ |
| `/auffuehrung`, `/inszenierung/auffuehrung` | Hören auf Remote-Befehle; Hinweis-Link zu `/remote` |
| `/director` | Not-Aus / Safety — **kein** Show-Start |

## API (Backend)

| Methode | Pfad | Zweck |
|---------|------|--------|
| `POST` | `/api/v1/director/remote-transport` | Body `{ "action": "play" \| "pause" \| "stop" }` |
| `GET` | `/api/v1/director/remote-transport?consume=1&heartbeat=1` | Mac-Tab: Befehl abholen + „ich bin da“ |

- In-Memory-Mailbox (ein Show-Rechner), kein Redis.
- Befehle älter als ~30 s verfallen.
- Kein Auth (wie übrige Director-Routes im LAN) — nur im vertrauenswürdigen Show-Netz nutzen.

## Code

| Teil | Pfad |
|------|------|
| Mailbox | `backend/app/director/remote_transport.py` |
| Routes | `backend/app/api/routes/director.py` |
| Listener-Hook | `frontend/features/show/useRemoteTransportListener.ts` |
| Handy-UI | `frontend/app/remote/page.tsx` |
| Tests | `backend/tests/test_remote_transport.py` |

```bash
backend/run-tests.sh tests/test_remote_transport.py
```

## Troubleshooting

| Symptom | Check |
|---------|--------|
| Handy erreicht Seite nicht | Mac-IP, Port 3003, gleiches WLAN, Firewall |
| „Kein Mac“ bleibt stehen | Aufführungs-Tab auf dem Mac wirklich offen und geladen? Backend läuft? |
| Play gesendet, nichts passiert | Stück/Korpus bereit (`canPlay`)? TTS/Buffer ok? Nur ein Listener-Tab? |
| Stimme kommt vom Handy | Falsch: Aufführung auf dem Handy gestartet. Stattdessen `/remote` nutzen und Mac-Tab Play ausführen lassen |
