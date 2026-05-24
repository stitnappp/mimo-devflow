"""
CLI for MIMO DevFlow - Rich terminal interface for running workflows.

Commands:
    mimo-devflow run       - Run a workflow file
    mimo-devflow chat      - Interactive chat with an agent
    mimo-devflow benchmark - Run benchmarks
    mimo-devflow config    - Manage configuration
    mimo-devflow models    - List available models
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from rich.table import Table
from rich.tree import Tree

from mimo_devflow.config import MimoConfig
from mimo_devflow.utils.logger import setup_logging

console = Console()


@click.group()
@click.version_option(version="0.3.0", prog_name="mimo-devflow")
@click.option("--config", "-c", type=click.Path(), help="Config file path")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.pass_context
def main(ctx: click.Context, config: Optional[str], verbose: bool) -> None:
    """MIMO DevFlow - Multi-agent orchestration framework for Xiaomi MiMo models."""
    setup_logging(level="DEBUG" if verbose else "INFO")
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config
    ctx.obj["verbose"] = verbose


@main.command()
@click.argument("workflow_file", type=click.Path(exists=True))
@click.option("--var", "-v", multiple=True, help="Context variables (key=value)")
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.pass_context
def run(ctx: click.Context, workflow_file: str, var: tuple, output: Optional[str]) -> None:
    """Run a workflow from a YAML file."""
    import yaml

    with open(workflow_file) as f:
        workflow_def = yaml.safe_load(f)

    # Parse context variables
    context = {}
    for v in var:
        if "=" in v:
            key, value = v.split("=", 1)
            context[key.strip()] = value.strip()

    config = _load_config(ctx)
    console.print(Panel(f"[bold blue]Running Workflow: {workflow_def.get('name', 'unnamed')}[/]", border_style="blue"))

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Executing workflow...", total=None)
        result = asyncio.run(_execute_workflow(workflow_def, config, context))
        progress.update(task, description="[green]Workflow complete!")

    _display_result(result)

    if output:
        with open(output, "w") as f:
            json.dump(result, f, indent=2, default=str)
        console.print(f"\n[dim]Results saved to {output}[/]")


@main.command()
@click.option("--model", "-m", default="mimo-v2.5-pro", help="Model to use")
@click.option("--system", "-s", help="System prompt")
@click.pass_context
def chat(ctx: click.Context, model: str, system: Optional[str]) -> None:
    """Interactive chat with a MiMo agent."""
    from mimo_devflow.agent import MimoAgent

    config = _load_config(ctx)
    agent = MimoAgent(config=config, model=model, system=system)

    console.print(Panel(
        f"[bold]MIMO DevFlow Chat[/]\n"
        f"Model: {model}\n"
        f"Type 'quit' or 'exit' to end the conversation",
        border_style="green",
    ))

    while True:
        try:
            user_input = Prompt.ask("\n[bold cyan]You[/]")
            if user_input.lower() in ("quit", "exit", "q"):
                console.print("[dim]Goodbye![/]")
                break

            if not user_input.strip():
                continue

            with Progress(SpinnerColumn(), TextColumn("[dim]Thinking...[/]"), console=console) as progress:
                progress.add_task("thinking", total=None)
                response = asyncio.run(agent.chat(user_input))

            console.print(f"\n[bold green]Agent ({response.model})[/]:")
            console.print(Markdown(response.content or "(no response)"))

            if response.tool_calls:
                console.print(f"\n[dim]Tool calls: {len(response.tool_calls)}[/]")

            console.print(f"[dim]Tokens: {response.input_tokens} in / {response.output_tokens} out ({response.latency_ms:.0f}ms)[/]")

        except KeyboardInterrupt:
            console.print("\n[dim]Interrupted. Goodbye![/]")
            break
        except Exception as e:
            console.print(f"\n[red]Error: {e}[/]")


@main.command()
@click.argument("test_file", type=click.Path(exists=True))
@click.option("--model", "-m", default="mimo-v2.5-pro", help="Model to benchmark")
@click.option("--output", "-o", type=click.Path(), help="Report output path")
@click.pass_context
def benchmark(ctx: click.Context, test_file: str, model: str, output: Optional[str]) -> None:
    """Run benchmarks from a test file."""
    from mimo_devflow.agent import MimoAgent
    from mimo_devflow.evaluate import Evaluator

    config = _load_config(ctx)
    agent = MimoAgent(config=config, model=model)
    evaluator = Evaluator(config=config)

    console.print(Panel(f"[bold]Running Benchmarks[/]\nModel: {model}\nTests: {test_file}", border_style="yellow"))

    evaluator.load_tests(test_file)

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        task = progress.add_task("Running tests...", total=None)
        result = asyncio.run(evaluator.benchmark(agent))
        progress.update(task, description="[green]Benchmarks complete!")

    _display_benchmark(result)

    report = evaluator.generate_report(result, output_path=output)
    if output:
        console.print(f"\n[dim]Report saved to {output}[/]")


@main.command()
@click.pass_context
def models(ctx: click.Context) -> None:
    """List available MiMo models."""
    from mimo_devflow.router import MODELS

    table = Table(title="Available MiMo Models", border_style="blue")
    table.add_column("Model", style="bold cyan")
    table.add_column("Max Tokens", justify="right")
    table.add_column("Vision", justify="center")
    table.add_column("Tools", justify="center")
    table.add_column("Audio", justify="center")
    table.add_column("Cost (in/out)", justify="right")
    table.add_column("Strengths")

    for name, caps in MODELS.items():
        table.add_row(
            name,
            str(caps.max_tokens),
            "✅" if caps.supports_vision else "❌",
            "✅" if caps.supports_tools else "❌",
            "✅" if caps.supports_audio else "❌",
            f"${caps.cost_per_1k_input:.4f} / ${caps.cost_per_1k_output:.4f}",
            ", ".join(s.value for s in caps.strengths[:3]),
        )

    console.print(table)


@main.command()
@click.option("--init", "do_init", is_flag=True, help="Create default config file")
@click.pass_context
def config(ctx: click.Context, do_init: bool) -> None:
    """Manage MIMO DevFlow configuration."""
    if do_init:
        config_path = Path("mimo_config.yaml")
        default_config = MimoConfig()
        default_config.save(config_path)
        console.print(f"[green]Created config file: {config_path}[/]")
        console.print("[dim]Edit the file to set your API key and preferences.[/]")
    else:
        config = _load_config(ctx)
        console.print(Panel("[bold]Current Configuration[/]", border_style="blue"))
        console.print(f"API Base URL: {config.api.base_url}")
        console.print(f"API Key: {'*' * 8 if config.api.api_key else '(not set)'}")
        console.print(f"Default Model: {config.model.default_model}")
        console.print(f"Temperature: {config.model.temperature}")
        console.print(f"Max Tokens: {config.model.max_tokens}")
        console.print(f"Optimizer Enabled: {config.optimizer.enabled}")


@main.command()
@click.argument("workflow_file", type=click.Path(exists=True))
@click.pass_context
def validate(ctx: click.Context, workflow_file: str) -> None:
    """Validate a workflow file."""
    import yaml

    with open(workflow_file) as f:
        workflow_def = yaml.safe_load(f)

    console.print(Panel(f"[bold]Validating: {workflow_file}[/]", border_style="yellow"))

    errors = []
    if "name" not in workflow_def:
        errors.append("Missing 'name' field")
    if "tasks" not in workflow_def:
        errors.append("Missing 'tasks' field")
    else:
        for i, task in enumerate(workflow_def["tasks"]):
            if "id" not in task:
                errors.append(f"Task {i}: missing 'id'")
            if "prompt" not in task:
                errors.append(f"Task {i}: missing 'prompt'")

    if errors:
        for err in errors:
            console.print(f"  [red]❌ {err}[/]")
        sys.exit(1)
    else:
        console.print("  [green]✅ Workflow is valid[/]")


def _load_config(ctx: click.Context) -> MimoConfig:
    """Load configuration from context."""
    config_path = ctx.obj.get("config_path")
    if config_path:
        return MimoConfig.from_file(config_path)
    return MimoConfig.from_env()


async def _execute_workflow(workflow_def: dict, config: MimoConfig, context: dict) -> dict:
    """Execute a workflow definition."""
    from mimo_devflow.agent import MimoAgent
    from mimo_devflow.workflow import Workflow

    workflow = Workflow(name=workflow_def.get("name", "unnamed"), config=config)

    agents = {}
    for task_def in workflow_def.get("tasks", []):
        agent_name = task_def.get("agent", "default")
        if agent_name not in agents:
            agents[agent_name] = MimoAgent(name=agent_name, config=config)
        workflow.add_task(
            task_id=task_def["id"],
            agent=agents[agent_name],
            prompt=task_def["prompt"],
            depends=task_def.get("depends", []),
        )

    result = await workflow.run(context)
    return {
        "status": result.status.value,
        "final_output": result.final_output,
        "total_tokens": result.total_tokens,
        "duration_ms": result.duration_ms,
        "task_results": {
            tid: {"status": r.status.value, "output": r.output}
            for tid, r in result.task_results.items()
        },
    }


def _display_result(result: dict) -> None:
    """Display workflow result."""
    status_color = "green" if result["status"] == "completed" else "red"
    console.print(f"\nStatus: [{status_color}]{result['status']}[/]")
    console.print(f"Duration: {result['duration_ms']:.0f}ms")
    console.print(f"Tokens: {result['total_tokens']}")
    if result.get("final_output"):
        console.print(Panel(Markdown(result["final_output"]), title="Final Output", border_style="green"))


def _display_benchmark(result) -> None:
    """Display benchmark results."""
    table = Table(title="Benchmark Results", border_style="yellow")
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")
    table.add_row("Total Tests", str(result.total_tests))
    table.add_row("Passed", f"[green]{result.passed}[/]")
    table.add_row("Failed", f"[red]{result.failed}[/]")
    table.add_row("Pass Rate", f"{result.pass_rate:.1%}")
    table.add_row("Avg Score", f"{result.avg_score:.3f}")
    table.add_row("Avg Latency", f"{result.avg_latency_ms:.0f}ms")
    table.add_row("P95 Latency", f"{result.p95_latency_ms:.0f}ms")
    table.add_row("Total Tokens", str(result.total_tokens))
    console.print(table)


if __name__ == "__main__":
    main()
