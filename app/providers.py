import asyncio
import json
from datetime import timedelta
import httpx
from app.errors import ServiceError


async def room_access(settings, item):
    from livekit import api
    token = (api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
             .with_identity(item.owner).with_name("Founder")
             .with_ttl(timedelta(minutes=5))
             .with_grants(api.VideoGrants(room_join=True, room="interview-" + item.id,
                                        can_publish=True, can_subscribe=True, can_publish_data=False,
                                        can_publish_sources=["microphone"]))
             .with_room_config(api.RoomConfiguration(agents=[api.RoomAgentDispatch(
                 agent_name="founder-interviewer", metadata=json.dumps({"interview_id": item.id}) )])))
    return {"url": settings.livekit_url, "token": token.to_jwt()}


async def close_room(settings, interview_id):
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


async def voice_preview(settings, config):
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
                    code = detail.get('status') if isinstance(detail, dict) else None
                except (ValueError, AttributeError):
                    code = None
                messages = {
                    'api_key_id_used_as_api_key': 'In ELEVENLABS_API_KEY steht die Key-ID. Bitte den geheimen API-Schlüssel aus der Schlüsselerstellung eintragen.',
                    'invalid_api_key': 'Der ElevenLabs-API-Schlüssel ist ungültig. Bitte den gespeicherten Schlüssel prüfen.',
                    'missing_permissions': 'Dem ElevenLabs-Schlüssel fehlt eine Berechtigung. Bitte Text to Speech freigeben.',
                    'quota_exceeded': 'Das ElevenLabs-Kontingent oder das gesetzte Kreditlimit ist ausgeschöpft.',
                    'voice_not_found': 'Diese Voice-ID ist für deinen ElevenLabs-Zugang nicht verfügbar.',
                    'paid_plan_required': 'ElevenLabs verlangt für diese Stimme oder Funktion einen kostenpflichtigen Tarif. Bitte eine verfügbare Standardstimme wählen.',
                }
                if code in messages:
                    raise ServiceError('VOICE_CONFIGURATION_ERROR', messages[code], 422)
                response.raise_for_status()
            return response.content
    except httpx.TimeoutException:
        raise ServiceError("VOICE_TIMEOUT", "Die Hörprobe hat zu lange gedauert. Bitte erneut versuchen.", 504, True)
    except httpx.HTTPError:
        raise ServiceError("VOICE_PROVIDER_ERROR", "Die Hörprobe konnte nicht geladen werden. Zugang und Stimme prüfen.", 502, True)
