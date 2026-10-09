# Umsetzungsstand

Implementiert: React Startup- und Admin-Oberflächen; FastAPI-API; lokale dauerhafte Speicherung und Firestore-Adapter; Konfigurationsversionen; sichere Founder-Einladungen; Gesprächszustand und Belege; strukturierter Export; LiveKit-WebRTC-Client; Python Voice Worker mit Deepgram, OpenAI-Tool-Extraktion, ElevenLabs, VAD und Turn Detector; Mute/Stop; Hörprobe; Fehlerbehandlung und Regressionstests; getrennte Containerdefinitionen.

Für die manuelle Abnahme noch erforderlich: ein Gespräch mit echtem Mikrofon/Headset, subjektiver Stimmenvergleich und mehrere Latenzmessungen. Anbieterzugänge, Standard-Teststimme und lokaler Worker sind eingerichtet. Cloud-Deployment und Firestore-Livetests benötigen ein Zielprojekt. HeyGen ist bewusst nachgelagert.

Erweitert am 9. Oktober 2026: konfigurierbare Antwortziele, bedingte Fragen, Pflicht-/optionale Angaben, begrenzte Rückfragen, versioniertes Match-Profil, gewichteter Score mit Belegabdeckung, Ergebnisgrafiken und durchsuchbares Transkript mit TXT-/JSON-Export.

Aktuell geprüft: 42 Python-Tests, fünf Edge-Browser-Tests und TypeScript-/Vite-Build. Desktop- und mobile Ergebnisansichten visuell geprüft. Beide Dockerimages und lokale Sprachaktivitäts-/Gesprächsende-Modelle wurden bereits vor dieser Erweiterung geprüft; die Images müssen für die neue Version neu gebaut werden. Inzwischen wurden reale Anbieter mit synthetischem Testinhalt geprüft; siehe LIVE_TEST_REPORT.md.

Live-Integration: neues Tool-Schema ohne Legacy-Felder für Antwortziel-Interviews; robuste Behandlung von LiveKit-AgentHandoff-Ereignissen; verständliche ElevenLabs-Konfigurationsfehler und opt-in Verbindungstests. Aktuell 48 Python-Regressionstests erfolgreich.
