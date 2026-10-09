# Founder Studio

Browserbasierter Startup-Interview-Agent mit React, FastAPI, LiveKit, Deepgram, OpenAI und ElevenLabs. Zwei Oberflächen: Startup-Gesprächsraum und Administrator-Konfiguration. Die ursprüngliche Aufgabenstellung liegt in `BackgroundInfo/Coding_Challenge_AI-Voice-Agent.pdf`.

## Guides

- [Demo-Guide](docs/DEMO_GUIDE.md): Präsentationsablauf, Beispielgespräch, Ergebnisbewertung und Fallback.
- [Technischer Guide](docs/TECHNICAL_GUIDE.md): Einrichtung, Architektur, Konfiguration, Betrieb, Tests und Fehlerbehebung.

- [Code study path](docs/learning/README.md): separate backend and frontend deep dives, reading order, interview questions and executable Python notebooks.

## Schnellstart unter Windows

Voraussetzungen: Python 3.11+, Node.js (empfohlen 22.22+), Mikrofon und ein aktueller Browser. Mikrofonzugriff benötigt localhost oder HTTPS.

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -e '.[test,voice]'
Set-Location frontend
npm ci
npm run build
Set-Location ..
.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Öffne http://localhost:8000. Ohne `.env` stehen auf dem lokalen Rechner zwei Vorschauzugänge bereit. Der **Text-Testlauf ist eine explizite Simulation ohne KI oder Audio**: Er testet Gesprächsfolge, unklare Antworten, Speicherung und Historie. Er bewertet Texte nicht automatisch.

Für die laufende Frontend-Entwicklung: `npm run dev` im Ordner `frontend`; `PUBLIC_ORIGIN=http://localhost:5173` setzen und den API-Server neu starten. Vite leitet `/api` an Port 8000 weiter.

## Echte Voice-Gespräche

