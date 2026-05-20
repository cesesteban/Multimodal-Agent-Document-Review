import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.services.agents import (
    _step_multimodal_parsing,
    _step_contextualization_agent,
    _step_extraction_and_validation_agent,
    execute_contract_comparison_pipeline
)
from app.schemas import ContractChangeOutput, ContractChangeDetail
from app.services.cache import clear_pipeline_cache

from langchain_core.runnables import Runnable

class MockLLM(Runnable):
    def __init__(self, ainvoke_mock=None):
        super().__init__()
        object.__setattr__(self, "_ainvoke_mock", ainvoke_mock or AsyncMock())
        object.__setattr__(self, "with_structured_output", MagicMock(return_value=self))

    def invoke(self, input, config=None, **kwargs):
        pass

    async def ainvoke(self, input, config=None, **kwargs):
        return await self._ainvoke_mock(input, config, **kwargs)


@pytest.mark.asyncio
async def test_step_multimodal_parsing():
    """
    Unit test for the vision parsing stage to ensure messages are parsed correctly.
    """
    mock_response = MagicMock()
    mock_response.content = "OCR parsed raw content"
    mock_llm = MockLLM(AsyncMock(return_value=mock_response))
    
    original_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
    addendum_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
    
    result = await _step_multimodal_parsing(mock_llm, original_b64, addendum_b64)
    assert result == {
        "original_text": "OCR parsed raw content",
        "addendum_text": "OCR parsed raw content"
    }
    assert mock_llm._ainvoke_mock.call_count == 2

@pytest.mark.asyncio
async def test_step_contextualization_agent():
    """
    Unit test for the clause contextualization mapping agent.
    """
    mock_response = MagicMock()
    mock_response.content = "Clause 1 Original maps to Clause 2 Addendum"
    mock_llm = MockLLM(AsyncMock(return_value=mock_response))
    
    parsed_texts = {
        "original_text": "Raw original text",
        "addendum_text": "Raw addendum text"
    }
    
    result = await _step_contextualization_agent(mock_llm, parsed_texts)
    assert result == "Clause 1 Original maps to Clause 2 Addendum"
    assert mock_llm._ainvoke_mock.call_count == 1

@pytest.mark.asyncio
async def test_step_extraction_and_validation_agent():
    """
    Unit test for the extraction and schema enforcement stage.
    """
    mock_data = ContractChangeOutput(
        changes=[
            ContractChangeDetail(
                sections_changed="Clause 10",
                topics_touched=["Jurisdiction"],
                summary_of_the_change="Changed to Madrid, Spain"
            )
        ]
    )
    mock_structured_llm = MockLLM(AsyncMock(return_value=mock_data))
    mock_llm = MockLLM()
    mock_llm.with_structured_output.return_value = mock_structured_llm
    
    parsed_texts = {
        "original_text": "Raw original text",
        "addendum_text": "Raw addendum text"
    }
    context_map = "Clause map index"
    
    result = await _step_extraction_and_validation_agent(mock_llm, parsed_texts, context_map, "Spanish")
    assert result == mock_data
    assert mock_llm.with_structured_output.call_count == 1
    assert mock_structured_llm._ainvoke_mock.call_count == 1

@pytest.mark.asyncio
@patch("app.services.agents._step_multimodal_parsing", new_callable=AsyncMock)
@patch("app.services.agents._step_contextualization_agent", new_callable=AsyncMock)
@patch("app.services.agents._step_extraction_and_validation_agent", new_callable=AsyncMock)
async def test_execute_contract_comparison_pipeline(mock_step3, mock_step2, mock_step1):
    """
    Unit test for the orchestrator pipeline coordinating vision parsing, mapping, and structure extraction.
    """
    original_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
    addendum_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
    
    mock_step1.return_value = {
        "original_text": "parsed original OCR content",
        "addendum_text": "parsed addendum OCR content"
    }
    mock_step2.return_value = "clause context mapping index"
    
    mock_data = ContractChangeOutput(changes=[])
    mock_step3.return_value = mock_data
    
    with patch("app.services.agents.settings") as mock_settings:
        mock_settings.OPENAI_MODEL_NAME = "gpt-4o"
        mock_settings.OPENAI_API_KEY.get_secret_value.return_value = "fake-key"
        
        clear_pipeline_cache()  # Clear cache to guarantee first execution runs
        result, trace_id = await execute_contract_comparison_pipeline(original_b64, addendum_b64, "Spanish")
        assert result == mock_data
        assert trace_id == "managed-by-observe-v4"

@pytest.mark.asyncio
@patch("app.services.agents._step_multimodal_parsing", new_callable=AsyncMock)
@patch("app.services.agents._step_contextualization_agent", new_callable=AsyncMock)
@patch("app.services.agents._step_extraction_and_validation_agent", new_callable=AsyncMock)
async def test_execute_contract_comparison_pipeline_caching(mock_step3, mock_step2, mock_step1):
    """
    Verifies that the contract comparison pipeline correctly caches results on identical inputs
    and returns a cached trace ID, preventing subsequent LLM agent executions.
    """
    original_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
    addendum_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
    
    mock_step1.return_value = {
        "original_text": "parsed original OCR content",
        "addendum_text": "parsed addendum OCR content"
    }
    mock_step2.return_value = "clause context mapping index"
    
    mock_data = ContractChangeOutput(changes=[])
    mock_step3.return_value = mock_data
    
    with patch("app.services.agents.settings") as mock_settings:
        mock_settings.OPENAI_MODEL_NAME = "gpt-4o"
        mock_settings.OPENAI_API_KEY.get_secret_value.return_value = "fake-key"
        
        clear_pipeline_cache()
        
        # 1. First execution should run agents and cache the result
        result1, trace_id1 = await execute_contract_comparison_pipeline(original_b64, addendum_b64, "Spanish")
        assert result1 == mock_data
        assert trace_id1 == "managed-by-observe-v4"
        assert mock_step1.call_count == 1
        assert mock_step2.call_count == 1
        assert mock_step3.call_count == 1
        
        # 2. Second execution with the same inputs should hit the cache
        # (and return cached- prefixed trace ID without invoking agents again)
        result2, trace_id2 = await execute_contract_comparison_pipeline(original_b64, addendum_b64, "Spanish")
        assert result2 == mock_data
        assert trace_id2 == "cached-managed-by-observe-v4"
        assert mock_step1.call_count == 1
        assert mock_step2.call_count == 1
        assert mock_step3.call_count == 1




