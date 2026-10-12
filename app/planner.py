"""Deterministic goal progression; the language model supplies evidenced answers only."""
from __future__ import annotations
from app.goals import AnswerGoal
from app.models import AgentConfig, Turn
from app.types import InterviewMode
from typing import cast
import re
from datetime import timezone
from hashlib import sha256
from uuid import uuid4
from app.errors import ServiceError
from app.goals import GoalState
from app.models import Interview, TopicState, TranscriptItem, now


def legal_form_only(value: str) -> bool:
    return re.sub(r'[^a-z0-9]', '', value.casefold()) in {
        'gmbh', 'gmbhcokg', 'ug', 'ughaftungsbeschrnkt', 'ag', 'kg', 'ohg', 'gbr', 'llc', 'ltd', 'inc',
    }


# Three states: True = relevant, False = irrelevant, None = prerequisite not yet known.
def applicability(interview: Interview, goal: AnswerGoal) -> bool | None:
    if not goal.enabled:
        return False
    if not goal.condition:
        return True
    source = next(g for g in interview.config.goals if g.key == goal.condition.goal_key)
    parent = applicability(interview, source)
    if parent is not True:
        return parent
    state = interview.goals[source.key]
    if state.status != 'answered':
        return None
    return state.choice_value == goal.condition.equals


# Topic cards are a projection of goal state, not a second source of interview decisions.
def sync_topics(interview: Interview) -> None:
    for topic in interview.config.topics:
        goals = [g for g in interview.config.goals if g.topic == topic.key and applicability(interview, g) is not False]
        states = [interview.goals[g.key] for g in goals]
        target = interview.topics[topic.key]
        target.value = '; '.join(f'{g.label}: {interview.goals[g.key].value}' for g in goals if interview.goals[g.key].value) or None
        target.status = ('clear' if not states or all(interview.goals[g.key].status == 'answered' and applicability(interview,g) is True for g in goals) else
                         'unknown' if all(s.exhausted or s.status in ('answered','unknown') for s in states) else
                         'vague' if any(s.asked or s.value for s in states) else 'open')


# Exhaust bounded follow-ups before selecting the next relevant goal; required goals take priority.
def select_next(interview: Interview) -> AnswerGoal | None:
    for goal in interview.config.goals:
        state=interview.goals[goal.key]
        if state.asked and state.status in ('open','partial') and state.followups_used>=goal.max_followups:
            state.exhausted=True
            if state.status=='open':
                state.status='unknown'
    candidates = [g for g in interview.config.goals if applicability(interview,g) is True
                  and interview.goals[g.key].status not in ('answered','unknown') and not interview.goals[g.key].exhausted]
    return next((g for g in candidates if g.required), next(iter(candidates), None))


def ask(interview: Interview, goal: AnswerGoal) -> None:
    state = interview.goals[goal.key]
    if state.asked:
        state.followups_used += 1
        question = goal.clarification
        if goal.key == 'startup_name' and state.value and legal_form_only(state.value):
            question = ('Ich habe nur die Rechtsform verstanden. Wie lautet der vollständige Firmenname?'
                        if interview.config.language == 'de' else
                        'I only caught the legal form. What is the full company name?')
    else:
        state.asked = True
        question = goal.question
    interview.current_goal, interview.current_topic = goal.key, goal.topic
    interview.current_prompt = question
    interview.last_reply = question
    interview.status = 'active'


def create(owner: str, config: AgentConfig, mode: InterviewMode) -> Interview:
    interview = Interview(id=uuid4().hex,owner=owner,config=config,mode=mode,
                     topics={t.key:TopicState() for t in config.topics},goals={g.key:GoalState() for g in config.goals})
    first_goal = select_next(interview)
    # Validated configurations have an enabled, initially applicable goal.
    assert first_goal is not None
    ask(interview, first_goal)
    interview.last_reply = (f'Hi, ich bin {config.name}. Schön, dass du da bist. ' if config.language=='de'
                       else f"Hi, I'm {config.name}. It's lovely to meet you. ") + interview.last_reply
    return interview


def spoken_summary(interview: Interview) -> str:
    goals = [g for g in interview.config.goals if applicability(interview,g) is not False]
    answered = [g for g in goals if applicability(interview,g) is True and interview.goals[g.key].status=='answered']
    # Full answers and evidence live in the report; keep spoken review concise.
    parts = [f'{g.label}: {cast(str, interview.goals[g.key].value)[:220]}.' for g in answered]
    missing = sum(g.required and (applicability(interview,g) is None or interview.goals[g.key].status!='answered') for g in goals)
    if missing:
        parts.append(f'{missing} Pflichtangaben bleiben ungeklärt.' if interview.config.language=='de' else f'{missing} required answers remain unresolved.')
    return ' '.join(parts) or ('Es liegen noch keine gesicherten Angaben vor.' if interview.config.language=='de' else 'No confirmed information yet.')


