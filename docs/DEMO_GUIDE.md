# Founder Studio – Demo-Guide

Stand: 9. Oktober 2026. Für eine etwa 12–15-minütige Präsentation der Coding Challenge. Alle Startup-Angaben in diesem Guide sind fiktiv.

## 1. Ziel der Demo

Zeige, wie ein Gründer mit dem Agenten spricht, wie der Agent fehlende Angaben gezielt erfragt und wie daraus ein nachvollziehbares Interviewergebnis entsteht. Die Demo umfasst beide Oberflächen: die Konfiguration durch einen Administrator und das Gespräch aus Sicht des Startups.

Möglicher Einstieg:

> „Founder Studio führt ein strukturiertes Erstgespräch mit einem Startup. Als Administrator lege ich fest, was wir erfahren möchten und wann eine Antwort ausreichend ist. Der Gründer kann frei sprechen. Der Agent berücksichtigt bereits genannte Angaben, fragt bei Unklarheiten nach und speichert das Ergebnis mit Belegen aus dem Gespräch.“

## 2. Vorbereitung vor dem Termin

- Browser auf [http://localhost:8000](http://localhost:8000) öffnen; aktuelle Version von Edge oder Chrome verwenden.
- Kopfhörer und das gewünschte Mikrofon anschließen. Mit „Mikrofon testen“ die Browserberechtigung erlauben und kurz sprechen: Der Pegelbalken sollte ausschlagen. Der lokale Test endet nach 15 Sekunden oder mit „Mikrofontest beenden“. Er überträgt und speichert kein Audio.
- API und Voice Worker müssen laufen. Ein geöffneter Browser allein reicht nicht.
- Im Admin-Bereich eine Hörprobe abspielen und danach ein kurzes echtes Gespräch testen. Hörproben und Voice-Gespräche verwenden kostenpflichtige APIs.
- Sprache, Fragen und Stimme prüfen. Die Auswahl „Englisch“ übersetzt vorhandene Fragen nicht automatisch.
- Ein abgeschlossenes Beispielgespräch für die Ergebnisansicht bereithalten. Automatische Voice-Tests sind in der Historie echte Voice-Sitzungen mit synthetischem Inhalt; bei deren Verwendung ausdrücklich darauf hinweisen.
- Für die Demonstration eines Match-Scores vor dem Gespräch ein Beispiel-Zielprofil veröffentlichen. Ohne Kriterien erscheint absichtlich kein Score.
- Während der Präsentation weder `.env` noch API-Schlüssel oder Einladungslinks auf dem geteilten Bildschirm zeigen.

Falls die Umgebung bereits installiert ist, genügen zwei Terminals im Projektverzeichnis. Nicht zusätzlich starten, wenn die Dienste schon laufen.

**Terminal 1 – Web-App und API:**

```powershell
Set-Location "C:/Users/ralf/OneDrive/Dokumente/git/voice_agent"
.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**Terminal 2 – Voice Worker:**

```powershell
Set-Location "C:/Users/ralf/OneDrive/Dokumente/git/voice_agent"
.venv/Scripts/python -m voice.worker start --log-level warn
```

**Anbieterauswahl vor dem Start:** In `.env` legt `STT_PROVIDER=deepgram` (Standard) oder `STT_PROVIDER=elevenlabs` die Spracherkennung fest. Bei ElevenLabs benötigt der gemeinsame `ELEVENLABS_API_KEY` auch „Speech to Text → Access“. Alternativ dafür `ELEVENLABS_STT_API_KEY` setzen. Nach Änderungen beide Dienste neu starten. Die Auswahl erfolgt derzeit nicht im Admin-Interface.

**Beenden:** Zuerst ein laufendes Interview im Browser mit „Stop“ beenden. Anschließend im Worker-Terminal und danach im API-Terminal jeweils **Strg+C** drücken und warten, bis die Eingabeaufforderung zurückkehrt. Das Schließen des Browser-Tabs allein beendet die Dienste nicht. Für einen Neustart dieselben beiden Befehle erneut ausführen. Nicht mehrere Instanzen parallel starten.

Ersteinrichtung und Fehlerdiagnose stehen im [technischen Guide](TECHNICAL_GUIDE.md).

## 3. Ablauf im Überblick

| Zeit | Aktion | Was damit sichtbar wird |
| --- | --- | --- |
| 0–1 Min. | Aufgabe und Produkt kurz vorstellen | Ziel des Erstgesprächs |
| 1–4 Min. | Admin-Oberfläche zeigen | Konfigurierbarkeit, Antwortziele, Zielprofil |
| 4–10 Min. | Als Startup ein Voice-Interview führen | Sprache, Nachfragen, Kontext und Korrekturen |
| 10–13 Min. | Ergebnis, Transkript und Historie öffnen | Strukturierte Ablage, Belege und Score |
| 13–15 Min. | Architektur und Abwägungen erklären | Technische Entscheidungen und Grenzen |

Die Dauer hängt von Sprechtempo und Rückfragen ab. Bei wenig Zeit das Live-Gespräch bewusst vorzeitig beenden und anschließend ein vorbereitetes abgeschlossenes Gespräch öffnen. Einen vorzeitigen Stopp nicht als regulären Abschluss darstellen.

## 4. Admin-Oberfläche demonstrieren

### Anmeldung und Persönlichkeit

Bei lokaler Entwicklung ohne Admin-Passwort: **„Admin-Bereich öffnen“**, dann **„Agent konfigurieren“**. Ist ein Admin-Passwort gesetzt, darüber anmelden. Für einen separaten Founder-Zugang kann der Administrator **„Startup einladen“** verwenden; der Link ist sieben Tage gültig.

Zeige mindestens zwei Einstellungen, beispielsweise Agentname und Tonalität. Zusätzlich sind Sprache, Gesprächsdauer, Voice-ID, Flash-/Turbo-Modell, Stimmstabilität, Stimmähnlichkeit, Tempo und minimale Gesprächspause konfigurierbar.

> „Der Agentname und die technische Voice-ID sind unabhängig. Die Stimme lässt sich austauschen, ohne die Gesprächssteuerung neu zu bauen.“

Die zuletzt live getestete Standardstimme ist George mit `JBFqnCBsd6RMkjVDRZzb`. Sie ist ein technischer Ausgangspunkt; eine subjektive Abnahme ihrer deutschen Aussprache steht noch aus.

### Ein Antwortziel erklären

Unter **„Antwortziele & Gesprächssteuerung“** das Ziel **„Messbare Traktion“** öffnen und zeigen:

- Pflichtangabe oder optional;
- Einstiegsfrage und gezielte Rückfrage;
- Kriterium für eine ausreichende Antwort;
- maximales Rückfragenbudget, standardmäßig eine Rückfrage.

> „Es reicht nicht, dass das Wort Traktion gefallen ist. Hier verlangen wir konkrete Kennzahlen mit Einheit und Zeitraum. Explizit noch keine Kunden oder Umsätze ist ebenfalls eine gültige Antwort. Nach ausgeschöpften Rückfragen bleibt eine Teilantwort sichtbar, statt als vollständig zu gelten.“

Danach **„Kapitalbedarf in EUR“** öffnen: Das Ziel wird nur relevant, wenn **„Finanzierung geplant“ = „Ja“** beantwortet ist. Schon früher genannte Antworten werden berücksichtigt.

### Beispiel-Zielprofil für den Score

Dieses Profil ist ausschließlich eine Demo-Präferenz, keine bereits festgelegte Investmentstrategie.

| Einstellung | Demo-Wert |
| --- | --- |
| Profilname | Demo: SaaS mit MVP |
| Kriterium Sektor | akzeptierte Kategorie **SaaS**, Gewicht **3** |
| Kriterium Entwicklungsphase | akzeptierte Kategorie **MVP**, Gewicht **1** |

Beim Hinzufügen eines Kriteriums gegebenenfalls die automatisch ausgewählte erste Option abwählen. Nur die gewünschten Kategorien aktiviert lassen.

**„Version veröffentlichen“** anklicken. Die veröffentlichte Version gilt für neue Gespräche; bestehende Gespräche behalten ihren ursprünglichen Fragenkatalog und ihr Zielprofil. Demo-Kriterien nach dem Termin bei Bedarf wieder entfernen und erneut veröffentlichen.

## 5. Voice-Interview als Startup

Vor dem Rollenwechsel darf kein Gespräch mehr aktiv sein. Abmelden und lokal **„Zum Startup-Interview“** wählen oder den Founder-Einladungslink in einem separaten Browserprofil öffnen. Tabs desselben Browserprofils teilen sich die Anmeldung.

1. **„Mikrofon testen“** anklicken.
2. **„Interview starten“** anklicken und die Browserberechtigung erteilen.
3. Auf **„Live verbunden“** und die Begrüßung des Agents warten.
4. Frei antworten. Die folgenden Angaben sind ein Spickzettel, kein Text, der am Stück vorgelesen werden muss.

### Fiktives Startup: Lumio

| Antwortziel | Beispielantwort |
| --- | --- |
| Name, Sektor, Problem, Zielkunden | „Unser Startup heißt Lumio, geschrieben L-U-M-I-O. Wir entwickeln SaaS für kleine Unternehmen mit mehreren Standorten. Unsere Software hilft ihnen, unnötigen Energieverbrauch zu erkennen und ihre Stromkosten zu senken.“ |
| Team und Erfahrung | „Wir sind zwei Gründer. Anna entwickelt das Produkt und hat fünf Jahre Erfahrung mit Energiemanagement-Software. Ben verantwortet den Vertrieb und hat zuvor B2B-Kunden in diesem Bereich betreut.“ |
| Produkt und Entwicklungsphase | „Wir haben ein MVP. Kunden können Verbrauchsdaten hochladen, Standorte vergleichen und ungewöhnliche Verbrauchsspitzen sehen. Drei Pilotunternehmen nutzen es bereits.“ |
| Traktion – zunächst absichtlich vage | „Wir bekommen erste positive Rückmeldungen.“ |
| Traktion – nach der Rückfrage | „Im September 2026 hatten wir drei aktive Pilotunternehmen. Die Piloten sind unbezahlt. Wir haben bisher keine zahlenden Kunden und noch keinen Umsatz.“ |
| Wettbewerb und Unterschied | „Die Unternehmen arbeiten bisher überwiegend mit Excel und den Portalen ihrer Energieversorger. Wir führen die Daten mehrerer Standorte zusammen und weisen automatisch auf Auffälligkeiten hin.“ |
| Finanzierung geplant | „Ja, wir planen eine Finanzierungsrunde.“ |
| Betrag und Runde | „Wir möchten 500.000 Euro in einer Pre-Seed-Runde aufnehmen.“ |
| Mittelverwendung | „Wir wollen eine weitere Entwicklerin einstellen, Schnittstellen zu Zählern bauen und die ersten zahlenden Kunden gewinnen.“ |
| Gewünschter nächster Schritt | „Wir wünschen uns ein Folgegespräch mit einer Produktdemo in der nächsten Woche.“ |
| Optionaler Finanzierungszeitplan | „Wir möchten die Runde bis Ende März 2027 abschließen.“ |

Die Reihenfolge kann abweichen: Bereits spontan beantwortete Ziele werden übersprungen; Pflichtziele haben Vorrang vor optionalen Fragen. Wenn der Agent eine klare Angabe dennoch nachfragt, kurz präzisieren und das Verhalten später als Beobachtung besprechen.

### Drei Verhaltensweisen bewusst zeigen

**Nachfragen:** Die vage Traktionsantwort verwenden und anschließend die konkreten Zahlen nennen. Erwartet wird die konfigurierte Rückfrage. Die semantische Einstufung kommt vom Modell und ist kein wortgetreu garantierter Ablauf.

**Unterbrechen:** Einmal während einer Agent-Antwort sagen: „Einen Moment, ich möchte etwas ergänzen.“ Prüfen, ob die Audioausgabe stoppt und die Ergänzung verarbeitet wird. Dieser Punkt ist Teil der manuellen Voice-Abnahme, nicht bereits umfassend durch die synthetischen Tests nachgewiesen.

**Korrigieren:** In der Abschlussprüfung sagen: „Eine Korrektur: Wir benötigen 600.000 Euro statt 500.000 Euro.“ Die Korrektur und die neue Zusammenfassung prüfen. Erst danach ausdrücklich bestätigen: „Ja, die Zusammenfassung stimmt.“

Ein bestätigtes Gespräch bekommt den Status **„Abgeschlossen“**. **„Gespräch beenden“** ist für den vorzeitigen Stopp gedacht und führt bei einem noch offenen Interview zu **„Vorzeitig beendet“**.

## 6. Ergebnis und Historie präsentieren

**„Auswertung & Transkript“** öffnen und drei unterschiedliche Werte erklären:

| Wert | Bedeutung |
| --- | --- |
| Match zum Zielprofil | Gewichteter Anteil passender Kriterien unter den Kriterien mit ausreichender Antwort |
| Bewertbare Kriterien | Wie viel des relevanten Zielprofils durch ausreichende Antworten belegt ist |
| Vollständigkeit | Wie viele relevante Pflichtangaben vollständig beantwortet sind |

Für das Beispielprofil ergibt **SaaS + MVP** einen Match von **100/100**, sofern beide Antworten vollständig erkannt wurden. Bei **SaaS + Prototyp** wären es **75/100**. Ist nur SaaS bekannt und die Phase ungeklärt, kann ebenfalls **100/100 Match** stehen, aber nur **75 % Belegabdeckung**. Deshalb nie nur den Match-Wert zeigen.

> „Der Score sagt, wie gut die Antworten zu unserem Zielprofil passen. Er ist keine allgemeine Bewertung der Startup-Qualität und keine Finanzierungsentscheidung. Fehlende Angaben zählen nicht automatisch als schlechte Antwort.“

Anschließend:

1. Unter **„So entsteht der Match“** ein Kriterium und **„Beleg ansehen“** öffnen.
2. Im Transkript Sprecher und Zeitangaben zeigen; nach einem Begriff suchen und den Sprecherfilter nutzen.
3. Unter **„Antworten & offene Punkte“** ein Ziel aufklappen und Antwortkriterium sowie Originalzitat erklären.
4. **„Transkript als Text“** oder **„Ergebnis herunterladen“** für den Export zeigen.
5. Über **„Gesprächsverlauf“** ein früheres Gespräch mit Datum, Uhrzeit und Status öffnen. Erst das aktuelle Gespräch beenden, bevor ein anderes ausgewählt wird.

Die Wortanteile in der Statistik sind aus dem Transkript berechnet. Sie sind keine Messung der Sprechzeit. Die Anwendung selbst zeichnet kein Roh-Audio auf.

## 7. Technische Erklärung in einer Minute

> „LiveKit verbindet Browser und Voice Worker per WebRTC. Deepgram erkennt die Sprache, OpenAI extrahiert Antworten über einen strukturierten Tool-Aufruf und ElevenLabs erzeugt die gestreamte Sprachausgabe. Die nächste Frage und die Speicherung entscheidet unser Backend. Dadurch bleiben Rückfragenbudget, Bedingungen und Abschlussregeln überprüfbar. Pro Gesprächsbeitrag gibt es einen Modellaufruf; wir vermeiden einen zweiten Aufruf nur zur Formulierung der nächsten Frage.“

Wichtige Abwägung: Die Fragen sind redaktionell konfiguriert. Das bringt Kontrolle und spart einen Modellaufruf, lässt den Dialog aber stärker geführt wirken. **Audio wird gestreamt; die LLM-Tool-Antwort wird vollständig validiert, bevor die Antwort gesprochen wird.**

## 8. Wenn während der Demo etwas nicht funktioniert

| Situation | Vorgehen |
| --- | --- |
| „Interview starten“ ist deaktiviert | Admin-Einstellungen, vorhandene Zugangsdaten und veröffentlichte Voice-ID prüfen. |
| Verbindung entsteht, aber kein Agent kommt | Worker prüfen. Nach dem Timeout die Sitzung beenden und neu starten. |
| Mikrofon wird abgelehnt | Browserberechtigung und ausgewähltes Gerät prüfen; localhost oder HTTPS verwenden. |
| Kein hörbares Audio | Tab stummgeschaltet? Richtiger Audioausgang? Hörprobe im Admin-Bereich testen. |
| Name falsch erkannt | Namen buchstabieren und die Korrektur ausdrücklich sagen. Originaltranskript bleibt erhalten. |
| Provider-Ausfall oder Netzproblem | Live-Versuch beenden, vorbereitetes Ergebnis zeigen oder den **Text-Testlauf** verwenden. |
| Kein Match-Score | Prüfen, ob vor Gesprächsbeginn ein Zielprofil mit Kriterien veröffentlicht wurde. |

Den Text-Testlauf ausdrücklich als Simulation erklären: Er ruft weder Spracherkennung noch LLM noch TTS auf. Antwortziel, Kategorie/Zahlenwert und „vage“ werden dort manuell zugeordnet. Er zeigt Gesprächssteuerung und Ergebnisdarstellung, ist aber kein Ersatznachweis für funktionierende Voice.

## 9. Was sich belastbar sagen lässt

Stand dieser Dokumentation: 48 Python-Tests erfolgreich; fünf reguläre Browser-Tests im vorherigen UI-Prüflauf erfolgreich; zusätzlich ein realer Browser-Voice-Rundlauf mit synthetischem Mikrofon erfolgreich. Dabei wurden reale Anbieter, Audio-Wiedergabe und Speicherung geprüft.

Ein letzter Worker-Messwert lag bei rund **1,4 Sekunden** ab erkanntem Sprechende bis Agent-Sprechbeginn. Das ist ein einzelner Proxy-Messwert, keine Garantie für unter zwei Sekunden am Browser und keine p95-Messung.

Eigennamen wurden in den synthetischen Tests teilweise falsch geschrieben. Natürlichkeit der Stimme, tatsächliche Mikrofone, Denkpausen, Unterbrechungen und hörbare End-to-End-Latenz müssen mit echten Personen geprüft werden. Details: [Live-Testbericht](LIVE_TEST_REPORT.md).

Nach der Präsentation das Gespräch beenden, gegebenenfalls Demo-Präferenzen zurücksetzen und die Dienste in den eigenen Terminals mit `Ctrl+C` stoppen, wenn sie nicht weiter gebraucht werden.

## Demo zurücksetzen

Im lokalen Demo-Modus steht unten auf der Seite „Demo zurücksetzen“. Der Button beendet eine aktive Sitzung, trennt die Audioverbindung und lädt die Oberfläche neu. Dadurch verschwinden das ausgewählte Gespräch, Transkript, Formularentwürfe und laufende Mikrofontests aus der aktuellen Ansicht. Die Anmeldung und veröffentlichte Agent-Konfiguration bleiben erhalten; gespeicherte Gespräche werden nicht gelöscht.

Mit „Interview starten“ bzw. „Text-Testlauf“ beginnt anschließend eine neue Sitzung mit neuer ID und ohne bisherigen Gesprächskontext. Scheitert das Speichern des Gesprächsstopps, wird der Fehler angezeigt und kein erfolgreicher Reset behauptet. Außerhalb des lokalen Demo-Modus ist der Button ausgeblendet.

## Agent-Konfiguration speichern und laden

Unter „Agent konfigurieren“ lädt „Konfiguration speichern“ alle aktuellen Formulareinstellungen als `agent-konfiguration.json` herunter, einschließlich noch nicht veröffentlichter Änderungen. Enthalten sind Fragen, Antwortziele, Zielprofil und Stimmeinstellungen. Server-Zugangsdaten sind nicht Teil dieser Datei.

„Konfiguration laden“ öffnet eine gespeicherte JSON-Datei (maximal 1 MB). Die Einstellungen werden validiert und als Entwurf ins Formular übernommen; bestehende Formularänderungen werden dabei ersetzt. Erst „Version veröffentlichen“ aktiviert den Entwurf für neue Gespräche. Ungültige Dateien verändern die Konfiguration nicht. Mehrere Varianten können unter unterschiedlichen Dateinamen aufbewahrt werden.
