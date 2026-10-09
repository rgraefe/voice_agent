# Architektur und Entscheidungen

## Datenfluss

React Browser <-> LiveKit WebRTC <-> Python Agents Worker <-> Deepgram Streaming STT / OpenAI Text-LLM / ElevenLabs Streaming TTS.
React und Worker sprechen mit FastAPI. Die API hält Konfigurationsversionen, Gesprächszustand, Transkript und Ergebnisse in SQLite (lokal) bzw. Firestore (Cloud).

Der Browser erhält ein kurzlebiges Token für genau einen Raum, eine Identität und die Mikrofonquelle. Er kann keine Geschäftsdaten über LiveKit-Datenpakete verändern. Die Zuordnung des Workers zum Interview erfolgt über vertrauenswürdige Room-Dispatch-Metadaten; der Worker prüft den Raumnamen und bindet die erlaubte Founder-Identität. Intern benötigt jede API-Anfrage das Worker-Geheimnis.

## Schnelle Sprachstrecke

Eine dauerhafte WebRTC-Verbindung, Deepgram-Zwischentranskripte, lokales Silero VAD, lokaler LiveKit v1-mini Turn Detector und kontinuierliche TTS-Ausgabe. Unterbrechungen sind erlaubt; kurze Rückmeldungen werden durch Mindestsprechdauer/-wortzahl und Wiederaufnahme bei Fehlunterbrechung abgefedert. Kein Avatar, keine sequenzielle Audio-Datei-Konvertierung und kein Dialogflow.

Pro User-Turn ein begrenzter OpenAI-Tool-Aufruf (`record_interview_observations`) für belegte Fakten, deren Qualität und eine kurze natürliche Reaktion. Die API entscheidet deterministisch, ob eine Frage, die einzige Rückfrage, eine Zusammenfassung oder der Abschluss folgt. Der Worker reicht diesen Text direkt an Streaming-TTS weiter. Es gibt keinen zweiten Modellaufruf für die nächste Frage. Der Text wird derzeit erst nach vollständiger validierter Tool-Antwort ausgegeben; Audio wird gestreamt. Der Trade-off ist ein kontrollierterer, etwas stärker redaktionell geführter Dialog. Die individuelle Tonalität wirkt auf die generierte Reaktion, die festen Fragen werden im Admin-Bereich redaktionell gestaltet.

Preemptive generation ist bewusst aus: Spekulative Tool-Aufrufe dürfen keinen Interviewzustand vor dem tatsächlichen Gesprächsende verändern. Ziel unter zwei Sekunden, aber noch kein echter Anbieter-Benchmark. Ein Modelltimeout beträgt sieben Sekunden; diese Fehlerfälle sind kein Latenz-Erfolg.

## Zustand und Konsistenz

Neue Interviews verwenden `planner_version=2`: bis zu 40 konkrete Antwortziele mit Frage, Rückfrage, Antwortkriterium, Pflichtstatus, Typ (Text/Auswahl/Zahl), Einheit und optionaler Bedingung. Bedingungen referenzieren frühere Auswahlziele; Zyklen sind ausgeschlossen. Der Controller priorisiert offene Pflichtziele, überspringt beantwortete oder nicht relevante Ziele und begrenzt Rückfragen pro Ziel (0–3, Standard 1). Teilantworten bleiben nach ausgeschöpftem Budget erhalten. Ungeklärte Bedingungen sind unbekannt, nicht automatisch „nicht relevant“. Korrekturen können in der Abschlussprüfung neue Fragen aktivieren.

Die KI liefert pro betroffenem Ziel Status, Wert, exaktes Zitat und ggf. kanonischen Auswahl-/Zahlenwert. Code validiert Schlüssel, Typen und exakte Zitatbelege, entscheidet über nächste Frage und Speicherung. Die semantische Korrektheit einer Zusammenfassung oder Kategorie bleibt eine Modellleistung; Zitatprüfung allein verhindert nicht jede Fehlinterpretation. Im Bericht sind Originalbelege zugänglich. Eine ausdrückliche Abschlussbestätigung ist erforderlich; neue Angaben im Bestätigungsturn erzwingen eine erneute Prüfung. Historische Interviews behalten den bisherigen Themencontroller (Version 1).

