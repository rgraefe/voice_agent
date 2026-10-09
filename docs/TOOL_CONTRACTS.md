# API- und Tool-Verträge

Interaktive OpenAPI-Dokumentation: `/docs`; JSON-Schema: `/openapi.json`.

Alle Browser-Schreibanfragen: `X-Requested-With: founder-app`, gleiche konfigurierte Origin, Session-Cookie. Alle Worker-Anfragen: `Authorization: Bearer <WORKER_SECRET>`. Browser/Founder dürfen keine Extraktionsergebnisse direkt an Worker-Endpunkte übergeben.

| Endpoint | Berechtigung / Wirkung |
| --- | --- |
| GET /api/bootstrap | Öffentliche Fähigkeiten und aktuelle Rolle, keine Geheimnisse |
| POST /api/login | Admin-Passwort oder signierte Einladung; lokal explizite Vorschau |
| POST /api/logout | Cookie entfernen |
| POST /api/admin/invites | Admin, sieben Tage gültiger Founder-Link |
| GET/PUT /api/admin/config | Admin, Lesen/Publizieren; version als optimistische Sperre |
| POST /api/admin/voice-preview | Admin, echte kostenpflichtige ElevenLabs-Hörprobe |
| GET/POST /api/interviews | Eigene Historie / Start mit mode und request_id |
| GET /api/interviews/{id} | Eigentümer oder Admin |
| POST /api/interviews/{id}/connection | Raumgebundenes LiveKit-Token für aktive Voice-Sitzung |
| POST /api/interviews/{id}/stop | Idempotent unvollständig beenden, Raum schließen |
| GET /api/interviews/{id}/analysis | Eigentümer/Admin: deterministischer Bericht mit Match, Abdeckung, Vollständigkeit, Belegen, Statistik und geordnetem Transkript |
| GET /api/interviews/{id}/export | Strukturiertes Ergebnis, Belege, Transkript und offene Themen |
| POST /api/interviews/{id}/simulation-turn | Nur lokale simulierte Sitzung, keine KI |
| GET /api/internal/interviews/{id} | Worker, kanonischer Zustand |
| POST /api/internal/interviews/{id}/turns | Worker, validierte Extraktion atomar anwenden |
| POST /api/internal/interviews/{id}/speech | Worker, tatsächlichen Transkriptbeitrag speichern |
| POST /api/internal/interviews/{id}/metrics | Worker, bounded Nutzungs-/Timing-Metriken |
| POST /api/internal/interviews/{id}/stop | Worker, idempotenter Abschluss eines unvollständigen Interviews |

## Extraktion

`Turn`: id, text, optional timestamp mit Zeitzone, extraction. Neue `Extraction`: answers, acknowledgment, confirmed_summary. Jede Antwort: goal_key, status (answered/partial/unknown), value, quote, optional number_value/choice_value. Exakte Zitate müssen im aktuellen Turn vorkommen; Ziele dürfen nur einmal vorkommen. Typisierte vollständige Antworten benötigen passende Werte. Legacy observations/facts werden nur für alte Interviews unterstützt. Das erzwungene Tool `record_interview_observations` schlägt Angaben vor; erst der atomare Backend-Commit bestätigt Speicherung.

`AgentConfig.goals`: key, topic, label, criteria, question, clarification, required, enabled, max_followups (0–3), kind, choices, unit, condition (goal_key, equals). `match_profile`: name, rules (goal_key, weight 1–10, operator one_of/range, accepted oder minimum/maximum). Referenzen, Typen, Reihenfolge der Bedingungen und Grenzen werden beim Publizieren validiert. Konfigurationsmigration ergänzt alte veröffentlichte Konfigurationen einmalig; existierende Interviews behalten ihre Snapshots.

Simulation: `goal_key` optional (sonst aktuelles Ziel), `choice_value`, `number_value`, `answer_status` optional; ohne answer_status entspricht clear=true einer vollständigen, false einer partiellen Antwort. Kein LLM und keine automatische Bewertung des Freitexts. Typwerte werden im Text-Testlauf explizit zugeordnet.

Bericht: score/coverage/completeness können null sein. rules enthalten Status matched/unmatched/unknown/not_applicable und Belegreferenzen. goals enthalten zusätzlich blocked für ungeklärte Bedingungen. statistics enthält Dauer, Beiträge, Wortzahlen, Rückfragen und unterbrochene Beiträge. Wortanteile sind keine gemessene Sprechzeit. Transkript-Replays behalten ursprüngliche Zeitstempel; Sprecherwechsel unter derselben ID wird abgewiesen. Text- und JSON-Export erfolgen aus der autorisierten Ergebnisansicht.

## Fehlerformat

```json
{"error":{"code":"VOICE_NOT_CONFIGURED","message":"Bitte zuerst die Voice-Zugänge und eine Stimme konfigurieren.","retryable":false}}
```

Wichtige Fehler: UNAUTHORIZED (401), FORBIDDEN/CSRF_REJECTED/ORIGIN_REJECTED (403), NOT_FOUND (404), CONFIG_CONFLICT/IDEMPOTENCY_CONFLICT/INTERVIEW_CLOSED (409), INVALID_EVIDENCE/VALIDATION_ERROR (422), RATE_LIMITED (429), VOICE_PROVIDER_ERROR (502), SERVICE_UNAVAILABLE/VOICE_NOT_CONFIGURED (503), VOICE_TIMEOUT (504). Fehlertexte enthalten keine eingegebenen Geheimnisse oder Provider-Antwortbodies.

## Konfigurationsdateien

`POST /api/admin/config/validate` benötigt einen Admin-Zugang und eine vollständige `AgentConfig`. Validiert Typen, Ziele, Bedingungen und Zielprofil ohne Speicherung. Liefert den Entwurf mit der aktuellen veröffentlichten Versionsnummer zurück; `PUT /api/admin/config` bleibt der einzige Veröffentlichungsschritt und prüft weiterhin Versionskonflikte. Ungültige oder unvollständige Dateien: 422. Kein Zugang: 401; Founder-Zugang: 403.
