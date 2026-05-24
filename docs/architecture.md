# MIMO DevFlow Architecture

## Overview

MIMO DevFlow is a multi-agent orchestration framework designed for Xiaomi's MiMo models. It provides a complete toolkit for building, running, and evaluating AI agent systems.

## Core Components

### 1. Agent Layer (`agent.py`)

The foundational component. Each `MimoAgent` manages:
- Conversation history and context
- Tool registration and execution
- Streaming and non-streaming responses
- Automatic retry with exponential backoff

```
User Input → MimoAgent → MiMo API → Response
                    ↓
              Tool Execution → Feedback Loop
```

### 2. Workflow Engine (`workflow.py`)

DAG-based orchestration that manages task dependencies:

```
Task A ──→ Task B ──→ Task D
   └──────→ Task C ──┘
```

Key features:
- Topological sorting for execution order
- Parallel execution of independent tasks
- Conditional branching
- Task-level retry policies
- Context templating

### 3. Model Router (`router.py`)

Intelligent model selection based on task characteristics:

| Input Type | Task Pattern | Selected Model |
|-----------|-------------|----------------|
| Text | Code generation | mimo-v2.5-pro |
| Image | Vision tasks | mimo-v2.5-vl |
| Audio | Speech tasks | mimo-tts |
| Text | General | mimo-v2.5-pro |

Scoring considers:
- Task type alignment (40%)
- Quality rating (30%)
- Cost efficiency (30%)

### 4. Token Optimizer (`optimizer.py`)

Reduces token usage through:
- Prompt compression (remove filler, deduplicate)
- Context window pruning (keep recent, prune old)
- Response caching (LRU with TTL)
- Real-time cost tracking

### 5. Collaboration Engine (`collaborate.py`)

Multi-agent communication:
- Direct messaging between agents
- Broadcast to all agents
- Shared memory store with namespaces
- Task delegation with tracking
- Structured discussion rounds

### 6. Evaluation Framework (`evaluate.py`)

Systematic agent assessment:
- Test case management
- Automated scoring
- Metric tracking over time
- Comparative benchmarking
- Report generation

## Data Flow

```
┌─────────────┐
│ User Input  │
└──────┬──────┘
       ↓
┌──────────────┐     ┌─────────────┐
│   Router     │────→│ Model Select│
└──────┬───────┘     └─────────────┘
       ↓
┌──────────────┐     ┌─────────────┐
│  Optimizer   │────→│  Compress   │
└──────┬───────┘     └─────────────┘
       ↓
┌──────────────┐     ┌─────────────┐
│   Agent      │────→│  MiMo API   │
└──────┬───────┘     └─────────────┘
       ↓
┌──────────────┐     ┌─────────────┐
│  Workflow    │────→│  Execute DAG│
└──────┬───────┘     └─────────────┘
       ↓
┌──────────────┐
│   Output     │
└──────────────┘
```

## Error Handling

All components implement consistent error handling:
- Exponential backoff for API failures
- Task-level retry with configurable policies
- Graceful degradation (fallback tasks)
- Budget enforcement with warnings

## Concurrency Model

- Async/await throughout (asyncio-based)
- Semaphore-limited parallel execution
- Non-blocking tool execution
- Streaming via SSE (Server-Sent Events)

## Configuration

Pydantic-based configuration with:
- YAML file support
- Environment variable fallback
- Per-component configuration sections
- Validation and type safety
