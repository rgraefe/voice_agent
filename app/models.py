from datetime import datetime, timezone
from typing import Literal
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator
from app.goals import AnswerGoal, MatchProfile, GoalAnswer, GoalState, default_goals, validate_goal_config


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


TopicKey = Literal["startup", "team", "product", "traction", "market", "funding", "next_step"]


class Topic(StrictModel):
    key: TopicKey
    title: str = Field(min_length=1, max_length=80)
    question: str = Field(min_length=10, max_length=500)
    clarification: str = Field(min_length=10, max_length=500)


def default_topics() -> list[Topic]:
    rows = [
        ("startup", "Startup & Sektor", "Wie heißt euer Startup und welches Problem löst ihr für wen?", "Kannst du euren Namen, die Branche und eure Zielgruppe etwas genauer beschreiben?"),
        ("team", "Team", "Wer gehört zum Gründerteam und welche Erfahrung bringt ihr mit?", "Wie verteilt ihr Rollen und Verantwortung im Team?"),
        ("product", "Produkt & Entwicklung", "Was kann euer Produkt heute schon und in welcher Entwicklungsphase seid ihr?", "Was ist bereits nutzbar und was ist euer nächster Produktmeilenstein?"),
        ("traction", "Traktion", "Welche messbare Traktion habt ihr bisher erreicht?", "Welche konkreten Kunden-, Nutzungs- oder Umsatzzahlen habt ihr, und für welchen Zeitraum?"),
        ("market", "Markt & Wettbewerb", "Welche Alternativen nutzen eure Kunden heute und wodurch unterscheidet ihr euch?", "Wer sind eure wichtigsten Wettbewerber und was macht euch für die Zielgruppe besonders?"),
        ("funding", "Finanzierung", "Welche Finanzierungsrunde plant ihr und wie viel Kapital benötigt ihr wofür?", "Kannst du Betrag, Währung, geplante Runde und Verwendung der Mittel konkretisieren?"),
        ("next_step", "Nächster Schritt", "Welchen nächsten Schritt wünscht ihr euch nach diesem Gespräch?", "Was wäre ein konkreter nächster Schritt und wann soll er stattfinden?"),
    ]
    return [Topic(key=k, title=t, question=q, clarification=c) for k, t, q, c in rows]


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
    def unique_topics(self):
        if {t.key for t in self.topics} != {t.key for t in default_topics()}:
            raise ValueError("Exactly one of each required topic is needed")
        validate_goal_config(self.goals, self.match_profile)
        return self


class Observation(StrictModel):
    topic: TopicKey
    value: str = Field(min_length=1, max_length=1500)
    quote: str = Field(min_length=1, max_length=1500)
    quality: Literal["clear", "vague"]


FactKey = Literal["startup_name", "sector", "stage", "team", "product", "traction", "target_market", "competitors", "funding_amount", "funding_currency", "funding_round", "use_of_funds", "next_step"]


class Fact(StrictModel):
    key: FactKey
    value: str = Field(min_length=1, max_length=600)
    quote: str = Field(min_length=1, max_length=1500)


class GoalExtraction(StrictModel):
    """Model-facing contract for the goal planner; excludes obsolete legacy fields."""
    answers: list[GoalAnswer] = Field(default_factory=list, max_length=40)
    acknowledgment: str = Field(default="", max_length=180)
    confirmed_summary: bool = False


class Extraction(StrictModel):
    answers: list[GoalAnswer] = Field(default_factory=list, max_length=40)
    facts: list[Fact] = Field(default_factory=list, max_length=13)
    observations: list[Observation] = Field(default_factory=list, max_length=7)
    acknowledgment: str = Field(default="", max_length=180)
    confirmed_summary: bool = False


class Turn(StrictModel):
    id: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    text: str = Field(min_length=1, max_length=10000)
    extraction: Extraction
    timestamp: AwareDatetime | None = None


class TopicState(StrictModel):
    status: Literal["open", "vague", "clear", "unknown"] = "open"
    value: str | None = None
    evidence_turn: str | None = None
    quote: str | None = None
    asked: bool = False
    clarification_used: bool = False


class TranscriptItem(StrictModel):
    id: str
    role: Literal["user", "assistant"]
    text: str
    timestamp: str = Field(default_factory=now)
    interrupted: bool = False


class Interview(StrictModel):
    id: str
    owner: str
    planner_version: Literal[1, 2] = 1
    goals: dict[str, GoalState] = Field(default_factory=dict)
    current_goal: str | None = None
    current_prompt: str = ""
    created_at: str = Field(default_factory=now)
    ended_at: str | None = None
    config: AgentConfig
    mode: Literal["voice", "simulation"]
    status: Literal["active", "review", "completed", "incomplete"] = "active"
    facts: dict[str, dict[str, str]] = Field(default_factory=dict)
    topics: dict[str, TopicState] = Field(default_factory=dict)
    current_topic: str | None = None
    interrupted_question: str | None = None
    transcript: list[TranscriptItem] = Field(default_factory=list)
    simulation_requests: dict[str, str] = Field(default_factory=dict)
    processed_turns: dict[str, str] = Field(default_factory=dict)
    last_reply: str = ""
    metrics: list[dict] = Field(default_factory=list)
    revision: int = 0
