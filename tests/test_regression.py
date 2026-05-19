import pytest
from app.schemas import ContractChangeOutput, ContractChangeDetail, ContractAnalysisRequest

def test_pydantic_schema_serialization():
    """
    Regression test to ensure ContractChangeOutput schema structure serializes and validates correctly.
    Verifies that fields are locked and do not drift during future model refactoring.
    """
    change_detail = {
        "sections_changed": "Section 9.4 (b)",
        "topics_touched": ["Limitation of Liability", "Damages"],
        "summary_of_the_change": "Increased liability ceiling from $1M USD to $5M USD."
    }
    
    # 1. Validating input detail
    detail = ContractChangeDetail(**change_detail)
    assert detail.sections_changed == "Section 9.4 (b)"
    assert detail.topics_touched == ["Limitation of Liability", "Damages"]
    
    # 2. Validating complete output structure
    output = ContractChangeOutput(changes=[detail])
    serialized = output.model_dump()
    
    assert "changes" in serialized
    assert len(serialized["changes"]) == 1
    assert serialized["changes"][0]["sections_changed"] == "Section 9.4 (b)"
    assert isinstance(serialized["changes"][0]["topics_touched"], list)

def test_request_schema_base64_stripping_regression():
    """
    Regression test verifying that the Base64 validator handles raw payloads and data URLs,
    extracting the raw Base64 data correctly.
    """
    raw_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    data_uri = f"data:image/png;base64,{raw_base64}"
    
    # Ensure raw base64 and data URI validate to the exact same clean base64 string
    req1 = ContractAnalysisRequest(
        contract_original_base64=raw_base64,
        addendum_base64=raw_base64
    )
    req2 = ContractAnalysisRequest(
        contract_original_base64=data_uri,
        addendum_base64=data_uri
    )
    
    assert req1.contract_original_base64 == raw_base64
    assert req2.contract_original_base64 == raw_base64
    assert req2.addendum_base64 == raw_base64
