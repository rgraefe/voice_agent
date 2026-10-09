import pytest
from app.errors import ServiceError
from app.interview import create_legacy_interview as create_interview, apply_turn, stop_interview
from app.models import AgentConfig, Extraction, Observation, Fact, Turn


def make_turn(id='t1', topic='startup', quality='clear', text='Acme baut Software.', **kwargs):
    return Turn(id=id, text=text, extraction=Extraction(observations=[Observation(topic=topic, value=text, quote=text, quality=quality)], **kwargs))


def test_once_then_move_on_and_do_not_repeat():
    item = create_interview('owner', AgentConfig(), 'voice')
    apply_turn(item, make_turn(quality='vague'))
    assert item.topics['startup'].clarification_used
    assert item.current_topic == 'startup'
    apply_turn(item, make_turn(id='t2', quality='vague'))
    assert item.topics['startup'].status == 'unknown'
    assert item.current_topic == 'team'
    assert item.last_reply == item.config.topics[1].question


def test_out_of_order_facts_skip_already_answered_topic():
    item = create_interview('owner', AgentConfig(), 'voice')
    turn = make_turn()
    turn.extraction.observations.append(Observation(topic='team', value='Zwei Gründer', quote='Acme', quality='clear'))
    apply_turn(item, turn)
    assert item.current_topic == 'product'


def test_duplicate_identical_turn_and_conflicting_reuse():
    item = create_interview('owner', AgentConfig(), 'voice')
    turn = make_turn()
    apply_turn(item, turn)
    before = item.model_dump()
    apply_turn(item, turn)
    assert item.model_dump() == before
    with pytest.raises(ServiceError, match='anderem Inhalt'):
        apply_turn(item, make_turn(text='Anderer Inhalt'))


def test_unsubstantiated_quote_rejected():
    item = create_interview('owner', AgentConfig(), 'voice')
    turn = make_turn()
    turn.extraction.observations[0].quote = 'not in transcript'
    with pytest.raises(ServiceError) as exc:
        apply_turn(item, turn)
    assert exc.value.code == 'INVALID_EVIDENCE'


def test_complete_requires_explicit_confirmation_and_saves_unknowns():
    item = create_interview('owner', AgentConfig(), 'voice')
    for i, t in enumerate(item.config.topics):
        apply_turn(item, make_turn(id=f't{i}', topic=t.key))
    assert item.status == 'review'
    apply_turn(item, Turn(id='ambiguous', text='Vielleicht', extraction=Extraction()))
    assert item.status == 'review'
    apply_turn(item, Turn(id='yes', text='Ja, stimmt.', extraction=Extraction(confirmed_summary=True)))
    assert item.status == 'completed'
    assert item.ended_at
    assert 'gespeichert' in item.last_reply
    with pytest.raises(ServiceError):
        apply_turn(item, make_turn(id='closed'))


def test_correction_replaces_fact_and_requires_fresh_confirmation():
    item = create_interview('owner', AgentConfig(), 'voice')
    first = make_turn(facts=[Fact(key='startup_name', value='Acme', quote='Acme')])
    apply_turn(item, first)
    item.status = 'review'
    correction = make_turn(id='correction', text='Unser Name ist Beta.', confirmed_summary=True,
                           facts=[Fact(key='startup_name', value='Beta', quote='Beta')])
    apply_turn(item, correction)
    assert item.facts['startup_name']['value'] == 'Beta'
    assert item.facts['startup_name']['evidence_turn'] == 'correction'
    assert item.status == 'review'


def test_stop_preserves_partial_and_is_idempotent():
    item = create_interview('owner', AgentConfig(), 'voice')
    apply_turn(item, make_turn())
    stop_interview(item)
    before = item.model_dump()
    stop_interview(item)
    assert item.model_dump() == before
    assert item.status == 'incomplete'
    assert item.topics['startup'].value


def test_missing_observations_get_one_clarification():
    item = create_interview('owner', AgentConfig(), 'voice')
    for id in ('empty1', 'empty2'):
        apply_turn(item, Turn(id=id, text='Weiß ich nicht.', extraction=Extraction()))
    assert item.current_topic == 'team'
    assert item.topics['startup'].status == 'unknown'


def test_config_cannot_drop_or_duplicate_required_topics():
    cfg = AgentConfig().model_dump()
    cfg['topics'][1] = cfg['topics'][0]
    with pytest.raises(ValueError):
        AgentConfig.model_validate(cfg)
