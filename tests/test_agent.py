"""Unit tests for MIMO DevFlow agent."""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mimo_devflow.agent import MimoAgent, AgentResponse, Message, ToolDefinition, _generate_params_schema
from mimo_devflow.config import MimoConfig
from mimo_devflow.optimizer import TokenOptimizer


class TestMimoAgent:
    """Test cases for MimoAgent."""

    def test_agent_creation(self):
        """Test basic agent creation."""
        config = MimoConfig(api_key="test-key")
        agent = MimoAgent(name="test-agent", config=config, system="Test system prompt")
        assert agent.name == "test-agent"
        assert agent.model == "mimo-v2.5-pro"
        assert len(agent._messages) == 1  # system prompt
        assert agent._messages[0].role == "system"

    def test_agent_custom_model(self):
        """Test agent with custom model."""
        config = MimoConfig(api_key="test-key")
        agent = MimoAgent(config=config, model="mimo-v2.5-vl")
        assert agent.model == "mimo-v2.5-vl"

    def test_agent_default_config(self):
        """Test agent with default config from env."""
        agent = MimoAgent()
        assert agent.config is not None

    def test_tool_decorator(self):
        """Test tool registration via decorator."""
        agent = MimoAgent()

        @agent.tool
        def my_tool(param: str) -> str:
            """A test tool."""
            return f"Result: {param}"

        assert "my_tool" in agent._tools
        assert agent._tools["my_tool"].description == "A test tool."
        assert agent._tools["my_tool"].function is my_tool

    def test_tool_decorator_with_params(self):
        """Test tool decorator with custom parameters."""
        agent = MimoAgent()

        @agent.tool(name="custom_name", description="Custom description")
        def some_func(x: int) -> int:
            return x * 2

        assert "custom_name" in agent._tools
        assert agent._tools["custom_name"].description == "Custom description"

    def test_tool_schema_generation(self):
        """Test tool schema generation."""
        agent = MimoAgent()

        @agent.tool
        def search(query: str, max_results: int = 10) -> list:
            """Search for items."""
            return []

        schemas = agent.get_tools()
        assert len(schemas) == 1
        schema = schemas[0]
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "search"
        assert "query" in schema["function"]["parameters"]["properties"]
        assert "max_results" in schema["function"]["parameters"]["properties"]

    def test_clear_history(self):
        """Test clearing conversation history."""
        agent = MimoAgent(system="System prompt")
        agent._messages.append(Message(role="user", content="Hello"))
        agent._messages.append(Message(role="assistant", content="Hi!"))

        agent.clear_history()
        assert len(agent._messages) == 1
        assert agent._messages[0].role == "system"

    def test_history_property(self):
        """Test history property."""
        agent = MimoAgent()
        agent._messages.append(Message(role="user", content="Hello"))

        history = agent.history
        assert len(history) == 1
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Hello"

    def test_token_usage(self):
        """Test token usage tracking."""
        agent = MimoAgent()
        agent._total_input_tokens = 100
        agent._total_output_tokens = 50

        usage = agent.token_usage
        assert usage["input_tokens"] == 100
        assert usage["output_tokens"] == 50
        assert usage["total_tokens"] == 150

    def test_repr(self):
        """Test agent string representation."""
        agent = MimoAgent(name="test")
        repr_str = repr(agent)
        assert "test" in repr_str
        assert "mimo-v2.5-pro" in repr_str


class TestMessage:
    """Test cases for Message."""

    def test_message_creation(self):
        """Test message creation."""
        msg = Message(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.timestamp > 0

    def test_message_to_dict(self):
        """Test message serialization."""
        msg = Message(role="user", content="Hello")
        d = msg.to_dict()
        assert d["role"] == "user"
        assert d["content"] == "Hello"

    def test_message_tool_calls(self):
        """Test message with tool calls."""
        msg = Message(
            role="assistant",
            content=None,
            tool_calls=[{"id": "tc1", "function": {"name": "test", "arguments": "{}"}}],
        )
        d = msg.to_dict()
        assert "tool_calls" in d
        assert len(d["tool_calls"]) == 1

    def test_message_tool_result(self):
        """Test tool result message."""
        msg = Message(
            role="tool",
            content='{"result": 42}',
            tool_call_id="tc1",
            name="calculator",
        )
        d = msg.to_dict()
        assert d["tool_call_id"] == "tc1"
        assert d["name"] == "calculator"


class TestAgentResponse:
    """Test cases for AgentResponse."""

    def test_response_creation(self):
        """Test response creation."""
        response = AgentResponse(content="Hello!", finish_reason="stop")
        assert response.content == "Hello!"
        assert response.finish_reason == "stop"

    def test_response_usage(self):
        """Test response token usage."""
        response = AgentResponse(
            content="Hi",
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        )
        assert response.input_tokens == 10
        assert response.output_tokens == 5
        assert response.total_tokens == 15

    def test_response_defaults(self):
        """Test response defaults."""
        response = AgentResponse()
        assert response.content is None
        assert response.tool_calls == []
        assert response.total_tokens == 0


class TestToolDefinition:
    """Test cases for ToolDefinition."""

    def test_tool_to_schema(self):
        """Test tool schema conversion."""
        tool = ToolDefinition(
            name="test",
            description="Test tool",
            parameters={"type": "object", "properties": {"x": {"type": "string"}}},
            function=lambda x: x,
        )
        schema = tool.to_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "test"
        assert schema["function"]["description"] == "Test tool"


class TestGenerateParamsSchema:
    """Test parameter schema generation."""

    def test_basic_params(self):
        """Test basic parameter generation."""
        def my_func(name: str, count: int = 5) -> str:
            return ""

        schema = _generate_params_schema(my_func)
        assert "name" in schema["properties"]
        assert "count" in schema["properties"]
        assert schema["properties"]["name"]["type"] == "string"
        assert schema["properties"]["count"]["type"] == "integer"
        assert "name" in schema["required"]
        assert "count" not in schema["required"]

    def test_no_params(self):
        """Test function with no parameters."""
        def no_params() -> str:
            return ""

        schema = _generate_params_schema(no_params)
        assert schema["properties"] == {}
        assert "required" not in schema


@pytest.mark.asyncio
class TestAgentAsync:
    """Async test cases for MimoAgent."""

    async def test_context_manager(self):
        """Test agent as async context manager."""
        async with MimoAgent(name="test") as agent:
            assert agent.name == "test"
        # Client should be closed after context exit

    @patch("mimo_devflow.agent.httpx.AsyncClient")
    async def test_chat_mock(self, mock_client_class):
        """Test chat with mocked HTTP client."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {"content": "Hello!", "tool_calls": []},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            "model": "mimo-v2.5-pro",
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False
        mock_client_class.return_value = mock_client

        agent = MimoAgent(config=MimoConfig(api_key="test-key"))
        response = await agent.chat("Hello")

        assert response.content == "Hello!"
        assert response.total_tokens == 15
