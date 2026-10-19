from __future__ import annotations
from typing import Literal
from typing import Never
from app.types import Document
from app.goals import GoalAnswer
import asyncio
from types import SimpleNamespace
import httpx
import pytest
from fastapi.testclient import TestClient
from livekit.agents import AgentSession
from app.config import Settings
from app.interview import create_interview, apply_turn
from app.models import AgentConfig, Extraction, Interview, Turn
from app.providers import voice_preview, room_access
from voice.worker import Interviewer, ControllerModel, Backend


class FakeBackend:
    def __init__(self) -> None:
        self.state = create_interview('owner',AgentConfig(),'voice')
        self.calls: list[tuple[str, str, Document | None]]=[]
    async def request(self, method: str, path: str='', payload: Document | None=None) -> Document:
        self.calls.append((method,path,payload))
        if path=='/turns':
            apply_turn(self.state,Turn.model_validate(payload))
        if path=='/stop':
            self.state.status='incomplete'
        return self.state.model_dump()


class FakeExtractor:
    async def extract(self,text: str,state: Interview) -> tuple[Extraction, dict[str, float]]:
        return Extraction(answers=[GoalAnswer(goal_key='startup_name',value=text,quote=text,status='answered')]), {'input_tokens':100.0}


def test_names_get_extra_pause_without_slowing_other_answers() -> None:
    from voice.worker import endpointing_delay
    state=create_interview('owner',AgentConfig(),'voice')
    assert endpointing_delay(state)==1.2
    state.current_goal='sector'
    assert endpointing_delay(state)==0.6
    state.current_goal='startup_name'
    state.config.pause_seconds=1.8
    assert endpointing_delay(state)==1.8


@pytest.mark.asyncio
async def test_worker_speaks_only_canonical_persisted_reply() -> None:
    backend=FakeBackend()
    agent=Interviewer(backend.state,backend,FakeExtractor())
    agent.pending_turn=('turn1','Acme baut Software.')
    output=[part async for part in agent.llm_node(None,[],None)]
    assert output==[backend.state.last_reply]
    assert backend.state.current_goal=='sector'
    assert backend.calls[0][1]=='/turns'


@pytest.mark.asyncio
async def test_worker_preserves_question_after_repeated_extraction_failure() -> None:
    class Broken:
        async def extract(self,*args: object) -> Never:
            raise TimeoutError()
    backend=FakeBackend()
    agent=Interviewer(backend.state,backend,Broken())
    agent.pending_turn=('turn1','Acme')
    first=[part async for part in agent.llm_node(None,[],None)]
    from voice.worker import RETRY_MESSAGES
    assert first[0] in RETRY_MESSAGES['de']
    second=[part async for part in agent.llm_node(None,[],None)]
    assert 'Wir bleiben bei dieser Frage' in second[0]
    assert backend.state.status=='active'
    assert backend.state.current_goal=='startup_name'
    assert not any(path=='/stop' for _,path,_ in backend.calls)
    assert not any(path=='/turns' for _,path,_ in backend.calls)
    assert any(path=='/speech' for _,path,_ in backend.calls)


@pytest.mark.parametrize('language', ['de', 'en'])
def test_retry_phrases_rotate_independently_of_failure_streak(language: Literal['de', 'en']) -> None:
    from voice.worker import RETRY_MESSAGES
    backend=FakeBackend()
    backend.state.config.language=language
    agent=Interviewer(backend.state,backend,FakeExtractor())
    phrases=[]
    for _ in range(4):
        agent.failures=0
        phrases.append(agent.retry_message())
    assert set(phrases[:3])==set(RETRY_MESSAGES[language])
    assert phrases[3]==phrases[0]
    assert all(a!=b for a,b in zip(phrases,phrases[1:]))


