from uuid import uuid4
import pytest
from app.models import AgentConfig, Extraction, Turn
from app.goals import GoalAnswer, MatchProfile, MatchRule
from app.interview import create_interview, apply_turn
from app.analysis import analyze
from app.errors import ServiceError


def answer(item,key,value='Belegte Antwort',status='answered',choice=None,number=None):
    return apply_turn(item,Turn(id=uuid4().hex,text=value,extraction=Extraction(answers=[GoalAnswer(
        goal_key=key,value=value,quote=value,status=status,choice_value=choice,number_value=number)])))


def test_granular_goals_skip_future_answers_and_bound_clarification():
    item=create_interview('a',AgentConfig(),'voice')
    answer(item,'team')
    assert item.current_goal=='startup_name'
    assert item.goals['startup_name'].followups_used==1
    answer(item,'startup_name',status='partial')
    assert item.current_goal=='sector'
    assert item.goals['startup_name'].status=='partial'
    assert item.goals['startup_name'].exhausted
    answer(item,'sector',choice='SaaS')
    answer(item,'problem')
    answer(item,'target_customer')
    assert item.current_goal=='product'  # team already provided


def test_legal_suffix_is_not_a_complete_company_name():
    item=create_interview('a',AgentConfig(),'voice')
    answer(item,'startup_name','GMBH.')
    assert item.goals['startup_name'].status=='partial'
    assert item.current_goal=='startup_name'
    assert 'vollständige Firmenname' in item.last_reply
    answer(item,'startup_name','Intergate Consulting & Trade GmbH')
    assert item.goals['startup_name'].value=='Intergate Consulting & Trade GmbH'
    assert item.current_goal=='sector'
    answer(item,'startup_name','GmbH')
    assert item.goals['startup_name'].value=='Intergate Consulting & Trade GmbH'


def test_name_followup_budget_still_applies():
    item=create_interview('a',AgentConfig(),'voice')
    answer(item,'startup_name','GmbH')
    answer(item,'startup_name','GmbH')
    assert item.goals['startup_name'].status=='partial'
    assert item.goals['startup_name'].exhausted
    assert item.current_goal=='sector'


def test_conditions_unknown_is_not_not_applicable_and_correction_reactivates():
    cfg=AgentConfig()
    keys={'fundraising','funding_amount','next_step'}
    cfg.goals=[g for g in cfg.goals if g.key in keys]
    item=create_interview('a',cfg,'voice')
    answer(item,'fundraising',status='unknown')
    report=analyze(item)
    assert next(g for g in report['goals'] if g['key']=='funding_amount')['status']=='blocked'
    answer(item,'next_step')
    assert item.status=='review'
    answer(item,'fundraising',choice='Nein')
    assert item.status=='review'
    assert analyze(item)['completeness']==100
    answer(item,'fundraising',choice='Ja')
    assert item.current_goal=='funding_amount'
    answer(item,'funding_amount',value='500000 EUR',number=500000)
    assert item.status=='review'
    apply_turn(item,Turn(id='confirm',text='Ja, stimmt.',extraction=Extraction(confirmed_summary=True)))
    assert item.status=='completed'


def test_match_weighted_known_denominator_and_unknown_coverage():
    cfg=AgentConfig(match_profile=MatchProfile(rules=[
        MatchRule(goal_key='sector',weight=3,operator='one_of',accepted=['SaaS']),
        MatchRule(goal_key='stage',weight=1,operator='one_of',accepted=['MVP']),
        MatchRule(goal_key='funding_amount',weight=4,operator='range',minimum=500000,maximum=1000000)]))
    item=create_interview('a',cfg,'voice')
    assert analyze(item)['score'] is None
    answer(item,'sector',choice='SaaS')
    answer(item,'stage',choice='Idee')
    report=analyze(item)
    assert report['score']==75
    assert report['coverage']==50
    answer(item,'fundraising',choice='Ja')
    answer(item,'funding_amount',value='500000 EUR',number=500000)
    report=analyze(item)
    assert report['score']==88 and report['coverage']==100
    answer(item,'fundraising',choice='Nein')
    report=analyze(item)
    assert report['score']==75 and report['coverage']==100
    assert report['rules'][2]['status']=='not_applicable'
    answer(item,'sector',status='unknown')
    assert analyze(item)['score']==0
    assert analyze(item)['coverage']==25