1. `.env.example` nach `.env` kopieren.
2. LiveKit-Projekt erstellen und `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` setzen.
3. `OPENAI_API_KEY`, `ELEVENLABS_API_KEY` und den Key für den gewählten STT-Anbieter setzen (standardmäßig `DEEPGRAM_API_KEY`, siehe unten). Diese APIs werden getrennt nach Nutzung abgerechnet.
4. `SESSION_SECRET` und `WORKER_SECRET` mit zwei unabhängig generierten Zufallswerten setzen. Beispiel: `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
5. Optional `ADMIN_PASSWORD` setzen; dann sind die lokalen passwortlosen Vorschauzugänge deaktiviert. Founder erhalten Einladungslinks aus dem Admin-Bereich.
6. API neu starten. Im Admin-Bereich eine gültige ElevenLabs Voice-ID aus deinem Account eintragen und die Konfiguration veröffentlichen. Die Hörprobe nutzt die echte API und ist kostenpflichtig.
7. In einem zweiten Terminal im Projektordner:

```powershell
.venv/Scripts/python -m livekit.agents download-files
.venv/Scripts/python -m voice.worker dev
```

Der Download lädt lokale Modelle für Sprachaktivität/Gesprächsenden. Er benötigt keine kostenpflichtige Voice-Sitzung. Danach im Browser anmelden, Mikrofon testen und Interview starten. Der Worker und die API müssen dieselben LiveKit- und Worker-Zugangsdaten verwenden. Keine API-Schlüssel im Browser oder in Git speichern.

Voice wird nur angeboten, wenn die erforderlichen Einstellungen vorliegen. Das ist eine Konfigurationsprüfung, kein Nachweis gültiger Schlüssel oder eines laufenden Workers. Ohne Worker meldet die Oberfläche nach 30 Sekunden einen Verbindungsfehler.

## Spracherkennung auswählen

Die Factory `voice/stt.py:create_stt` liefert für beide Anbieter ein `livekit.agents.stt.STT`-Objekt. Streaming, Transkript-Ereignisse und Fehlerbehandlung nutzen dadurch dieselbe Schnittstelle; ein zusätzlicher Wrapper ist nicht nötig.

In `.env` wählen:

```dotenv
STT_PROVIDER=deepgram
```

Deepgram Nova-3 bleibt der Standard und benötigt `DEEPGRAM_API_KEY`. Für ElevenLabs Scribe v2 Realtime stattdessen `STT_PROVIDER=elevenlabs` setzen. Dann wird `ELEVENLABS_API_KEY` für Spracherkennung und Sprachausgabe verwendet; der Key benötigt beide Berechtigungen. Optional kann `ELEVENLABS_STT_API_KEY` einen separaten Key nur für Spracherkennung enthalten. Ein Deepgram-Key ist bei dieser Auswahl nicht erforderlich.

API und Worker nach Änderungen neu starten; beide müssen dieselbe Anbieterauswahl verwenden. Die Auswahl gilt für den Server und erfolgt aktuell nicht im Admin-UI. Es gibt keinen automatischen Anbieterwechsel bei Fehlern. Der Live-Check prüft den gewählten STT-Anbieter. Die ElevenLabs-STT-Anbindung ist offline gegen das installierte SDK getestet; ein echter Sprach- und Latenzvergleich steht noch aus.

## Bedienung

- **Startup:** Start, Mute, Stop, sichtbarer Verlauf, Themenfortschritt und Ergebnisprofil. Die eigene Historie bleibt nach Server-Neustart erhalten, sofern `SESSION_SECRET` stabil bleibt und der Founder denselben Einladungszugang verwendet.
- **Admin:** Agentname, Deutsch/Englisch, Tonalität, Fragen/Rückfragen, Dauer, ElevenLabs-Stimme, Flash/Turbo, Stabilität, Ähnlichkeit, Tempo und Pausentoleranz. Fragen sind redaktioneller Inhalt und müssen in der gewählten Sprache formuliert werden. Änderungen werden versioniert und gelten erst für neue Gespräche.
- **Steuerung:** konkrete Antwortziele mit Pflichtstatus, ausreichender Antwort, Rückfragenbudget und Bedingungen. Fragen können ergänzt, deaktiviert und geordnet werden. Bereits beantwortete Ziele werden übersprungen.
- **Match:** konfigurierbares Zielprofil ohne voreingestellte Präferenzen. Kategorien und Zahlenintervalle mit Gewichten; nachvollziehbarer Score und separate Belegabdeckung. Das Profil wird pro Gespräch eingefroren.
- **Auswertung:** grafische Vollständigkeit nach Themen, Gesprächsstatistik und durchsuchbares Transkript mit Sprecherfilter, Zeitangaben, Unterbrechungen und Belegverknüpfungen. TXT-/JSON-Download.
- **Ergebnis:** sieben Themen und einzelne belegte Fakten, darunter Name, Sektor, Stage, Team, Produkt, Traktion, Markt, Wettbewerb, Finanzierungsbetrag/Währung/Runde, Mittelverwendung, nächster Schritt. Unbekannte Angaben werden nicht erfunden. JSON-Export enthält Belege und Transkript.
- **Abschluss:** Der Agent fasst zusammen; eine ausdrückliche Bestätigung schließt das Interview ab. Korrekturen erfordern eine neue Bestätigung. Stop beendet die Mikrofonaufnahme sofort und speichert einen unvollständigen Verlauf.

## Provider-Verbindung prüfen

Nach dem Eintragen der geheimen API-Schlüssel (nicht deren Key-IDs) und der Voice-ID:

```powershell
.venv/Scripts/python -m scripts.voice_check --live
```

Dieser ausdrücklich aktivierte Test verwendet echte APIs, einen kurzen fiktiven Startup-Satz, eine Sekunde Stille und eine kurze Hörprobe. Er kann Gebühren verursachen und gibt keine Schlüssel oder Provider-Antwortbodies aus. Er prüft OpenAI-Tool-Extraktion und Validierung, LiveKit-Authentifizierung, den WebSocket-Zugang des gewählten STT-Anbieters und ElevenLabs-Audiostream. Bei ElevenLabs-STT prüft er die authentifizierte Sitzung, nicht die Erkennungsqualität. Fehlercodes unterscheiden z. B. Key-ID statt Secret, fehlende Berechtigung und erschöpftes Kontingent.

Die synthetische WAV-Datei lässt sich unter Windows mit `./scripts/make_voice_fixture.ps1` erstellen (installierte Stimme Microsoft Hedda Desktop). Sie enthält ausschließlich fiktive Testdaten.

Die opt-in Browserprüfung `frontend/e2e/voice.live.spec.ts` benötigt `.local/browser-microphone.wav` (16-kHz-Mono-PCM-WAV, synthetische deutsche Vorstellung, 12 Sekunden Stille davor und 55 danach). Mit `RUN_LIVE_VOICE=1` und `npm test -- voice.live.spec.ts` nutzt Edge ausschließlich dieses künstliche Mikrofon. Echte Anbieter werden aufgerufen; der Test beendet die Sitzung auch bei Fehlern. Ergebnisse liegen in `.local/live-voice-result.json`. Ohne ausdrückliches Opt-in wird dieser Test übersprungen. Reale Mikrofon-/Headset-Qualität bleibt eine separate manuelle Abnahme.

## Tests

```powershell
.venv/Scripts/python -m pytest
Set-Location frontend
npm run build
npm test
```

Die Browser-Tests erwarten eine laufende API auf `http://localhost:8000` mit dem gebauten Frontend, eine leere lokale Testumgebung ohne `ADMIN_PASSWORD` sowie Microsoft Edge. Für einen separaten Testserver `TEST_BASE_URL` setzen und dessen `PUBLIC_ORIGIN` passend konfigurieren. Sie verwenden nur den lokalen Text-Testlauf und erstellen echte lokale Testgespräche. Screenshots liegen unter `.local/screenshots` (ignoriert). Für andere Browser `channel` in `frontend/playwright.config.ts` anpassen.

