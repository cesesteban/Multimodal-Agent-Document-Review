import hashlib
from typing import Dict, Tuple, Optional
from app.schemas import ContractChangeOutput

# In-memory database representation for the pipeline execution results.
# Maps a SHA256 key of inputs to a tuple of (ContractChangeOutput, trace_id)
_pipeline_cache: Dict[str, Tuple[ContractChangeOutput, str]] = {}

def compute_pipeline_cache_key(original_b64: str, addendum_b64: str, language: str) -> str:
    """
    Computes a deterministic SHA256 digest of the request inputs.
    """
    hasher = hashlib.sha256()
    hasher.update(original_b64.encode("utf-8"))
    hasher.update(addendum_b64.encode("utf-8"))
    hasher.update(language.encode("utf-8"))
    return hasher.hexdigest()

def get_cached_pipeline_result(key: str) -> Optional[Tuple[ContractChangeOutput, str]]:
    """
    Retrieves a cached comparison result if present.
    """
    return _pipeline_cache.get(key)

def set_cached_pipeline_result(key: str, result: ContractChangeOutput, trace_id: str) -> None:
    """
    Stores a comparison result in the cache.
    """
    _pipeline_cache[key] = (result, trace_id)

def clear_pipeline_cache() -> None:
    """
    Flushes all entries from the in-memory cache. Useful for testing isolation.
    """
    _pipeline_cache.clear()
