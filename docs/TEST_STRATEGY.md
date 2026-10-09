# Teststrategie

Automatisiert: deterministische Fragefolge, fehlende/vage Angaben, einmalige Rückfrage, Themen außerhalb der Reihenfolge, Korrekturen, Zusammenfassungsbestätigung, idempotente Speicherung, Zustandsgrenzen, ungültige Belege, Auth/Rollentrennung, fremde Daten, CSRF, Konfigurationssnapshot/-konflikt, dauerhafte SQLite-Ablage, Provider-Timeout und 500, Worker-Fehlerpfade, Raumtoken-Beschränkung. Ein Test führt den echten installierten LiveKit AgentSession-Lebenszyklus mit simuliertem Extraktionsanbieter aus.

Browser: echte React-App im Edge, lokaler Start, vage Antwort/Rückfrage, strukturierte Ergebnisse, Stop, Historie, Admin-Publishing, mobile Darstellung ohne horizontalen Überlauf. Keine realen API-Aufrufe oder automatisierte Mikrofonaufnahme in diesen Tests.

Manuelle Voice-Abnahme nach Konfiguration:
1. 20 deutsche Gesprächswechsel mit kurzem/langem Satz, Zahlen, englischen Startup-Begriffen und Denkpausen.
2. Median und p95 vom tatsächlichen Sprechende bis zum ersten hörbaren Antwortsample messen; Ziel <2 s bei normalen Turns. Worker-Metriken sind nur ein Proxy und müssen gegen Audio überprüft werden.
3. Agent mitten im Satz unterbrechen; kein altes Audio darf weiterlaufen. Fortsetzung berücksichtigt nur tatsächlich gehörte Frage.
4. Stimme Flash/Turbo und 2 Voice-IDs mit denselben Texten vergleichen; Natürlichkeit, Verständlichkeit, Aussprache, Pausen und Latenz protokollieren.
5. Kein Mikrofonrecht, Netzverlust, Worker nicht gestartet, falscher Schlüssel, ungültige Voice-ID, Anbieter-Ausfall, Tab schließen, Dauerlimit.
6. Bestätigung verweigern, Finanzierungswährung korrigieren, bereits freiwillig genannte Themen nicht erneut fragen. Unbekannte Angaben bleiben unbekannt.
7. Firestore-Emulator bzw. isolierte Testdatenbank mit zwei API-Instanzen: atomare Updates, konkurrierende Konfigurationsversionen, Server-Neustart und IAM prüfen.

Cloud/Firestore und echte STT/TTS-Qualität sind ohne externe Zugangsdaten nicht live verifiziert. Docker-Builds sind nur dann als geprüft zu bezeichnen, wenn sie tatsächlich gelaufen sind.

## Antwortziele und Auswertung

Zusätzliche Regressionen: bedingte Ziele (Ja/Nein/unbekannt), Reaktivierung nach Korrektur, Pflicht/optional, begrenzte Rückfragen mit Teilantworterhalt, Typ-/Belegvalidierung vor Mutation, gewichtete Match-Berechnung, inklusive Grenzen, unbekannte vs. nicht relevante Kriterien, leeres Zielprofil, unveränderte historische Snapshots, autorisierte Berichte und chronologische idempotente Transkripte. Browser prüft vollständigen Ablauf, Auswertung, Transkriptsuche und responsive Darstellung.
