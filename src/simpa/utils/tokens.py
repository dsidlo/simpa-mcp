"""Token counting utilities for LLM context management."""

import time
from dataclasses import dataclass
from typing import Any

import structlog
import tiktoken

from simpa.config import settings
from simpa.utils.logging import get_logger, log_trace

logger = get_logger(__name__)

# Global encoder (lazy loaded)
_encoder = None


def get_encoder(model: str = "gpt-4") -> tiktoken.Encoding:
    """Get tiktoken encoder for a model.
    
    Args:
        model: Model name (default: gpt-4)
        
    Returns:
        tiktoken.Encoding instance
    """
    global _encoder
    if _encoder is None:
        try:
            _encoder = tiktoken.encoding_for_model(model)
        except KeyError:
            # Fallback to cl100k_base (used by GPT-4, GPT-3.5-turbo, etc.)
            _encoder = tiktoken.get_encoding("cl100k_base")
    return _encoder


def count_tokens(text: str, model: str = "gpt-4") -> int:
    """Count tokens in text using tiktoken.
    
    Args:
        text: Text to count
        model: Model name for encoding
        
    Returns:
        Token count
    """
    if not text:
        return 0
    encoder = get_encoder(model)
    return len(encoder.encode(text))


def count_prompt_tokens(original_prompt: str, refined_prompt: str, model: str = "gpt-4") -> tuple[int, int, int]:
    """Count tokens for a prompt record.
    
    Args:
        original_prompt: Original prompt text
        refined_prompt: Refined prompt text
        model: Model name
        
    Returns:
        Tuple of (original_tokens, refined_tokens, total_tokens)
    """
    orig_tokens = count_tokens(original_prompt, model)
    ref_tokens = count_tokens(refined_prompt, model)
    total = orig_tokens + ref_tokens
    return orig_tokens, ref_tokens, total


@dataclass
class TokenCounts:
    """Token count results for a prompt."""
    prompt_id: str
    original_tokens: int
    refined_tokens: int
    total_tokens: int
    original_prompt_length: int
    refined_prompt_length: int


def log_token_counts(prompts: list[Any], model: str = "gpt-4") -> list[TokenCounts]:
    """Log token counts for a list of prompts.
    
    Args:
        prompts: List of prompt objects (should have prompt_key, original_prompt, refined_prompt)
        model: Model name
        
    Returns:
        List of TokenCounts
    """
    log_start = time.monotonic()
    results: list[TokenCounts] = []
    total_all_tokens = 0
    
    log_trace(logger, "log_token_counts_start", prompt_count=len(prompts), model=model)
    
    for prompt in prompts:
        orig_tokens, ref_tokens, total = count_prompt_tokens(
            getattr(prompt, "original_prompt", "") or "",
            getattr(prompt, "refined_prompt", "") or "",
            model
        )
        
        prompt_id = str(getattr(prompt, "prompt_key", "unknown"))
        orig_len = len(getattr(prompt, "original_prompt", "") or "")
        ref_len = len(getattr(prompt, "refined_prompt", "") or "")
        
        results.append(TokenCounts(
            prompt_id=prompt_id,
            original_tokens=orig_tokens,
            refined_tokens=ref_tokens,
            total_tokens=total,
            original_prompt_length=orig_len,
            refined_prompt_length=ref_len,
        ))
        
        total_all_tokens += total
        
        log_trace(
            logger,
            "token_count_single",
            prompt_id=prompt_id,
            original_tokens=orig_tokens,
            refined_tokens=ref_tokens,
            total_tokens=total,
            original_length=orig_len,
            refined_length=ref_len,
        )
    
    log_trace(
        logger,
        "token_counts_summary",
        prompt_count=len(prompts),
        total_tokens=total_all_tokens,
        avg_tokens_per_prompt=total_all_tokens // max(len(prompts), 1),
        model=model,
        duration_ms=(time.monotonic() - log_start) * 1000,
    )
    
    log_trace(logger, "log_token_counts_complete", count=len(results), total_tokens=total_all_tokens)
    
    return results


def calculate_context_size(
    prompts: list[Any],
    include_original: bool = True,
    include_refined: bool = True,
    model: str = "gpt-4"
) -> dict[str, Any]:
    """Calculate total context size for prompts.
    
    Args:
        prompts: List of prompts
        include_original: Whether to include original prompt text
        include_refined: Whether to include refined prompt text
        model: Model name
        
    Returns:
        Dictionary with token statistics
    """
    total = 0
    per_prompt: list[dict[str, Any]] = []
    
    for prompt in prompts:
        orig_toks = count_tokens(getattr(prompt, "original_prompt", "") or "", model)
        ref_toks = count_tokens(getattr(prompt, "refined_prompt", "") or "", model)
        
        prompt_total = 0
        if include_original:
            prompt_total += orig_toks
        if include_refined:
            prompt_total += ref_toks
        
        total += prompt_total
        
        per_prompt.append({
            "prompt_id": str(getattr(prompt, "prompt_key", "unknown")),
            "original_tokens": orig_toks if include_original else 0,
            "refined_tokens": ref_toks if include_refined else 0,
            "total": prompt_total,
        })
    
    return {
        "total_tokens": total,
        "prompt_count": len(prompts),
        "avg_tokens_per_prompt": total // max(len(prompts), 1),
        "model": model,
        "include_original": include_original,
        "include_refined": include_refined,
        "per_prompt": per_prompt,
    }


# Back-compat alias for older code
estimate_token_count = count_tokens
