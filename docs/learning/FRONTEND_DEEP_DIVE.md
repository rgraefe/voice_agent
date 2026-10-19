# Frontend code deep dive

The frontend is a React application written in TypeScript. It owns user interaction and browser audio resources. It displays the backend's interview decisions; it does not independently decide which answers are sufficient or calculate investment fit.

Read the files in this order: `package.json` and `vite.config.ts`, `src/api.ts`, `src/main.tsx`, `src/App.tsx` in sections, `src/MicrophoneTest.tsx`, `src/GoalEditor.tsx`, `src/InterviewReport.tsx`, then `src/style.css` and `e2e/`.

## 1. Build and entry point

[package.json](../../frontend/package.json) declares React, LiveKit's browser SDK and UI icons. `npm run build` first type-checks with TypeScript, then builds with Vite. `npm ci` uses the package lock; `npm run dev` starts Vite. A separate API process is still required.

[vite.config.ts](../../frontend/vite.config.ts) enables the React plugin and proxies `/api` to port 8000 during development. It places LiveKit in a separate build chunk. A separate chunk is not the same as lazy-loading it: App imports LiveKit statically. The large-chunk warning is a performance consideration, not a failed build.

[index.html](../../frontend/index.html) contains the root element and module entry. [main.tsx](../../frontend/src/main.tsx) mounts App with `createRoot` and imports global CSS. `StrictMode` helps expose unsafe effects during development by exercising setup and cleanup. It is not authentication or error handling.

The production API serves `frontend/dist`; changing TSX does not update that built output until you rebuild. Vite development mode updates source changes interactively. This explains why a browser refresh alone is sometimes insufficient.

Run `npm run format` from `frontend/` to format all TypeScript and TSX source files, or `npm run format:check` to check formatting. The project uses Prettier with an 80-column target; long strings can still exceed it.

## 2. Shared contracts and HTTP

Read [api.ts](../../frontend/src/api.ts) before JSX.

`Config`, `Interview`, `Goal`, `GoalState`, `MatchRule`, `Bootstrap` and `Report` describe what the frontend expects from the backend. Types make editor mistakes visible, but disappear at runtime. `api<Report>()` does not validate a server response against the Report type. This is an important difference from Pydantic on the Python side.

`api<T>()` prefixes `/api`, includes same-origin cookies and sends the custom request header expected by the server. Failed HTTP responses become JavaScript Errors using the safe server message. The current helper discards structured error codes and retryability; more nuanced recovery could preserve them later.

`statusLabel` is a display mapping, not a state machine. `date()` formats stored timestamps for the German UI. `Record<string, GoalState>` means a lookup object indexed by goal key. Optional chaining (`current?.id`) and nullish coalescing (`value ?? fallback`) distinguish absent values from valid falsy values such as zero.

Interview exercise: follow one error from Python `ServiceError` to JSON, `api()`, `perform()` and finally an alert banner.

## 3. App.tsx state ownership

[App.tsx](../../frontend/src/App.tsx) currently combines orchestration and page rendering. Read the hooks and handlers first, then the JSX. Prettier formats the JSX and statements across readable lines. Extracting page components is a reasonable next refactor, not a feature already implemented.

| State | Meaning | Authority |
| --- | --- | --- |
| `boot` | User role, public agent details, configuration readiness | Backend |
| `current` | Selected interview including progress and transcript | Backend snapshot |
| `config` | Editable admin draft | Local until published |
| `history` | Visible conversations | Backend, filtered by identity |
| `page` | Current view | Browser only; no routing library |
| `connection` | Browser room connection status | LiveKit |
| `agentReady` | Agent participant has joined | LiveKit |
| `liveText` | Interim recognition, still subject to revision | LiveKit |
| `busy`, errors, notices | Interaction feedback | Browser |
| Simulation fields | Explicit offline test inputs | Browser |

A render uses a snapshot of state. `setState` schedules a new render; it does not mutate the variables in an already-running callback. This is why long-lived asynchronous listeners need careful lifetime management.

`useRef` holds mutable values without triggering renders: the Room, DOM audio container, timers, connection generation counter and preview object URL. The `currentRef` in this version is assigned but not read elsewhere; it should not be credited with solving stale-state races. It is a cleanup candidate.

### Effects

- Initial bootstrap retrieves public/user state. The invite token is read from the URL fragment and removed from the address bar.
- After login and on page changes, history is fetched; admins also fetch published config. Consequently, navigating can replace an unsaved admin draft. Saving to a file avoids losing a draft, but a dedicated dirty-form warning would be better.
- While a voice connection is active, the saved interview is polled every 1.5 seconds.
- Transcript growth scrolls to the bottom.
- Unmount cleanup disconnects the room, stops preview playback and clears resources.