def test_empty_profile_no_invented_score_and_optional_not_in_completeness():
    cfg=AgentConfig();cfg.goals=cfg.goals[:2];cfg.goals[1].required=False
    item=create_interview('a',cfg,'voice');answer(item,'startup_name')
    report=analyze(item)
    assert report['score'] is None and not report['configured']
    assert report['completeness']==100


def test_validation_atomic_evidence_and_typed_answers():
    item=create_interview('a',AgentConfig(),'voice')
    before=item.model_dump()
    with pytest.raises(ServiceError):
        apply_turn(item,Turn(id='invalid',text='Acme',extraction=Extraction(answers=[
            GoalAnswer(goal_key='startup_name',value='Acme',quote='Acme',status='answered'),
            GoalAnswer(goal_key='team',value='Invented',quote='not said',status='answered')])) )
    assert item.model_dump()==before
    with pytest.raises(ServiceError):
        answer(item,'sector',choice='Invented')
    with pytest.raises(ServiceError):
        answer(item,'funding_amount')


def test_no_followup_budget_and_duplicate_turn():
    cfg=AgentConfig();cfg.goals[0].max_followups=0
    item=create_interview('a',cfg,'voice')
    turn=Turn(id='one',text='Keine Antwort',extraction=Extraction())
    apply_turn(item,turn)
    assert item.current_goal=='sector'
    assert item.goals['startup_name'].status=='unknown'
    before=item.model_dump();apply_turn(item,turn);assert item.model_dump()==before


def test_config_rejects_cycles_bad_types_and_nan():
    cfg=AgentConfig().model_dump()
    cfg['goals'][0]['condition']={'goal_key':'sector','equals':'SaaS'}
    with pytest.raises(ValueError): AgentConfig.model_validate(cfg)
    with pytest.raises(ValueError): GoalAnswer(goal_key='funding_amount',value='NaN',quote='NaN',status='answered',number_value=float('nan'))
    with pytest.raises(ValueError): AgentConfig(match_profile=MatchProfile(rules=[MatchRule(goal_key='team',operator='one_of',accepted=['yes'])]))


def test_report_authorization_transcript_and_config_snapshot(client,app):
    from conftest import start,login
    from fastapi.testclient import TestClient
    item=start(client);base='/api/interviews/'+item['id']
    headers={'Authorization':'Bearer '+'w'*40}
    payload={'id':'speech','text':'Original speech','timestamp':'2026-01-01T12:00:00+00:00','interrupted':True}
    assert client.post('/api/internal/interviews/'+item['id']+'/speech',json=payload,headers=headers).status_code==200
    client.post('/api/internal/interviews/'+item['id']+'/speech',json={**payload,'timestamp':'2026-01-01T13:00:00+00:00'},headers=headers)
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

def test_correction_cannot_exceed_used_followup_budget():
    item=create_interview('a',AgentConfig(),'voice')
    answer(item,'startup_name',status='partial')
    answer(item,'startup_name')
    assert item.goals['startup_name'].followups_used==1
    answer(item,'startup_name',status='partial')
    assert item.goals['startup_name'].exhausted
    assert item.goals['startup_name'].followups_used==1
    assert item.current_goal!='startup_name'


def test_legacy_config_migration_preserves_history_once(tmp_path):
    from app.config import Settings
    from app.store import SqliteStore
    from app.main import create_app
    from app.interview import create_legacy_interview
    from app.models import Interview
    path=str(tmp_path/'migration.db')
    cfg=AgentConfig().model_dump();cfg.pop('goals');cfg.pop('match_profile')
    store=SqliteStore(path);store.update('config','published',lambda _: {'config':cfg,'versions':[]})
    legacy=create_legacy_interview('owner',AgentConfig(),'voice').model_dump()
    for field in ('planner_version','goals','current_goal','current_prompt'):
        legacy.pop(field)
    legacy['config']=cfg
    store.update('interviews',legacy['id'],lambda _:legacy)
    settings=Settings(_env_file=None,database_path=path,session_secret='s'*40)
    app=create_app(settings)
    assert app.state.store.get('config','published')['config']['version']==2
    app=create_app(settings)
    assert len(app.state.store.get('config','published')['versions'])==1
    old=Interview.model_validate(app.state.store.get('interviews',legacy['id']))
    assert old.config.version==1 and old.planner_version==1
    assert analyze(old)['legacy'] and analyze(old)['score'] is None
