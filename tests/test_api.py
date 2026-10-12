from __future__ import annotations
from pathlib import Path
from fastapi import FastAPI
import jwt
import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from conftest import login, start


def test_unauthorized_and_role_separation(client: TestClient) -> None:
    assert client.get('/api/interviews').status_code == 401
    login(client)
    assert client.get('/api/admin/config').status_code == 403
    assert client.post('/api/admin/invites').status_code == 403


def test_founder_cannot_read_or_stop_another_founder_session(client: TestClient, app: FastAPI) -> None:
    interview = start(client)
    with TestClient(app, headers={'X-Requested-With': 'founder-app'}) as other:
        other.cookies.set('founder_session', app.state.auth.token('other-founder', 'founder'))
        assert other.get('/api/interviews').json() == []
        assert other.get('/api/interviews/'+interview['id']).status_code == 404
        assert other.post('/api/interviews/'+interview['id']+'/stop').status_code == 404
        assert other.get('/api/interviews/'+interview['id']+'/export').status_code == 404


def test_worker_requires_secret(client: TestClient) -> None:
    interview = start(client)
    assert client.get('/api/internal/interviews/'+interview['id']).status_code == 401
    assert client.get('/api/internal/interviews/'+interview['id'], headers={'Authorization':'Bearer '+'w'*40}).status_code == 200


def test_create_idempotency_and_validation(client: TestClient) -> None:
    interview = start(client)
    duplicate = client.post('/api/interviews', json={'mode':'simulation','request_id':'test-request-123'})
    assert duplicate.json()['id'] == interview['id']
    assert len(client.get('/api/interviews').json()) == 1
    assert client.post('/api/interviews', json={'mode':'invalid','request_id':'valid-request'}).status_code == 422


def test_config_snapshot_and_compare_and_swap(client: TestClient) -> None:
    interview = start(client)
    login(client, 'admin')
    cfg = client.get('/api/admin/config').json()
    cfg['name'] = 'Nova'
    published = client.put('/api/admin/config', json=cfg)
    assert published.status_code == 200
    assert published.json()['version'] == 2
    assert client.put('/api/admin/config', json=cfg).status_code == 409
    old = client.get('/api/interviews/'+interview['id']).json()
    assert old['config']['name'] == 'Mira'
    assert old['config']['version'] == 1


def test_config_file_validates_without_publishing_and_rebases_version(client: TestClient) -> None:
    login(client,'admin')
    original=client.get('/api/admin/config').json()
    imported={**original,'name':'Geladener Agent','version':987}
    result=client.post('/api/admin/config/validate',json=imported)
    assert result.status_code==200
    draft=result.json()
    assert draft=={**imported,'version':original['version']}
    assert client.get('/api/admin/config').json()==original
    assert client.put('/api/admin/config',json=draft).status_code==200
    # Re-importing an older file uses the current publish version.
    assert client.post('/api/admin/config/validate',json=original).json()['version']==2


def test_config_file_rejects_invalid_and_unauthorized_imports(client: TestClient) -> None:
    from app.models import AgentConfig
    cfg=AgentConfig().model_dump()
    assert client.post('/api/admin/config/validate',json=cfg).status_code==401
    login(client)
    assert client.post('/api/admin/config/validate',json=cfg).status_code==403
    login(client,'admin')
    for data in [{}, {**cfg,'speed':99}, {**cfg,'api_key':'must-not-import'}, {**cfg,'goals':[]}]:
        assert client.post('/api/admin/config/validate',json=data).status_code==422
    assert client.get('/api/admin/config').json()['version']==1


def test_voice_not_silently_simulated(client: TestClient) -> None:
    login(client)
    r = client.post('/api/interviews', json={'mode':'voice','request_id':'voice-request'})
    assert r.status_code == 503
    assert r.json()['error']['code'] == 'VOICE_NOT_CONFIGURED'