def advance(interview: Interview, turn: Turn) -> Interview:
    # The same turn ID and payload is a harmless retry; changed content under that ID is a conflict.
    digest=sha256(turn.model_dump_json().encode()).hexdigest()
    if turn.id in interview.processed_turns:
        if interview.processed_turns[turn.id]!=digest:
            raise ServiceError('IDEMPOTENCY_CONFLICT','Nachricht bereits mit anderem Inhalt verarbeitet.',409)
        return interview
    if interview.status not in ('active','review'):
        raise ServiceError('INTERVIEW_CLOSED','Dieses Gespräch ist bereits beendet.',409)
    if len(interview.processed_turns)>=200:
        raise ServiceError('TURN_LIMIT','Die maximale Gesprächslänge ist erreicht.',409)
    by_key={g.key:g for g in interview.config.goals}
    seen=set()
    # Validate the entire extraction before mutating any state.
    for answer in turn.extraction.answers:
        goal=by_key.get(answer.goal_key)
        if not goal or not goal.enabled or answer.goal_key in seen or answer.quote not in turn.text:
            raise ServiceError('INVALID_EVIDENCE','Antwortziele benötigen eindeutige Belege aus der aktuellen Aussage.',422)
        seen.add(answer.goal_key)
        if (answer.choice_value is not None and (goal.kind!='choice' or answer.choice_value not in goal.choices)
            or answer.number_value is not None and goal.kind!='number'
            or answer.status=='answered' and (goal.kind=='choice' and answer.choice_value is None or goal.kind=='number' and answer.number_value is None)):
            raise ServiceError('INVALID_ANSWER','Die Antwort passt nicht zum konfigurierten Antworttyp.',422)
    for answer in turn.extraction.answers:
        state=interview.goals[answer.goal_key]
        if answer.goal_key == 'startup_name' and legal_form_only(answer.value):
            # A suffix is not a replacement for an already evidenced company name.
            if state.value and not legal_form_only(state.value):
                continue
            answer = answer.model_copy(update={'status': 'partial'})
        for key in ('status','value','quote','number_value','choice_value'):
            setattr(state,key,getattr(answer,key))
        state.evidence_turn=turn.id
        if state.status=='answered':
            state.exhausted=False
        # Explicit corrections preserve their evidence, including a retraction to unknown.
    if not any(t.id==turn.id for t in interview.transcript):
        interview.transcript.append(TranscriptItem(id=turn.id,role='user',text=turn.text,
                                              timestamp=turn.timestamp.astimezone(timezone.utc).isoformat() if turn.timestamp else now()))
    de=interview.config.language=='de'
    current=interview.goals.get(interview.current_goal) if interview.current_goal is not None else None
    current_goal=by_key.get(interview.current_goal) if interview.current_goal is not None else None
    was_review=interview.status=='review'
    if current and current_goal and current.status not in ('answered','unknown') and applicability(interview,current_goal) is True:
        if interview.interrupted_question:
            interview.last_reply=interview.interrupted_question
            interview.interrupted_question=None
            interview.processed_turns[turn.id]=digest
            interview.revision+=1
            sync_topics(interview)
            return interview
        if current.followups_used>=current_goal.max_followups:
            current.exhausted=True
            if current.status=='open':
                current.status='unknown'
    interview.interrupted_question=None
    next_goal=select_next(interview)
    if next_goal:
        ask(interview,next_goal)
        ack=turn.extraction.acknowledgment.strip()
        if ack and '?' not in ack:
            interview.last_reply=ack+' '+interview.last_reply
    # Only an explicit confirmation without new facts may complete the interview.
    elif was_review and turn.extraction.confirmed_summary and not turn.extraction.answers:
        interview.status,interview.ended_at='completed',now()
        interview.last_reply='Danke! Dein Gesprächsergebnis ist gespeichert.' if de else 'Thank you! Your interview result has been saved.'
    else:
        interview.status,interview.current_goal,interview.current_topic='review',None,None
        interview.current_prompt=''
        interview.last_reply=spoken_summary(interview)+(' Stimmt das, oder möchtest du etwas korrigieren?' if de else ' Is that correct, or would you like to correct anything?')
    sync_topics(interview)
    interview.processed_turns[turn.id]=digest
    interview.revision+=1
    return interview
