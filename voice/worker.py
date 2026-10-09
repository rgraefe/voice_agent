"""Run: python -m livekit.agents download-files; python -m voice.worker dev."""
from datetime import datetime, timezone
import asyncio
import json
import logging
import time
from uuid import uuid4

import httpx
from dotenv import load_dotenv
from livekit.agents import Agent, AgentSession, AgentServer, JobContext, cli, llm, room_io, inference
from livekit.plugins import deepgram, elevenlabs, silero

from app.config import Settings
from app.models import Interview, Turn
from voice.extraction import Extractor

load_dotenv()
settings = Settings()
def prewarm(process):
    from livekit.local_inference import init_eot
    init_eot()
    process.userdata['vad'] = silero.VAD.load()


server = AgentServer(setup_fnc=prewarm, num_idle_processes=1, ws_url=settings.livekit_url or None, api_key=settings.livekit_api_key or None,
                     api_secret=settings.livekit_api_secret or None, log_level='WARN')


class Backend:
    def __init__(self, interview_id):
        self.client = httpx.AsyncClient(base_url=settings.backend_url,
            headers={'Authorization': 'Bearer ' + settings.worker_secret}, timeout=8)
        self.prefix = '/api/internal/interviews/' + interview_id

    async def request(self, method, path='', payload=None):
        # Retry identical requests only; backend IDs make writes idempotent.
        for attempt in range(2):
            try:
                response = await self.client.request(method, self.prefix + path, json=payload)
                response.raise_for_status()
                return response.json()
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt:
                    raise
                await asyncio.sleep(0.15)


def spoken_message(item):
    """LiveKit also emits non-message history events such as AgentHandoff."""
    if getattr(item, 'role', None) != 'assistant':
        return None
    return {'id': item.id, 'text': item.text_content or '',
            'timestamp': datetime.fromtimestamp(item.created_at, timezone.utc).isoformat(),
            'interrupted': item.interrupted}


class ControllerModel(llm.LLM):
    """Enable LiveKit's pipeline lifecycle; Interviewer.llm_node owns the single API call."""
    def chat(self, **kwargs):
        raise RuntimeError('Use the interview agent llm_node')


class Interviewer(Agent):
    def __init__(self, state, backend, extractor):
        super().__init__(instructions='Conduct the configured interview. All speech comes from the validated interview controller.')
        self.state, self.backend, self.extractor = state, backend, extractor
        self.failures = 0
        self.pending_turn = None

    async def on_enter(self):
        await self.session.say(self.state.last_reply, allow_interruptions=True)

    async def on_user_turn_completed(self, turn_ctx, new_message):
        self.pending_turn = (new_message.id, new_message.text_content or '')

    async def llm_node(self, chat_ctx, tools, model_settings):
        messages = getattr(chat_ctx, 'items', [])
        latest = next((m for m in reversed(messages) if getattr(m, 'role', None) == 'user'), None)
        if latest is not None:
            turn_id, text = latest.id, latest.text_content or ''
        elif self.pending_turn:
            turn_id, text = self.pending_turn
        else:
            return
        if not text.strip():
            return
        started = time.perf_counter()
        try:
            state = self.state
            if state.status not in ('active', 'review'):
                return
            extraction, usage = await self.extractor.extract(text, state)
            turn = Turn(id=turn_id, text=text, extraction=extraction, timestamp=datetime.fromtimestamp(latest.created_at, timezone.utc) if latest is not None else None)
            self.state = Interview.model_validate(await self.backend.request('POST', '/turns', turn.model_dump(mode='json')))
            self.failures = 0
            # No second LLM roundtrip: publish the canonical next question immediately to streaming TTS.
            controller_seconds = time.perf_counter() - started
            yield self.state.last_reply
            try:
                await self.backend.request('POST', '/metrics', {'id': turn_id + '-llm', 'kind': 'llm',
                    'values': {**usage, 'controller_seconds': controller_seconds}})
            except httpx.HTTPError:
                pass
        except Exception:
            # Do not print exception bodies: providers may include transcript or credentials.
            self.failures += 1
            try:
                await self.backend.request('POST', '/speech', {'id': turn_id, 'role': 'user', 'text': text, 'interrupted': False})
            except httpx.HTTPError:
                pass
            de = self.state.config.language == 'de'
            if self.failures >= 2:
                try:
                    await self.backend.request('POST', '/stop')
                except httpx.HTTPError:
                    pass
                yield ('Die Verbindung ist gerade nicht zuverlässig. Bitte beende das Gespräch und versuche es später erneut.' if de
                       else 'The connection is not reliable right now. Please end the interview and try again later.')
            else:
                yield ('Entschuldige, das konnte ich gerade nicht verarbeiten. Kannst du das bitte noch einmal sagen?' if de
                       else 'Sorry, I could not process that. Could you say it once more?')


