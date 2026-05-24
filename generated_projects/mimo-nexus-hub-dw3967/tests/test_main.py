"""Tests for MIMO Nexus Hub"""
import pytest
import asyncio
from src.main import MiMoAgent, AgentConfig, WorkflowEngine

def test_agent_config():
    config = AgentConfig(name="test")
    assert config.name == "test"
    assert config.model == "mimo-v2.5-pro"

def test_workflow_add_step():
    engine = WorkflowEngine()
    engine.add_step("step1", None, "test prompt")
    assert len(engine.steps) == 1

def test_workflow_dependency():
    engine = WorkflowEngine()
    engine.add_step("a", None, "step a")
    engine.add_step("b", None, "step b", depends_on=["a"])
    assert engine.steps[1]["depends_on"] == ["a"]

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
