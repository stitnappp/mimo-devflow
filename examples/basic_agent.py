"""
Basic Agent Usage Example

Demonstrates how to create and use a MIMO DevFlow agent for simple tasks.
"""

import asyncio
from mimo_devflow import MimoAgent, MimoConfig


async def main():
    # Create configuration
    config = MimoConfig(api_key="your-api-key-here")

    # Create an agent with a system prompt
    agent = MimoAgent(
        name="my-assistant",
        config=config,
        system="You are a helpful AI assistant. Be concise and clear.",
        temperature=0.7,
    )

    # Basic chat
    response = await agent.chat("What is machine learning?")
    print(f"Response: {response.content}")
    print(f"Tokens: {response.input_tokens} in / {response.output_tokens} out")
    print(f"Latency: {response.latency_ms:.1f}ms")

    # Multi-turn conversation
    response = await agent.chat("Can you give me a simple example?")
    print(f"\nFollow-up: {response.content}")

    # Check token usage
    usage = agent.token_usage
    print(f"\nTotal tokens used: {usage['total_tokens']}")

    # Streaming
    print("\n--- Streaming Response ---")
    async for chunk in agent.stream("Write a haiku about programming"):
        if chunk.content:
            print(chunk.content, end="", flush=True)
    print()


async def with_tools():
    """Example with tool calling."""
    config = MimoConfig(api_key="your-api-key-here")

    agent = MimoAgent(name="tool-agent", config=config)

    @agent.tool
    def get_weather(city: str) -> dict:
        """Get current weather for a city."""
        # Simulated weather data
        return {
            "city": city,
            "temperature": 22,
            "condition": "sunny",
            "humidity": 65,
        }

    @agent.tool
    def calculate(expression: str) -> dict:
        """Evaluate a mathematical expression."""
        try:
            result = eval(expression)  # Only for demo - use safe eval in production
            return {"expression": expression, "result": result}
        except Exception as e:
            return {"error": str(e)}

    # Agent will automatically use tools when appropriate
    response = await agent.chat("What's the weather in Beijing and what is 42 * 17?")
    print(f"Response: {response.content}")
    if response.tool_calls:
        print(f"Tools called: {[tc['function']['name'] for tc in response.tool_calls]}")


async def with_optimizer():
    """Example with token optimization."""
    from mimo_devflow import TokenOptimizer

    config = MimoConfig(api_key="your-api-key-here")
    optimizer = TokenOptimizer(budget=50000)

    agent = MimoAgent(
        name="optimized-agent",
        config=config,
        optimizer=optimizer,
    )

    # Long prompt gets compressed automatically
    long_prompt = """
    Please note that I would like you to analyze the following data.
    It is important to consider all aspects carefully.
    In order to provide a thorough analysis, please consider:
    1. The historical trends
    2. The current market conditions
    3. The future projections

    Data: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    """

    response = await agent.chat(long_prompt, compress=True)
    print(f"Response: {response.content}")
    print(f"Tokens saved by compression: {optimizer.tokens_saved}")


if __name__ == "__main__":
    asyncio.run(main())
