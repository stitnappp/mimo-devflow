"""
Smart Model Router - Automatically selects the optimal MiMo model based on task type.

Analyzes input characteristics (text, images, audio, code) and routes to the
best-suited model with cost/quality trade-off optimization.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from mimo_devflow.agent import AgentResponse, MimoAgent
from mimo_devflow.config import MimoConfig
from mimo_devflow.optimizer import TokenOptimizer
from mimo_devflow.utils.logger import get_logger

logger = get_logger("router")


class TaskType(str, enum.Enum):
    """Classification of task types."""

    TEXT_GENERATION = "text_generation"
    TEXT_ANALYSIS = "text_analysis"
    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    VISION = "vision"
    MULTIMODAL = "multimodal"
    SPEECH = "speech"
    TRANSLATION = "translation"
    SUMMARIZATION = "summarization"
    QUESTION_ANSWERING = "question_answering"
    MATH = "math"
    REASONING = "reasoning"
    CREATIVE_WRITING = "creative_writing"
    DATA_ANALYSIS = "data_analysis"
    CONVERSATION = "conversation"


@dataclass
class ModelCapabilities:
    """Capabilities and characteristics of a MiMo model."""

    name: str
    max_tokens: int
    supports_vision: bool = False
    supports_tools: bool = True
    supports_streaming: bool = True
    supports_audio: bool = False
    cost_per_1k_input: float = 0.001
    cost_per_1k_output: float = 0.002
    speed_rating: float = 1.0  # 1.0 = baseline, higher = faster
    quality_rating: float = 1.0  # 1.0 = baseline, higher = better
    strengths: list[TaskType] = field(default_factory=list)


# Model registry
MODELS: dict[str, ModelCapabilities] = {
    "mimo-v2.5-pro": ModelCapabilities(
        name="mimo-v2.5-pro",
        max_tokens=32768,
        supports_vision=False,
        supports_tools=True,
        supports_streaming=True,
        cost_per_1k_input=0.001,
        cost_per_1k_output=0.002,
        speed_rating=1.0,
        quality_rating=1.0,
        strengths=[
            TaskType.TEXT_GENERATION,
            TaskType.CODE_GENERATION,
            TaskType.CODE_REVIEW,
            TaskType.REASONING,
            TaskType.MATH,
            TaskType.QUESTION_ANSWERING,
            TaskType.DATA_ANALYSIS,
        ],
    ),
    "mimo-v2.5-vl": ModelCapabilities(
        name="mimo-v2.5-vl",
        max_tokens=16384,
        supports_vision=True,
        supports_tools=True,
        supports_streaming=True,
        cost_per_1k_input=0.002,
        cost_per_1k_output=0.003,
        speed_rating=0.8,
        quality_rating=1.1,
        strengths=[
            TaskType.VISION,
            TaskType.MULTIMODAL,
            TaskType.DATA_ANALYSIS,
        ],
    ),
    "mimo-tts": ModelCapabilities(
        name="mimo-tts",
        max_tokens=4096,
        supports_vision=False,
        supports_tools=False,
        supports_streaming=True,
        supports_audio=True,
        cost_per_1k_input=0.0005,
        cost_per_1k_output=0.001,
        speed_rating=1.5,
        quality_rating=0.9,
        strengths=[TaskType.SPEECH],
    ),
}


@dataclass
class RoutingDecision:
    """Record of a model routing decision."""

    selected_model: str
    task_type: TaskType
    confidence: float
    reasoning: str
    alternatives: list[tuple[str, float]] = field(default_factory=list)
    estimated_cost: float = 0.0


class ModelRouter:
    """Intelligent model router for MiMo models.

    Analyzes task characteristics and selects the optimal model based on:
    - Input modality (text, image, audio)
    - Task type (code, math, creative, etc.)
    - Cost/quality trade-off preferences
    - Model capabilities and strengths

    Example:
        >>> router = ModelRouter(api_key="...")
        >>> decision = router.analyze_task("Write a Python function to sort a list")
        >>> print(decision.selected_model)  # "mimo-v2.5-pro"

        >>> response = await router.route("Describe this image", image="photo.jpg")
    """

    def __init__(
        self,
        config: Optional[MimoConfig] = None,
        default_model: str = "mimo-v2.5-pro",
        cost_weight: float = 0.3,
        quality_weight: float = 0.7,
        custom_models: Optional[dict[str, ModelCapabilities]] = None,
    ):
        self.config = config or MimoConfig()
        self.default_model = default_model
        self.cost_weight = cost_weight
        self.quality_weight = quality_weight
        self._models = {**MODELS}
        if custom_models:
            self._models.update(custom_models)
        self._agents: dict[str, MimoAgent] = {}
        self._routing_history: list[RoutingDecision] = []

    def analyze_task(
        self,
        prompt: str,
        image: Optional[str] = None,
        audio: Optional[str] = None,
        text_to_speech: bool = False,
        tools: Optional[list] = None,
    ) -> RoutingDecision:
        """Analyze a task and determine the best model.

        Args:
            prompt: The task prompt
            image: Optional image URL or path
            audio: Optional audio data
            text_to_speech: Whether TTS is requested
            tools: Available tools

        Returns:
            RoutingDecision with selected model and reasoning
        """
        # Determine task type
        task_type = self._classify_task(prompt, image, audio, text_to_speech)

        # Score each model
        scores: list[tuple[str, float, str]] = []
        for model_name, caps in self._models.items():
            score, reason = self._score_model(caps, task_type, image, audio, text_to_speech, tools)
            scores.append((model_name, score, reason))

        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)

        if not scores:
            selected = self.default_model
            confidence = 0.5
            reasoning = "No models available, using default"
        else:
            selected = scores[0][0]
            confidence = scores[0][1]
            reasoning = scores[0][2]

        alternatives = [(name, score) for name, score, _ in scores[1:4]]

        decision = RoutingDecision(
            selected_model=selected,
            task_type=task_type,
            confidence=min(confidence, 1.0),
            reasoning=reasoning,
            alternatives=alternatives,
            estimated_cost=self._estimate_cost(selected, prompt),
        )

        self._routing_history.append(decision)
        logger.info(
            "Routed to '%s' (task=%s, confidence=%.2f)",
            selected, task_type.value, confidence,
        )

        return decision

    async def route(
        self,
        prompt: str,
        image: Optional[str] = None,
        audio: Optional[str] = None,
        text_to_speech: bool = False,
        system: Optional[str] = None,
        **kwargs: Any,
    ) -> AgentResponse:
        """Route and execute a task with the optimal model.

        Args:
            prompt: The task prompt
            image: Optional image URL or path
            audio: Optional audio data
            text_to_speech: Whether TTS is requested
            system: Optional system prompt
            **kwargs: Additional arguments passed to the agent

        Returns:
            AgentResponse from the selected model
        """
        decision = self.analyze_task(prompt, image, audio, text_to_speech)

        agent = self._get_or_create_agent(
            model=decision.selected_model,
            system=system,
        )

        return await agent.chat(prompt, image=image, **kwargs)

    def _classify_task(
        self,
        prompt: str,
        image: Optional[str] = None,
        audio: Optional[str] = None,
        text_to_speech: bool = False,
    ) -> TaskType:
        """Classify the task type based on input characteristics."""
        if text_to_speech:
            return TaskType.SPEECH
        if audio:
            return TaskType.SPEECH
        if image:
            return TaskType.VISION

        prompt_lower = prompt.lower()

        # Code patterns
        code_patterns = [
            r"\b(def |class |import |function |const |let |var |async )\b",
            r"\b(implement|code|program|script|module|package)\b",
            r"\b(python|javascript|typescript|rust|go|java|c\+\+)\b",
        ]
        if any(re.search(p, prompt_lower) for p in code_patterns):
            if any(w in prompt_lower for w in ["review", "check", "audit", "analyze"]):
                return TaskType.CODE_REVIEW
            return TaskType.CODE_GENERATION

        # Math patterns
        math_patterns = [
            r"\b(calculate|compute|solve|equation|formula|integral|derivative)\b",
            r"\b(math|mathematical|algebra|geometry|statistics|probability)\b",
        ]
        if any(re.search(p, prompt_lower) for p in math_patterns):
            return TaskType.MATH

        # Reasoning patterns
        reasoning_patterns = [
            r"\b(explain why|reason|think step|chain of thought|analyze)\b",
            r"\b(compare|contrast|evaluate|assess|judge)\b",
        ]
        if any(re.search(p, prompt_lower) for p in reasoning_patterns):
            return TaskType.REASONING

        # Creative writing
        creative_patterns = [
            r"\b(write a story|creative|poem|novel|fiction|imagine)\b",
            r"\b(write me|draft|compose|narrative)\b",
        ]
        if any(re.search(p, prompt_lower) for p in creative_patterns):
            return TaskType.CREATIVE_WRITING

        # Translation
        if any(w in prompt_lower for w in ["translate", "translation", "convert to"]):
            return TaskType.TRANSLATION

        # Summarization
        if any(w in prompt_lower for w in ["summarize", "summary", "brief", "tldr"]):
            return TaskType.SUMMARIZATION

        # Q&A
        if prompt.strip().endswith("?") or prompt_lower.startswith(("what", "how", "why", "when", "where", "who")):
            return TaskType.QUESTION_ANSWERING

        # Data analysis
        if any(w in prompt_lower for w in ["data", "dataset", "csv", "analyze", "statistics"]):
            return TaskType.DATA_ANALYSIS

        return TaskType.TEXT_GENERATION

    def _score_model(
        self,
        model: ModelCapabilities,
        task_type: TaskType,
        image: Optional[str],
        audio: Optional[str],
        text_to_speech: bool,
        tools: Optional[list],
    ) -> tuple[float, str]:
        """Score a model for a given task."""
        score = 0.0
        reasons = []

        # Hard requirements
        if image and not model.supports_vision:
            return 0.0, "Does not support vision"
        if text_to_speech and not model.supports_audio:
            return 0.0, "Does not support audio"
        if tools and not model.supports_tools:
            return 0.0, "Does not support tool calling"

        # Task alignment
        if task_type in model.strengths:
            score += 0.4
            reasons.append(f"Strong at {task_type.value}")

        # Quality score
        quality_score = model.quality_rating * self.quality_weight
        score += quality_score * 0.3
        reasons.append(f"Quality: {model.quality_rating:.1f}")

        # Cost score (inverse — lower cost = higher score)
        cost_score = (1.0 / (model.cost_per_1k_input + model.cost_per_1k_output + 0.001))
        cost_normalized = min(cost_score / 1000, 1.0)
        score += cost_normalized * self.cost_weight * 0.3
        reasons.append(f"Cost efficiency: {cost_normalized:.2f}")

        return score, "; ".join(reasons)

    def _estimate_cost(self, model_name: str, prompt: str) -> float:
        """Estimate the cost of a request."""
        model = self._models.get(model_name)
        if not model:
            return 0.0
        # Rough estimate: ~4 chars per token
        input_tokens = len(prompt) / 4
        estimated_output = min(input_tokens * 2, model.max_tokens)
        return (input_tokens * model.cost_per_1k_input / 1000) + (
            estimated_output * model.cost_per_1k_output / 1000
        )

    def _get_or_create_agent(
        self,
        model: str,
        system: Optional[str] = None,
    ) -> MimoAgent:
        """Get or create an agent for the specified model."""
        key = f"{model}:{system or ''}"
        if key not in self._agents:
            self._agents[key] = MimoAgent(
                name=f"router-{model}",
                config=self.config,
                model=model,
                system=system,
            )
        return self._agents[key]

    @property
    def available_models(self) -> list[str]:
        """List available models."""
        return list(self._models.keys())

    @property
    def routing_history(self) -> list[RoutingDecision]:
        """Get routing decision history."""
        return list(self._routing_history)

    def register_model(self, capabilities: ModelCapabilities) -> None:
        """Register a custom model."""
        self._models[capabilities.name] = capabilities
        logger.info("Registered model '%s'", capabilities.name)
