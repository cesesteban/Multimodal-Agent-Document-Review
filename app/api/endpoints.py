from fastapi import APIRouter, HTTPException, status, Depends
from app.schemas import ContractAnalysisRequest, ContractAnalysisResponse
from app.services.agents import execute_contract_comparison_pipeline
from app.api.dependencies import validate_api_key, get_target_language

router = APIRouter()

@router.post(
    "/compare",
    response_model=ContractAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Compare original contract and addendum via multi-agent vision",
    description="Processes Base64 images of documents, semantically maps clauses, and returns structured differences."
)
async def compare_contracts(
    payload: ContractAnalysisRequest,
    _auth: str = Depends(validate_api_key),
    language: str = Depends(get_target_language)
):
    """
    HTTP Router endpoint to run the multi-agent comparison pipeline on two contract documents.
    Authenticates requests via X-API-Key (if enabled) and respects user language selection.
    """
    try:
        # Run comparison pipeline with base64 strings and target language parameter
        structured_data, trace_id = await execute_contract_comparison_pipeline(
            original_b64=payload.contract_original_base64,
            addendum_b64=payload.addendum_base64,
            language=language
        )
        return ContractAnalysisResponse(
            success=True,
            data=structured_data,
            telemetry_trace_id=trace_id
        )
    except ValueError as val_err:
        # Catch and isolate validation and Base64 format errors as 422 Unprocessable Entity
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Schema or Base64 validation failure (Sentinel 422): {str(val_err)}"
        )
    except Exception as err:
        # Isolate deep LLM/tracing runtime failures and return HTTP 500
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Critical failure within the autonomous pipeline: {str(err)}"
        )
