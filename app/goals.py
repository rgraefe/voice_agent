"""Versioned interview goal and match profile schemas, independent of voice providers."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Schema(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class Condition(Schema):
    goal_key: str = Field(pattern=r'^[a-z][a-z0-9_]{0,49}$')
    equals: str = Field(min_length=1, max_length=100)


class AnswerGoal(Schema):
    key: str = Field(pattern=r'^[a-z][a-z0-9_]{0,49}$')
    topic: Literal['startup','team','product','traction','market','funding','next_step']
    label: str = Field(min_length=1, max_length=100)
    criteria: str = Field(min_length=10, max_length=1000)
    question: str = Field(min_length=10, max_length=500)
    clarification: str = Field(min_length=10, max_length=500)
    required: bool = True
    enabled: bool = True
    max_followups: int = Field(default=1, ge=0, le=3)
    kind: Literal['text','choice','number'] = 'text'
    choices: list[str] = Field(default_factory=list, max_length=20)
    unit: str = Field(default='', max_length=30)
    condition: Condition | None = None

    @model_validator(mode='after')
    def valid_type(self):
        if self.kind == 'choice':
            if len(self.choices) < 2 or any(not x.strip() or len(x)>100 for x in self.choices):
                raise ValueError('Choice goals need 2–20 nonempty options')
            if len({x.casefold().strip() for x in self.choices}) != len(self.choices):
                raise ValueError('Choice options must be unique')
        elif self.choices:
            raise ValueError('Only choice goals can have options')
        if self.kind != 'number' and self.unit:
            raise ValueError('Only number goals can have a unit')
        return self


class MatchRule(Schema):
    goal_key: str = Field(pattern=r'^[a-z][a-z0-9_]{0,49}$')
    weight: int = Field(default=1, ge=1, le=10)
    operator: Literal['one_of','range']
    accepted: list[str] = Field(default_factory=list, max_length=20)
    minimum: float | None = None
    maximum: float | None = None

    @model_validator(mode='after')
    def valid_rule(self):
        if self.operator=='one_of' and (not self.accepted or self.minimum is not None or self.maximum is not None):
            raise ValueError('Choice rule needs accepted options and no numeric limits')
        if self.operator=='range':
            if self.accepted or (self.minimum is None and self.maximum is None):
                raise ValueError('Number rule needs at least one bound and no options')
            if self.minimum is not None and self.maximum is not None and self.minimum>self.maximum:
                raise ValueError('Minimum cannot exceed maximum')
        return self


class MatchProfile(Schema):
    name: str = Field(default='Mein Zielprofil', min_length=1, max_length=100)
    rules: list[MatchRule] = Field(default_factory=list, max_length=40)


# Model-proposed evidence for one turn; the planner validates its quote before accepting it.
class GoalAnswer(Schema):
    goal_key: str = Field(pattern=r'^[a-z][a-z0-9_]{0,49}$')
    status: Literal['answered','partial','unknown']
    value: str = Field(min_length=1, max_length=1000)
    quote: str = Field(min_length=1, max_length=1500)
    number_value: float | None = None
    choice_value: str | None = Field(default=None, max_length=100)


# Persisted progress is separate from the model output, including the bounded clarification counter.
class GoalState(Schema):
    status: Literal['open','partial','answered','unknown'] = 'open'
    value: str | None = None
    quote: str | None = None
    evidence_turn: str | None = None
    number_value: float | None = None
    choice_value: str | None = None
    asked: bool = False
    followups_used: int = 0
    exhausted: bool = False


def default_goals() -> list[AnswerGoal]:
    rows = [
      ('startup_name','startup','Startup-Name','Der Name des Startups ist eindeutig genannt.','Wie heißt euer Startup?','Unter welchem Namen tretet ihr auf?'),
      ('sector','startup','Sektor','Die Branche wird konkret genannt und einer Auswahl eindeutig zugeordnet.','In welcher Branche seid ihr tätig?','Welcher Branche würdest du euer Startup konkret zuordnen?'),
      ('problem','startup','Problem & Nutzen','Ein konkretes Kundenproblem und der Nutzen der Lösung sind benannt.','Welches Problem löst ihr für eure Kunden?','Kannst du ein konkretes Beispiel für dieses Kundenproblem nennen?'),
      ('target_customer','startup','Zielkunden','Ein konkretes Kundensegment mit erkennbaren Merkmalen ist genannt.','Für welche Kunden entwickelt ihr eure Lösung?','Welche Unternehmen oder Menschen sollen eure ersten Kunden sein?'),
      ('team','team','Team & Erfahrung','Teamrollen und für das Vorhaben relevante Erfahrungen sind beschrieben.','Wer gehört zum Team und welche Erfahrung bringt ihr mit?','Wie verteilt ihr Rollen und welche relevante Erfahrung habt ihr bereits?'),
      ('product','product','Produkt','Die Lösung und die bereits nutzbaren Funktionen sind konkret beschrieben.','Was kann euer Produkt heute bereits?','Was kann ein Kunde heute tatsächlich mit eurem Produkt machen?'),
      ('stage','product','Entwicklungsphase','Der aktuelle Entwicklungsstand ist eindeutig, nicht nur ein zukünftiges Ziel.','In welcher Entwicklungsphase seid ihr gerade?','Habt ihr eine Idee, einen Prototyp, ein MVP oder bereits ein marktreifes Produkt?'),
      ('traction','traction','Messbare Traktion','Konkrete Kennzahlen inklusive Zeitraum und Einheit. Explizit noch keine Kunden/Umsätze ist ebenfalls eine klare Antwort.','Welche messbaren Fortschritte oder Kundenzahlen habt ihr bisher erreicht?','Welche konkreten Zahlen habt ihr und auf welchen Zeitraum beziehen sie sich?'),
      ('competitors','market','Wettbewerb & Unterschied','Bestehende Alternativen oder Wettbewerber und die eigene Differenzierung sind beschrieben.','Welche Alternativen nutzen eure Kunden und was unterscheidet euch davon?','Kannst du eine konkrete Alternative und euren wichtigsten Unterschied nennen?'),
      ('fundraising','funding','Finanzierung geplant','Es ist ausdrücklich geklärt, ob aktuell eine Finanzierungsrunde geplant ist.','Plant ihr aktuell eine Finanzierungsrunde?','Ist eine Runde bereits geplant, nicht vorgesehen oder noch offen?'),
      ('funding_amount','funding','Kapitalbedarf in EUR','Ein konkreter Betrag in Euro ist genannt. Fremdwährungen nicht umrechnen oder als EUR ausgeben.','Wie viel Kapital benötigt ihr in Euro?','Welchen konkreten Betrag in Euro plant ihr aufzunehmen?'),
      ('funding_round','funding','Geplante Runde','Die Bezeichnung der geplanten Finanzierungsrunde ist eindeutig.','Welche Finanzierungsrunde plant ihr?','Geht es um Pre-Seed, Seed, Series A oder eine spätere Runde?'),
      ('use_of_funds','funding','Mittelverwendung','Konkrete Verwendungszwecke des Kapitals sind genannt.','Wofür möchtet ihr das Kapital einsetzen?','Welche konkreten Ausgaben oder Meilensteine soll das Kapital finanzieren?'),
      ('funding_timeline','funding','Finanzierungszeitplan','Ein konkreter Zeitpunkt oder Zeitraum für die Runde ist genannt.','Wann möchtet ihr die Finanzierungsrunde abschließen?','Welcher Monat oder Zeitraum wäre euer Ziel für den Abschluss?'),
      ('next_step','next_step','Nächster Schritt','Ein konkreter gewünschter nächster Schritt ist benannt.','Welchen nächsten Schritt wünscht ihr euch nach diesem Gespräch?','Was sollen wir als Nächstes konkret miteinander besprechen oder vereinbaren?'),
    ]
    goals = [AnswerGoal(key=k,topic=t,label=l,criteria=c,question=q,clarification=f) for k,t,l,c,q,f in rows]
    choices = {'sector':['SaaS','ClimateTech','HealthTech','FinTech','Industrie','Sonstiges'],
               'stage':['Idee','Prototyp','MVP','Marktreif'], 'fundraising':['Ja','Nein','Noch offen'],
               'funding_round':['Pre-Seed','Seed','Series A','Series B oder später']}
    for goal in goals:
        if goal.key in choices:
            goal.kind, goal.choices = 'choice', choices[goal.key]
        if goal.key=='funding_amount':
            goal.kind, goal.unit = 'number', 'EUR'
        if goal.key in ('funding_amount','funding_round','use_of_funds','funding_timeline'):
            goal.condition = Condition(goal_key='fundraising',equals='Ja')
        if goal.key=='funding_timeline':
            goal.required = False
    return goals


# Cross-field checks keep conditions and scoring rules consistent with the configured answer types.
def validate_goal_config(goals: list[AnswerGoal], profile: MatchProfile):
    by_key = {g.key:g for g in goals}
    if len(by_key)!=len(goals) or not any(g.enabled and g.required for g in goals):
        raise ValueError('Unique goal keys and at least one enabled required goal are needed')
    prior = set()
    for goal in goals:
        if goal.condition:
            source=by_key.get(goal.condition.goal_key)
            if source is None or source.key not in prior or source.kind!='choice' or goal.condition.equals not in source.choices:
                raise ValueError('Conditions must refer to an earlier choice goal and one of its options')
            if goal.enabled and not source.enabled:
                raise ValueError('An enabled goal cannot depend on a disabled goal')
        prior.add(goal.key)
    if len({r.goal_key for r in profile.rules})!=len(profile.rules):
        raise ValueError('Only one match rule per goal is allowed')
    for rule in profile.rules:
        goal=by_key.get(rule.goal_key)
        if not goal:
            raise ValueError('Match rule references an unknown goal')
        if rule.operator=='one_of' and (goal.kind!='choice' or not set(rule.accepted)<=set(goal.choices)):
            raise ValueError('Match options must belong to the choice goal')
        if rule.operator=='range' and goal.kind!='number':
            raise ValueError('Range rules require a number goal')
