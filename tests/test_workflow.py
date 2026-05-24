"""Unit tests for MIMO DevFlow workflow engine."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mimo_devflow.agent import MimoAgent, AgentResponse
from mimo_devflow.config import MimoConfig, RetryPolicy
from mimo_devflow.workflow import Workflow, Task, TaskStatus, TaskResult, WorkflowStatus, _render_template


class TestWorkflow:
    """Test cases for Workflow."""

    def test_workflow_creation(self):
        """Test basic workflow creation."""
        workflow = Workflow("test-workflow")
        assert workflow.name == "test-workflow"
        assert workflow.workflow_id is not None

    def test_add_task(self):
        """Test adding tasks to workflow."""
        workflow = Workflow("test")
        agent = MimoAgent(name="agent1")

        task = workflow.add_task("task1", agent, prompt="Do something")
        assert task.id == "task1"
        assert "task1" in workflow._tasks

    def test_add_task_with_dependencies(self):
        """Test adding tasks with dependencies."""
        workflow = Workflow("test")
        agent = MimoAgent(name="agent1")

        workflow.add_task("task1", agent, prompt="Step 1")
        workflow.add_task("task2", agent, prompt="Step 2", depends=["task1"])

        assert workflow._in_degree["task1"] == 0
        assert workflow._in_degree["task2"] == 1
        assert "task2" in workflow._adjacency["task1"]

    def test_add_task_duplicate_id(self):
        """Test adding task with duplicate ID raises error."""
        workflow = Workflow("test")
        agent = MimoAgent(name="agent1")
        workflow.add_task("task1", agent, prompt="Step 1")

        with pytest.raises(ValueError, match="already exists"):
            workflow.add_task("task1", agent, prompt="Duplicate")

    def test_add_task_missing_dependency(self):
        """Test adding task with missing dependency raises error."""
        workflow = Workflow("test")
        agent = MimoAgent(name="agent1")

        with pytest.raises(ValueError, match="not found"):
            workflow.add_task("task2", agent, prompt="Step 2", depends=["nonexistent"])

    def test_validate_valid_workflow(self):
        """Test validation of a valid workflow."""
        workflow = Workflow("test")
        agent = MimoAgent(name="agent1")
        workflow.add_task("task1", agent, prompt="Step 1")
        workflow.add_task("task2", agent, prompt="Step 2", depends=["task1"])

        errors = workflow.validate()
        assert errors == []

    def test_validate_cycle_detection(self):
        """Test cycle detection in workflow."""
        workflow = Workflow("test")
        agent = MimoAgent(name="agent1")
        workflow.add_task("a", agent, prompt="A")
        workflow.add_task("b", agent, prompt="B", depends=["a"])
        # Manually create a cycle for testing
        workflow._tasks["a"].depends = ["b"]
        workflow._in_degree["a"] = 1
        workflow._adjacency["b"].add("a")

        errors = workflow.validate()
        assert any("cycle" in e for e in errors)

    def test_topological_order(self):
        """Test topological ordering."""
        workflow = Workflow("test")
        agent = MimoAgent(name="agent1")
        workflow.add_task("a", agent, prompt="A")
        workflow.add_task("b", agent, prompt="B", depends=["a"])
        workflow.add_task("c", agent, prompt="C", depends=["a"])
        workflow.add_task("d", agent, prompt="D", depends=["b", "c"])

        order = workflow.topological_order()
        assert order.index("a") < order.index("b")
        assert order.index("a") < order.index("c")
        assert order.index("b") < order.index("d")
        assert order.index("c") < order.index("d")

    def test_execution_plan(self):
        """Test execution plan generation."""
        workflow = Workflow("test")
        agent = MimoAgent(name="agent1")
        workflow.add_task("a", agent, prompt="A")
        workflow.add_task("b", agent, prompt="B", depends=["a"])
        workflow.add_task("c", agent, prompt="C", depends=["a"])
        workflow.add_task("d", agent, prompt="D", depends=["b", "c"])

        plan = workflow.get_execution_plan()
        assert len(plan) == 3  # 3 levels
        assert plan[0] == ["a"]
        assert set(plan[1]) == {"b", "c"}
        assert plan[2] == ["d"]

    def test_task_should_run(self):
        """Test task condition evaluation."""
        agent = MimoAgent(name="agent1")
        task = Task(
            id="conditional",
            agent=agent,
            prompt="Do something",
            condition=lambda ctx: ctx.get("run", False),
        )

        assert task.should_run({"run": True}) is True
        assert task.should_run({"run": False}) is False
        assert task.should_run({}) is False

    def test_fallback_task(self):
        """Test adding fallback tasks."""
        workflow = Workflow("test")
        agent = MimoAgent(name="agent1")
        fallback = MimoAgent(name="fallback")
        workflow.add_task("task1", agent, prompt="Do something")
        workflow.add_fallback("task1", fallback, condition="failure")

        assert "task1_fallback" in workflow._tasks
        assert "task1" in workflow._tasks["task1_fallback"].depends

    def test_set_retry_policy(self):
        """Test setting retry policy."""
        workflow = Workflow("test")
        agent = MimoAgent(name="agent1")
        workflow.add_task("task1", agent, prompt="Do something")
        workflow.set_retry_policy("task1", max_retries=5, backoff=3.0)

        policy = workflow._tasks["task1"].retry_policy
        assert policy.max_retries == 5
        assert policy.backoff_factor == 3.0

    def test_set_retry_policy_missing_task(self):
        """Test setting retry policy on missing task."""
        workflow = Workflow("test")
        with pytest.raises(ValueError, match="not found"):
            workflow.set_retry_policy("nonexistent")

    def test_repr(self):
        """Test workflow string representation."""
        workflow = Workflow("test")
        repr_str = repr(workflow)
        assert "test" in repr_str


class TestRenderTemplate:
    """Test template rendering."""

    def test_simple_variable(self):
        """Test simple variable substitution."""
        result = _render_template("Hello {{name}}", {"name": "World"})
        assert result == "Hello World"

    def test_nested_variable(self):
        """Test nested variable access."""
        result = _render_template("Output: {{task.output}}", {"task": {"output": "done"}})
        assert result == "Output: done"

    def test_missing_variable(self):
        """Test missing variable leaves template intact."""
        result = _render_template("Hello {{missing}}", {})
        assert result == "Hello {{missing}}"

    def test_multiple_variables(self):
        """Test multiple variables."""
        result = _render_template("{{greeting}} {{name}}!", {"greeting": "Hi", "name": "Alice"})
        assert result == "Hi Alice!"

    def test_object_variable(self):
        """Test object with attribute access."""
        class Obj:
            output = "result"
        result = _render_template("Value: {{obj.output}}", {"obj": Obj()})
        assert result == "Value: result"


@pytest.mark.asyncio
class TestWorkflowAsync:
    """Async test cases for Workflow."""

    @patch.object(MimoAgent, "chat")
    async def test_simple_workflow(self, mock_chat):
        """Test simple workflow execution."""
        mock_chat.return_value = AgentResponse(
            content="Task complete",
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        )

        workflow = Workflow("test")
        agent = MimoAgent(name="agent1")
        workflow.add_task("task1", agent, prompt="Do something")

        result = await workflow.run()

        assert result.status == WorkflowStatus.COMPLETED
        assert result.final_output == "Task complete"
        assert "task1" in result.task_results

    @patch.object(MimoAgent, "chat")
    async def test_dependent_workflow(self, mock_chat):
        """Test workflow with dependencies."""
        mock_chat.return_value = AgentResponse(
            content="Done",
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        )

        workflow = Workflow("test")
        agent = MimoAgent(name="agent1")
        workflow.add_task("task1", agent, prompt="Step 1")
        workflow.add_task("task2", agent, prompt="Step 2", depends=["task1"])

        result = await workflow.run()

        assert result.status == WorkflowStatus.COMPLETED
        assert len(result.task_results) == 2

    @patch.object(MimoAgent, "chat")
    async def test_workflow_with_context(self, mock_chat):
        """Test workflow with initial context."""
        mock_chat.return_value = AgentResponse(
            content="Processed",
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        )

        workflow = Workflow("test")
        agent = MimoAgent(name="agent1")
        workflow.add_task("task1", agent, prompt="Process {{data}}")

        result = await workflow.run({"data": "test input"})

        assert result.status == WorkflowStatus.COMPLETED
        # Verify the prompt was rendered with context
        call_args = mock_chat.call_args[0][0]
        assert "test input" in call_args

    @patch.object(MimoAgent, "chat")
    async def test_workflow_failure(self, mock_chat):
        """Test workflow handling of task failure."""
        mock_chat.side_effect = RuntimeError("API Error")

        workflow = Workflow("test")
        agent = MimoAgent(name="agent1")
        workflow.add_task("task1", agent, prompt="This will fail")

        result = await workflow.run()

        assert result.status == WorkflowStatus.FAILED
        assert "task1" in result.failed_tasks


class TestTaskResult:
    """Test cases for TaskResult."""

    def test_task_result_duration(self):
        """Test duration calculation."""
        result = TaskResult(
            task_id="test",
            status=TaskStatus.COMPLETED,
            start_time=100.0,
            end_time=101.5,
        )
        assert result.duration_ms == 1500.0

    def test_task_result_no_duration(self):
        """Test duration when times not set."""
        result = TaskResult(task_id="test", status=TaskStatus.PENDING)
        assert result.duration_ms == 0.0

    def test_task_result_tokens(self):
        """Test token count from agent response."""
        response = AgentResponse(
            content="test",
            usage={"total_tokens": 100},
        )
        result = TaskResult(
            task_id="test",
            status=TaskStatus.COMPLETED,
            agent_response=response,
        )
        assert result.tokens_used == 100


class TestWorkflowResult:
    """Test cases for WorkflowResult."""

    def test_workflow_result_metrics(self):
        """Test workflow result metrics."""
        from mimo_devflow.workflow import WorkflowResult

        result = WorkflowResult(
            workflow_id="test",
            status=WorkflowStatus.COMPLETED,
            start_time=100.0,
            end_time=105.0,
        )
        assert result.duration_ms == 5000.0

    def test_workflow_result_tokens(self):
        """Test total token count."""
        from mimo_devflow.workflow import WorkflowResult

        result = WorkflowResult(
            workflow_id="test",
            status=WorkflowStatus.COMPLETED,
            task_results={
                "t1": TaskResult(
                    task_id="t1",
                    status=TaskStatus.COMPLETED,
                    agent_response=AgentResponse(content="a", usage={"total_tokens": 100}),
                ),
                "t2": TaskResult(
                    task_id="t2",
                    status=TaskStatus.COMPLETED,
                    agent_response=AgentResponse(content="b", usage={"total_tokens": 200}),
                ),
            },
        )
        assert result.total_tokens == 300