@server.rtc_session(agent_name='founder-interviewer')
async def entrypoint(ctx: JobContext):
    interview_id = json.loads(ctx.job.metadata)['interview_id']
    if ctx.room.name != 'interview-' + interview_id:
        raise ValueError('Room/session mismatch')
    backend = Backend(interview_id)
    state = Interview.model_validate(await backend.request('GET'))
    if state.status not in ('active', 'review'):
        await backend.client.aclose()
        return
    cfg = state.config
    extractor = Extractor(settings.openai_api_key, settings.llm_model)
    agent = Interviewer(state, backend, extractor)
    session = AgentSession(
        stt=deepgram.STT(api_key=settings.deepgram_api_key, model='nova-3', language=cfg.language,
                        interim_results=True, smart_format=True, mip_opt_out=True),
        llm=ControllerModel(), vad=ctx.proc.userdata['vad'], turn_detection=inference.TurnDetector(version='v1-mini'),
        tts=elevenlabs.TTS(api_key=settings.elevenlabs_api_key, voice_id=cfg.voice_id, model=cfg.tts_model,
            language=cfg.language, enable_logging=False,
            voice_settings=elevenlabs.VoiceSettings(stability=cfg.stability, similarity_boost=cfg.similarity,
                                                  speed=cfg.speed, style=0, use_speaker_boost=False)),
        min_endpointing_delay=cfg.pause_seconds, max_endpointing_delay=3.0,
        allow_interruptions=True, min_interruption_duration=0.3, min_interruption_words=1,
        resume_false_interruption=True, preemptive_generation=False, use_tts_aligned_transcript=True)
    tasks = set()

    def schedule(coro):
        task = asyncio.create_task(coro)
        tasks.add(task)
        def done(t):
            tasks.discard(t)
            if not t.cancelled() and t.exception():
                logging.getLogger('founder').warning('Background session event could not be persisted')
        task.add_done_callback(done)

    @session.on('conversation_item_added')
    def conversation(event):
        payload = spoken_message(event.item)
        if payload is not None:
            schedule(backend.request('POST', '/speech', payload))

    @session.on('metrics_collected')
    def metrics(event):
        metric = event.metrics
        name = getattr(metric, 'type', '')
        kind = next((k for k in ('tts', 'stt', 'eou', 'llm') if k in name), None)
        if kind:
            fields = ('ttfb', 'duration', 'audio_duration', 'end_of_utterance_delay', 'transcription_delay', 'characters_count')
            values = {k: float(getattr(metric, k)) for k in fields if isinstance(getattr(metric, k, None), (int, float))}
            schedule(backend.request('POST', '/metrics', {'id': uuid4().hex, 'kind': kind, 'values': values}))

    last_user_end = None

    @session.on('user_state_changed')
    def user_state(event):
        nonlocal last_user_end
        if event.old_state == 'speaking' and event.new_state != 'speaking':
            last_user_end = time.perf_counter()

    @session.on('agent_state_changed')
    def agent_state(event):
        nonlocal last_user_end
        if event.new_state == 'speaking' and last_user_end is not None:
            delay = time.perf_counter() - last_user_end
            last_user_end = None
            schedule(backend.request('POST', '/metrics', {'id': uuid4().hex, 'kind': 'latency',
                'values': {'speech_end_to_agent_speaking_seconds': delay}}))

    @session.on('error')
    def error(event):
        schedule(backend.request('POST', '/metrics', {'id': uuid4().hex, 'kind': 'error', 'values': {'count': 1}}))

    async def watchdog():
        deadline = time.monotonic() + cfg.max_minutes * 60
        while True:
            await asyncio.sleep(2)
            try:
                current = await backend.request('GET')
                if current['status'] in ('completed', 'incomplete') or time.monotonic() > deadline:
                    if current['status'] == 'completed':
                        await asyncio.sleep(5)  # allow the short closing audio to finish
                    await session.aclose()
                    await backend.request('POST', '/stop')
                    ctx.shutdown(reason='interview finished')
                    return
            except httpx.HTTPError:
                await session.aclose()
                ctx.shutdown(reason='backend unavailable')
                return

    async def shutdown():
        monitor.cancel()
        await session.aclose()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        try:
            await backend.request('POST', '/stop')
        finally:
            await backend.client.aclose()
            await extractor.client.close()

    await ctx.connect()
    await ctx.wait_for_participant(identity=state.owner)
    await session.start(agent=agent, room=ctx.room, record=False, room_options=room_io.RoomOptions(
        participant_identity=state.owner, text_input=False, video_input=False, delete_room_on_close=True))
    monitor = asyncio.create_task(watchdog())
    ctx.add_shutdown_callback(shutdown)


if __name__ == '__main__':
    cli.run_app(server)
