"""
MIMO DevFlow Agent - Multi-agent orchestration framework for Xiaomi MiMo models.

A production-grade framework for building intelligent, collaborative AI agent systems
with DAG-based workflow orchestration, smart model routing, and token optimization.
"""

__version__ = "0.3.0"
__author__ = "MIMO DevFlow Contributors"
__license__ = "MIT"

from mimo_devflow.agent import MimoAgent
from mimo_devflow.workflow import Workflow, Task
from mimo_devflow.router import ModelRouter
from mimo_devflow.optimizer import TokenOptimizer
from mimo_devflow.collaborate import CollaborativeAgentGroup, SharedMemory
from mimo_devflow.evaluate import Evaluator, MetricTracker
from mimo_devflow.config import MimoConfig

__all__ = [
    "MimoAgent",
    "Workflow",
    "Task",
    "ModelRouter",
    "TokenOptimizer",
    "CollaborativeAgentGroup",
    "SharedMemory",
    "Evaluator",
    "MetricTracker",
    "MimoConfig",
]
