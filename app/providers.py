from __future__ import annotations
from app.config import Settings
from app.models import AgentConfig, Interview
import asyncio
import json
from datetime import timedelta
import httpx
from app.errors import ServiceError


# Grant access to one interview room and microphone publication only; provider secrets stay on the server.
async def room_access(settings: Settings, interview: Interview) -> dict[str, str]:
    from livekit import api
    token = (api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
             .with_identity(interview.owner).with_name("Founder")
             .with_ttl(timedelta(minutes=5))
             .with_grants(api.VideoGrants(room_join=True, room="interview-" + interview.id,
                                        can_publish=True, can_subscribe=True, can_publish_data=False,
                                        can_publish_sources=["microphone"]))
             .with_room_config(api.RoomConfiguration(agents=[api.RoomAgentDispatch(
                 agent_name="founder-interviewer", metadata=json.dumps({"interview_id": interview.id}) )])))
    return {"url": settings.livekit_url, "token": token.to_jwt()}


async def close_room(settings: Settings, interview_id: str) -> bool:
    if not settings.livekit_api_key:
        return False
    from livekit import api
    try:
        async with api.LiveKitAPI(settings.livekit_url, settings.livekit_api_key, settings.livekit_api_secret) as client:
            await asyncio.wait_for(client.room.delete_room(api.DeleteRoomRequest(room="interview-" + interview_id)), 5)
        return True
    except Exception:
        # Browser stops its microphone independently; worker also checks persistent status.
        return False


async def voice_preview(settings: Settings, config: AgentConfig) -> bytes:
    if not settings.elevenlabs_api_key or not config.voice_id:
        raise ServiceError("VOICE_NOT_CONFIGURED", "ElevenLabs-Zugang und Voice-ID fehlen.", 503)
    text = (f"Hallo, ich bin {config.name}. Erzähl mir von deinem Startup. Was möchtet ihr verändern?"
            if config.language == "de" else f"Hi, I'm {config.name}. Tell me about your startup. What would you like to change?")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(f"https://api.elevenlabs.io/v1/text-to-speech/{config.voice_id}",
                headers={"xi-api-key": settings.elevenlabs_api_key}, json={"text": text, "model_id": config.tts_model,
                "voice_settings": {"stability": config.stability, "similarity_boost": config.similarity,
                                   "speed": config.speed, "style": 0, "use_speaker_boost": False}})
            if not response.is_success:
                try:
                    detail = response.json().get('detail', {})
                    codes = [detail.get(key) for key in ('code', 'status', 'type')] if isinstance(detail, dict) else []
                except (ValueError, AttributeError):
                    codes = []
                # Translate known provider codes without exposing response bodies or credentials.
                messages = {
                    'api_key_id_used_as_api_key': 'In ELEVENLABS_API_KEY steht die Key-ID. Bitte den geheimen API-Schlüssel aus der Schlüsselerstellung eintragen.',
                    'invalid_api_key': 'Der ElevenLabs-API-Schlüssel ist ungültig. Bitte den gespeicherten Schlüssel prüfen.',
                    'missing_permissions': 'Dem ElevenLabs-Schlüssel fehlt eine Berechtigung. Bitte Text to Speech freigeben.',
                    'quota_exceeded': 'Das ElevenLabs-Kontingent oder das gesetzte Kreditlimit ist ausgeschöpft.',
                    'voice_not_found': 'Diese Voice-ID ist für deinen ElevenLabs-Zugang nicht verfügbar.',
                    'paid_plan_required': 'ElevenLabs verlangt für diese Stimme oder Funktion einen kostenpflichtigen Tarif. Bitte eine verfügbare Standardstimme wählen.',
                }
                messages.update({
                    'payment_required': 'ElevenLabs verlangt eine Zahlung: Bitte prüfen, ob diese Stimme für deinen API-Tarif freigegeben ist und ausreichend Guthaben vorhanden ist.',
                    'free_users_not_allowed': 'Diese Stimme ist über die ElevenLabs-API nicht im kostenlosen Tarif verfügbar. Bitte eine freigegebene Stimme wählen oder den Tarif bei ElevenLabs prüfen.',
                    'invalid_voice_id': 'Die Voice-ID ist ungültig. Bitte nur die ID der Stimme eintragen, keinen Link.',
                    'unsupported_model': 'Das gewählte Sprachmodell wird für diese Anfrage nicht unterstützt. Bitte ein anderes Modell testen.',
                    'invalid_voice_settings': 'ElevenLabs lehnt die Stimmeinstellungen ab. Bitte die Einstellungen prüfen.',
                    'authentication_error': 'ElevenLabs konnte den API-Schlüssel nicht bestätigen. Bitte den gespeicherten Schlüssel prüfen.',
                    'authorization_error': 'Der ElevenLabs-Zugang hat keine Berechtigung für diese Stimme oder Funktion.',
                })
                for code in codes:
                    if isinstance(code, str) and code in messages:
                        raise ServiceError('VOICE_CONFIGURATION_ERROR', messages[code], 422)
                if response.status_code == 402:
                    raise ServiceError('VOICE_CONFIGURATION_ERROR', messages['payment_required'], 422)
                if response.status_code == 429:
                    raise ServiceError('VOICE_RATE_LIMIT', 'ElevenLabs ist gerade ausgelastet oder das Anfragelimit wurde erreicht. Bitte kurz warten und erneut versuchen.', 429, True)
                response.raise_for_status()
            return response.content
    except httpx.TimeoutException:
        raise ServiceError("VOICE_TIMEOUT", "Die Hörprobe hat zu lange gedauert. Bitte erneut versuchen.", 504, True)
    except httpx.HTTPError:
        raise ServiceError("VOICE_PROVIDER_ERROR", "Die Hörprobe konnte nicht geladen werden. Zugang und Stimme prüfen.", 502, True)
