"""
Token Optimizer - Prompt compression, context window management, and cost tracking.

Optimizes token usage through intelligent prompt compression, context pruning,
response caching, and real-time cost monitoring.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Optional

from mimo_devflow.utils.logger import get_logger

logger = get_logger("optimizer")


@dataclass
class TokenUsage:
    """Token usage record."""

    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    compressed_tokens_saved: int = 0
    timestamp: float = field(default_factory=time.time)
    model: str = ""
    task_id: str = ""
    cost: float = 0.0


@dataclass
class CostBreakdown:
    """Detailed cost breakdown."""

    total_cost: float = 0.0
    input_cost: float = 0.0
    output_cost: float = 0.0
    cached_savings: float = 0.0
    compression_savings: float = 0.0
    requests: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0


class LRUCache:
    """Simple LRU cache for response caching."""

    def __init__(self, max_size: int = 1000, ttl: float = 3600.0):
        self._cache: OrderedDict[str, tuple[str, float]] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[str]:
        """Get a cached value if it exists and hasn't expired."""
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < self._ttl:
                self._cache.move_to_end(key)
                self._hits += 1
                return value
            else:
                del self._cache[key]
        self._misses += 1
        return None

    def set(self, key: str, value: str) -> None:
        """Cache a value."""
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = (value, time.time())
        if len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    @property
    def size(self) -> int:
        return len(self._cache)