The polling effect clears its interval, but it does not abort an already-running HTTP request. Connection-generation checks protect setup, not every asynchronous callback. A future hook should add cancellation or generation checks to all session-bound requests.

## 4. Starting, stopping and resetting

`perform()` centralizes busy state and errors around an asynchronous action. It uses `try/catch/finally`, so controls recover after failures. It is not a queue; a single boolean would not accurately count overlapping independent operations.

`login()` posts a demo role, invitation or password, then refreshes bootstrap. Session identity lives in an HttpOnly cookie managed by the browser. There is no need to store the token in localStorage.

`start(mode)` first creates the interview with a fresh random request ID. In simulation mode it returns after creation. Voice mode fetches a scoped room token, constructs a LiveKit Room and installs listeners before connecting.

The browser calls `connect`, `startAudio`, and enables its microphone. After each awaited step it checks `connectionAttempt`. If Stop or Reset changed that counter, the obsolete attempt closes its resources rather than continuing to capture audio.

| LiveKit event | Frontend response |
| --- | --- |
| `ParticipantConnected` | Mark the agent ready, cancel the join timeout |
| `TrackSubscribed` | Attach received audio to the audio container |
| `TrackUnsubscribed` | Remove detached audio elements |
| `ConnectionStateChanged` | Update connection UI |
| `ActiveSpeakersChanged` | Animate speaking state |
| `TranscriptionReceived` | Show non-final text separately |
| `Disconnected` | Clear live state and persist a stop if not intentional |

A connected room does not necessarily contain an agent. The 30-second timeout specifically handles a missing worker. It is not a maximum response timeout for every conversational turn.

`stop()` invalidates setup, stops microphone tracks before persistence requests, disconnects the room and requests the saved terminal state. Stopping local capture must not wait for a slow database. `mute()` toggles track publication through LiveKit.

`resetDemo()` stops an active interview and reloads the page after the server confirms the stop. The reload removes callbacks, draft inputs, selected results and microphone tests. It does not delete history or clear the login cookie. The next start produces a new interview and room. It is displayed only in local-demo mode. A stop error prevents a success-looking reload.

Exercise: say what happens if you press Stop while `getUserMedia` or room connection is still awaiting completion. Then distinguish the protections in App from those in MicrophoneTest.

## 5. Admin configuration and voice preview

The four named voice presets are a convenience mapping to IDs. Their presence does not guarantee language quality or provider entitlement. Manual IDs remain supported.

`set(key, value)` creates an updated draft object. `publish()` sends that draft with its version. The server checks conflicts and increments the published version. Existing interviews retain their snapshots. UI-only restrictions are never a replacement for the server's admin check.

`saveConfig()` validates the current form and downloads a JSON Blob. The browser object URL is temporary and is revoked after use. `loadConfig()` checks file size, parses JSON and asks the API to validate it before replacing the draft. TypeScript's `unknown` is useful here: the file is not trusted just because it has a `.json` extension. Importing does not publish automatically.

The 1 MB import check is in the browser. It is not a server-wide request-size limit. Validation ensures the settings are well-formed, but prompts/questions remain user-controlled content, not executable code.

`preview()` uses `fetch` directly because the response is audio, not JSON. It creates an object URL, instantiates `Audio` and requests playback. Previous previews are paused and revoked. Browser autoplay policies and provider rejection are different error paths. The error now appears next to the preview button. The preview uses unsaved form values; that lets the admin compare settings before publishing.

## 6. MicrophoneTest.tsx

[MicrophoneTest.tsx](../../frontend/src/MicrophoneTest.tsx) is independent of LiveKit and backend storage.

Its states are idle, permission, testing, done and error. `begin()` opens/resumes an AudioContext, requests microphone permission and connects the microphone source to an AnalyserNode. It does not connect the analyser to speakers or a recorder.

Each animation frame reads 1024 floating-point samples and computes RMS:

```text
RMS = square root of the average squared sample amplitude
visual level = min(100, round(RMS × 500))
```

This is a convenient visual scale, not calibrated decibels. RMS above 0.01 latches `heard=true`. Background noise can satisfy that threshold; the test proves input activity, not intelligibility or correct STT.

The generation token changes on stop/unmount. After each awaited operation the code checks it, disposing of a late-granted stream if the test is no longer current. `release()` cancels animation frames and the timer, disconnects the source, stops all tracks and closes the AudioContext. The test times out after 15 seconds once capture begins. The browser permission dialog itself is not covered by that timer.

`role='meter'` and ARIA values expose the measurement to assistive technologies. The status text explains what to do; reduced-motion CSS disables the width transition. Repeating the test creates new resources after the prior resources are closed.

## 7. GoalEditor.tsx

