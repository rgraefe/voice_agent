# Live-Voice-Abnahme – 9. Oktober 2026

## Aufbau

Lokale FastAPI/SQLite-App und LiveKit-Worker; echtes LiveKit Cloud, Deepgram Nova-3 (Deutsch), OpenAI GPT-4.1 mini und ElevenLabs Flash v2.5. Standard-Teststimme: George, Voice-ID JBFqnCBsd6RMkjVDRZzb. Edge erhält eine synthetische WAV-Datei über sein Fake-Mikrofon; kein menschliches Mikrofon wird aufgezeichnet. Alle Anbieterschlüssel bleiben ausschließlich in der lokalen .env.

## Gefundene und behobene Integrationsfehler

- GPT-4.1 mini befüllte Legacy-Facts trotz anderslautendem Prompt. Neue Interviews verwenden jetzt ein eigenes Tool-Schema ohne diese Felder. Die kanonische Backend-Validierung bleibt bestehen.
- LiveKit sendet auch AgentHandoff als Conversation-Event. Der Transkript-Handler verarbeitet jetzt ausschließlich Assistant-Nachrichten, statt für andere Ereignistypen auf ein fehlendes role-Feld zuzugreifen.
- ElevenLabs war zunächst mit der Key-ID statt dem Secret konfiguriert. Nach Austausch erfolgreich. Die Hörprobe unterscheidet nun falschen Schlüssel, fehlende Rechte, erschöpftes Kontingent und nicht verfügbare Stimme mit verständlichen Meldungen.
- Der Extraktionskontext enthält nur die benötigten Kriterien und vorhandenen Antworten; doppelte Themenzustände und ungenutzte Legacy-Felder entfallen.

## Bereits live verifiziert

- LiveKit-Authentifizierung und Browser-Raumverbindung.
- Deepgram-WebSocket und Erkennung synthetischer deutscher Sprache.
- Echter OpenAI-Tool-Call, Beleg-/Typvalidierung und Fortschreiben konkreter Antwortziele.
- ElevenLabs liefert echte Audiodaten; Browser spielt den empfangenen Audiostream.
- User-/Assistant-Beiträge und Antworten werden gespeichert; Stop beendet die Testsitzung.
- 48 Python-Regressionstests erfolgreich.
- Finale opt-in Edge-Prüfung bestanden: 3 erkannte User-Beiträge, 2 gespeicherte Assistant-Beiträge, laufende Audio-Wiedergabe. Exakter Namensvergleich in diesem Lauf: False.

## Grenzen der Prüfung

Exakte Eigennamen-Erkennung war mit der synthetischen Windows-Stimme nicht zuverlässig: Lumio wurde als Lumyo/Lunyo, Solar als Sula erkannt. Frühere Browserläufe bestanden Audio-/Speicherprüfungen, scheiterten aber an der zusätzlichen exakten Namensprüfung. Die finale Transportprüfung prüft deshalb korrekte gewöhnliche Wörter und belegte Extraktion; sie speichert den exakten Namensvergleich separat als name_spelling_exact. Dies ist keine bestandene Eigennamen-Abnahme. Kein stilles Alias-Mapping oder nachträgliches Umschreiben des Transkripts.

Ein erster Worker-Messwert nach der letzten Pause betrug etwa 1,33 Sekunden bis Agent-Sprechbeginn. Das ist ein Proxy ab erkanntem Sprechende; kein Browser-Sample-Benchmark und keine p95-Zusage. Aktuelle Messwerte und das Ergebnis der letzten Browserprüfung stehen in .local/live-voice-result.json (nicht eingecheckt). Die Prüfung umfasst wenige künstliche Turns, keine belastbare Latenzstudie.

Noch manuell zu prüfen: Natürlichkeit und deutsche Aussprache der ausgewählten Stimme, echte Mikrofone/Headsets, Denkpausen, bewusstes Unterbrechen, Korrektur von Eigennamen und Finanzierungszahlen, sowie Median/p95 der hörbaren Antwortlatenz. Die Cloud-/Firestore-Bereitstellung und HeyGen sind nicht Teil dieser lokalen Voice-Abnahme.

## Wiederholung

1. API und Worker mit derselben .env starten.
2. Unter Windows ./scripts/make_voice_fixture.ps1 ausführen.
3. In frontend RUN_LIVE_VOICE=1 setzen, dann npm test -- voice.live.spec.ts ausführen.
4. Ohne dieses Opt-in wird kein kostenpflichtiger Browser-Voice-Test ausgeführt.

Der separate Befehl python -m scripts.voice_check --live prüft die vier Anbieter mit minimalem Testinhalt. Beide Tests verursachen reale API-Nutzung.
