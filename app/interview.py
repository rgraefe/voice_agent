"""Interview lifecycle: create, process a turn, summarize, or stop."""
from __future__ import annotations

from app.models import AgentConfig, Interview, Turn, now
from app.planner import advance, create, spoken_summary
from app.types import InterviewMode


def create_interview(owner: str, config: AgentConfig, mode: InterviewMode) -> Interview:
    return create(owner, config, mode)


def summary(interview: Interview) -> str:
    return spoken_summary(interview)


def apply_turn(interview: Interview, turn: Turn) -> Interview:
    return advance(interview, turn)


# Stopping capture is not confirmation; retain unfinished answers for history.
def stop_interview(interview: Interview) -> Interview:
    if interview.status in ("active", "review"):
        interview.status, interview.ended_at = "incomplete", now()
        interview.revision += 1
    return interview