[GoalEditor.tsx](../../frontend/src/GoalEditor.tsx) exports two controlled components. They receive `config` and `onChange`; the parent owns the draft. Updating arrays with `map`, `filter` and spread creates new values instead of mutating the existing React state.

`GoalEditor.update()` replaces one goal by key. `move()` swaps a copied array. Stable goal keys preserve identity even if position changes. Changing a goal type resets fields specific to the old type. Choice text is split into lines; final validation still happens at the server.

The condition selector offers earlier enabled choice goals. Reordering can nevertheless invalidate an existing condition; the server is the final authority. “Remove” is represented by disabling a goal so that keys and historical snapshots remain interpretable. A new goal receives a random key and starts optional.

`MatchEditor` manipulates the profile's rules. Choice rules contain accepted values; number rules contain inclusive bounds. An empty numeric field maps to `null`, not zero. A rule cannot be added twice from the selector, and free-text goals are excluded. No scoring runs in this component.

The non-null assertion in `find(...)!` tells TypeScript to assume a referenced goal exists. It is not a runtime check. Validated persisted data supports the assumption, but transient inconsistent drafts could still need more defensive rendering. Be honest about this distinction in a review.

## 8. InterviewReport.tsx

[InterviewReport.tsx](../../frontend/src/InterviewReport.tsx) requests a backend-derived report when the selected interview, transcript length or status changes. Its effect uses a `live` flag to ignore late responses after cleanup. That guards state updates but does not cancel the network request.

`Gauge` deliberately renders a dash for null. A zero score means known criteria did not match; null means no usable score exists. The conic gradient is visual only. The denominator calculation belongs to `app/analysis.py`.

Search and speaker filters create a filtered display from `report.transcript`. They do not change the stored data. The evidence handler clears filters and defers scrolling until the relevant entry can render, then focuses it. This connects a summary claim to the original recognized contribution.

The report shows three different concepts: match, evidence coverage and completeness. Its word-share bar counts words, not time. Duration includes pauses. Exporting this report produces a derived report JSON; App's interview export calls a separate endpoint containing additional interview fields. Both are useful but not identical file formats.

The effect does not currently clear an earlier report error on a later successful response, and it does not key on every possible revision change. Those are concrete robustness opportunities, not reasons to claim all report state is perfectly synchronized.

## 9. Styling and browser tests

[style.css](../../frontend/src/style.css) defines tokens, navigation, cards, responsive breakpoints, status colors, the voice animation and component-specific panels. CSS classes such as `speaking` reflect React state; they do not measure audio themselves. A visualization of an active speaker is not proof that the user's speakers emitted sound.

Test files in [e2e](../../frontend/e2e) cover different boundaries:

- `app.spec.ts`: workflow tests against an API, using local simulation and known configuration assumptions.
- `voice.live.spec.ts`: opt-in real provider/LiveKit test with synthetic microphone audio; costs may apply.
- `microphone.spec.ts`: mocked audio input for level updates, silence timeout, denial and cleanup.
- `reset.spec.ts`: mocked persistence and UI reset, including server-stop failure and demo-only visibility.

`playwright.microphone.config.ts` runs the mocked microphone/reset suites with its own Vite server. These suites do not require the real API or microphone. The ordinary Playwright configuration assumes an application server is available. Do not run all tests against a demo with valuable configuration and expect no changes: some tests publish config and create conversations.

A successful build proves type-checking and bundling. Mocked tests prove specific UI transitions. Neither proves microphone hardware, natural speech, provider permissions or end-to-end latency.

## 10. Trace one complete feature

For a configuration import: file input → `loadConfig` → JSON parsing → `/admin/config/validate` → backend Pydantic and role checks → local draft → `publish` → version comparison → new published config → new interview snapshot. No existing interview changes.

For a spoken answer: microphone track → LiveKit worker → STT → structured extraction → atomic planner write → streamed TTS. Separately, browser polling updates the transcript and topic cards. The browser never determines answer sufficiency from the displayed transcript.

## Questions to rehearse

1. Why use refs for Room/AudioContext lifetimes and state for visible status?
2. What is a stale closure, and which requests still lack cancellation?
3. Why does an HttpOnly cookie reduce exposure without eliminating XSS risk?
4. Why is `api<Report>()` not runtime validation?
5. Why is stopping a track more urgent than saving an incomplete interview?
6. Why can a voice preview work while a real interview fails?
7. What would you extract from App first? A session hook with explicit lifecycle and cancellation is a strong candidate.
8. Why do we keep scoring and ownership checks on the server?

An accurate answer includes the tradeoff: this structure makes the challenge easy to demonstrate, but App is too concentrated for a larger product. The next step would be separate pages and hooks, generated API types/runtime validation, explicit draft handling, and stronger cancellation tests. None of those require changing the domain planner.
