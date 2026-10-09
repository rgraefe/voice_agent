from hashlib import sha256
from uuid import uuid4
from app.errors import ServiceError
from app.models import AgentConfig, Interview, TopicState, TranscriptItem, Turn, now


def create_interview(owner: str, config: AgentConfig, mode: str) -> Interview:
    from app.planner import create
    return create(owner, config, mode)


def create_legacy_interview(owner: str, config: AgentConfig, mode: str) -> Interview:
    first = config.topics[0]
    item = Interview(id=uuid4().hex, owner=owner, config=config, mode=mode,
                     topics={t.key: TopicState() for t in config.topics}, current_topic=first.key)
    item.topics[first.key].asked = True
    greeting = (f"Hi, ich bin {config.name}. Schön, dass du da bist. " if config.language == "de"
                else f"Hi, I'm {config.name}. It's lovely to meet you. ")
    item.last_reply = greeting + first.question
    return item


def summary(item: Interview) -> str:
    if item.planner_version == 2:
        from app.planner import spoken_summary
        return spoken_summary(item)
    parts = [f"{t.title}: {item.topics[t.key].value or ('Noch offen' if item.config.language == 'de' else 'Unknown')}."
             for t in item.config.topics]
    return " ".join(parts)


def apply_turn(item: Interview, turn: Turn) -> Interview:
    if item.planner_version == 2:
        from app.planner import advance
        return advance(item, turn)
    digest = sha256(turn.model_dump_json().encode()).hexdigest()
    if turn.id in item.processed_turns:
        if item.processed_turns[turn.id] != digest:
            raise ServiceError("IDEMPOTENCY_CONFLICT", "Diese Nachricht wurde bereits mit anderem Inhalt verarbeitet.", 409)
        return item
    if item.status not in ("active", "review"):
        raise ServiceError("INTERVIEW_CLOSED", "Dieses Gespräch ist bereits beendet.", 409)
    if len(item.processed_turns) >= 100:
        raise ServiceError("TURN_LIMIT", "Die maximale Gesprächslänge ist erreicht.", 409)
    facts_seen = set()
    for fact in turn.extraction.facts:
        if fact.key in facts_seen or fact.quote not in turn.text:
            raise ServiceError("INVALID_EVIDENCE", "Fakten benötigen Belege aus der aktuellen Aussage.", 422)
        facts_seen.add(fact.key)
        item.facts[fact.key] = {"value": fact.value, "quote": fact.quote, "evidence_turn": turn.id}
    topics_seen = set()
    for observation in turn.extraction.observations:
        if observation.topic in topics_seen or observation.quote not in turn.text:
            raise ServiceError("INVALID_EVIDENCE", "Angaben benötigen eindeutige Belege aus der aktuellen Aussage.", 422)
        topics_seen.add(observation.topic)
        state = item.topics[observation.topic]
        state.value, state.quote, state.evidence_turn = observation.value, observation.quote, turn.id
        state.status = observation.quality
    if not any(t.id == turn.id for t in item.transcript):
        item.transcript.append(TranscriptItem(id=turn.id, role="user", text=turn.text))
    de = item.config.language == "de"
    if item.status == "review":
        # A correction and confirmation in one utterance requires a fresh review.
        if turn.extraction.confirmed_summary and not turn.extraction.observations and not turn.extraction.facts:
            item.status, item.ended_at = "completed", now()
            item.last_reply = "Danke! Dein Gesprächsergebnis ist gespeichert." if de else "Thank you! Your interview result has been saved."
        else:
            item.last_reply = summary(item) + (" Stimmt diese Zusammenfassung?" if de else " Is this summary correct?")
    else:
        current = item.topics[item.current_topic] if item.current_topic else None
        if current and current.status != "clear" and item.interrupted_question:
            # The founder did not hear the whole question. Do not consume another clarification.
            item.last_reply = item.interrupted_question
            item.interrupted_question = None
            item.processed_turns[turn.id] = digest
            item.revision += 1
            return item
        item.interrupted_question = None
        if current and current.status != "clear":
            if current.clarification_used:
                current.status = "unknown"
            else:
                current.status = "vague"
        next_topic = next((t for t in item.config.topics if item.topics[t.key].status in ("open", "vague")), None)
        if next_topic:
            state = item.topics[next_topic.key]
            item.current_topic = next_topic.key
            if state.asked:
                state.clarification_used = True
                question = next_topic.clarification
            else:
                state.asked = True
                question = next_topic.question
            # Acknowledgments are optional, bounded, and cannot introduce another question.
            ack = turn.extraction.acknowledgment.strip()
            item.last_reply = ((ack + " ") if ack and "?" not in ack else "") + question
        else:
            item.status, item.current_topic = "review", None
            item.last_reply = ("Ich fasse kurz zusammen. " if de else "Let me summarize. ") + summary(item)
            item.last_reply += " Stimmt das, oder möchtest du etwas korrigieren?" if de else " Is that correct, or would you like to correct anything?"
    item.processed_turns[turn.id] = digest
    item.revision += 1
    return item


def stop_interview(item: Interview) -> Interview:
    if item.status in ("active", "review"):
        item.status, item.ended_at = "incomplete", now()
        item.revision += 1
    return item
