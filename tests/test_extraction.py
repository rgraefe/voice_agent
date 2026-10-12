from __future__ import annotations
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from app.models import AgentConfig
from app.interview import create_interview
from voice.extraction import Extractor


@pytest.mark.asyncio
async def test_goal_tool_contract_prevents_obsolete_fact_fields() -> None:
    # The model and backend share the same narrow answer contract.
    extractor=Extractor('test-key','gpt-4.1-mini')
    response=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=[
        SimpleNamespace(function=SimpleNamespace(arguments=json.dumps({
            'answers':[{'goal_key':'startup_name','status':'answered','value':'Lumio','quote':'Lumio','choice_value':None,'number_value':None}],
            'acknowledgment':'','confirmed_summary':False}))) ]))],usage=None)
    create=AsyncMock(return_value=response)
    setattr(extractor.client.chat.completions, 'create', create)
    try:
        state=create_interview('test',AgentConfig(),'voice')
        result,_=await extractor.extract('Lumio',state)
        params=create.call_args.kwargs['tools'][0]['function']['parameters']
        assert set(params['properties'])=={'answers','acknowledgment','confirmed_summary'}
        assert params['additionalProperties'] is False
        assert result.answers[0].value=='Lumio'
        assert set(result.model_dump()) == {"answers", "acknowledgment", "confirmed_summary"}
    finally:
        await extractor.client.close()
