import asyncio
from langfuse import observe
from langfuse.langchain import CallbackHandler
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage
from app.config import settings
from app.schemas import ContractChangeOutput
from app.services.cache import (
    compute_pipeline_cache_key,
    get_cached_pipeline_result,
    set_cached_pipeline_result
)
from app.logging import logger

@observe(name="Pipeline - Compare Contracts")
async def execute_contract_comparison_pipeline(original_b64: str, addendum_b64: str, language: str = "Spanish"):
    """
    Main asynchronous orchestration pipeline for comparing contracts.
    Coordinates Vision extraction, contextual clause mapping, and structured semantic diff generation.
    All trace information is propagated natively into Langfuse.
    """
    cache_key = compute_pipeline_cache_key(original_b64, addendum_b64, language)
    logger.info(f"Initializing contract comparison pipeline. Cache Key: {cache_key} - Language: {language}")
    
    cached_result = get_cached_pipeline_result(cache_key)
    if cached_result is not None:
        logger.info(f"Cache Hit for key: {cache_key}. Bypassing LLM agent pipeline execution.")
        data, trace_id = cached_result
        return data, f"cached-{trace_id}"
        
    logger.info(f"Cache Miss for key: {cache_key}. Executing multi-agent comparison chain.")
    try:
        # Initialize low-temperature deterministic ChatOpenAI model
        llm = ChatOpenAI(
            model=settings.OPENAI_MODEL_NAME,
            api_key=settings.OPENAI_API_KEY.get_secret_value(),
            temperature=0.0
        )
        
        # Step 1: Extract textual data from images using vision capabilities concurrently
        logger.info("Executing Agent Step 1: Parallel Multimodal OCR / Vision Parsing...")
        parsed_texts = await _step_multimodal_parsing(llm, original_b64, addendum_b64)
        logger.info("Agent Step 1 Completed successfully. Both documents transcribed.")
        
        # Step 2: Establish connection map and context relationships between clauses
        logger.info("Executing Agent Step 2: Contextual Clause Mapping...")
        context_map = await _step_contextualization_agent(llm, parsed_texts)
        logger.info("Agent Step 2 Completed successfully.")
        
        # Step 3 & 4: Extract changes and validate output strictly against the ContractChangeOutput schema
        logger.info(f"Executing Agent Step 3 & 4: Extraction & Validation of changes in {language}...")
        structured_output = await _step_extraction_and_validation_agent(llm, parsed_texts, context_map, language)
        logger.info("Agent Step 3 & 4 Completed successfully. Output schema validated.")
        
        set_cached_pipeline_result(cache_key, structured_output, "managed-by-observe-v4")
        logger.info(f"Pipeline finished successfully. Result cached under key: {cache_key}")
        return structured_output, "managed-by-observe-v4"
    except Exception as exc:
        logger.error(f"Critical error occurred inside contract comparison pipeline: {str(exc)}", exc_info=True)
        raise exc


@observe(as_type="generation", name="OCR Transcription Step")
async def _transcribe_document(llm: ChatOpenAI, base64_image: str, document_role: str) -> str:
    """
    Helper function to run isolated OCR on a single document image.
    """
    handler = CallbackHandler()
    config = {"callbacks": [handler]}
    
    messages = [
        SystemMessage(content=(
            "You are an expert in advanced OCR. Transcribe all text from the provided document image "
            "faithfully, exactly, and completely. Keep the layout, section numbers, titles, and values intact."
        )),
        HumanMessage(content=[
            {"type": "text", "text": f"Transcribe this {document_role} image exactly:"},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}", "detail": "high"}}
        ])
    ]
    response = await llm.ainvoke(messages, config=config)
    return response.content


async def _step_multimodal_parsing(llm: ChatOpenAI, original_b64: str, addendum_b64: str) -> dict:
    """
    Orchestrates OCR transcription of both original and addendum documents concurrently.
    """
    original_text, addendum_text = await asyncio.gather(
        _transcribe_document(llm, original_b64, "ORIGINAL CONTRACT"),
        _transcribe_document(llm, addendum_b64, "ADDENDUM / AMENDMENT")
    )
    return {
        "original_text": original_text,
        "addendum_text": addendum_text
    }


@observe(as_type="generation", name="Step 2 - Contextualization Agent")
async def _step_contextualization_agent(llm: ChatOpenAI, parsed_texts: dict) -> str:
    """
    Contextualizer agent identifying matching sections and building a legal clause comparison index map.
    """
    handler = CallbackHandler()
    config = {"callbacks": [handler]}
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", (
            "You are an expert Legal Contextualization Agent.\n"
            "Your task is to map corresponding clauses and sections between the ORIGINAL CONTRACT and the ADDENDUM / AMENDMENT.\n"
            "Identify matches by section numbers, titles, and topics. Create a clear mapping of which sections in the original contract are modified, added, or referenced by the addendum."
        )),
        ("user", "ORIGINAL CONTRACT:\n{original_text}\n\nADDENDUM / AMENDMENT:\n{addendum_text}")
    ])
    chain = prompt | llm
    response = await chain.ainvoke({
        "original_text": parsed_texts["original_text"],
        "addendum_text": parsed_texts["addendum_text"]
    }, config=config)
    return response.content


@observe(as_type="generation", name="Step 3 and 4 - Extraction and Validation Agent")
async def _step_extraction_and_validation_agent(llm: ChatOpenAI, parsed_texts: dict, context_map: str, language: str) -> ContractChangeOutput:
    """
    Extractor and schema enforcement agent returning strictly validated structured changes in the target language.
    """
    handler = CallbackHandler()
    config = {"callbacks": [handler]}
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", (
            "You are a High Precision Legal Extraction Agent.\n"
            "Your task is to analyze the ORIGINAL CONTRACT, the ADDENDUM / AMENDMENT, and their CONTEXTUAL CLAUSE MAP to extract the precise changes.\n"
            "CRITICAL RULES:\n"
            "1. Identify the exact direction of the change: from the Original Contract terms TO the Addendum/Amendment terms.\n"
            "2. Do not invent, hallucinate, or reverse the values. If the Original says '12 months' and the Addendum says '24 months', the change is '12 months to 24 months'.\n"
            "3. Synthesize and write all descriptions, sections, and summaries strictly in the requested target language: {language}.\n"
            "4. Be extremely precise with numbers, currencies, dates, and names."
        )),
        ("user", (
            "ORIGINAL CONTRACT:\n{original_text}\n\n"
            "ADDENDUM / AMENDMENT:\n{addendum_text}\n\n"
            "CONTEXTUAL CLAUSE MAP:\n{context_map}"
        ))
    ])
    
    # Force direct Pydantic structure parsing
    structured_llm = llm.with_structured_output(ContractChangeOutput)
    chain = prompt | structured_llm
    
    output = await chain.ainvoke({
        "original_text": parsed_texts["original_text"],
        "addendum_text": parsed_texts["addendum_text"],
        "context_map": context_map,
        "language": language
    }, config=config)
    
    return output
