"""Offline contracts against the installed SDK; no billable provider requests."""
import pytest
from pydantic import ValidationError
from livekit.agents import stt
from livekit.plugins import deepgram, elevenlabs

from app.config import Settings
from voice.stt import create_stt


def settings(**overrides):
    return Settings(_env_file=None, **{
        'stt_provider': 'deepgram', 'deepgram_api_key': 'test-deepgram',
        'elevenlabs_api_key': 'test-shared', 'elevenlabs_stt_api_key': '',
        'livekit_url': 'wss://example.invalid', 'livekit_api_key': 'test',
        'livekit_api_secret': 'test', 'worker_secret': 'test', 'openai_api_key': 'test',
        **overrides,
    })


@pytest.mark.asyncio
@pytest.mark.parametrize('provider,expected', [('deepgram', deepgram.STT), ('elevenlabs', elevenlabs.STT)])
@pytest.mark.parametrize('language', ['de', 'en'])
async def test_factory_returns_common_streaming_interface(provider, expected, language):
    recognizer = create_stt(settings(stt_provider=provider), language=language)
    try:
        assert isinstance(recognizer, stt.STT)
        assert isinstance(recognizer, expected)
        assert recognizer.capabilities.streaming
        assert recognizer.capabilities.interim_results
        # Check real plugin configuration: batch mode/manual-only commits would stall interviews.
        if provider == 'elevenlabs':
            assert recognizer._opts.model_id == 'scribe_v2_realtime'
            assert recognizer._opts.language_code == language
            assert recognizer._opts.server_vad['vad_silence_threshold_secs'] == 0.5
            assert recognizer._opts.enable_logging is False
        else:
            assert recognizer._opts.model == 'nova-3'
            assert recognizer._opts.language == language
    finally:
        await recognizer.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize('separate,expected', [('', 'test-shared'), ('test-separate', 'test-separate')])
async def test_elevenlabs_shared_or_dedicated_key(separate, expected):
    cfg = settings(stt_provider='elevenlabs', elevenlabs_stt_api_key=separate, deepgram_api_key='')
    recognizer = create_stt(cfg, language='de')
    try:
        assert recognizer._opts.api_key == expected
        assert cfg.missing_voice() == []
    finally:
        await recognizer.aclose()


def test_readiness_requires_selected_provider_and_tts_credentials():
    assert settings(deepgram_api_key='').missing_voice() == ['DEEPGRAM_API_KEY']
    assert settings(stt_provider='elevenlabs', deepgram_api_key='').missing_voice() == []
    # A separate STT key does not replace the key needed for voice output.
    assert settings(stt_provider='elevenlabs', elevenlabs_api_key='',
                    elevenlabs_stt_api_key='test-stt').missing_voice() == ['ELEVENLABS_API_KEY']


@pytest.mark.parametrize('provider', ['deepgram', 'elevenlabs'])
def test_missing_key_fails_without_fallback(provider):
    cfg = settings(stt_provider=provider, deepgram_api_key='', elevenlabs_api_key='', elevenlabs_stt_api_key='')
    with pytest.raises(ValueError, match='API_KEY'):
        create_stt(cfg, language='de')


def test_unknown_provider_and_language_rejected():
    with pytest.raises(ValidationError):
        settings(stt_provider='unknown')
    with pytest.raises(ValueError, match='language'):
        create_stt(settings(), language='unknown')


def test_provider_selected_from_environment(monkeypatch):
    monkeypatch.setenv('STT_PROVIDER', 'elevenlabs')
    assert Settings(_env_file=None).stt_provider == 'elevenlabs'
