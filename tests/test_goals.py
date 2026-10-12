from __future__ import annotations
from app.models import Interview
from fastapi.testclient import TestClient
from typing import Literal
from pathlib import Path
from fastapi import FastAPI
from uuid import uuid4
import pytest
from app.models import AgentConfig, Extraction, Turn
from app.goals import GoalAnswer, MatchProfile, MatchRule
from app.interview import create_interview, apply_turn
from app.analysis import analyze
from app.errors import ServiceError


def answer(interview: Interview,key: str,value: str='Belegte Antwort',status: Literal['answered', 'partial', 'unknown']='answered',choice: str | None=None,number: float | None=None) -> Interview:
    return apply_turn(interview,Turn(id=uuid4().hex,text=value,extraction=Extraction(answers=[GoalAnswer(
        goal_key=key,value=value,quote=value,status=status,choice_value=choice,number_value=number)])))


def test_granular_goals_skip_future_answers_and_bound_clarification() -> None:
    interview=create_interview('a',AgentConfig(),'voice')
    answer(interview,'team')
    assert interview.current_goal=='startup_name'
    assert interview.goals['startup_name'].followups_used==1
    answer(interview,'startup_name',status='partial')
    assert interview.current_goal=='sector'
    assert interview.goals['startup_name'].status=='partial'
    assert interview.goals['startup_name'].exhausted
    answer(interview,'sector',choice='SaaS')
    answer(interview,'problem')
    answer(interview,'target_customer')
    assert interview.current_goal=='product'  # team already provided


def test_legal_suffix_is_not_a_complete_company_name() -> None:
    interview=create_interview('a',AgentConfig(),'voice')
    answer(interview,'startup_name','GMBH.')
    assert interview.goals['startup_name'].status=='partial'
    assert interview.current_goal=='startup_name'
    assert 'vollständige Firmenname' in interview.last_reply
    answer(interview,'startup_name','Intergate Consulting & Trade GmbH')
    assert interview.goals['startup_name'].value=='Intergate Consulting & Trade GmbH'
    assert interview.current_goal=='sector'
    answer(interview,'startup_name','GmbH')
    assert interview.goals['startup_name'].value=='Intergate Consulting & Trade GmbH'


def test_name_followup_budget_still_applies() -> None:
    interview=create_interview('a',AgentConfig(),'voice')
    answer(interview,'startup_name','GmbH')
    answer(interview,'startup_name','GmbH')
    assert interview.goals['startup_name'].status=='partial'
    assert interview.goals['startup_name'].exhausted
    assert interview.current_goal=='sector'


def test_conditions_unknown_is_not_not_applicable_and_correction_reactivates() -> None:
    cfg=AgentConfig()
    keys={'fundraising','funding_amount','next_step'}
    cfg.goals=[g for g in cfg.goals if g.key in keys]
    interview=create_interview('a',cfg,'voice')
    answer(interview,'fundraising',status='unknown')
    report=analyze(interview)
    assert next(g for g in report['goals'] if g['key']=='funding_amount')['status']=='blocked'
    answer(interview,'next_step')
    assert interview.status=='review'
    answer(interview,'fundraising',choice='Nein')
    assert interview.status=='review'
    assert analyze(interview)['completeness']==100
    answer(interview,'fundraising',choice='Ja')
    assert interview.current_goal=='funding_amount'
    answer(interview,'funding_amount',value='500000 EUR',number=500000)
    assert interview.status=='review'
    apply_turn(interview,Turn(id='confirm',text='Ja, stimmt.',extraction=Extraction(confirmed_summary=True)))
    assert interview.status=='completed'


def test_match_weighted_known_denominator_and_unknown_coverage() -> None:
    cfg=AgentConfig(match_profile=MatchProfile(rules=[
        MatchRule(goal_key='sector',weight=3,operator='one_of',accepted=['SaaS']),
        MatchRule(goal_key='stage',weight=1,operator='one_of',accepted=['MVP']),
        MatchRule(goal_key='funding_amount',weight=4,operator='range',minimum=500000,maximum=1000000)]))
    interview=create_interview('a',cfg,'voice')
    assert analyze(interview)['score'] is None
    answer(interview,'sector',choice='SaaS')
    answer(interview,'stage',choice='Idee')
    report=analyze(interview)
    assert report['score']==75
    assert report['coverage']==50
    answer(interview,'fundraising',choice='Ja')
    answer(interview,'funding_amount',value='500000 EUR',number=500000)
    report=analyze(interview)
    assert report['score']==88 and report['coverage']==100
    answer(interview,'fundraising',choice='Nein')
    report=analyze(interview)
    assert report['score']==75 and report['coverage']==100
    assert report['rules'][2]['status']=='not_applicable'
    answer(interview,'sector',status='unknown')
    assert analyze(interview)['score']==0
    assert analyze(interview)['coverage']==25