@pytest.mark.asyncio
async def test_worker_does_not_claim_success_on_failed_write() -> None:
    backend=FakeBackend()
    original=backend.request
    async def failed(method: str,path: str='',payload: Document | None=None) -> Document:
        if path=='/turns':
            raise httpx.ConnectError('offline')
        return await original(method,path,payload)
    setattr(backend, 'request', failed)
    agent=Interviewer(backend.state,backend,FakeExtractor())
    agent.pending_turn=('turn1','Acme')
    result=[part async for part in agent.llm_node(None,[],None)]
    assert 'gespeichert' not in result[0]
    assert backend.state.current_topic=='startup'


@pytest.mark.asyncio
async def test_committed_turn_with_lost_response_is_reconciled() -> None:
    backend = FakeBackend()
    original = backend.request
    async def lost_response(method: str, path: str = '', payload: Document | None = None) -> Document:
        result = await original(method, path, payload)
        if path == '/turns':
            raise httpx.ReadTimeout('private payload')
        return result
    setattr(backend, 'request', lost_response)
    agent = Interviewer(backend.state.model_copy(deep=True), backend, FakeExtractor())
    agent.pending_turn = ('saved-turn', 'Acme')
    result = [part async for part in agent.llm_node(None, [], None)]
    assert result == [backend.state.last_reply]
    assert agent.state.current_goal == 'sector'
    assert agent.failures == 0
    assert sum(path == '/turns' for _, path, _ in backend.calls) == 1


@pytest.mark.asyncio
async def test_validation_failure_then_success_keeps_budget_and_logs_no_secrets(caplog: pytest.LogCaptureFixture) -> None:
    backend = FakeBackend()
    original = backend.request
    async def rejected(method: str, path: str = '', payload: Document | None = None) -> Document:
        if path == '/turns':
            response = httpx.Response(422, text='secret transcript', request=httpx.Request('POST', 'https://example.test'))
            raise httpx.HTTPStatusError('secret credential', request=response.request, response=response)
        return await original(method, path, payload)
    setattr(backend, 'request', rejected)
    agent = Interviewer(backend.state.model_copy(deep=True), backend, FakeExtractor())
    agent.pending_turn = ('rejected-turn', 'Acme')
    before = {key: value.model_copy(deep=True) for key, value in backend.state.goals.items()}
    _ = [part async for part in agent.llm_node(None, [], None)]
    assert backend.state.goals == before
    assert 'category=validation' in caplog.text and 'stage=save_turn' in caplog.text
    assert 'secret' not in caplog.text
    setattr(backend, 'request', original)
    agent.pending_turn = ('new-turn', 'Acme')
    result = [part async for part in agent.llm_node(None, [], None)]
    assert result == [backend.state.last_reply]
    assert agent.failures == 0


@pytest.mark.asyncio
async def test_metrics_failure_never_replays_or_rejects_successful_answer() -> None:
    backend = FakeBackend()
    original = backend.request
    async def failed_metric(method: str, path: str = '', payload: Document | None = None) -> Document:
        if path == '/metrics':
            raise ValueError('private metric response')
        return await original(method, path, payload)
    setattr(backend, 'request', failed_metric)
    agent = Interviewer(backend.state, backend, FakeExtractor())
    agent.pending_turn = ('turn', 'Acme')
    result = [part async for part in agent.llm_node(None, [], None)]
    assert result == [backend.state.last_reply]
    assert agent.failures == 0


@pytest.mark.parametrize('status,retry', [(401, False), (403, False), (404, False), (429, True), (503, True)])
def test_watchdog_only_tolerates_transient_errors(status: int, retry: bool) -> None:
    from voice.diagnostics import transient_backend_error
    response = httpx.Response(status, request=httpx.Request('GET', 'https://example.test'))
    error = httpx.HTTPStatusError('private', request=response.request, response=response)
    assert transient_backend_error(error) == retry


