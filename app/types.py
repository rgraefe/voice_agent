"""Shared annotations for dynamic documents at persistence and HTTP boundaries."""
from typing import Any, Literal, TypeAlias

# Documents contain heterogeneous model dumps. Validate them with the relevant
# Pydantic model when entering the domain; this alias does not validate JSON.
Document: TypeAlias = dict[str, Any]
TopicKey: TypeAlias = Literal['startup', 'team', 'product', 'traction', 'market', 'funding', 'next_step']
InterviewMode: TypeAlias = Literal['voice', 'simulation']
