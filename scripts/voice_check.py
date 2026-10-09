"""Explicit, bounded live-provider checks. Never prints secrets or provider response bodies."""
import asyncio
import json
import logging
import time
import aiohttp
import httpx
from app.store import SqliteStore
from app.errors import ServiceError
from livekit import api
from app.config import Settings
from app.interview import create_interview, apply_turn
from app.models import AgentConfig, Turn
from voice.extraction import Extractor

async def check(name, operation):
    started=time.perf_counter()
    try:
        details=await asyncio.wait_for(operation(),25)
        return {'provider':name,'ok':True,'seconds':round(time.perf_counter()-started,3),**(details or {})}
    except Exception as exc:
        status=getattr(exc,'status_code',None) or getattr(exc,'status',None)
        return {'provider':name,'ok':False,'error_type':type(exc).__name__,'status':status,'code':getattr(exc,'code',None),
                'seconds':round(time.perf_counter()-started,3)}

async def main(voice_id=None):
    logging.disable(logging.CRITICAL)
    settings=Settings()
    async def reasoning():
        extractor=Extractor(settings.openai_api_key,settings.llm_model)
        try:
            state=create_interview('automated-provider-check',AgentConfig(),'voice')
            text='Unser Startup heißt Lumio. Wir entwickeln SaaS für kleine Unternehmen.'
            extracted,usage=await extractor.extract(text,state)
            apply_turn(state,Turn(id='provider-check',text=text,extraction=extracted))
            assert state.goals['startup_name'].status=='answered'
            assert state.goals['sector'].choice_value=='SaaS'
            return {'structured_tool_valid':True,'next_goal':state.current_goal,**usage}
        finally:
            await extractor.client.close()
    async def transport():
        async with api.LiveKitAPI(settings.livekit_url,settings.livekit_api_key,settings.livekit_api_secret) as client:
            await client.room.list_rooms(api.ListRoomsRequest())
        return {'authenticated':True}
    async def recognition():
        async with aiohttp.ClientSession() as client:
            async with client.ws_connect('wss://api.deepgram.com/v1/listen?model=nova-3&language=de&encoding=linear16&sample_rate=16000&channels=1&mip_opt_out=true',
                                         headers={'Authorization':'Token '+settings.deepgram_api_key}) as ws:
                await ws.send_bytes(bytes(32000))
                await ws.send_json({'type':'CloseStream'})
                async for msg in ws:
                    if msg.type==aiohttp.WSMsgType.TEXT:
                        payload=json.loads(msg.data)
                        if payload.get('type')=='Metadata':
                            return {'stream_authenticated':True}
                        if payload.get('type')=='Error':
                            raise RuntimeError('Provider rejected stream')
                raise RuntimeError('No stream acknowledgement')
    async def speech():
        selected=voice_id
        if not selected and settings.persistence_backend=='sqlite':
            published=SqliteStore(settings.database_path).get('config','published')
            selected=published['config'].get('voice_id') if published else None
        if not selected:
            raise ServiceError('VOICE_ID_MISSING','Configure a voice in the administrator interface.',422)
        async with httpx.AsyncClient(timeout=15) as client:
            async with client.stream('POST',f'https://api.elevenlabs.io/v1/text-to-speech/{selected}/stream',
                headers={'xi-api-key':settings.elevenlabs_api_key},
                json={'text':'Hallo, bereit für unser Gespräch?', 'model_id':'eleven_flash_v2_5','language_code':'de'}) as response:
                if not response.is_success:
                    body=json.loads(await response.aread())
                    detail=body.get('detail',{})
                    code=detail.get('status','VOICE_PROVIDER_ERROR') if isinstance(detail,dict) else 'VOICE_PROVIDER_ERROR'
                    # Only an allowlisted code, never provider bodies or credentials.
                    allowed={'api_key_id_used_as_api_key','invalid_api_key','missing_permissions','quota_exceeded','voice_not_found','paid_plan_required'}
                    raise ServiceError(code if code in allowed else 'VOICE_PROVIDER_ERROR','Voice provider rejected request.',response.status_code)
                chunks=0;size=0
                async for chunk in response.aiter_bytes():
                    size+=len(chunk);chunks+=1
                if not size:raise RuntimeError('Empty speech')
                return {'audio_bytes':size,'received_chunks':chunks}
    results=await asyncio.gather(check('OpenAI',reasoning),check('LiveKit',transport),check('Deepgram',recognition),check('ElevenLabs',speech))
    print(json.dumps(results,indent=2))

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true',help='Allow small billable provider requests using .env')
    parser.add_argument('--voice-id',help='Optional public voice ID for the test')
    args=parser.parse_args()
    if not args.live:
        parser.error('--live is required: requests can incur provider charges')
    asyncio.run(main(args.voice_id))
