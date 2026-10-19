from __future__ import annotations
from typing import Self
from app.types import TopicKey as TopicKey
from datetime import datetime, timezone
from typing import Literal
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator
from app.goals import AnswerGoal, MatchProfile, GoalAnswer, GoalState, default_goals, validate_goal_config


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Topic(StrictModel):
    key: TopicKey
    title: str = Field(min_length=1, max_length=80)


def default_topics() -> list[Topic]:
    rows: list[tuple[TopicKey, str]] = [
        ('startup', 'Startup & Sektor'),
        ('team', 'Team'),
        ('product', 'Produkt & Entwicklung'),
        ('traction', 'Traktion'),
        ('market', 'Markt & Wettbewerb'),
        ('funding', 'Finanzierung'),
        ('next_step', 'Nächster Schritt'),
    ]
    return [Topic(key=key, title=title) for key, title in rows]


# Published settings are copied into each interview so later admin edits do not change its rules.
class AgentConfig(StrictModel):
    version: int = Field(default=1, ge=1)
    name: str = Field(default="Mira", min_length=1, max_length=40)
    language: Literal["de", "en"] = "de"
    tone: Literal["warm", "professional", "curious"] = "warm"
    voice_id: str = Field(default="", max_length=80, pattern=r"^[a-zA-Z0-9_-]*$")
    tts_model: Literal["eleven_flash_v2_5", "eleven_turbo_v2_5"] = "eleven_flash_v2_5"
    stability: float = Field(default=0.5, ge=0, le=1)
    similarity: float = Field(default=0.75, ge=0, le=1)
    speed: float = Field(default=1.0, ge=0.7, le=1.2)
    pause_seconds: float = Field(default=0.6, ge=0.3, le=2)
    max_minutes: int = Field(default=20, ge=5, le=45)
    guidance: str = Field(default="Bleibe freundlich, konkret und wertschätzend. Keine Investitionszusagen.", max_length=2000)
    goals: list[AnswerGoal] = Field(default_factory=default_goals, min_length=1, max_length=40)
    match_profile: MatchProfile = Field(default_factory=MatchProfile)
    topics: list[Topic] = Field(default_factory=default_topics, min_length=7, max_length=7)

    @model_validator(mode="after")
    def unique_topics(self) -> Self:
        if {t.key for t in self.topics} != {t.key for t in default_topics()}:
            raise ValueError("Exactly one of each required topic is needed")
        validate_goal_config(self.goals, self.match_profile)
        return self


class Extraction(StrictModel):
    """Structured answers proposed by the model and validated by the planner."""
    answers: list[GoalAnswer] = Field(default_factory=list, max_length=40)
    acknowledgment: str = Field(default="", max_length=180)
    confirmed_summary: bool = False
    # Dialogue requests are not failed attempts to answer the pending goal.
    dialogue_act: Literal["answer", "repeat", "clarify", "review_missing"] = "answer"


# Turn IDs provide idempotency; evidence quotes must refer to this turn's original text.
class Turn(StrictModel):
    id: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    text: str = Field(min_length=1, max_length=10000)
    extraction: Extraction
    timestamp: AwareDatetime | None = None


class TopicState(StrictModel):
    """Display summary derived from individual answer goals."""
    status: Literal["open", "vague", "clear", "unknown"] = "open"
    value: str | None = None


class TranscriptItem(StrictModel):
    id: str
    role: Literal["user", "assistant"]
    text: str
    timestamp: str = Field(default_factory=now)
    interrupted: bool = False


class Interview(StrictModel):
    id: str
    owner: str
    goals: dict[str, GoalState] = Field(default_factory=dict)
    current_goal: str | None = None
    current_prompt: str = ""
    created_at: str = Field(default_factory=now)
    ended_at: str | None = None
    config: AgentConfig
    mode: Literal["voice", "simulation"]
    status: Literal["active", "review", "completed", "incomplete"] = "active"
    topics: dict[str, TopicState] = Field(default_factory=dict)
    current_topic: str | None = None
    interrupted_question: str | None = None
    transcript: list[TranscriptItem] = Field(default_factory=list)
    simulation_requests: dict[str, str] = Field(default_factory=dict)
    processed_turns: dict[str, str] = Field(default_factory=dict)
    last_reply: str = ""
    metrics: list[dict] = Field(default_factory=list)
    revision: int = 0