def test_simulation_history_export_stop(client: TestClient) -> None:
    interview = start(client)
    base = '/api/interviews/'+interview['id']
    r = client.post(base+'/simulation-turn', json={'id':'answer1','text':'Acme baut Software.','clear':True})
    assert r.status_code == 200
    assert r.json()['current_goal'] == 'sector'
    assert len(r.json()['transcript']) == 3
    assert client.get(base+'/export').json()['analysis']['goals'][0]['value'] == 'Acme baut Software.'
    assert client.post(base+'/stop').json()['status'] == 'incomplete'
    assert client.post(base+'/simulation-turn', json={'id':'answer2','text':'No'}).status_code == 409


def test_csrf_and_foreign_origin(client: TestClient) -> None:
    assert client.post('/api/login', json={'demo_role':'admin'}, headers={'X-Requested-With':''}).status_code == 403
    assert client.post('/api/login', json={'demo_role':'admin'}, headers={'Origin':'https://evil.example'}).status_code == 403


def test_error_response_does_not_echo_sensitive_input(client: TestClient) -> None:
    r = client.post('/api/login', json={'password':['sensitive-secret']})
    assert r.status_code == 422
    assert 'sensitive-secret' not in r.text


def test_invite_login_and_invalid_role_token(client: TestClient, app: FastAPI) -> None:
    login(client, 'admin')
    link = client.post('/api/admin/invites').json()['url']
    token = link.split('#invite=')[1]
    assert client.post('/api/login', json={'invite':token}).json()['role'] == 'founder'
    assert client.get('/api/admin/config').status_code == 403
    invalid = app.state.auth.token('test', 'admin')
    assert client.post('/api/login', json={'invite':invalid}).status_code == 401


def test_production_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        Settings(_env_file=None, environment='production')


def test_persistence_survives_restart(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, database_path=str(tmp_path/'durable.db'),session_secret='s'*40)
    app1 = create_app(settings)
    with TestClient(app1, headers={'X-Requested-With':'founder-app'}) as c:
        interview=start(c)
    app2 = create_app(settings)
    with TestClient(app2, headers={'X-Requested-With':'founder-app'}) as c:
        login(c)
        assert c.get('/api/interviews/'+interview['id']).status_code == 200


def test_worker_invalid_evidence_rolls_back_atomically(client: TestClient) -> None:
    interview=start(client)
    headers={'Authorization':'Bearer '+'w'*40}
    r=client.post('/api/internal/interviews/'+interview['id']+'/turns',headers=headers,json={
        'id':'bad','text':'Acme','extraction':{'answers':[{'goal_key':'startup_name','value':'Acme','quote':'Acme','status':'answered'},
        {'goal_key':'team','value':'invented','quote':'not said','status':'answered'}]}})
    assert r.status_code == 422
    stored=client.get('/api/interviews/'+interview['id']).json()
    assert stored['topics']['startup']['value'] is None
    assert len(stored['transcript']) == 1


def test_duplicate_simulation_request_does_not_answer_next_topic(client: TestClient) -> None:
    interview=start(client)
    path='/api/interviews/'+interview['id']+'/simulation-turn'
    body={'id':'same','text':'Acme baut Software.','clear':True}
    first=client.post(path,json=body).json()
    second=client.post(path,json=body)
    assert second.status_code==200
    assert second.json()==first
    assert client.post(path,json={**body,'text':'Different'}).status_code==409


def test_interrupted_question_does_not_use_extra_clarification(client: TestClient) -> None:
    interview=start(client)
    worker='/api/internal/interviews/'+interview['id']
    headers={'Authorization':'Bearer '+'w'*40}
    assert client.post(worker+'/speech',headers=headers,json={'id':'cut-off','text':'Wie heißt','interrupted':True}).status_code==200
    response=client.post(worker+'/turns',headers=headers,json={'id':'interrupt','text':'Einen Moment bitte','extraction':{}})
    assert response.status_code==200
    result=response.json()
    assert result['goals']['startup_name']['followups_used'] == 0
    assert result['current_topic']=='startup'
    assert result['last_reply']==result['config']['goals'][0]['question']
