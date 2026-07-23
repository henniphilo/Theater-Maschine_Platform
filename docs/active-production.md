# Active Production — Speicherentscheidung (MS1)

**Stand:** 2026-07-23  
**Bezug:** [platform-prd.md](platform-prd.md) §3.2, §6.2

## Entscheidung

Die **aktive Produktion** wird in MS1 als **eine `production_id` pro Backend-Instanz** gespeichert in:

```text
{DIRECTOR_DATA_DIR}/active_production.json
```

Beispielinhalt:

```json
{
  "production_id": "9f3c2a1b-...."
}
```

`null` bzw. fehlende Datei bedeutet: keine aktive Produktion.

API:

- `GET /api/v1/productions/active`
- `PUT /api/v1/productions/active` mit `{"production_id": "<uuid>|null"}`

Implementierung: `backend/app/services/active_production.py`

## Warum so (und nicht anders)

| Option | Bewertung für MS1 |
|--------|-------------------|
| JSON-Datei unter `data/` | **Gewählt** — nachvollziehbar, restart-sicher, kein neues DB-Tabellen-Konzept, ops-freundlich |
| Nur In-Memory | Zu flüchtig für lokale Native-Restarts |
| PostgreSQL-Singleton-Tabelle | Unnötig für einen Skalar; kommt ggf. später bei Multi-Operator |
| Nur Frontend-`localStorage` | Keine Server-Quelle der Wahrheit; Uploads/Cues bräuchten Backend-Kontext |

## Frontend-Spiegel

Die UI hält zusätzlich `localStorage["tm.activeProductionId"]` für schnelle Anzeige und Offline-Hinweis. **Autoritative Quelle bleibt die API.** Beim Laden von `/productions` wird der Serverstand gelesen und der Spiegel aktualisiert.

## Regeln

- Archivierte Produktionen können nicht aktiv gesetzt werden.
- Archivieren der aktiven Produktion leert die aktive Auswahl.
- Bestehende Burgtheater-Flows (Teil 1/2, Director) lesen diesen Kontext in MS1 **noch nicht** — parallel und unverändert.

## Später

Bei Multi-Replica oder Auth: Persistenz in PostgreSQL und/oder Session-Kontext; Datei-Adapter bleibt austauschbar hinter derselben Service-API.
