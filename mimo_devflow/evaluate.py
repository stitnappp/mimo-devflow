"""
Evaluation Framework - Benchmark agents, track metrics, generate reports.

Provides tools for systematic agent evaluation including:
- Performance benchmarking across task types
- Quality metrics tracking
- Cost efficiency analysis
- Comparative reports between agents/models
"""

from __future__ import annotations

import json
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from mimo_devflow.agent import AgentResponse, MimoAgent
from mimo_devflow.config import MimoConfig
from mimo_devflow.utils.logger import get_logger

logger = get_logger("evaluate")


@dataclass
class TestCase:
    """A single evaluation test case."""

    id: str
    name: str
    input_prompt: str
    expected_output: Optional[str] = None
    expected_contains: Optional[list[str]] = None
    max_tokens: Optional[int] = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TestResult:
    """Result of running a single test case."""

    test_id: str
    passed: bool
    response: Optional[AgentResponse] = None
    actual_output: Optional[str] = None
    score: float = 0.0  # 0.0 to 1.0
    latency_ms: float = 0.0
    tokens_used: int = 0
    error: Optional[str] = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkResult:
    """Results of a full benchmark run."""

    agent_name: str
    model: str
    test_results: list[TestResult] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_tests(self) -> int:
        return len(self.test_results)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.test_results if r.passed)

    @property
    def failed(self) -> int:
        return self.total_tests - self.passed

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total_tests if self.total_tests > 0 else 0.0

    @property
    def avg_score(self) -> float:
        scores = [r.score for r in self.test_results if r.score > 0]
        return statistics.mean(scores) if scores else 0.0

    @property
    def avg_latency_ms(self) -> float:
        latencies = [r.latency_ms for r in self.test_results if r.latency_ms > 0]
        return statistics.mean(latencies) if latencies else 0.0

    @property
    def p95_latency_ms(self) -> float:
        latencies = sorted(r.latency_ms for r in self.test_results if r.latency_ms > 0)
        if not latencies:
            return 0.0
        idx = int(len(latencies) * 0.95)
        return latencies[min(idx, len(latencies) - 1)]

    @property
    def total_tokens(self) -> int:
        return sum(r.tokens_used for r in self.test_results)

    @property
    def duration_ms(self) -> float:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time) * 1000
        return 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "agent_name": self.agent_name,
            "model": self.model,
            "total_tests": self.total_tests,
            "passed": self.passed,
            "failed": self.failed,
            "pass_rate": round(self.pass_rate, 4),
            "avg_score": round(self.avg_score, 4),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "p95_latency_ms": round(self.p95_latency_ms, 2),
            "total_tokens": self.total_tokens,
            "duration_ms": round(self.duration_ms, 2),
            "test_results": [
                {
                    "test_id": r.test_id,
                    "passed": r.passed,
                    "score": round(r.score, 4),
                    "latency_ms": round(r.latency_ms, 2),
                    "tokens_used": r.tokens_used,
                    "error": r.error,
                }
                for r in self.test_results
            ],
        }


class MetricTracker:
    """Tracks performance metrics over time.

    Records metrics with timestamps for trend analysis and reporting.
    """

    def __init__(self):
        self._metrics: dict[str, list[tuple[float, float]]] = {}
        self._counters: dict[str, int] = {}

    def record(self, metric_name: str, value: float) -> None:
        """Record a metric value with timestamp."""
        if metric_name not in self._metrics:
            self._metrics[metric_name] = []
        self._metrics[metric_name].append((time.time(), value))

    def increment(self, counter_name: str, amount: int = 1) -> None:
        """Increment a counter."""
        self._counters[counter_name] = self._counters.get(counter_name, 0) + amount

    def get_latest(self, metric_name: str) -> Optional[float]:
        """Get the most recent value of a metric."""
        if metric_name in self._metrics and self._metrics[metric_name]:
            return self._metrics[metric_name][-1][1]
        return None

    def get_mean(self, metric_name: str) -> Optional[float]:
        """Get the mean value of a metric."""
        if metric_name in self._metrics and self._metrics[metric_name]:
            return statistics.mean(v for _, v in self._metrics[metric_name])
        return None

    def get_p95(self, metric_name: str) -> Optional[float]:
        """Get the 95th percentile value."""
        if metric_name not in self._metrics or not self._metrics[metric_name]:
            return None
        values = sorted(v for _, v in self._metrics[metric_name])
        idx = int(len(values) * 0.95)
        return values[min(idx, len(values) - 1)]

    def get_counter(self, counter_name: str) -> int:
        """Get counter value."""
        return self._counters.get(counter_name, 0)

    def get_summary(self) -> dict[str, Any]:
        """Get summary of all tracked metrics."""
        summary = {}
        for name, values in self._metrics.items():
            if values:
                vals = [v for _, v in values]
                summary[name] = {
                    "count": len(vals),
                    "mean": round(statistics.mean(vals), 4),
                    "min": round(min(vals), 4),
                    "max": round(max(vals), 4),
                    "latest": round(vals[-1], 4),
                }
                if len(vals) >= 2:
                    summary[name]["stdev"] = round(statistics.stdev(vals), 4)
        summary["counters"] = dict(self._counters)
        return summary