class TokenOptimizer:
    """Token usage optimizer with compression, caching, and cost tracking.

    Features:
        - Prompt compression by removing redundancy
        - Context window management with intelligent pruning
        - Response caching with TTL
        - Real-time cost tracking per model
        - Budget enforcement

    Example:
        >>> optimizer = TokenOptimizer(budget=100000)
        >>> compressed = optimizer.compress_prompt(long_prompt)
        >>> print(f"Saved {optimizer.tokens_saved} tokens")
    """

    def __init__(
        self,
        budget: Optional[int] = None,
        compression_enabled: bool = True,
        cache_enabled: bool = True,
        cache_ttl: float = 3600.0,
        cache_max_size: int = 1000,
        cost_per_1k_input: float = 0.001,
        cost_per_1k_output: float = 0.002,
    ):
        self.budget = budget
        self.compression_enabled = compression_enabled
        self.cache_enabled = cache_enabled
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output

        self._cache = LRUCache(max_size=cache_max_size, ttl=cache_ttl) if cache_enabled else None
        self._usage_history: list[TokenUsage] = []
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_cached_tokens = 0
        self._total_compressed_saved = 0

    def compress_prompt(self, prompt: str) -> str:
        """Compress a prompt by removing redundancy while preserving meaning.

        Techniques:
        - Collapse multiple whitespace/newlines
        - Remove filler phrases
        - Deduplicate repeated sentences
        - Trim verbose instructions

        Args:
            prompt: Original prompt text

        Returns:
            Compressed prompt text
        """
        if not self.compression_enabled:
            return prompt

        original_len = len(prompt)
        compressed = prompt

        # Collapse whitespace
        compressed = re.sub(r"\n{3,}", "\n\n", compressed)
        compressed = re.sub(r"[ \t]{2,}", " ", compressed)
        compressed = re.sub(r" +\n", "\n", compressed)

        # Remove common filler phrases (conservative)
        fillers = [
            r"\bPlease note that\b",
            r"\bIt is important to\b",
            r"\bI would like you to\b",
            r"\bI want you to\b",
            r"\bCan you please\b",
            r"\bMake sure to\b",
            r"\bAs mentioned before,?\b",
            r"\bIn order to\b",
            r"\bFor the purpose of\b",
        ]
        for filler in fillers:
            compressed = re.sub(filler, "", compressed, flags=re.IGNORECASE)

        # Deduplicate exact repeated lines
        lines = compressed.split("\n")
        seen = set()
        unique_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped and stripped in seen:
                continue
            if stripped:
                seen.add(stripped)
            unique_lines.append(line)
        compressed = "\n".join(unique_lines)

        # Clean up artifacts
        compressed = re.sub(r"  +", " ", compressed)
        compressed = compressed.strip()

        tokens_saved = self._estimate_tokens(prompt) - self._estimate_tokens(compressed)
        self._total_compressed_saved += max(tokens_saved, 0)

        logger.debug(
            "Compressed prompt: %d -> %d chars (%d tokens saved)",
            original_len, len(compressed), max(tokens_saved, 0),
        )

        return compressed

    async def compress_messages(self, messages: list) -> list:
        """Compress a list of messages for context window management.

        Prunes older messages if approaching context limits, and compresses
        system prompts.

        Args:
            messages: List of Message objects

        Returns:
            Compressed list of messages
        """
        if not self.compression_enabled:
            return messages

        # Don't compress system messages or recent messages
        if len(messages) <= 4:
            return messages

        result = []
        system_msgs = [m for m in messages if m.role == "system"]
        other_msgs = [m for m in messages if m.role != "system"]

        # Always include system messages (compressed)
        for msg in system_msgs:
            compressed_msg = msg
            if hasattr(msg, "content") and isinstance(msg.content, str):
                compressed_msg = type(msg)(
                    role=msg.role,
                    content=self.compress_prompt(msg.content),
                    **{k: v for k, v in msg.__dict__.items() if k not in ("role", "content", "timestamp")},
                )
            result.append(compressed_msg)

        # Keep the most recent messages, compress older ones
        max_history = 20  # Keep last 20 messages
        if len(other_msgs) > max_history:
            # Keep first 2 (establish context) and last max_history-2
            keep = other_msgs[:2] + other_msgs[-(max_history - 2):]
            logger.info("Pruned %d old messages from context", len(other_msgs) - len(keep))
        else:
            keep = other_msgs

        result.extend(keep)
        return result

    def check_cache(self, prompt: str, model: str = "") -> Optional[str]:
        """Check if a response is cached for this prompt.

        Args:
            prompt: The prompt to check
            model: Model name for cache key

        Returns:
            Cached response or None
        """
        if not self._cache:
            return None
        cache_key = self._cache_key(prompt, model)
        result = self._cache.get(cache_key)
        if result:
            cached_tokens = self._estimate_tokens(result)
            self._total_cached_tokens += cached_tokens
            logger.debug("Cache hit: saved %d tokens", cached_tokens)
        return result

    def cache_response(self, prompt: str, response: str, model: str = "") -> None:
        """Cache a response for future reuse.

        Args:
            prompt: The prompt
            response: The response to cache
            model: Model name for cache key
        """
        if not self._cache:
            return
        cache_key = self._cache_key(prompt, model)
        self._cache.set(cache_key, response)

    def record_usage(
        self,
        input_tokens: int,
        output_tokens: int,
        model: str = "",
        task_id: str = "",
        cached_tokens: int = 0,
    ) -> TokenUsage:
        """Record token usage for tracking.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            model: Model used
            task_id: Task identifier
            cached_tokens: Tokens served from cache

        Returns:
            TokenUsage record
        """
        cost = (
            (input_tokens * self.cost_per_1k_input / 1000)
            + (output_tokens * self.cost_per_1k_output / 1000)
        )

        usage = TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            model=model,
            task_id=task_id,
            cost=cost,
        )

        self._usage_history.append(usage)
        self._total_input_tokens += input_tokens
        self._total_output_tokens += output_tokens

        if self.budget and self.total_tokens > self.budget:
            logger.warning(
                "Token budget exceeded! Used %d / %d tokens",
                self.total_tokens,
                self.budget,
            )

        return usage

    def get_cost_breakdown(self, model: Optional[str] = None) -> CostBreakdown:
        """Get detailed cost breakdown.

        Args:
            model: Optional model filter

        Returns:
            CostBreakdown with detailed costs
        """
        records = self._usage_history
        if model:
            records = [u for u in records if u.model == model]

        breakdown = CostBreakdown()
        for u in records:
            breakdown.total_cost += u.cost
            breakdown.input_cost += u.input_tokens * self.cost_per_1k_input / 1000
            breakdown.output_cost += u.output_tokens * self.cost_per_1k_output / 1000
            breakdown.total_input_tokens += u.input_tokens
            breakdown.total_output_tokens += u.output_tokens
            breakdown.requests += 1

        breakdown.cached_savings = self._total_cached_tokens * self.cost_per_1k_input / 1000
        breakdown.compression_savings = self._total_compressed_saved * self.cost_per_1k_input / 1000

        return breakdown

    @property
    def total_tokens(self) -> int:
        """Total tokens used (input + output)."""
        return self._total_input_tokens + self._total_output_tokens

    @property
    def total_cost(self) -> float:
        """Total cost incurred."""
        return sum(u.cost for u in self._usage_history)

    @property
    def tokens_saved(self) -> int:
        """Total tokens saved through compression and caching."""
        return self._total_compressed_saved + self._total_cached_tokens

    @property
    def budget_remaining(self) -> Optional[int]:
        """Remaining token budget, or None if no budget set."""
        if self.budget is None:
            return None
        return max(0, self.budget - self.total_tokens)

    @property
    def cache_stats(self) -> dict[str, Any]:
        """Cache performance statistics."""
        if not self._cache:
            return {"enabled": False}
        return {
            "enabled": True,
            "size": self._cache.size,
            "hits": self._cache._hits,
            "misses": self._cache._misses,
            "hit_rate": self._cache.hit_rate,
            "tokens_saved": self._total_cached_tokens,
        }

    def _cache_key(self, prompt: str, model: str) -> str:
        """Generate cache key from prompt and model."""
        content = f"{model}:{prompt}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count (rough: ~4 chars per token for English)."""
        return max(1, len(text) // 4)

    def reset(self) -> None:
        """Reset all tracking counters."""
        self._usage_history.clear()
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_cached_tokens = 0
        self._total_compressed_saved = 0
