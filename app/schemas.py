from pydantic import BaseModel, Field, field_validator
from typing import List
import base64
import re

class ContractAnalysisRequest(BaseModel):
    """
    Data contract representing the client's request payload containing original contract and addendum images.
    Includes custom field validation to verify syntactic base64 compliance.
    """
    contract_original_base64: str = Field(
        ..., 
        description="Base64 encoded string of the original contract image (JPEG/PNG)."
    )
    addendum_base64: str = Field(
        ..., 
        description="Base64 encoded string of the addendum/amendment image (JPEG/PNG)."
    )

    @field_validator("contract_original_base64", "addendum_base64")
    @classmethod
    def validate_base64(cls, value: str) -> str:
        """
        Validates that the provided string is a valid Base64 payload.
        Strips standard data URL headers (e.g. data:image/png;base64,...) if present.
        """
        cleaned_value = value
        if "," in value:
            # Strip potential data URI prefix
            parts = value.split(",", 1)
            cleaned_value = parts[1]
            
        # Remove any whitespace characters
        cleaned_value = re.sub(r"\s+", "", cleaned_value)
        
        if not cleaned_value:
            raise ValueError("The Base64 string cannot be empty.")
            
        try:
            # Attempt parsing base64 string strictly
            decoded_bytes = base64.b64decode(cleaned_value, validate=True)
            if len(decoded_bytes) == 0:
                raise ValueError("Decoded Base64 content is empty.")
        except Exception:
            raise ValueError("Invalid Base64 syntax. The string is not properly encoded in Base64.")
            
        return cleaned_value

class ContractChangeDetail(BaseModel):
    """
    Structured model holding detailed semantic changes for a single modified section or clause.
    """
    sections_changed: str = Field(
        ..., 
        description="Exact identification of the section, clause, or paragraph modified in both documents."
    )
    topics_touched: List[str] = Field(
        ..., 
        description="List of legal topics affected by the change (e.g., 'Indemnity', 'Deadlines', 'Jurisdiction')."
    )
    summary_of_the_change: str = Field(
        ..., 
        description="Detailed semantic summary describing what was changed, removed, or added."
    )

class ContractChangeOutput(BaseModel):
    """
    Structured output from the agent pipeline summarizing all changes identified in the contract comparison.
    """
    changes: List[ContractChangeDetail] = Field(
        ..., 
        description="Collection of all identified changes between the documents."
    )

class ContractAnalysisResponse(BaseModel):
    """
    The final API response payload structure containing status, structured analysis, and trace ID.
    """
    success: bool
    data: ContractChangeOutput
    telemetry_trace_id: str = Field(
        ..., 
        description="The Langfuse trace ID associated with this analysis for debugging and auditing."
    )
