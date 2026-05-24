# MIMO DevFlow API Reference

## Core Classes

### `MimoAgent`

Primary interface for MiMo model interactions.

```python
class MimoAgent:
    def __init__(
        name: str = "default",
        config: MimoConfig = None,
        system: str = None,
        model: str = None,
        tools: list[ToolDefinition] = None,
        max_turns: int = 50,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        optimizer: TokenOptimizer = None,
    )
```

#### Methods

##### `chat(message, *, image=None, compress=False, metadata=None) -> AgentResponse`
Send a message and get a complete response. Handles multi-turn tool calling automatically.

**Parameters:**
- `message` (str): User message text
- `image` (str, optional): Image URL or base64 for vision models
- `compress` (bool): Apply prompt compression via optimizer
- `metadata` (dict, optional): Metadata to attach to the message

**Returns:** `AgentResponse`

##### `stream(message, *, image=None) -> AsyncIterator[StreamChunk]`
Stream a response chunk by chunk.

**Parameters:**
- `message` (str): User message text
- `image` (str, optional): Image URL or base64

**Yields:** `StreamChunk` objects

##### `tool(func=None, *, name=None, description=None, parameters=None) -> Callable`
Decorator to register a function as a callable tool.

```python
@agent.tool
def my_tool(param: str) -> dict:
    """Tool description."""
    return {"result": param}
```

##### `clear_history() -> None`
Clear conversation history, preserving system prompt.

##### `close() -> None`
Close the HTTP client and clean up resources.

#### Properties

- `history` → `list[dict]`: Conversation history
- `token_usage` → `dict[str, int]`: Total token usage statistics
- `get_tools()` → `list[dict]`: Registered tool schemas

---

### `AgentResponse`

Response from the agent.

```python
@dataclass
class AgentResponse:
    content: Optional[str]           # Response text
    tool_calls: list[dict]           # Tool calls requested
    finish_reason: Optional[str]     # "stop", "tool_calls", etc.
    usage: dict[str, int]            # Token usage
    model: Optional[str]             # Model used
    message_id: str                  # Unique message ID
    latency_ms: float                # Request latency
    metadata: dict[str, Any]         # Additional metadata
```

**Properties:**
- `total_tokens` → `int`: Total tokens used
- `input_tokens` → `int`: Input/prompt tokens
- `output_tokens` → `int`: Output/completion tokens

---

### `Workflow`

DAG-based workflow orchestration engine.

```python
class Workflow:
    def __init__(
        name: str,
        config: MimoConfig = None,
        max_parallel: int = 5,
        timeout: float = 600.0,
        on_task_complete: Callable = None,
        on_workflow_complete: Callable = None,
    )
```

#### Methods

##### `add_task(task_id, agent, prompt, *, depends=None, condition=None, retry_policy=None, timeout=None) -> Task`
Add a task to the workflow.

**Parameters:**
- `task_id` (str): Unique task identifier
- `agent` (MimoAgent): Agent to execute this task
- `prompt` (str): Task prompt with `{{variable}}` templating
- `depends` (list[str], optional): Task IDs this task depends on
- `condition` (Callable, optional): Function returning True if task should execute
- `retry_policy` (RetryPolicy, optional): Retry configuration
- `timeout` (float, optional): Task timeout in seconds

##### `add_fallback(task_id, fallback_agent, condition="failure") -> None`
Add a fallback task that runs when the original fails.

##### `set_retry_policy(task_id, max_retries=3, backoff=2.0, initial_delay=1.0) -> None`
Set retry policy for a specific task.

##### `validate() -> list[str]`
Validate the workflow DAG. Returns list of errors (empty if valid).

##### `topological_order() -> list[str]`
Get topological ordering of tasks.

##### `get_execution_plan() -> list[list[str]]`
Get execution plan showing parallel task groups.

##### `run(context=None) -> WorkflowResult`
Execute the workflow.

**Parameters:**
- `context` (dict, optional): Initial context variables

**Returns:** `WorkflowResult`

---

### `WorkflowResult`

```python
@dataclass
class WorkflowResult:
    workflow_id: str
    status: WorkflowStatus
    task_results: dict[str, TaskResult]
    final_output: Optional[str]
    start_time: float
    end_time: float
```

**Properties:**
- `duration_ms` → `float`: Total duration
- `total_tokens` → `int`: Total tokens used
- `succeeded_tasks` → `list[str]`: IDs of completed tasks
- `failed_tasks` → `list[str]`: IDs of failed tasks

---

### `ModelRouter`

Intelligent model selection.

```python
class ModelRouter:
    def __init__(
        config: MimoConfig = None,
        default_model: str = "mimo-v2.5-pro",
        cost_weight: float = 0.3,
        quality_weight: float = 0.7,
    )
```