Das Match-Profil wird mit der Konfiguration beim Gesprächsstart gespeichert. Standardmäßig enthält es keine Präferenzen. Auswahlkriterien und inklusive Zahlenintervalle ergeben deterministisch Treffer oder Nichttreffer mit Gewichten 1–10. Match = 100 × Treffergewicht / bewertbares Gewicht; Abdeckung = 100 × bewertbares Gewicht / relevantes Gewicht. Unbekannte und partielle Angaben zählen nur bei der Abdeckung, nicht als negativer Treffer. Nicht relevante Kriterien entfallen. Ohne bewertbare Kriterien ist der Score null. Vollständigkeit zählt separat vollständig beantwortete relevante Pflichtziele. Kein Modellaufruf zur Bewertung, keine Bewertung von Stimme oder persönlichen Eigenschaften.

Assistant-Transkript wird aus LiveKits gesprochenem/aliniertem Conversation-Event gespeichert, nicht beim Generieren des Textes. Unterbrochene Fragen werden als unvollständig markiert und verbrauchen beim nächsten Turn keine zusätzliche Rückfrage. Die genaue Audio-/Text-Ausrichtung muss mit echten Stimmen getestet werden.

SQLite nutzt BEGIN IMMEDIATE, Firestore echte Transaktionen. Ganze Sitzungen sind für diese begrenzten Erstgespräche atomare Dokumente, limitiert auf 200 User-Turns (100 im historischen Controller) und 850 KB serialisierten Inhalt; bei größerer Skalierung in geordnete Turn-Subcollections aufteilen. Listen sind aktuell für kleine Deployments ausgelegt und liefern maximal 100 Ergebnisse; serverseitige Pagination/Retention ist ein nächster Produktionsschritt.

## Fehler und Sicherheit

HttpOnly/SameSite-Cookies, feste erlaubte Origin plus CSRF-Header, serverseitige Rollen- und Ownership-Prüfung, expirierende signierte Founder-Einladungen, persistente Anmeldebegrenzung und validierte Konfigurationen. Produktionsmodus verweigert Start ohne sichere getrennte Geheimnisse, HTTPS-Origin und Firestore. Lokale passwortlose Vorschau existiert nur bei direktem Loopback-Zugriff ohne gesetztes Admin-Passwort.

Bei wiederholter Extraktions-/Backendstörung wird der Verlauf nicht erfunden und das Gespräch unvollständig beendet. Mikrofonstopp ist browserseitig unabhängig vom Backend. Worker überwacht Status und Dauer und schließt die Sitzung. Keine stillschweigende Umschaltung auf simulierte Sprache. Tokenzugriffe und Sprache benötigen echte Anbieterzugänge.

## Messung und Kosten

Gespeichert werden LLM-Tokenverbrauch und Controller-Laufzeit, STT-/TTS-/EOU-Metriken sowie Worker-Zeit von erkanntem Sprechende bis Agent-Sprechbeginn. Dieser letzte Wert ist ein Proxy, keine Messung des tatsächlichen ersten hörbaren Samples im Browser. Browser-Audio-Latenz mit realen Geräten separat messen. Keine erfundenen Dollarwerte: zur Kostenbewertung Verbrauch mit den zum Testzeitpunkt gültigen Anbieterraten und LiveKit-Transport/Worker-Kosten multiplizieren.

## Bewusst später

HeyGen, Websuche, automatische Investitionsentscheidungen, CRM, SSO, Wiederaufnahme abgebrochener Voice-Sitzungen und automatisierte Datenlöschfristen. Es gibt keine Investmentzusage und keine automatische Entscheidung über eine Finanzierung.