def test_empty_profile_no_invented_score_and_optional_not_in_completeness() -> None:
    cfg=AgentConfig();cfg.goals=cfg.goals[:2];cfg.goals[1].required=False
    interview=create_interview('a',cfg,'voice');answer(interview,'startup_name')
    report=analyze(interview)
    assert report['score'] is None and not report['configured']
    assert report['completeness']==100


def test_validation_atomic_evidence_and_typed_answers() -> None:
    interview=create_interview('a',AgentConfig(),'voice')
    before=interview.model_dump()
    with pytest.raises(ServiceError):
        apply_turn(interview,Turn(id='invalid',text='Acme',extraction=Extraction(answers=[
            GoalAnswer(goal_key='startup_name',value='Acme',quote='Acme',status='answered'),
            GoalAnswer(goal_key='team',value='Invented',quote='not said',status='answered')])) )
    assert interview.model_dump()==before
    with pytest.raises(ServiceError):
        answer(interview,'sector',choice='Invented')
    with pytest.raises(ServiceError):
        answer(interview,'funding_amount')


def test_no_followup_budget_and_duplicate_turn() -> None:
    cfg=AgentConfig();cfg.goals[0].max_followups=0
    interview=create_interview('a',cfg,'voice')
    turn=Turn(id='one',text='Keine Antwort',extraction=Extraction())
    apply_turn(interview,turn)
    assert interview.current_goal=='sector'
    assert interview.goals['startup_name'].status=='unknown'
    before=interview.model_dump();apply_turn(interview,turn);assert interview.model_dump()==before


def test_config_rejects_cycles_bad_types_and_nan() -> None:
    cfg=AgentConfig().model_dump()
    cfg['goals'][0]['condition']={'goal_key':'sector','equals':'SaaS'}
    with pytest.raises(ValueError): AgentConfig.model_validate(cfg)
    with pytest.raises(ValueError): GoalAnswer(goal_key='funding_amount',value='NaN',quote='NaN',status='answered',number_value=float('nan'))
    with pytest.raises(ValueError): AgentConfig(match_profile=MatchProfile(rules=[MatchRule(goal_key='team',operator='one_of',accepted=['yes'])]))


def test_report_authorization_transcript_and_config_snapshot(client: TestClient,app: FastAPI) -> None:
    from conftest import start,login
    from fastapi.testclient import TestClient
    interview=start(client);base='/api/interviews/'+interview['id']
    headers={'Authorization':'Bearer '+'w'*40}
    payload={'id':'speech','text':'Original speech','timestamp':'2026-01-01T12:00:00+00:00','interrupted':True}
    assert client.post('/api/internal/interviews/'+interview['id']+'/speech',json=payload,headers=headers).status_code==200
    client.post('/api/internal/interviews/'+interview['id']+'/speech',json={**payload,'timestamp':'2026-01-01T13:00:00+00:00'},headers=headers)
    report=client.get(base+'/analysis').json()
    assert report['transcript'][0]['timestamp']=='2026-01-01T12:00:00+00:00'
    assert report['statistics']['interruptions']==1
    assert sum(t['id']=='speech' for t in report['transcript'])==1
    login(client,'admin');cfg=client.get('/api/admin/config').json()
    cfg['match_profile']['rules']=[{'goal_key':'sector','operator':'one_of','accepted':['SaaS'],'weight':1}]
    assert client.put('/api/admin/config',json=cfg).status_code==200
    assert not client.get(base+'/analysis').json()['configured']
    with TestClient(app) as other:
        other.cookies.set('founder_session',app.state.auth.token('other','founder'))
        assert other.get(base+'/analysis').status_code==404

def test_correction_cannot_exceed_used_followup_budget() -> None:
    interview=create_interview('a',AgentConfig(),'voice')
    answer(interview,'startup_name',status='partial')
    answer(interview,'startup_name')
    assert interview.goals['startup_name'].followups_used==1
    answer(interview,'startup_name',status='partial')
    assert interview.goals['startup_name'].exhausted
    assert interview.goals['startup_name'].followups_used==1
    assert interview.current_goal!='startup_name'
