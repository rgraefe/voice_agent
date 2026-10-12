"""Explainable snapshot scoring. Missing evidence never becomes a negative match."""
from __future__ import annotations
from app.models import Interview
from app.types import Document
from typing import TypedDict
import re
from datetime import datetime
from app.planner import applicability


class TopicProgress(TypedDict):
    key: str
    label: str
    answered: int
    total: int


class InterviewStatistics(TypedDict):
    duration_seconds: int
    turns: dict[str, int]
    words: dict[str, int]
    interruptions: int
    followups: int


class AnalysisReport(TypedDict):
    """Report fields; unavailable percentages are None rather than zero."""
    configuration_version: int
    profile_name: str
    configured: bool
    score: int | None
    coverage: int | None
    completeness: int | None
    answered_required: int
    total_required: int
    rules: list[Document]
    goals: list[Document]
    topics: list[TopicProgress]
    transcript: list[Document]
    statistics: InterviewStatistics


def analyze(interview: Interview) -> AnalysisReport:
    goals: list[Document]=[]
    for goal in interview.config.goals:
        state=interview.goals[goal.key]
        applies=applicability(interview,goal)
        status: str='not_applicable' if applies is False else 'blocked' if applies is None else state.status
        goals.append({**goal.model_dump(),**state.model_dump(),'status':status,'applicable':applies})
    # Unknown conditions still count as unresolved; explicitly inapplicable goals do not.
    required=[g for g in goals if g['required'] and g['applicable'] is not False]
    answered=sum(g['status']=='answered' for g in required)
    denominator=len(required)
    by_key={g['key']:g for g in goals}
    rules: list[Document]=[]
    # Match uses known evidence only; coverage separately exposes how much evidence is missing.
    known_weight=eligible_weight=matched_weight=0
    for rule in interview.config.match_profile.rules:
        g=by_key[rule.goal_key]
        status='unknown'
        if g['applicable'] is False:
            status='not_applicable'
        else:
            eligible_weight+=rule.weight
            if g['status']=='answered':
                value=g['choice_value'] if rule.operator=='one_of' else g['number_value']
                if value is not None:
                    fits=(value in rule.accepted if rule.operator=='one_of' else
                          (rule.minimum is None or value>=rule.minimum) and (rule.maximum is None or value<=rule.maximum))
                    status='matched' if fits else 'unmatched'
                    known_weight+=rule.weight
                    if fits:
                        matched_weight+=rule.weight
        rules.append({**rule.model_dump(),'label':g['label'],'unit':g['unit'],'status':status,
                      'value':g['value'],'quote':g['quote'],'evidence_turn':g['evidence_turn']})
    # Callback arrival order can differ from the actual speech timestamps.
    transcript=sorted((t.model_dump() for t in interview.transcript),key=lambda t:datetime.fromisoformat(t['timestamp']))
    start=datetime.fromisoformat(interview.created_at)
    for t in transcript:
        t['offset_seconds']=max(0,round((datetime.fromisoformat(t['timestamp'])-start).total_seconds()))
    # Word counts describe transcript share, not speaking time (raw audio is not retained).
    words={role:sum(len(re.findall(r'\b\w+\b',t['text'])) for t in transcript if t['role']==role) for role in ('user','assistant')}
    end=datetime.fromisoformat(interview.ended_at) if interview.ended_at else (datetime.fromisoformat(transcript[-1]['timestamp']) if transcript else start)
    topics: list[TopicProgress]=[]
    for topic in interview.config.topics:
        rows=[g for g in goals if g['topic']==topic.key and g['applicable'] is not False]
        topics.append({'key':topic.key,'label':topic.title,'answered':sum(g['status']=='answered' for g in rows),'total':len(rows)})
    return {'configuration_version':interview.config.version,
            'profile_name':interview.config.match_profile.name,'configured':bool(rules),'score':round(100*matched_weight/known_weight) if known_weight else None,
            'coverage':round(100*known_weight/eligible_weight) if eligible_weight else None,
            'completeness':round(100*answered/denominator) if denominator else None,
            'answered_required':answered,'total_required':denominator,'rules':rules,'goals':goals,'topics':topics,
            'transcript':transcript,'statistics':{'duration_seconds':max(0,round((end-start).total_seconds())),
              'turns':{r:sum(t['role']==r for t in transcript) for r in words},'words':words,
              'interruptions':sum(t['interrupted'] for t in transcript),'followups':sum(s.followups_used for s in interview.goals.values())}}
