"""Configuration management for MIMO DevFlow using Pydantic."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field, field_validator


class MimoAPIConfig(BaseModel):
    """MiMo API connection configuration."""

    base_url: str = Field(
        default="https://api.xiaomimimo.com/v1",
        description="MiMo API base URL",
    )
    api_key: Optional[str] = Field(
        default=None,
        description="API key for authentication. Falls back to MIMO_API_KEY env var.",
    )
    timeout: float = Field(default=60.0, description="Request timeout in seconds")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    retry_delay: float = Field(default=1.0, description="Base retry delay in seconds")

    @field_validator("api_key", mode="before")
    @classmethod
    def resolve_api_key(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return v
        return os.environ.get("MIMO_API_KEY")


class ModelConfig(BaseModel):
    """Model selection configuration."""

    default_model: str = Field(
        default="mimo-v2.5-pro", description="Default model to use"
    )
    available_models: list[str] = Field(
        default=["mimo-v2.5-pro", "mimo-v2.5-vl", "mimo-tts"],
        description="List of available models",
    )
    temperature: float = Field(
        default=0.7, ge=0.0, le=2.0, description="Sampling temperature"
    )
    max_tokens: int = Field(
        default=4096, ge=1, description="Maximum tokens in response"
    )
    top_p: float = Field(default=1.0, ge=0.0, le=1.0, description="Top-p sampling")
    frequency_penalty: float = Field(
        default=0.0, ge=-2.0, le=2.0, description="Frequency penalty"
    )
    presence_penalty: float = Field(
        default=0.0, ge=-2.0, le=2.0, description="Presence penalty"
    )


class WorkflowConfig(BaseModel):
    """Workflow engine configuration."""

    max_parallel_tasks: int = Field(
        default=5, ge=1, description="Maximum parallel task execution"
    )
    task_timeout: float = Field(
        default=120.0, description="Default task timeout in seconds"
    )
    workflow_timeout: float = Field(
        default=600.0, description="Default workflow timeout in seconds"
    )
    retry_policy: RetryPolicy = Field(
        default_factory=lambda: RetryPolicy(), description="Default retry policy"
    )


class RetryPolicy(BaseModel):
    """Retry policy configuration."""

    max_retries: int = Field(default=3, ge=0, description="Maximum retry attempts")
    backoff_factor: float = Field(
        default=2.0, ge=1.0, description="Exponential backoff factor"
    )
    initial_delay: float = Field(
        default=1.0, ge=0.0, description="Initial retry delay in seconds"
    )
    max_delay: float = Field(
        default=60.0, ge=0.0, description="Maximum retry delay in seconds"
    )
    retryable_errors: list[str] = Field(
        default=["TimeoutError", "RateLimitError", "ConnectionError"],
        description="Error types that trigger retries",
    )


class OptimizerConfig(BaseModel):
    """Token optimizer configuration."""

    enabled: bool = Field(default=True, description="Enable token optimization")
    budget: Optional[int] = Field(
        default=None, description="Token budget (None for unlimited)"
    )
    compression_enabled: bool = Field(
        default=True, description="Enable prompt compression"
    )
    cache_enabled: bool = Field(default=True, description="Enable response caching")
    cache_ttl: float = Field(
        default=3600.0, description="Cache time-to-live in seconds"
    )
    cost_per_1k_input: float = Field(
        default=0.001, description="Cost per 1000 input tokens"
    )
    cost_per_1k_output: float = Field(
        default=0.002, description="Cost per 1000 output tokens"
    )


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = Field(default="INFO", description="Log level")
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format string",
    )
    file: Optional[str] = Field(default=None, description="Log file path")
    rich_console: bool = Field(default=True, description="Use Rich console output")


class MimoConfig(BaseModel):
    """Main configuration object for MIMO DevFlow."""

    api: MimoAPIConfig = Field(
        default_factory=MimoAPIConfig, description="API configuration"
    )
    model: ModelConfig = Field(
        default_factory=ModelConfig, description="Model configuration"
    )
    workflow: WorkflowConfig = Field(
        default_factory=WorkflowConfig, description="Workflow configuration"
    )
    optimizer: OptimizerConfig = Field(
        default_factory=OptimizerConfig, description="Optimizer configuration"
    )
    logging: LoggingConfig = Field(
        default_factory=LoggingConfig, description="Logging configuration"
    )

    def __init__(self, api_key: Optional[str] = None, **kwargs):
        if api_key and "api" not in kwargs:
            kwargs["api"] = {"api_key": api_key}
        super().__init__(**kwargs)

    @classmethod
    def from_file(cls, path: str | Path) -> "MimoConfig":
        """Load configuration from a YAML file."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path) as f:
            data = yaml.safe_load(f) or {}

        return cls(**data)

    @classmethod
    def from_env(cls) -> "MimoConfig":
        """Load configuration from environment variables."""
        return cls(
            api_key=os.environ.get("MIMO_API_KEY"),
            model={
                "default_model": os.environ.get("MIMO_MODEL", "mimo-v2.5-pro"),
                "temperature": float(os.environ.get("MIMO_TEMPERATURE", "0.7")),
                "max_tokens": int(os.environ.get("MIMO_MAX_TOKENS", "4096")),
            },
        )

    def save(self, path: str | Path) -> None:
        """Save configuration to a YAML file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            yaml.dump(self.model_dump(), f, default_flow_style=False, sort_keys=False)
