"""Explainable snapshot scoring. Missing evidence never becomes a negative match."""
import re
from datetime import datetime
from app.planner import applicability


def analyze(item):
    goals=[]
    for goal in item.config.goals if item.planner_version==2 else []:
        state=item.goals[goal.key]
        applies=applicability(item,goal)
        status='not_applicable' if applies is False else 'blocked' if applies is None else state.status
        goals.append({**goal.model_dump(),**state.model_dump(),'status':status,'applicable':applies})
    required=[g for g in goals if g['required'] and g['applicable'] is not False]
    answered=sum(g['status']=='answered' for g in required)
    if item.planner_version==1:
        answered=sum(s.status=='clear' for s in item.topics.values())
        denominator=len(item.topics)
    else:
        denominator=len(required)
    by_key={g['key']:g for g in goals}
    rules=[]
    known_weight=eligible_weight=matched_weight=0
    for rule in item.config.match_profile.rules if item.planner_version==2 else []:
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
    transcript=sorted((t.model_dump() for t in item.transcript),key=lambda t:datetime.fromisoformat(t['timestamp']))
    start=datetime.fromisoformat(item.created_at)
    for t in transcript:
        t['offset_seconds']=max(0,round((datetime.fromisoformat(t['timestamp'])-start).total_seconds()))
    words={role:sum(len(re.findall(r'\b\w+\b',t['text'])) for t in transcript if t['role']==role) for role in ('user','assistant')}
    end=datetime.fromisoformat(item.ended_at) if item.ended_at else (datetime.fromisoformat(transcript[-1]['timestamp']) if transcript else start)
    topics=[]
    for topic in item.config.topics:
        rows=[g for g in goals if g['topic']==topic.key and g['applicable'] is not False]
        topics.append({'key':topic.key,'label':topic.title,'answered':sum(g['status']=='answered' for g in rows),'total':len(rows)})
    return {'legacy':item.planner_version==1,'configuration_version':item.config.version,
            'profile_name':item.config.match_profile.name,'configured':bool(rules),'score':round(100*matched_weight/known_weight) if known_weight else None,
            'coverage':round(100*known_weight/eligible_weight) if eligible_weight else None,
            'completeness':round(100*answered/denominator) if denominator else None,
            'answered_required':answered,'total_required':denominator,'rules':rules,'goals':goals,'topics':topics,
            'transcript':transcript,'statistics':{'duration_seconds':max(0,round((end-start).total_seconds())),
              'turns':{r:sum(t['role']==r for t in transcript) for r in words},'words':words,
              'interruptions':sum(t['interrupted'] for t in transcript),'followups':sum(s.followups_used for s in item.goals.values())}}
