# Startup Interview – Project Instructions

## Mission
Build a browser-based startup interview voice agent with two interfaces: administrator configuration and founder interviews/history. Prioritize natural German speech, uninterrupted streaming, reliable turn taking, and measured end-of-speech to first-audio latency (target under two seconds).

## Architecture
- React + TypeScript frontend.
- FastAPI + Pydantic backend with structured errors and server-side authorization.
- LiveKit WebRTC and Python Agents worker; streaming Deepgram STT, OpenAI text LLM, ElevenLabs Flash/Turbo TTS.
- Firestore for deployed persistence; a durable local store for development is acceptable.
- Keep interview state and persistence independent of voice providers. No Dialogflow, customer service domain, or avatar in the initial scope.
- API and static frontend can run on Cloud Run. Voice workers run separately.

## Interview contract
Cover startup/sector, team, product/development, traction, market/competition, funding/round/use of funds, and next steps. Capture information offered out of order. Define concrete answer goals with sufficiency criteria, required/optional status, conditional applicability, and a configurable bounded clarification budget (default one per goal). Ask targeted questions only for missing goals; preserve partial answers when the budget is exhausted. Never fabricate evidence or financial figures. Store evidence references with extracted facts. Corrections replace outdated facts.

Use deterministic code for topic progression, clarification limits, ownership, validation, and persistence. The LLM interprets and phrases dialogue. Snapshot configuration per interview. A successful write must be confirmed by the backend before reporting success. Ending microphone capture must be immediate; incomplete interviews remain available.

Match scores must be deterministic against the versioned, administrator-configured target profile. Keep match, evidence coverage, and interview completeness separate. Unknown answers do not equal a negative match; show unknown/not-applicable criteria and scoring evidence. Never infer personal characteristics or score voice/accent. Preserve original transcripts, chronology, interruptions, and evidence links.

## Security and operations
Never commit secrets or log transcripts/credentials. Use server environment variables/Secret Manager. Browser receives only short-lived room-scoped access. Admin and founder rights must be enforced server-side. Worker callbacks require authentication. Production must fail closed without configured credentials. Include timeout/error handling and idempotent writes. Default to no stored raw audio.

## UI
Admin: name, language, tone, questions, voice and supported settings, versioned publishing, test conversations, history/results.
Founder: microphone check, start/mute/stop, clear connection/speaking state, transcript, own timestamped history, structured results and open points. Clearly label any offline simulation; never present it as real voice AI.

## Working style and validation
Inspect before changes. Prefer small coherent modules. Remove obsolete ServicePilot files when replacing their responsibilities; preserve the supplied challenge PDF. Do not create subagents unless the user explicitly asks. Test features and meaningful failure paths: invalid inputs, unauthorized access, timeouts/provider failures, retries/duplicates, interrupted speech, vague answers, corrections, partial conversations, and persistence. Keep architecture, setup, API contracts, and test instructions current. Report unverified live-provider behavior honestly.
