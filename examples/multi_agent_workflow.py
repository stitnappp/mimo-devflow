"""
Multi-Agent Workflow Example

Demonstrates building a research-to-writing pipeline with multiple agents.
"""

import asyncio
from mimo_devflow import MimoAgent, MimoConfig, Workflow


async def main():
    config = MimoConfig(api_key="your-api-key-here")

    # Create specialized agents
    researcher = MimoAgent(
        name="researcher",
        config=config,
        system=(
            "You are a research specialist. Analyze topics thoroughly, "
            "identify key points, and provide well-structured research notes."
        ),
    )

    writer = MimoAgent(
        name="writer",
        config=config,
        system=(
            "You are a professional writer. Transform research into "
            "engaging, well-structured articles with clear prose."
        ),
    )

    editor = MimoAgent(
        name="editor",
        config=config,
        system=(
            "You are a senior editor. Review content for accuracy, clarity, "
            "and style. Provide the final polished version."
        ),
    )

    fact_checker = MimoAgent(
        name="fact-checker",
        config=config,
        system=(
            "You are a fact-checker. Verify claims, flag unsupported statements, "
            "and suggest corrections."
        ),
    )

    # Build the workflow DAG
    workflow = Workflow(
        name="content-pipeline",
        config=config,
        max_parallel=3,
    )

    # Research phase
    workflow.add_task(
        task_id="research",
        agent=researcher,
        prompt="Research the following topic thoroughly:\n{{topic}}",
    )

    # Fact-check and write in parallel (both depend on research)
    workflow.add_task(
        task_id="fact-check",
        agent=fact_checker,
        prompt=(
            "Verify the claims in this research:\n"
            "{{research.output}}\n\n"
            "Flag any unsupported or potentially incorrect statements."
        ),
        depends=["research"],
    )

    workflow.add_task(
        task_id="draft",
        agent=writer,
        prompt=(
            "Write an engaging article based on this research:\n"
            "{{research.output}}\n\n"
            "Target length: 500 words. Use clear, accessible language."
        ),
        depends=["research"],
    )

    # Final edit depends on both draft and fact-check
    workflow.add_task(
        task_id="edit",
        agent=editor,
        prompt=(
            "Edit and finalize this article:\n"
            "{{draft.output}}\n\n"
            "Fact-check notes:\n{{fact-check.output}}\n\n"
            "Produce the final polished version."
        ),
        depends=["draft", "fact-check"],
    )

    # Execute the workflow
    print("Starting content pipeline...")
    result = await workflow.run({
        "topic": "The impact of large language models on software development",
    })

    # Display results
    print(f"\nWorkflow Status: {result.status.value}")
    print(f"Duration: {result.duration_ms:.0f}ms")
    print(f"Total Tokens: {result.total_tokens}")

    print("\n--- Final Article ---")
    print(result.final_output)

    # Show execution plan
    print("\n--- Execution Plan ---")
    plan = workflow.get_execution_plan()
    for i, level in enumerate(plan):
        print(f"  Level {i}: {', '.join(level)}")


async def parallel_agents_example():
    """Example of running multiple agents in parallel."""
    config = MimoConfig(api_key="your-api-key-here")

    agents = [
        MimoAgent(name="optimist", config=config, system="You are an optimist. Always see the bright side."),
        MimoAgent(name="pessimist", config=config, system="You are a pessimist. Always consider risks."),
        MimoAgent(name="realist", config=config, system="You are a realist. Provide balanced analysis."),
    ]

    topic = "Should companies adopt AI coding assistants?"

    # Run all agents in parallel
    tasks = [agent.chat(topic) for agent in agents]
    responses = await asyncio.gather(*tasks)

    print("=== Parallel Agent Responses ===\n")
    for agent, response in zip(agents, responses):
        print(f"[{agent.name}]:")
        print(response.content)
        print()


if __name__ == "__main__":
    asyncio.run(main())
