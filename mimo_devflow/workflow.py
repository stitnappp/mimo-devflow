"""
Workflow Orchestration Engine - DAG-based task execution with parallel agents.

Supports:
- Directed Acyclic Graph (DAG) task dependencies
- Parallel execution of independent tasks
- Conditional branching based on task results
- Task retries with configurable policies
- Context templating with Jinja2-like syntax
- Real-time execution monitoring
"""

from __future__ import annotations

import asyncio
import enum
import json
import re
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from mimo_devflow.agent import AgentResponse, MimoAgent
from mimo_devflow.config import MimoConfig, RetryPolicy
from mimo_devflow.utils.logger import get_logger

logger = get_logger("workflow")


class TaskStatus(str, enum.Enum):
    """Status of a workflow task."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class WorkflowStatus(str, enum.Enum):
    """Status of a workflow."""

    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskResult:
    """Result of a single task execution."""

    task_id: str
    status: TaskStatus
    output: Optional[str] = None
    agent_response: Optional[AgentResponse] = None
    error: Optional[str] = None
    start_time: float = 0.0
    end_time: float = 0.0
    attempts: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time) * 1000
        return 0.0

    @property
    def tokens_used(self) -> int:
        if self.agent_response:
            return self.agent_response.total_tokens
        return 0


@dataclass
class Task:
    """A unit of work in a workflow.

    Args:
        id: Unique task identifier
        agent: The agent to execute this task
        prompt: Task prompt (supports {{variable}} templating)
        depends: List of task IDs this task depends on
        condition: Optional callable that determines if task should run
        retry_policy: Optional retry configuration
        timeout: Optional task-specific timeout
        output_key: Key to store output under in context
    """

    id: str
    agent: MimoAgent
    prompt: str
    depends: list[str] = field(default_factory=list)
    condition: Optional[Callable[[dict[str, Any]], bool]] = None
    retry_policy: Optional[RetryPolicy] = None
    timeout: Optional[float] = None
    output_key: Optional[str] = None

    def should_run(self, context: dict[str, Any]) -> bool:
        """Check if task condition is met."""
        if self.condition is None:
            return True
        try:
            return self.condition(context)
        except Exception as e:
            logger.warning("Task '%s' condition evaluation failed: %s", self.id, e)
            return False


@dataclass
class WorkflowResult:
    """Result of an entire workflow execution."""

    workflow_id: str
    status: WorkflowStatus
    task_results: dict[str, TaskResult] = field(default_factory=dict)
    final_output: Optional[str] = None
    start_time: float = 0.0
    end_time: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time) * 1000
        return 0.0

    @property
    def total_tokens(self) -> int:
        return sum(r.tokens_used for r in self.task_results.values())

    @property
    def succeeded_tasks(self) -> list[str]:
        return [tid for tid, r in self.task_results.items() if r.status == TaskStatus.COMPLETED]

    @property
    def failed_tasks(self) -> list[str]:
        return [tid for tid, r in self.task_results.items() if r.status == TaskStatus.FAILED]


class Workflow:
    """DAG-based workflow orchestration engine.

    Build complex multi-agent pipelines with dependency management,
    parallel execution, conditional branching, and error recovery.

    Example:
        >>> workflow = Workflow("my-pipeline")
        >>> workflow.add_task("research", researcher, prompt="Research: {{topic}}")
        >>> workflow.add_task("write", writer, prompt="Write about: {{research.output}}", depends=["research"])
        >>> result = await workflow.run({"topic": "quantum computing"})
    """

    def __init__(
        self,
        name: str,
        config: Optional[MimoConfig] = None,
        max_parallel: int = 5,
        timeout: float = 600.0,
        on_task_complete: Optional[Callable[[str, TaskResult], None]] = None,
        on_workflow_complete: Optional[Callable[[WorkflowResult], None]] = None,
    ):
        self.name = name
        self.workflow_id = str(uuid.uuid4())[:8]
        self.config = config or MimoConfig()
        self.max_parallel = max_parallel
        self.timeout = timeout
        self.on_task_complete = on_task_complete
        self.on_workflow_complete = on_workflow_complete

        self._tasks: dict[str, Task] = {}
        self._adjacency: dict[str, set[str]] = defaultdict(set)  # task -> dependents
        self._in_degree: dict[str, int] = defaultdict(int)
        self._retry_policies: dict[str, RetryPolicy] = {}

        logger.info("Workflow '%s' (%s) created", self.name, self.workflow_id)

    def add_task(
        self,
        task_id: str,
        agent: MimoAgent,
        prompt: str,
        depends: Optional[list[str]] = None,
        condition: Optional[Callable[[dict[str, Any]], bool]] = None,
        retry_policy: Optional[RetryPolicy] = None,
        timeout: Optional[float] = None,
        output_key: Optional[str] = None,
    ) -> Task:
        """Add a task to the workflow.

        Args:
            task_id: Unique task identifier
            agent: Agent to execute this task
            prompt: Task prompt with {{variable}} templating
            depends: Task IDs this task depends on
            condition: Function that returns True if task should execute
            retry_policy: Retry configuration
            timeout: Task timeout in seconds
            output_key: Custom key for storing output

        Returns:
            The created Task object

        Raises:
            ValueError: If task_id already exists or dependency not found
        """
        if task_id in self._tasks:
            raise ValueError(f"Task '{task_id}' already exists in workflow")

        task = Task(
            id=task_id,
            agent=agent,
            prompt=prompt,
            depends=depends or [],
            condition=condition,
            retry_policy=retry_policy,
            timeout=timeout,
            output_key=output_key or task_id,
        )

        self._tasks[task_id] = task

        # Update DAG structure
        self._in_degree[task_id] = len(task.depends)
        for dep_id in task.depends:
            if dep_id not in self._tasks:
                raise ValueError(f"Dependency '{dep_id}' not found for task '{task_id}'")
            self._adjacency[dep_id].add(task_id)

        logger.debug("Added task '%s' with %d dependencies", task_id, len(task.depends))
        return task

    def add_fallback(
        self,
        task_id: str,
        fallback_agent: MimoAgent,
        condition: str = "failure",
    ) -> None:
        """Add a fallback task that runs when the original fails or times out.

        Args:
            task_id: ID of the original task
            fallback_agent: Agent to use for the fallback
            condition: When to trigger ("failure", "timeout", "always")
        """
        fallback_id = f"{task_id}_fallback"
        original = self._tasks.get(task_id)
        if not original:
            raise ValueError(f"Task '{task_id}' not found")

        def fallback_condition(ctx: dict[str, Any]) -> bool:
            result = ctx.get(f"{task_id}_result")
            if result is None:
                return True
            if condition == "failure":
                return result.status == TaskStatus.FAILED
            if condition == "timeout":
                return "timeout" in (result.error or "").lower()
            return True

        self.add_task(
            task_id=fallback_id,
            agent=fallback_agent,
            prompt=original.prompt,
            depends=[task_id],
            condition=fallback_condition,
        )

    def set_retry_policy(
        self,
        task_id: str,
        max_retries: int = 3,
        backoff: float = 2.0,
        initial_delay: float = 1.0,
    ) -> None:
        """Set retry policy for a specific task."""
        if task_id not in self._tasks:
            raise ValueError(f"Task '{task_id}' not found")
        self._tasks[task_id].retry_policy = RetryPolicy(
            max_retries=max_retries,
            backoff_factor=backoff,
            initial_delay=initial_delay,
        )

    def validate(self) -> list[str]:
        """Validate the workflow DAG for cycles and missing dependencies.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check for cycles using Kahn's algorithm
        in_degree = dict(self._in_degree)
        queue = deque([tid for tid, deg in in_degree.items() if deg == 0])
        visited = 0

        while queue:
            node = queue.popleft()
            visited += 1
            for neighbor in self._adjacency.get(node, set()):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if visited != len(self._tasks):
            errors.append("Workflow contains a cycle")

        # Check for missing dependencies
        for task in self._tasks.values():
            for dep in task.depends:
                if dep not in self._tasks:
                    errors.append(f"Task '{task.id}' depends on missing task '{dep}'")

        return errors

    def topological_order(self) -> list[str]:
        """Get topological ordering of tasks for execution planning."""
        in_degree = dict(self._in_degree)
        queue = deque(sorted([tid for tid, deg in in_degree.items() if deg == 0]))
        order = []

        while queue:
            node = queue.popleft()
            order.append(node)
            for neighbor in sorted(self._adjacency.get(node, set())):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        return order

    async def run(
        self,
        context: Optional[dict[str, Any]] = None,
    ) -> WorkflowResult:
        """Execute the workflow.

        Args:
            context: Initial context variables available to all tasks

        Returns:
            WorkflowResult with all task outputs

        Raises:
            ValueError: If workflow validation fails
        """
        errors = self.validate()
        if errors:
            raise ValueError(f"Workflow validation failed: {', '.join(errors)}")

        ctx = dict(context or {})
        result = WorkflowResult(
            workflow_id=self.workflow_id,
            status=WorkflowStatus.RUNNING,
            start_time=time.time(),
        )

        logger.info("Starting workflow '%s' (%s)", self.name, self.workflow_id)

        # Track completed and failed tasks
        completed: set[str] = set()
        failed: set[str] = set()
        running: dict[str, asyncio.Task] = {}

        semaphore = asyncio.Semaphore(self.max_parallel)

        try:
            async with asyncio.timeout(self.timeout):
                while len(completed) + len(failed) < len(self._tasks):
                    # Find ready tasks
                    ready = []
                    for task_id, task in self._tasks.items():
                        if task_id in completed or task_id in failed or task_id in running:
                            continue
                        if all(dep in completed for dep in task.depends):
                            if task.should_run(ctx):
                                ready.append(task_id)

                    if not ready and not running:
                        # No tasks ready and nothing running — deadlock or done
                        break

                    # Launch ready tasks
                    for task_id in ready:
                        running[task_id] = asyncio.create_task(
                            self._run_task(task_id, ctx, semaphore, result)
                        )

                    # Wait for at least one task to complete
                    if running:
                        done_set, _ = await asyncio.wait(
                            running.values(),
                            return_when=asyncio.FIRST_COMPLETED,
                        )

                        for task_id in list(running.keys()):
                            if running[task_id].done():
                                task_result = running.pop(task_id).result()
                                result.task_results[task_id] = task_result
                                ctx[f"{task_id}_result"] = task_result
                                ctx[f"{task_id}_output"] = task_result.output or ""

                                if task_result.status == TaskStatus.COMPLETED:
                                    completed.add(task_id)
                                    logger.info(
                                        "Task '%s' completed in %.1fms",
                                        task_id,
                                        task_result.duration_ms,
                                    )
                                else:
                                    failed.add(task_id)
                                    logger.warning(
                                        "Task '%s' failed: %s",
                                        task_id,
                                        task_result.error,
                                    )

                                if self.on_task_complete:
                                    self.on_task_complete(task_id, task_result)

        except asyncio.TimeoutError:
            logger.error("Workflow '%s' timed out", self.name)
            result.status = WorkflowStatus.FAILED
            # Cancel running tasks
            for t in running.values():
                t.cancel()

        except Exception as e:
            logger.error("Workflow '%s' failed: %s", self.name, e)
            result.status = WorkflowStatus.FAILED
            for t in running.values():
                t.cancel()

        # Determine final status
        if result.status != WorkflowStatus.FAILED:
            if failed:
                result.status = WorkflowStatus.FAILED
            else:
                result.status = WorkflowStatus.COMPLETED

        result.end_time = time.time()

        # Get final output from last task or specified output
        if result.status == WorkflowStatus.COMPLETED:
            topo = self.topological_order()
            if topo:
                last_task_id = topo[-1]
                last_result = result.task_results.get(last_task_id)
                if last_result:
                    result.final_output = last_result.output

        if self.on_workflow_complete:
            self.on_workflow_complete(result)

        logger.info(
            "Workflow '%s' finished: %s (%.1fms, %d tokens)",
            self.name,
            result.status.value,
            result.duration_ms,
            result.total_tokens,
        )

        return result

    async def _run_task(
        self,
        task_id: str,
        context: dict[str, Any],
        semaphore: asyncio.Semaphore,
        workflow_result: WorkflowResult,
    ) -> TaskResult:
        """Execute a single task with retry logic."""
        task = self._tasks[task_id]
        retry = task.retry_policy or self.config.workflow.retry_policy
        task_result = TaskResult(task_id=task_id, status=TaskStatus.RUNNING)

        # Render prompt with context
        prompt = _render_template(task.prompt, context)

        for attempt in range(retry.max_retries + 1):
            task_result.attempts = attempt + 1
            task_result.start_time = time.time()

            try:
                async with semaphore:
                    if task.timeout:
                        async with asyncio.timeout(task.timeout):
                            response = await task.agent.chat(prompt)
                    else:
                        response = await task.agent.chat(prompt)

                task_result.end_time = time.time()
                task_result.agent_response = response
                task_result.output = response.content
                task_result.status = TaskStatus.COMPLETED
                return task_result

            except Exception as e:
                task_result.end_time = time.time()
                task_result.error = str(e)

                if attempt < retry.max_retries:
                    delay = retry.initial_delay * (retry.backoff_factor ** attempt)
                    delay = min(delay, retry.max_delay)
                    task_result.status = TaskStatus.RETRYING
                    logger.warning(
                        "Task '%s' attempt %d failed, retrying in %.1fs: %s",
                        task_id, attempt + 1, delay, e,
                    )
                    await asyncio.sleep(delay)
                else:
                    task_result.status = TaskStatus.FAILED
                    logger.error("Task '%s' failed after %d attempts: %s",
                               task_id, attempt + 1, e)

        return task_result

    def get_execution_plan(self) -> list[list[str]]:
        """Get execution plan showing which tasks can run in parallel.

        Returns:
            List of execution levels, each containing task IDs that can run simultaneously
        """
        in_degree = dict(self._in_degree)
        levels = []
        remaining = set(self._tasks.keys())

        while remaining:
            level = [
                tid for tid in sorted(remaining)
                if in_degree.get(tid, 0) == 0
            ]
            if not level:
                break
            levels.append(level)
            for tid in level:
                remaining.discard(tid)
                for neighbor in self._adjacency.get(tid, set()):
                    in_degree[neighbor] -= 1

        return levels

    def __repr__(self) -> str:
        return (
            f"Workflow(name='{self.name}', id='{self.workflow_id}', "
            f"tasks={len(self._tasks)})"
        )


def _render_template(template: str, context: dict[str, Any]) -> str:
    """Render a template string with context variables.

    Supports {{variable}} and {{task_id.output}} syntax.
    """
    def replacer(match: re.Match) -> str:
        key = match.group(1).strip()
        parts = key.split(".")

        value: Any = context
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part, match.group(0))
            elif hasattr(value, part):
                value = getattr(value, part, match.group(0))
            else:
                return match.group(0)

        if isinstance(value, (dict, list)):
            return json.dumps(value, indent=2)
        return str(value) if value is not None else match.group(0)

    return re.sub(r"\{\{(.+?)\}\}", replacer, template)
