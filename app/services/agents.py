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

@observe(name="Pipeline - Compare Contracts")
async def execute_contract_comparison_pipeline(original_b64: str, addendum_b64: str, language: str = "Spanish"):
    """
    Main asynchronous orchestration pipeline for comparing contracts.
    Coordinates Vision extraction, contextual clause mapping, and structured semantic diff generation.
    All trace information is propagated natively into Langfuse.
    """
    cache_key = compute_pipeline_cache_key(original_b64, addendum_b64, language)
    cached_result = get_cached_pipeline_result(cache_key)
    if cached_result is not None:
        data, trace_id = cached_result
        return data, f"cached-{trace_id}"
        
    # Initialize low-temperature deterministic ChatOpenAI model
    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL_NAME,
        api_key=settings.OPENAI_API_KEY.get_secret_value(),
        temperature=0.0
    )
    
    # Step 1: Extract textual data from images using vision capabilities
    parsed_texts = await _step_multimodal_parsing(llm, original_b64, addendum_b64)
    
    # Step 2: Establish connection map and context relationships between clauses
    context_map = await _step_contextualization_agent(llm, parsed_texts)
    
    # Step 3 & 4: Extract changes and validate output strictly against the ContractChangeOutput schema
    structured_output = await _step_extraction_and_validation_agent(llm, parsed_texts, context_map, language)
    
    set_cached_pipeline_result(cache_key, structured_output, "managed-by-observe-v4")
    return structured_output, "managed-by-observe-v4"


@observe(as_type="generation", name="Step 1 - Multimodal Parsing (Vision)")
async def _step_multimodal_parsing(llm: ChatOpenAI, original_b64: str, addendum_b64: str) -> dict:
    """
    Multimodal vision parser extracting raw textual data from base64 document images.
    """
    handler = CallbackHandler()
    config = {"callbacks": [handler]}
    
    messages = [
        SystemMessage(content="You are an expert in advanced OCR. Transcribe the text faithfully and exactly, respecting the numerical structure."),
        HumanMessage(content=[
            {"type": "text", "text": "Transcribe this ORIGINAL CONTRACT exactly:"},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{original_b64}", "detail": "high"}}
        ]),
        HumanMessage(content=[
            {"type": "text", "text": "Transcribe this ADDENDUM / AMENDMENT exactly:"},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{addendum_b64}", "detail": "high"}}
        ])
    ]
    response = await llm.ainvoke(messages, config=config)
    return {"content": response.content}

@observe(as_type="generation", name="Step 2 - Contextualization Agent")
async def _step_contextualization_agent(llm: ChatOpenAI, parsed_texts: dict) -> str:
    """
    Contextualizer agent identifying matching sections and building a legal clause comparison index map.
    """
    handler = CallbackHandler()
    config = {"callbacks": [handler]}
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a Legal Contextualization Agent. Map the equivalent clauses between both documents."),
        ("user", "Content extracted from the documents: {texts}")
    ])
    chain = prompt | llm
    response = await chain.ainvoke({"texts": parsed_texts["content"]}, config=config)
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
            "You are a High Precision Extraction Agent. Isolate exclusively the additions, deletions, or modifications. "
            "You MUST synthesize and write all descriptions, sections, and summaries strictly in the requested target language: {language}."
        )),
        ("user", "Base Texts: {texts}\n\nContextual Map: {context_map}")
    ])
    
    # Force direct Pydantic structure parsing
    structured_llm = llm.with_structured_output(ContractChangeOutput)
    chain = prompt | structured_llm
    
    output = await chain.ainvoke({
        "texts": parsed_texts["content"],
        "context_map": context_map,
        "language": language
    }, config=config)
    
    return output