`requirements-lock.txt` dokumentiert die geprüfte Windows-Python-Umgebung; `frontend/package-lock.json` fixiert die Frontend-Abhängigkeiten. Das LiveKit Agents SDK ist in `pyproject.toml` auf die geprüfte Version fixiert. Anbieterintegration ist mit Mocks und dem echten SDK-Lebenszyklus getestet; ein echter Audio-/Latenztest benötigt deine Zugangsdaten und ein Mikrofon.

## Deployment

`Dockerfile` baut React und die API, `Dockerfile.worker` den separaten Voice Worker. Lokaler Containerstart: `docker compose up --build`; mit Voice Worker: `docker compose --profile voice up --build`. In Docker `ADMIN_PASSWORD`, `SESSION_SECRET` und `WORKER_SECRET` setzen: Containerzugriffe sind keine lokalen passwortlosen Demoanmeldungen.

Für Cloud Run: API-Image mit `ENVIRONMENT=production`, `PERSISTENCE_BACKEND=firestore`, einer HTTPS-`PUBLIC_ORIGIN` und drei unterschiedlichen Geheimnissen/Passworten von jeweils mindestens 32 Zeichen starten. GCP-Zugriff über Service Account/ADC, Geheimnisse über Secret Manager. Der Browser erreicht die App über HTTPS; die App prüft die Rollen selbst. Den internen Worker-Zugriff zusätzlich am Ingress absichern, wenn die Infrastruktur das unterstützt. Voice Worker separat auf LiveKit Cloud oder einem dauerhaft laufenden Container betreiben; `BACKEND_URL` auf die API setzen. Firestore-Datenbank vorab anlegen.

Die Anwendung speichert selbst kein Roh-Audio. Transkripte und Ergebnisse liegen in der Datenbank; technische Logs enthalten keine von uns ausgegebenen Gesprächsinhalte. Die Datenverarbeitung/Aufbewahrung bei externen Anbietern muss für den jeweiligen produktiven Einsatz gesondert eingestellt werden.

## Projektstruktur

- `app/`: API, Authentifizierung, Konfiguration, Datenmodelle, atomare Persistenz und deterministische Gesprächssteuerung.
- `voice/`: LiveKit Worker und strukturierte KI-Extraktion.
- `frontend/`: React-Oberflächen und Browser-Tests.
- `tests/`: Backend-, Gesprächs- und Voice-Vertragstests.
- `docs/`: Architektur, API-Verträge, Teststrategie und aktueller Umsetzungsstand.

Das alte ServicePilot-Projekt und seine Paketmetadaten wurden entfernt. Die ursprüngliche Aufgabenstellung in `BackgroundInfo/` bleibt erhalten.
