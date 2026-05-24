"""
Core MIMO Agent - Primary interface for interacting with Xiaomi MiMo models.

Supports multi-turn conversation, function/tool calling, streaming,
and automatic retry with exponential backoff.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Optional, TypeVar

import httpx
from pydantic import BaseModel

from mimo_devflow.config import MimoConfig
from mimo_devflow.optimizer import TokenOptimizer
from mimo_devflow.utils.logger import get_logger

logger = get_logger("agent")

T = TypeVar("T")


@dataclass
class ToolDefinition:
    """A tool that can be called by the agent."""

    name: str
    description: str
    parameters: dict[str, Any]
    function: Callable
    strict: bool = False

    def to_schema(self) -> dict[str, Any]:
        """Convert to OpenAI-compatible tool schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
                "strict": self.strict,
            },
        }


@dataclass
class Message:
    """A conversation message."""

    role: str  # "system", "user", "assistant", "tool"
    content: Optional[str] = None
    tool_calls: Optional[list[dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to API-compatible dictionary."""
        d: dict[str, Any] = {"role": self.role}
        if self.content is not None:
            d["content"] = self.content
        if self.tool_calls is not None:
            d["tool_calls"] = self.tool_calls
        if self.tool_call_id is not None:
            d["tool_call_id"] = self.tool_call_id
        if self.name is not None:
            d["name"] = self.name
        return d


@dataclass
class AgentResponse:
    """Response from the agent."""

    content: Optional[str] = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    finish_reason: Optional[str] = None
    usage: dict[str, int] = field(default_factory=dict)
    model: Optional[str] = None
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    latency_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.usage.get("total_tokens", 0)

    @property
    def input_tokens(self) -> int:
        return self.usage.get("prompt_tokens", 0)

    @property
    def output_tokens(self) -> int:
        return self.usage.get("completion_tokens", 0)


@dataclass
class StreamChunk:
    """A chunk from a streaming response."""

    content: Optional[str] = None
    tool_calls: Optional[list[dict[str, Any]]] = None
    finish_reason: Optional[str] = None
    delta: Optional[dict[str, Any]] = None


class MimoAgent:
    """Primary agent class for interacting with Xiaomi MiMo models.

    Features:
        - Multi-turn conversation with history management
        - Function/tool calling with automatic validation
        - Streaming responses
        - Automatic retry with exponential backoff
        - Token usage tracking
        - Configurable system prompts and model parameters

    Example:
        >>> agent = MimoAgent(config=MimoConfig(api_key="..."))
        >>> response = await agent.chat("Hello!")
        >>> print(response.content)
    """

    def __init__(
        self,
        name: str = "default",
        config: Optional[MimoConfig] = None,
        system: Optional[str] = None,
        model: Optional[str] = None,
        tools: Optional[list[ToolDefinition]] = None,
        max_turns: int = 50,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        optimizer: Optional[TokenOptimizer] = None,
    ):
        self.name = name
        self.config = config or MimoConfig()
        self.agent_id = str(uuid.uuid4())[:8]
        self.max_turns = max_turns

        # Model parameters
        self.model = model or self.config.model.default_model
        self.temperature = temperature if temperature is not None else self.config.model.temperature
        self.max_tokens = max_tokens or self.config.model.max_tokens
        self.top_p = self.config.model.top_p
        self.frequency_penalty = self.config.model.frequency_penalty
        self.presence_penalty = self.config.model.presence_penalty

        # Conversation state
        self._messages: list[Message] = []
        self._tools: dict[str, ToolDefinition] = {}
        self._optimizer = optimizer

        # HTTP client
        self._client: Optional[httpx.AsyncClient] = None

        # Register system prompt
        if system:
            self._messages.append(Message(role="system", content=system))

        # Register provided tools
        if tools:
            for tool in tools:
                self._tools[tool.name] = tool

        # Statistics
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_requests = 0
        self._created_at = time.time()

        logger.info(
            "Agent '%s' (%s) initialized with model=%s",
            self.name,
            self.agent_id,
            self.model,
        )

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.config.api.base_url,
                headers={
                    "Authorization": f"Bearer {self.config.api.api_key}",
                    "Content-Type": "application/json",
                    "X-Agent-Name": self.name,
                    "X-Agent-ID": self.agent_id,
                },
                timeout=httpx.Timeout(self.config.api.timeout),
            )
        return self._client

    def tool(
        self,
        func: Optional[Callable] = None,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        parameters: Optional[dict[str, Any]] = None,
    ) -> Callable:
        """Decorator to register a function as a callable tool.

        Can be used as @agent.tool or @agent.tool(name="custom_name")

        Args:
            func: The function to register (auto-detected when used as decorator)
            name: Custom tool name (defaults to function name)
            description: Tool description (defaults to function docstring)
            parameters: JSON Schema for parameters (auto-generated from type hints)

        Returns:
            The original function (unmodified)
        """
        def decorator(fn: Callable) -> Callable:
            tool_name = name or fn.__name__
            tool_desc = description or fn.__doc__ or f"Call {tool_name}"
            tool_params = parameters or _generate_params_schema(fn)

            tool_def = ToolDefinition(
                name=tool_name,
                description=tool_desc.strip(),
                parameters=tool_params,
                function=fn,
            )
            self._tools[tool_name] = tool_def
            logger.debug("Registered tool '%s' on agent '%s'", tool_name, self.name)
            return fn

        if func is not None:
            return decorator(func)
        return decorator

    async def chat(
        self,
        message: str,
        *,
        image: Optional[str] = None,
        compress: bool = False,
        metadata: Optional[dict[str, Any]] = None,
    ) -> AgentResponse:
        """Send a message and get a complete response.

        Handles multi-turn tool calling automatically: if the model requests
        tool calls, they are executed and results fed back until the model
        produces a final text response or max_turns is reached.

        Args:
            message: User message text
            image: Optional image URL or base64 for vision models
            compress: Whether to apply prompt compression via optimizer
            metadata: Optional metadata to attach to the message

        Returns:
            AgentResponse with content, tool calls, usage stats
        """
        start_time = time.monotonic()

        # Build user message
        if image:
            content = [
                {"type": "text", "text": message},
                {"type": "image_url", "image_url": {"url": image}},
            ]
        else:
            content = message

        self._messages.append(Message(
            role="user",
            content=content if isinstance(content, str) else json.dumps(content),
            metadata=metadata or {},
        ))

        # Apply compression if enabled
        messages_to_send = self._messages.copy()
        if compress and self._optimizer:
            messages_to_send = await self._optimizer.compress_messages(messages_to_send)

        # Multi-turn tool calling loop
        turn = 0
        final_response: Optional[AgentResponse] = None

        while turn < self.max_turns:
            turn += 1
            response = await self._request_completion(messages_to_send)

            if response.content:
                self._messages.append(Message(
                    role="assistant",
                    content=response.content,
                    tool_calls=response.tool_calls or None,
                ))

            if response.tool_calls:
                # Execute tool calls and append results
                if not response.content:
                    self._messages.append(Message(
                        role="assistant",
                        content=None,
                        tool_calls=response.tool_calls,
                    ))

                for tc in response.tool_calls:
                    tool_result = await self._execute_tool(tc)
                    self._messages.append(Message(
                        role="tool",
                        content=json.dumps(tool_result) if not isinstance(tool_result, str) else tool_result,
                        tool_call_id=tc["id"],
                        name=tc["function"]["name"],
                    ))

                messages_to_send = self._messages.copy()
                if compress and self._optimizer:
                    messages_to_send = await self._optimizer.compress_messages(messages_to_send)

                final_response = response
                continue

            # No tool calls — we have a final response
            final_response = response
            break

        if final_response is None:
            final_response = AgentResponse(
                content="[Agent reached max turns without a final response]",
                finish_reason="max_turns",
            )

        final_response.latency_ms = (time.monotonic() - start_time) * 1000
        self._total_input_tokens += final_response.input_tokens
        self._total_output_tokens += final_response.output_tokens
        self._total_requests += 1

        return final_response

    async def stream(
        self,
        message: str,
        *,
        image: Optional[str] = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a response chunk by chunk.

        Args:
            message: User message text
            image: Optional image URL or base64

        Yields:
            StreamChunk objects with partial content
        """
        self._messages.append(Message(role="user", content=message))

        client = await self._get_client()
        payload = self._build_payload(stream=True)

        async with client.stream(
            "POST", "/chat/completions", json=payload
        ) as response:
            response.raise_for_status()
            full_content = ""
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    data = json.loads(data_str)
                    delta = data.get("choices", [{}])[0].get("delta", {})
                    chunk = StreamChunk(
                        content=delta.get("content"),
                        tool_calls=delta.get("tool_calls"),
                        finish_reason=data.get("choices", [{}])[0].get("finish_reason"),
                        delta=delta,
                    )
                    if chunk.content:
                        full_content += chunk.content
                    yield chunk
                except json.JSONDecodeError:
                    continue

        self._messages.append(Message(role="assistant", content=full_content))

    async def _request_completion(self, messages: list[Message]) -> AgentResponse:
        """Send a completion request to the MiMo API with retry logic."""
        client = await self._get_client()
        payload = self._build_payload(messages=messages)

        last_error = None
        for attempt in range(self.config.api.max_retries):
            try:
                t0 = time.monotonic()
                resp = await client.post("/chat/completions", json=payload)
                latency = (time.monotonic() - t0) * 1000

                if resp.status_code == 429:
                    retry_after = float(resp.headers.get("Retry-After", self.config.api.retry_delay * (2 ** attempt)))
                    logger.warning("Rate limited, retrying after %.1fs", retry_after)
                    await asyncio.sleep(retry_after)
                    continue

                resp.raise_for_status()
                data = resp.json()

                choice = data.get("choices", [{}])[0]
                message_data = choice.get("message", {})

                return AgentResponse(
                    content=message_data.get("content"),
                    tool_calls=message_data.get("tool_calls", []),
                    finish_reason=choice.get("finish_reason"),
                    usage=data.get("usage", {}),
                    model=data.get("model"),
                    latency_ms=latency,
                    metadata={"attempt": attempt + 1},
                )

            except httpx.TimeoutException as e:
                last_error = e
                delay = self.config.api.retry_delay * (2 ** attempt)
                logger.warning("Request timeout (attempt %d/%d), retrying in %.1fs",
                             attempt + 1, self.config.api.max_retries, delay)
                await asyncio.sleep(delay)

            except httpx.HTTPStatusError as e:
                if e.response.status_code >= 500:
                    last_error = e
                    delay = self.config.api.retry_delay * (2 ** attempt)
                    logger.warning("Server error %d (attempt %d/%d), retrying in %.1fs",
                                 e.response.status_code, attempt + 1, self.config.api.max_retries, delay)
                    await asyncio.sleep(delay)
                else:
                    raise

        raise RuntimeError(
            f"Failed after {self.config.api.max_retries} attempts. Last error: {last_error}"
        )

    def _build_payload(
        self,
        messages: Optional[list[Message]] = None,
        stream: bool = False,
    ) -> dict[str, Any]:
        """Build the API request payload."""
        msgs = messages or self._messages
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [m.to_dict() for m in msgs],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "frequency_penalty": self.frequency_penalty,
            "presence_penalty": self.presence_penalty,
            "stream": stream,
        }

        if self._tools:
            payload["tools"] = [t.to_schema() for t in self._tools.values()]

        return payload

    async def _execute_tool(self, tool_call: dict[str, Any]) -> Any:
        """Execute a tool call from the model."""
        func_name = tool_call["function"]["name"]
        if func_name not in self._tools:
            logger.error("Tool '%s' not found", func_name)
            return {"error": f"Tool '{func_name}' not found"}

        tool = self._tools[func_name]
        try:
            args = json.loads(tool_call["function"]["arguments"])
            logger.info("Executing tool '%s' with args: %s", func_name, list(args.keys()))

            if asyncio.iscoroutinefunction(tool.function):
                result = await tool.function(**args)
            else:
                result = tool.function(**args)

            return result
        except Exception as e:
            logger.error("Tool '%s' execution failed: %s", func_name, e)
            return {"error": str(e)}

    def clear_history(self) -> None:
        """Clear conversation history, preserving system prompt."""
        system_msgs = [m for m in self._messages if m.role == "system"]
        self._messages = system_msgs

    @property
    def history(self) -> list[dict[str, Any]]:
        """Get conversation history as list of dicts."""
        return [m.to_dict() for m in self._messages]

    @property
    def token_usage(self) -> dict[str, int]:
        """Get total token usage statistics."""
        return {
            "input_tokens": self._total_input_tokens,
            "output_tokens": self._total_output_tokens,
            "total_tokens": self._total_input_tokens + self._total_output_tokens,
            "total_requests": self._total_requests,
        }

    def get_tools(self) -> list[dict[str, Any]]:
        """Get list of registered tool schemas."""
        return [t.to_schema() for t in self._tools.values()]

    async def close(self) -> None:
        """Close the HTTP client and clean up resources."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    def __repr__(self) -> str:
        return (
            f"MimoAgent(name='{self.name}', id='{self.agent_id}', "
            f"model='{self.model}', tools={len(self._tools)}, "
            f"messages={len(self._messages)})"
        )


def _generate_params_schema(func: Callable) -> dict[str, Any]:
    """Auto-generate JSON Schema parameters from function signature and type hints."""
    import inspect

    sig = inspect.signature(func)
    hints = func.__annotations__ if hasattr(func, "__annotations__") else {}

    type_map = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
    }

    properties = {}
    required = []

    for param_name, param in sig.parameters.items():
        if param_name == "self":
            continue

        param_type = hints.get(param_name, str)
        json_type = type_map.get(param_type, "string")

        prop: dict[str, Any] = {"type": json_type}

        if param.default is inspect.Parameter.empty:
            required.append(param_name)
        else:
            prop["default"] = param.default

        properties[param_name] = prop

    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        schema["required"] = required

    return schema