class Evaluator:
    """Agent evaluation framework.

    Run benchmarks, compare agents, and generate performance reports.

    Example:
        >>> evaluator = Evaluator()
        >>> evaluator.add_test(TestCase(id="t1", name="Greeting", input_prompt="Hello!"))
        >>> result = await evaluator.benchmark(agent)
        >>> print(f"Pass rate: {result.pass_rate:.1%}")
    """

    def __init__(
        self,
        config: Optional[MimoConfig] = None,
        custom_scorers: Optional[dict[str, Callable]] = None,
    ):
        self.config = config or MimoConfig()
        self._tests: list[TestCase] = []
        self._custom_scorers = custom_scorers or {}
        self._metric_tracker = MetricTracker()
        self._benchmarks: list[BenchmarkResult] = []

    def add_test(self, test: TestCase) -> None:
        """Add a test case to the evaluation suite."""
        self._tests.append(test)
        logger.debug("Added test '%s' (%s)", test.name, test.id)

    def add_tests(self, tests: list[TestCase]) -> None:
        """Add multiple test cases."""
        for test in tests:
            self.add_test(test)

    def load_tests(self, path: str) -> None:
        """Load test cases from a JSON file.

        Expected format:
        [
            {"id": "t1", "name": "Test 1", "input_prompt": "...", "expected_output": "..."},
            ...
        ]
        """
        with open(path) as f:
            data = json.load(f)

        for item in data:
            test = TestCase(
                id=item["id"],
                name=item["name"],
                input_prompt=item["input_prompt"],
                expected_output=item.get("expected_output"),
                expected_contains=item.get("expected_contains"),
                max_tokens=item.get("max_tokens"),
                tags=item.get("tags", []),
                metadata=item.get("metadata", {}),
            )
            self.add_test(test)

        logger.info("Loaded %d tests from %s", len(data), path)

    async def benchmark(
        self,
        agent: MimoAgent,
        tests: Optional[list[TestCase]] = None,
        tags: Optional[list[str]] = None,
    ) -> BenchmarkResult:
        """Run benchmark tests against an agent.

        Args:
            agent: The agent to benchmark
            tests: Specific tests to run (None for all)
            tags: Filter tests by tags

        Returns:
            BenchmarkResult with all test results
        """
        test_suite = tests or self._tests
        if tags:
            test_suite = [t for t in test_suite if any(tag in t.tags for tag in tags)]

        if not test_suite:
            logger.warning("No tests to run")
            return BenchmarkResult(agent_name=agent.name, model=agent.model)

        logger.info(
            "Running %d tests on agent '%s' (model=%s)",
            len(test_suite), agent.name, agent.model,
        )

        result = BenchmarkResult(
            agent_name=agent.name,
            model=agent.model,
            start_time=time.time(),
        )

        for test in test_suite:
            test_result = await self._run_test(agent, test)
            result.test_results.append(test_result)

            self._metric_tracker.record(f"latency.{test.id}", test_result.latency_ms)
            self._metric_tracker.record(f"score.{test.id}", test_result.score)

            if test_result.passed:
                self._metric_tracker.increment("tests_passed")
            else:
                self._metric_tracker.increment("tests_failed")

        result.end_time = time.time()
        self._benchmarks.append(result)

        logger.info(
            "Benchmark complete: %d/%d passed (%.1f%%), avg latency=%.1fms",
            result.passed, result.total_tests,
            result.pass_rate * 100, result.avg_latency_ms,
        )

        return result

    async def _run_test(self, agent: MimoAgent, test: TestCase) -> TestResult:
        """Run a single test case."""
        start = time.monotonic()

        try:
            response = await agent.chat(test.input_prompt)
            latency = (time.monotonic() - start) * 1000

            # Score the response
            score = self._score_response(response, test)
            passed = score >= 0.7  # 70% threshold

            # Check expected contains
            if test.expected_contains and response.content:
                for phrase in test.expected_contains:
                    if phrase.lower() not in response.content.lower():
                        passed = False
                        score *= 0.5

            return TestResult(
                test_id=test.id,
                passed=passed,
                response=response,
                actual_output=response.content,
                score=score,
                latency_ms=latency,
                tokens_used=response.total_tokens,
            )

        except Exception as e:
            latency = (time.monotonic() - start) * 1000
            logger.error("Test '%s' failed with error: %s", test.id, e)
            return TestResult(
                test_id=test.id,
                passed=False,
                latency_ms=latency,
                error=str(e),
            )

    def _score_response(self, response: AgentResponse, test: TestCase) -> float:
        """Score a response against expected output.

        Returns a score between 0.0 and 1.0.
        """
        if not response.content:
            return 0.0

        # If no expected output, score based on response quality
        if not test.expected_output:
            # Basic quality heuristics
            score = 0.5  # Base score for generating any response
            if len(response.content) > 20:
                score += 0.2  # Substantial response
            if response.finish_reason == "stop":
                score += 0.2  # Clean completion
            if not response.tool_calls:
                score += 0.1  # Direct answer
            return min(score, 1.0)

        # Similarity-based scoring
        expected_words = set(test.expected_output.lower().split())
        actual_words = set(response.content.lower().split())

        if not expected_words:
            return 0.5

        overlap = expected_words & actual_words
        recall = len(overlap) / len(expected_words)

        # Check for custom scorers
        for name, scorer in self._custom_scorers.items():
            try:
                custom_score = scorer(response.content, test.expected_output)
                if custom_score is not None:
                    return float(custom_score)
            except Exception:
                continue

        return min(recall, 1.0)

    def compare(
        self,
        *benchmark_results: BenchmarkResult,
    ) -> dict[str, Any]:
        """Compare multiple benchmark results.

        Args:
            *benchmark_results: Benchmark results to compare

        Returns:
            Comparison report dictionary
        """
        if len(benchmark_results) < 2:
            raise ValueError("Need at least 2 benchmark results to compare")

        comparison = {
            "agents": [],
            "winner": None,
            "metrics": {},
        }

        best_pass_rate = 0.0
        winner = ""

        for result in benchmark_results:
            agent_info = {
                "name": result.agent_name,
                "model": result.model,
                "pass_rate": round(result.pass_rate, 4),
                "avg_score": round(result.avg_score, 4),
                "avg_latency_ms": round(result.avg_latency_ms, 2),
                "p95_latency_ms": round(result.p95_latency_ms, 2),
                "total_tokens": result.total_tokens,
                "duration_ms": round(result.duration_ms, 2),
            }
            comparison["agents"].append(agent_info)

            if result.pass_rate > best_pass_rate:
                best_pass_rate = result.pass_rate
                winner = result.agent_name

        comparison["winner"] = winner
        return comparison

    def generate_report(
        self,
        result: BenchmarkResult,
        output_path: Optional[str] = None,
    ) -> str:
        """Generate a formatted benchmark report.

        Args:
            result: Benchmark result to report on
            output_path: Optional path to save report

        Returns:
            Report text
        """
        lines = [
            f"# Benchmark Report: {result.agent_name}",
            f"Model: {result.model}",
            f"Duration: {result.duration_ms:.0f}ms",
            "",
            "## Summary",
            f"- Total Tests: {result.total_tests}",
            f"- Passed: {result.passed}",
            f"- Failed: {result.failed}",
            f"- Pass Rate: {result.pass_rate:.1%}",
            f"- Average Score: {result.avg_score:.3f}",
            f"- Average Latency: {result.avg_latency_ms:.1f}ms",
            f"- P95 Latency: {result.p95_latency_ms:.1f}ms",
            f"- Total Tokens: {result.total_tokens}",
            "",
            "## Test Results",
            "",
        ]

        for tr in result.test_results:
            status = "✅" if tr.passed else "❌"
            lines.append(
                f"- {status} `{tr.test_id}`: score={tr.score:.3f}, "
                f"latency={tr.latency_ms:.0f}ms, tokens={tr.tokens_used}"
            )
            if tr.error:
                lines.append(f"  Error: {tr.error}")

        report = "\n".join(lines)

        if output_path:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(report)
            logger.info("Report saved to %s", output_path)

        return report

    @property
    def metric_tracker(self) -> MetricTracker:
        """Access the metric tracker."""
        return self._metric_tracker

    @property
    def benchmarks(self) -> list[BenchmarkResult]:
        """Get all benchmark results."""
        return list(self._benchmarks)
