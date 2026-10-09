from app.goals import GoalAnswer
import asyncio
from types import SimpleNamespace
import httpx
import pytest
from fastapi.testclient import TestClient
from livekit.agents import AgentSession
from app.config import Settings
from app.interview import create_interview, apply_turn
from app.models import AgentConfig, Extraction, Observation, Interview, Turn
from app.providers import voice_preview, room_access
from voice.worker import Interviewer, ControllerModel, Backend


class FakeBackend:
    def __init__(self):
        self.state = create_interview('owner',AgentConfig(),'voice')
        self.calls=[]
    async def request(self, method, path='', payload=None):
        self.calls.append((method,path,payload))
        if path=='/turns':
            apply_turn(self.state,Turn.model_validate(payload))
        if path=='/stop':
            self.state.status='incomplete'
        return self.state.model_dump()


class FakeExtractor:
    async def extract(self,text,state):
        return Extraction(answers=[GoalAnswer(goal_key='startup_name',value=text,quote=text,status='answered')]), {'input_tokens':100.0}


@pytest.mark.asyncio
async def test_worker_speaks_only_canonical_persisted_reply():
    backend=FakeBackend()
    agent=Interviewer(backend.state,backend,FakeExtractor())
    agent.pending_turn=('turn1','Acme baut Software.')
    output=[part async for part in agent.llm_node(None,[],None)]
    assert output==[backend.state.last_reply]
    assert backend.state.current_goal=='sector'
    assert backend.calls[0][1]=='/turns'


@pytest.mark.asyncio
async def test_worker_closes_after_repeated_extraction_failure():
    class Broken:
        async def extract(self,*args):
            raise TimeoutError()
    backend=FakeBackend()
    agent=Interviewer(backend.state,backend,Broken())
    agent.pending_turn=('turn1','Acme')
    first=[part async for part in agent.llm_node(None,[],None)]
    assert 'noch einmal' in first[0]
    second=[part async for part in agent.llm_node(None,[],None)]
    assert 'nicht zuverlässig' in second[0]
    assert backend.state.status=='incomplete'
    assert not any(path=='/turns' for _,path,_ in backend.calls)
    assert any(path=='/speech' for _,path,_ in backend.calls)


@pytest.mark.asyncio
async def test_worker_does_not_claim_success_on_failed_write():
    backend=FakeBackend()
    original=backend.request
    async def failed(method,path='',payload=None):
        if path=='/turns':
            raise httpx.ConnectError('offline')
        return await original(method,path,payload)
    backend.request=failed
    agent=Interviewer(backend.state,backend,FakeExtractor())
    agent.pending_turn=('turn1','Acme')
    result=[part async for part in agent.llm_node(None,[],None)]
    assert 'gespeichert' not in result[0]
    assert backend.state.current_topic=='startup'


@pytest.mark.asyncio
async def test_livekit_session_uses_custom_pipeline_node():
    # Exercise the actual installed SDK lifecycle without microphones or paid providers.
    backend=FakeBackend()
    agent=Interviewer(backend.state,backend,FakeExtractor())
    async def no_greeting():
        pass
    agent.on_enter=no_greeting
    session=AgentSession(llm=ControllerModel())
    try:
        await session.start(agent=agent)
        await session.run(user_input='Acme baut Software.')
        assert backend.state.current_goal=='sector'
    finally:
        await session.aclose()


@pytest.mark.asyncio
async def test_token_is_room_scoped_microphone_only():
    import jwt
    settings=Settings(_env_file=None,livekit_api_key='key',livekit_api_secret='x'*40)
    item=create_interview('owner',AgentConfig(),'voice')
    access=await room_access(settings,item)
    claims=jwt.decode(access['token'],'x'*40,algorithms=['HS256'])
    assert claims['video']['room']=='interview-'+item.id
    assert claims['video']['canPublishSources']==['microphone']
    assert claims['video']['canPublishData'] is False
    assert claims['sub']=='owner'


@pytest.mark.asyncio
@pytest.mark.parametrize('failure',['timeout','500'])
async def test_voice_preview_errors_are_structured(monkeypatch,failure):
    import app.providers as providers
    original=httpx.AsyncClient
    def handler(request):
        if failure=='timeout':
            raise httpx.ReadTimeout('private transcript',request=request)
        return httpx.Response(500,text='private credential')
    monkeypatch.setattr(providers.httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handler)))
    from app.errors import ServiceError
    with pytest.raises(ServiceError) as exc:
        await voice_preview(Settings(_env_file=None,elevenlabs_api_key='secret'),AgentConfig(voice_id='abc'))
    assert exc.value.status in (502,504)
    assert exc.value.retryable
    assert 'private' not in exc.value.message

@pytest.mark.asyncio
@pytest.mark.parametrize('code,expected',[
    ('api_key_id_used_as_api_key','Key-ID'),
    ('missing_permissions','Text to Speech'),
    ('quota_exceeded','Kreditlimit'),
    ('voice_not_found','Voice-ID'),
])
async def test_voice_preview_configuration_errors_are_actionable(monkeypatch,code,expected):
    import app.providers as providers
    original=httpx.AsyncClient
    def handler(request):
        return httpx.Response(400,json={'detail':{'status':code,'message':'private-provider-body'}})
    monkeypatch.setattr(providers.httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handler)))
    from app.errors import ServiceError
    with pytest.raises(ServiceError) as exc:
        await voice_preview(Settings(_env_file=None,elevenlabs_api_key='secret'),AgentConfig(voice_id='abc'))
    assert expected in exc.value.message
    assert exc.value.code=='VOICE_CONFIGURATION_ERROR'
    assert not exc.value.retryable
    assert 'private' not in exc.value.message

def test_non_message_livekit_events_do_not_break_transcript_callback():
    from voice.worker import spoken_message
    assert spoken_message(SimpleNamespace(type='agent_handoff')) is None
    assert spoken_message(SimpleNamespace(role='user')) is None
    result=spoken_message(SimpleNamespace(role='assistant',id='spoken',text_content='Hallo',created_at=1700000000.0,interrupted=True))
    assert result['text']=='Hallo' and result['interrupted']
    assert result['timestamp'].endswith('+00:00')
