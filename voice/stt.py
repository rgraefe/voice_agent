"""Provider selection behind LiveKit's common streaming STT interface."""
from livekit.agents import stt
from livekit.plugins import deepgram, elevenlabs

from app.config import Settings


def create_stt(settings: Settings, *, language: str) -> stt.STT:
    """Create a session-owned recognizer; never silently switch providers on failure."""
    if language not in ('de', 'en'):
        raise ValueError('Unsupported interview language')
    if settings.stt_provider == 'deepgram':
        if not settings.deepgram_api_key.strip():
            raise ValueError('DEEPGRAM_API_KEY is required for Deepgram STT')
        return deepgram.STT(
            api_key=settings.deepgram_api_key, model='nova-3', language=language,
            interim_results=True, smart_format=True, mip_opt_out=True,
        )
    # Both plugins normalize provider-specific events to LiveKit's streaming STT interface.
    if settings.stt_provider == 'elevenlabs':
        key = settings.elevenlabs_stt_api_key or settings.elevenlabs_api_key
        if not key.strip():
            raise ValueError('ELEVENLABS_API_KEY or ELEVENLABS_STT_API_KEY is required for ElevenLabs STT')
        return elevenlabs.STT(
            api_key=key, model='scribe_v2_realtime', language_code=language,
            enable_logging=False, no_verbatim=False,
            # AgentSession receives continuous audio. Server VAD commits final
            # transcripts without requiring our controller to flush the stream.
            # LiveKit's local turn detector still decides when to answer.
            server_vad={'vad_silence_threshold_secs': 0.5, 'min_silence_duration_ms': 500},
        )
    raise ValueError('Unsupported STT provider')