#### Methods

##### `analyze_task(prompt, *, image=None, audio=None, text_to_speech=False) -> RoutingDecision`
Analyze a task and determine the best model.

##### `route(prompt, *, image=None, system=None, **kwargs) -> AgentResponse`
Route and execute with the optimal model.

##### `register_model(capabilities: ModelCapabilities) -> None`
Register a custom model.

---

### `TokenOptimizer`

Token usage optimization.

```python
class TokenOptimizer:
    def __init__(
        budget: int = None,
        compression_enabled: bool = True,
        cache_enabled: bool = True,
        cache_ttl: float = 3600.0,
        cost_per_1k_input: float = 0.001,
        cost_per_1k_output: float = 0.002,
    )
```

#### Methods

##### `compress_prompt(prompt: str) -> str`
Compress a prompt by removing redundancy.

##### `compress_messages(messages: list) -> list`
Compress message list for context management.

##### `check_cache(prompt, model="") -> Optional[str]`
Check if a response is cached.

##### `cache_response(prompt, response, model="") -> None`
Cache a response.

##### `record_usage(input_tokens, output_tokens, ...) -> TokenUsage`
Record token usage for tracking.

##### `get_cost_breakdown(model=None) -> CostBreakdown`
Get detailed cost breakdown.

#### Properties

- `total_tokens` → `int`: Total tokens used
- `total_cost` → `float`: Total cost
- `tokens_saved` → `int`: Tokens saved via optimization
- `budget_remaining` → `Optional[int]`: Remaining budget
- `cache_stats` → `dict`: Cache performance stats

---

### `CollaborativeAgentGroup`

Multi-agent collaboration.

```python
class CollaborativeAgentGroup:
    def __init__(name: str, config: MimoConfig = None)
```

#### Methods

##### `add_agent(agent: MimoAgent, role: str = "") -> None`
Add an agent to the group.

##### `set_moderator(agent: MimoAgent) -> None`
Set a moderator agent.

##### `send_message(sender, receiver, content, ...) -> AgentMessage`
Send a message between agents.

##### `delegate_task(delegator, delegate, description, ...) -> DelegatedTask`
Delegate a task from one agent to another.

##### `discuss(topic, rounds=3, ...) -> DiscussionResult`
Run a structured multi-round discussion.

---

### `SharedMemory`

Shared memory store for agent groups.

```python
class SharedMemory:
    async def set(namespace, key, value, author="") -> None
    async def get(namespace, key, default=None) -> Any
    async def get_namespace(namespace) -> dict
    async def append(namespace, key, item, author="") -> None
    def get_history(namespace, key) -> list
    def snapshot() -> dict
```

---

### `Evaluator`

Agent evaluation framework.

```python
class Evaluator:
    def __init__(config: MimoConfig = None, custom_scorers: dict = None)
```

#### Methods

##### `add_test(test: TestCase) -> None`
Add a test case.

##### `load_tests(path: str) -> None`
Load tests from JSON file.

##### `benchmark(agent, tests=None, tags=None) -> BenchmarkResult`
Run benchmark tests.

##### `compare(*benchmark_results) -> dict`
Compare multiple benchmark results.

##### `generate_report(result, output_path=None) -> str`
Generate a formatted benchmark report.

---

### `MimoConfig`

Configuration management.

```python
class MimoConfig:
    api: MimoAPIConfig          # API connection settings
    model: ModelConfig          # Model parameters
    workflow: WorkflowConfig    # Workflow engine settings
    optimizer: OptimizerConfig  # Token optimizer settings
    logging: LoggingConfig      # Logging configuration
```

**Class Methods:**
- `from_file(path: str) -> MimoConfig`: Load from YAML file
- `from_env() -> MimoConfig`: Load from environment variables

**Instance Methods:**
- `save(path: str) -> None`: Save to YAML file

---

## Enums

### `TaskStatus`
`PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `SKIPPED`, `CANCELLED`, `RETRYING`

### `WorkflowStatus`
`CREATED`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED`

### `TaskType`
`TEXT_GENERATION`, `CODE_GENERATION`, `CODE_REVIEW`, `VISION`, `MULTIMODAL`, `SPEECH`, `TRANSLATION`, `SUMMARIZATION`, `QUESTION_ANSWERING`, `MATH`, `REASONING`, `CREATIVE_WRITING`, `DATA_ANALYSIS`, `CONVERSATION`

### `MessageType`
`DIRECT`, `BROADCAST`, `REQUEST`, `RESPONSE`, `DELEGATION`, `STATUS`, `FEEDBACK`
