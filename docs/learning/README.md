# Code study path for the interview

This study pack explains the implementation in this repository, including its limitations. Read with the source open next to it. You should be able to trace an answer from the browser to durable storage and back to spoken output, and explain which component is responsible when it goes wrong.

## Recommended order

| Pass | Read | What to understand | Suggested time |
| --- | --- | --- | --- |
| 1 | This page, then the diagrams in the backend guide | Three processes and their boundaries | 20 min |
| 2 | `app/goals.py`, `app/models.py`, `app/errors.py` | Configuration, observations, state, evidence | 45–60 min |
| 3 | `app/planner.py`, `app/interview.py`, `app/analysis.py` | Deterministic conversation and scoring | 60–90 min |
| 4 | `app/store.py`, `app/config.py`, `app/auth.py` | Atomic writes, settings, identity | 45–60 min |
| 5 | `app/main.py`, `app/providers.py` | Trace a request through authorization and persistence | 60 min |
| 6 | `voice/stt.py`, `voice/extraction.py`, `voice/worker.py` | Streaming, extraction, turn taking and cleanup | 60–90 min |
| 7 | `frontend/src/api.ts`, `main.tsx`, `App.tsx` | Data contracts, React state, browser connection | 60–90 min |
| 8 | `MicrophoneTest.tsx`, `GoalEditor.tsx`, `InterviewReport.tsx` | Audio lifetime, editing, reports | 45–60 min |
| 9 | Tests, build and deployment files | What is proved and what remains a live test | 45 min |

These are study estimates, not an expectation to memorize every line. Start with the pure domain code, not the large `app/main.py` or `App.tsx` orchestration files.

## Separate walkthroughs

- [Backend and voice deep dive](APP_DEEP_DIVE.md)
- [Frontend deep dive](FRONTEND_DEEP_DIVE.md)

Each walkthrough includes function responsibilities, execution traces, language concepts and interview questions. Relative links open the actual source files.

## Executable Python lessons

1. [Data contracts and validation](01_contracts.ipynb)
2. [Conversation state and scoring](02_conversation.ipynb)
3. [Persistence, retries and identity](03_persistence.ipynb)

Use the repository Python environment as your notebook kernel. The examples use fictional data, pure domain functions and temporary SQLite files. They do not read `.env`, invoke providers, start servers, or modify existing interviews. Do not import `app.main` casually in a notebook: its module-level `app = create_app()` initializes storage using the configured environment.

Jupyter is not installed in the current project environment. To use notebooks interactively, install the optional learning tools yourself from the repository root:

```powershell
.venv/Scripts/python -m pip install jupyterlab ipykernel
.venv/Scripts/python -m jupyter lab docs/learning
```

Alternatively open the notebooks in VS Code with its Jupyter extension and select `.venv/Scripts/python.exe`. The notebook code cells were checked by executing them in order in ordinary Python; that is not a browser or interactive-kernel test. Clear outputs and run all cells to repeat a lesson. Re-running a single state-mutating cell may intentionally encounter idempotency rules; restart the lesson to reset its state.

## A two-minute explanation to rehearse

“The browser handles microphone capture and plays streamed audio over LiveKit. A separate Python worker performs speech recognition and makes one structured language-model call per turn. The model proposes evidenced answers. The API validates those answers and a deterministic planner decides the next question. Only after saving that result does the worker speak it. Configuration is frozen per interview. Match scoring is deterministic, and missing information is shown separately from a negative match.”

Then qualify the claim: schema and quote validation do not prove semantic correctness. The system still needs real speech tests, especially for names, interruptions and pauses.

## Prove your understanding without notes

- Draw the path for one spoken answer and label each network boundary.
- Explain why the browser has a room token but no ElevenLabs or OpenAI key.
- Explain what happens if a save succeeds but its HTTP response is lost.
- Give an example of unknown versus inapplicable versus unmatched.
- Explain why the report may appear after the audio starts: durable state is polled every 1.5 seconds.
- Explain why choosing a new voice is different from changing the STT provider.
- Name three limitations you would address next and the evidence that would justify them.

Do not claim that the prototype has a proven sub-two-second p95, complete conversational repair, transactional external side effects, or production deployment verification. See the deep dives for the precise boundaries.
