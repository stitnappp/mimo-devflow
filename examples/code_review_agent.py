"""
Code Review Agent Example

A multi-agent workflow for automated code review with specialized agents.
"""

import asyncio
from mimo_devflow import MimoAgent, MimoConfig, Workflow, CollaborativeAgentGroup


SAMPLE_CODE = '''
def fetch_user_data(user_id):
    import requests
    response = requests.get(f"https://api.example.com/users/{user_id}")
    data = response.json()
    password = data.get("password")
    name = data["name"]
    email = data.get("email", "")
    if email:
        if "@" in email:
            return {"name": name, "email": email, "password": password}
    return None

def process_users(user_ids):
    results = []
    for uid in user_ids:
        data = fetch_user_data(uid)
        if data:
            results.append(data)
    return results
'''


async def main():
    config = MimoConfig(api_key="your-api-key-here")

    # Create specialized code review agents
    security_analyst = MimoAgent(
        name="security",
        config=config,
        system=(
            "You are a security analyst. Review code for vulnerabilities, "
            "injection risks, data exposure, and security best practices. "
            "Be specific about issues and provide fix recommendations."
        ),
    )

    style_reviewer = MimoAgent(
        name="style",
        config=config,
        system=(
            "You are a code style reviewer. Check for PEP 8 compliance, "
            "naming conventions, code organization, and readability. "
            "Rate the code style on a scale of 1-10."
        ),
    )

    performance_analyst = MimoAgent(
        name="performance",
        config=config,
        system=(
            "You are a performance analyst. Identify performance bottlenecks, "
            "unnecessary operations, and optimization opportunities. "
            "Focus on algorithmic complexity and resource usage."
        ),
    )

    documentation_writer = MimoAgent(
        name="docs",
        config=config,
        system=(
            "You are a documentation specialist. Generate comprehensive "
            "docstrings and inline comments for the code. Follow Google "
            "docstring style."
        ),
    )

    reviewer = MimoAgent(
        name="reviewer",
        config=config,
        system=(
            "You are a senior code reviewer. Synthesize feedback from "
            "multiple specialists into a clear, actionable code review. "
            "Prioritize issues by severity and provide a final assessment."
        ),
    )

    # Build the review workflow
    workflow = Workflow("code-review", config=config, max_parallel=4)

    # Phase 1: Parallel analysis
    workflow.add_task(
        "security-analysis",
        security_analyst,
        prompt="Review this code for security issues:\n```python\n{{code}}\n```",
    )
    workflow.add_task(
        "style-analysis",
        style_reviewer,
        prompt="Review this code for style issues:\n```python\n{{code}}\n```",
    )
    workflow.add_task(
        "performance-analysis",
        performance_analyst,
        prompt="Analyze this code for performance:\n```python\n{{code}}\n```",
    )
    workflow.add_task(
        "generate-docs",
        documentation_writer,
        prompt="Generate documentation for:\n```python\n{{code}}\n```",
    )

    # Phase 2: Synthesize review
    workflow.add_task(
        "final-review",
        reviewer,
        prompt=(
            "Synthesize the following analyses into a final code review:\n\n"
            "Security Analysis:\n{{security-analysis.output}}\n\n"
            "Style Review:\n{{style-analysis.output}}\n\n"
            "Performance Analysis:\n{{performance-analysis.output}}\n\n"
            "Provide an overall assessment and prioritized list of changes."
        ),
        depends=["security-analysis", "style-analysis", "performance-analysis"],
    )

    # Execute
    print("Starting code review...\n")
    result = await workflow.run({"code": SAMPLE_CODE})

    print(f"Status: {result.status.value}")
    print(f"Duration: {result.duration_ms:.0f}ms")
    print(f"Tokens: {result.total_tokens}")

    # Display each analysis
    for task_id, task_result in result.task_results.items():
        print(f"\n{'='*60}")
        print(f"  {task_id.upper()}")
        print(f"{'='*60}")
        print(task_result.output)

    print(f"\n{'='*60}")
    print("  FINAL REVIEW")
    print(f"{'='*60}")
    print(result.final_output)


async def collaborative_review():
    """Alternative: collaborative group-based code review."""
    config = MimoConfig(api_key="your-api-key-here")

    group = CollaborativeAgentGroup("code-review-group", config=config)

    group.add_agent(MimoAgent(
        name="junior", config=config,
        system="You are a junior developer learning to review code.",
    ))
    group.add_agent(MimoAgent(
        name="senior", config=config,
        system="You are a senior developer with deep expertise.",
    ))
    group.add_agent(MimoAgent(
        name="lead", config=config,
        system="You are a tech lead who makes final decisions.",
    ))
    group.set_moderator(MimoAgent(
        name="moderator", config=config,
        system="Moderate the code review discussion.",
    ))

    result = await group.discuss(
        topic=f"Review this code and discuss improvements:\n```python\n{SAMPLE_CODE}\n```",
        rounds=2,
    )

    print("=== Collaborative Review ===")
    print(f"Participants: {result.participants}")
    print(f"Contributions: {result.total_contributions}")
    print(f"\nConsensus:\n{result.consensus}")


if __name__ == "__main__":
    asyncio.run(main())