@pytest.mark.asyncio
async def test_livekit_session_uses_custom_pipeline_node() -> None:
    # Exercise the actual installed SDK lifecycle without microphones or paid providers.
    backend=FakeBackend()
    agent=Interviewer(backend.state,backend,FakeExtractor())
    async def no_greeting() -> None:
        pass
    setattr(agent, 'on_enter', no_greeting)
    session: AgentSession[None]=AgentSession(llm=ControllerModel())
    try:
        await session.start(agent=agent)
        await session.run(user_input='Acme baut Software.')
        assert backend.state.current_goal=='sector'
    finally:
        await session.aclose()


@pytest.mark.asyncio
async def test_token_is_room_scoped_microphone_only() -> None:
    import jwt
    settings=Settings(_env_file=None,livekit_api_key='key',livekit_api_secret='x'*40)
    interview=create_interview('owner',AgentConfig(),'voice')
    access=await room_access(settings,interview)
    claims=jwt.decode(access['token'],'x'*40,algorithms=['HS256'])
    assert claims['video']['room']=='interview-'+interview.id
    assert claims['video']['canPublishSources']==['microphone']
    assert claims['video']['canPublishData'] is False
    assert claims['sub']=='owner'


@pytest.mark.asyncio
@pytest.mark.parametrize('failure',['timeout','500'])
async def test_voice_preview_errors_are_structured(monkeypatch: pytest.MonkeyPatch,failure: str) -> None:
    import app.providers as providers
    original=httpx.AsyncClient
    def handler(request: httpx.Request) -> httpx.Response:
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
async def test_voice_preview_configuration_errors_are_actionable(monkeypatch: pytest.MonkeyPatch,code: str,expected: str) -> None:
    import app.providers as providers
    original=httpx.AsyncClient
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400,json={'detail':{'status':code,'message':'private-provider-body'}})
    monkeypatch.setattr(providers.httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handler)))
    from app.errors import ServiceError
    with pytest.raises(ServiceError) as exc:
        await voice_preview(Settings(_env_file=None,elevenlabs_api_key='secret'),AgentConfig(voice_id='abc'))
    assert expected in exc.value.message
    assert exc.value.code=='VOICE_CONFIGURATION_ERROR'
    assert not exc.value.retryable
    assert 'private' not in exc.value.message

def test_non_message_livekit_events_do_not_break_transcript_callback() -> None:
    from voice.worker import spoken_message
    assert spoken_message(SimpleNamespace(type='agent_handoff')) is None
    assert spoken_message(SimpleNamespace(role='user')) is None
    result=spoken_message(SimpleNamespace(role='assistant',id='spoken',text_content='Hallo',created_at=1700000000.0,interrupted=True))
    assert result is not None
    assert result['text']=='Hallo' and result['interrupted']
    assert result['timestamp'].endswith('+00:00')


@pytest.mark.asyncio
@pytest.mark.parametrize('detail,status,expected',[
    ({'code':'paid_plan_required','type':'payment_required'},402,'kostenpflichtigen Tarif'),
    ({'status':'payment_required'},402,'Zahlung'),
    ({'type':'payment_required'},402,'Zahlung'),
    ({'status':'free_users_not_allowed','code':'bad_request'},400,'kostenlosen Tarif'),
    ({'code':'invalid_voice_id'},400,'Voice-ID'),
    ({'status':['invalid']},402,'Zahlung'),
])
async def test_preview_understands_old_and_new_provider_error_formats(monkeypatch: pytest.MonkeyPatch,detail: Document,status: int,expected: str) -> None:
    import app.providers as providers
    from app.errors import ServiceError
    original=httpx.AsyncClient
    detail['message']='private-provider-body'
    monkeypatch.setattr(providers.httpx,'AsyncClient',lambda **kwargs:original(
        transport=httpx.MockTransport(lambda request:httpx.Response(status,json={'detail':detail}))))
    with pytest.raises(ServiceError) as exc:
        await voice_preview(Settings(_env_file=None,elevenlabs_api_key='test-key'),AgentConfig(voice_id='abc'))
    assert exc.value.status==422 and not exc.value.retryable
    assert expected in exc.value.message
    assert 'private' not in exc.value.message
