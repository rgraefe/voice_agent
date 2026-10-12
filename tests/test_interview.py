"""Lifecycle tests exercise the same goal controller used by the application."""
from __future__ import annotations
from typing import Literal
import pytest
from app.errors import ServiceError
from app.goals import GoalAnswer
from app.interview import apply_turn, create_interview, stop_interview, summary
from app.models import AgentConfig, Extraction, Interview, Turn


def small_interview() -> Interview:
    config = AgentConfig()
    config.goals = [goal for goal in config.goals if goal.key in ('startup_name', 'team')]
    return create_interview('owner', config, 'voice')


def make_turn(
    id: str = 't1', key: str = 'startup_name', text: str = 'Acme',
    status: Literal['answered', 'partial', 'unknown'] = 'answered',
    confirm: bool = False,
) -> Turn:
    return Turn(id=id, text=text, extraction=Extraction(
        answers=[GoalAnswer(goal_key=key, value=text, quote=text, status=status)],
        confirmed_summary=confirm,
    ))


def test_once_then_move_on_and_do_not_repeat() -> None:
    interview = small_interview()
    apply_turn(interview, make_turn(status='partial'))
    assert interview.goals['startup_name'].followups_used == 1
    assert interview.current_goal == 'startup_name'
    apply_turn(interview, make_turn(id='t2', status='partial'))
    assert interview.goals['startup_name'].exhausted
    assert interview.goals['startup_name'].status == 'partial'
    assert interview.current_goal == 'team'
    assert interview.last_reply == interview.config.goals[1].question


def test_out_of_order_answers_skip_already_answered_goal() -> None:
    interview = small_interview()
    apply_turn(interview, make_turn(key='team', text='Zwei Gründer, Entwicklung und Vertrieb.'))
    apply_turn(interview, make_turn(id='name'))
    assert interview.status == 'review'
    assert interview.current_goal is None
    assert 'Acme' in summary(interview)
    assert 'Zwei Gründer' in summary(interview)


def test_duplicate_identical_turn_and_conflicting_reuse() -> None:
    interview = small_interview()
    turn = make_turn()
    apply_turn(interview, turn)
    before = interview.model_dump()
    apply_turn(interview, turn)
    assert interview.model_dump() == before
    with pytest.raises(ServiceError, match='anderem Inhalt'):
        apply_turn(interview, make_turn(text='Anderer Inhalt'))


def test_unsubstantiated_quote_rejected() -> None:
    interview = small_interview()
    before = interview.model_dump()
    turn = make_turn()
    turn.extraction.answers[0].quote = 'not in transcript'
    with pytest.raises(ServiceError) as exc:
        apply_turn(interview, turn)
    assert exc.value.code == 'INVALID_EVIDENCE'
    assert interview.model_dump() == before


def test_complete_requires_explicit_confirmation_and_saves_unknowns() -> None:
    interview = small_interview()
    apply_turn(interview, make_turn())
    apply_turn(interview, make_turn(id='team', key='team', text='Noch offen', status='unknown'))
    assert interview.status == 'review'
    assert '1 Pflichtangaben' in summary(interview)
    apply_turn(interview, Turn(id='ambiguous', text='Vielleicht', extraction=Extraction()))
    assert interview.status == 'review'
    apply_turn(interview, Turn(id='yes', text='Ja, stimmt.', extraction=Extraction(confirmed_summary=True)))
    assert interview.status == 'completed'
    assert interview.ended_at
    assert interview.goals['team'].status == 'unknown'
    with pytest.raises(ServiceError) as exc:
        apply_turn(interview, make_turn(id='closed'))
    assert exc.value.code == 'INTERVIEW_CLOSED'


def test_correction_replaces_answer_and_requires_fresh_confirmation() -> None:
    interview = small_interview()
    apply_turn(interview, make_turn())
    apply_turn(interview, make_turn(id='team', key='team', text='Zwei erfahrene Gründer.'))
    assert interview.status == 'review'
    apply_turn(interview, make_turn(id='correction', text='Beta', confirm=True))
    assert interview.goals['startup_name'].value == 'Beta'
    assert interview.goals['startup_name'].evidence_turn == 'correction'
    assert interview.status == 'review'
    assert 'Beta' in summary(interview)
    assert 'Acme' not in summary(interview)


def test_stop_preserves_partial_and_is_idempotent() -> None:
    interview = small_interview()
    apply_turn(interview, make_turn(status='partial'))
    stop_interview(interview)
    before = interview.model_dump()
    stop_interview(interview)
    assert interview.model_dump() == before
    assert interview.status == 'incomplete'
    assert interview.goals['startup_name'].value == 'Acme'
    assert interview.goals['startup_name'].status == 'partial'


def test_missing_answers_get_one_clarification() -> None:
    interview = small_interview()
    for id in ('empty1', 'empty2'):
        apply_turn(interview, Turn(id=id, text='Weiß ich nicht.', extraction=Extraction()))
    assert interview.current_goal == 'team'
    assert interview.goals['startup_name'].status == 'unknown'
    assert interview.goals['startup_name'].followups_used == 1


def test_config_cannot_drop_or_duplicate_required_topics() -> None:
    config = AgentConfig().model_dump()
    config['topics'][1] = config['topics'][0]
    with pytest.raises(ValueError):
        AgentConfig.model_validate(config)
