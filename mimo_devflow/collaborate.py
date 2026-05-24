"""
Multi-Agent Collaboration - Agent-to-agent messaging, shared memory, task delegation.

Enables teams of agents to work together through structured communication,
shared knowledge bases, and intelligent task routing.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from mimo_devflow.agent import AgentResponse, MimoAgent
from mimo_devflow.config import MimoConfig
from mimo_devflow.utils.logger import get_logger

logger = get_logger("collaborate")


class MessageType(str, Enum):
    """Types of inter-agent messages."""

    DIRECT = "direct"  # Point-to-point
    BROADCAST = "broadcast"  # To all agents
    REQUEST = "request"  # Requesting help
    RESPONSE = "response"  # Responding to a request
    DELEGATION = "delegation"  # Delegating a task
    STATUS = "status"  # Status update
    FEEDBACK = "feedback"  # Feedback on output


@dataclass
class AgentMessage:
    """A message passed between agents."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    sender: str = ""
    receiver: str = ""  # Empty for broadcast
    message_type: MessageType = MessageType.DIRECT
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    in_reply_to: Optional[str] = None


@dataclass
class DelegatedTask:
    """A task delegated from one agent to another."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    delegator: str = ""
    delegate: str = ""
    description: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    result: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None


class SharedMemory:
    """Shared memory store accessible by all agents in a group.

    Supports key-value storage with namespaces, versioning,
    and change notifications.
    """

    def __init__(self):
        self._store: dict[str, dict[str, Any]] = defaultdict(dict)
        self._history: dict[str, list[tuple[float, str, Any]]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def set(
        self,
        namespace: str,
        key: str,
        value: Any,
        author: str = "",
    ) -> None:
        """Set a value in shared memory.

        Args:
            namespace: Memory namespace (e.g., agent name or topic)
            key: Key to store under
            value: Value to store (must be JSON-serializable)
            author: Who set this value
        """
        async with self._lock:
            self._store[namespace][key] = value
            self._history[f"{namespace}.{key}"].append((time.time(), author, value))
            logger.debug("SharedMemory: %s.%s set by %s", namespace, key, author)

    async def get(
        self,
        namespace: str,
        key: str,
        default: Any = None,
    ) -> Any:
        """Get a value from shared memory.

        Args:
            namespace: Memory namespace
            key: Key to retrieve
            default: Default if key not found

        Returns:
            Stored value or default
        """
        return self._store.get(namespace, {}).get(key, default)

    async def get_namespace(self, namespace: str) -> dict[str, Any]:
        """Get all key-value pairs in a namespace."""
        return dict(self._store.get(namespace, {}))

    async def keys(self, namespace: str) -> list[str]:
        """Get all keys in a namespace."""
        return list(self._store.get(namespace, {}).keys())

    async def append(
        self,
        namespace: str,
        key: str,
        item: Any,
        author: str = "",
    ) -> None:
        """Append to a list in shared memory. Creates list if not exists."""
        async with self._lock:
            current = self._store[namespace].get(key, [])
            if not isinstance(current, list):
                current = [current]
            current.append(item)
            self._store[namespace][key] = current
            self._history[f"{namespace}.{key}"].append((time.time(), author, item))

    def get_history(self, namespace: str, key: str) -> list[tuple[float, str, Any]]:
        """Get change history for a key."""
        return list(self._history.get(f"{namespace}.{key}", []))

    def snapshot(self) -> dict[str, dict[str, Any]]:
        """Get a snapshot of all shared memory."""
        return {ns: dict(vals) for ns, vals in self._store.items()}


class CollaborativeAgentGroup:
    """A group of agents that collaborate to solve tasks.

    Supports:
    - Agent-to-agent direct messaging
    - Broadcast communication
    - Shared memory for knowledge sharing
    - Task delegation with tracking
    - Structured discussion rounds

    Example:
        >>> group = CollaborativeAgentGroup("research-team")
        >>> group.add_agent(MimoAgent(name="researcher", system="Research topics"))
        >>> group.add_agent(MimoAgent(name="writer", system="Write reports"))
        >>> group.add_agent(MimoAgent(name="reviewer", system="Review content"))
        >>> result = await group.discuss("What are the latest AI trends?", rounds=3)
    """

    def __init__(
        self,
        name: str,
        config: Optional[MimoConfig] = None,
        max_message_history: int = 1000,
    ):
        self.name = name
        self.group_id = str(uuid.uuid4())[:8]
        self.config = config or MimoConfig()
        self.max_message_history = max_message_history

        self._agents: dict[str, MimoAgent] = {}
        self._shared_memory = SharedMemory()
        self._messages: list[AgentMessage] = []
        self._tasks: dict[str, DelegatedTask] = {}
        self._moderator: Optional[MimoAgent] = None

        logger.info("CollaborativeAgentGroup '%s' (%s) created", self.name, self.group_id)

    def add_agent(self, agent: MimoAgent, role: str = "") -> None:
        """Add an agent to the group.

        Args:
            agent: The agent to add
            role: Optional role description
        """
        self._agents[agent.name] = agent
        if role:
            asyncio.create_task(
                self._shared_memory.set("roles", agent.name, role, author="system")
            )
        logger.info("Agent '%s' joined group '%s'", agent.name, self.name)

    def set_moderator(self, agent: MimoAgent) -> None:
        """Set a moderator agent for discussions."""
        self._moderator = agent
        if agent.name not in self._agents:
            self.add_agent(agent, role="moderator")

    async def send_message(
        self,
        sender: str,
        receiver: str,
        content: str,
        message_type: MessageType = MessageType.DIRECT,
        metadata: Optional[dict[str, Any]] = None,
    ) -> AgentMessage:
        """Send a message between agents.

        Args:
            sender: Sender agent name
            receiver: Receiver agent name (empty for broadcast)
            content: Message content
            message_type: Type of message
            metadata: Optional metadata

        Returns:
            The sent AgentMessage
        """
        if sender not in self._agents:
            raise ValueError(f"Sender '{sender}' not in group")
        if receiver and receiver not in self._agents:
            raise ValueError(f"Receiver '{receiver}' not in group")

        msg = AgentMessage(
            sender=sender,
            receiver=receiver,
            message_type=message_type,
            content=content,
            metadata=metadata or {},
        )

        self._messages.append(msg)

        # Store in shared memory
        await self._shared_memory.append(
            "messages", "inbox", msg.__dict__, author=sender
        )

        logger.info(
            "Message: %s -> %s [%s]: %s...",
            sender, receiver or "ALL", message_type.value, content[:50],
        )

        return msg

    async def delegate_task(
        self,
        delegator: str,
        delegate: str,
        description: str,
        context: Optional[dict[str, Any]] = None,
    ) -> DelegatedTask:
        """Delegate a task from one agent to another.

        Args:
            delegator: Agent delegating the task
            delegate: Agent receiving the task
            description: Task description
            context: Optional context for the task

        Returns:
            DelegatedTask with execution result
        """
        if delegate not in self._agents:
            raise ValueError(f"Delegate '{delegate}' not in group")

        task = DelegatedTask(
            delegator=delegator,
            delegate=delegate,
            description=description,
            context=context or {},
        )

        # Execute the delegated task
        task.status = "running"
        agent = self._agents[delegate]

        try:
            response = await agent.chat(
                f"Task from {delegator}: {description}\n\n"
                f"Context: {context or 'None provided'}"
            )
            task.result = response.content
            task.status = "completed"
            task.completed_at = time.time()

            # Notify delegator
            await self.send_message(
                sender=delegate,
                receiver=delegator,
                content=f"Completed task: {description}\n\nResult: {task.result}",
                message_type=MessageType.RESPONSE,
                metadata={"task_id": task.id},
            )

        except Exception as e:
            task.status = "failed"
            task.result = str(e)
            task.completed_at = time.time()
            logger.error("Task delegation failed: %s", e)

        self._tasks[task.id] = task
        return task

    async def discuss(
        self,
        topic: str,
        rounds: int = 3,
        participants: Optional[list[str]] = None,
        summarizer: Optional[str] = None,
    ) -> DiscussionResult:
        """Run a structured multi-round discussion.

        Args:
            topic: Discussion topic or question
            rounds: Number of discussion rounds
            participants: List of agent names (None for all)
            summarizer: Agent to produce final summary (None for moderator or last)

        Returns:
            DiscussionResult with all contributions and consensus
        """
        agents = participants or list(self._agents.keys())
        agent_list = [self._agents[name] for name in agents if name in self._agents]

        if not agent_list:
            raise ValueError("No valid participants for discussion")

        contributions: list[dict[str, Any]] = []
        round_summaries: list[str] = []

        logger.info(
            "Starting discussion '%s' with %d agents, %d rounds",
            topic, len(agent_list), rounds,
        )

        for round_num in range(1, rounds + 1):
            round_contributions = []

            for agent in agent_list:
                # Build context from previous contributions
                context = self._build_discussion_context(
                    topic, contributions, round_num
                )

                response = await agent.chat(context)
                contribution = {
                    "agent": agent.name,
                    "round": round_num,
                    "content": response.content,
                    "timestamp": time.time(),
                }
                contributions.append(contribution)
                round_contributions.append(contribution)

                # Store in shared memory
                await self._shared_memory.set(
                    "discussion", f"round_{round_num}_{agent.name}",
                    response.content, author=agent.name,
                )

            # Summarize round
            round_text = "\n".join(
                f"[{c['agent']}]: {c['content']}" for c in round_contributions
            )
            round_summaries.append(f"Round {round_num}:\n{round_text}")

            logger.info("Discussion round %d/%d complete", round_num, rounds)

        # Generate final summary
        if summarizer and summarizer in self._agents:
            summary_agent = self._agents[summarizer]
        elif self._moderator:
            summary_agent = self._moderator
        else:
            summary_agent = agent_list[-1]

        summary_prompt = (
            f"Discussion Topic: {topic}\n\n"
            f"Discussion History:\n"
            + "\n\n".join(round_summaries)
            + "\n\nPlease synthesize the key points and provide a consensus summary."
        )

        summary_response = await summary_agent.chat(summary_prompt)

        return DiscussionResult(
            topic=topic,
            rounds=rounds,
            contributions=contributions,
            consensus=summary_response.content,
            participants=[a.name for a in agent_list],
        )

    def _build_discussion_context(
        self,
        topic: str,
        previous: list[dict[str, Any]],
        current_round: int,
    ) -> str:
        """Build context prompt for a discussion round."""
        parts = [f"Discussion Topic: {topic}"]

        if previous:
            parts.append("\nPrevious contributions:")
            for contrib in previous[-10:]:  # Last 10 for context
                parts.append(f"[{contrib['agent']}, Round {contrib['round']}]: {contrib['content']}")

        if current_round == 1:
            parts.append("\nPlease provide your initial perspective on this topic.")
        else:
            parts.append(
                f"\nThis is round {current_round}. "
                "Build on previous points, address disagreements, "
                "and deepen the analysis."
            )

        return "\n".join(parts)

    @property
    def agents(self) -> list[str]:
        """List of agent names in the group."""
        return list(self._agents.keys())

    @property
    def message_history(self) -> list[dict[str, Any]]:
        """Get all messages as dicts."""
        return [msg.__dict__ for msg in self._messages]

    @property
    def shared_memory(self) -> SharedMemory:
        """Access the shared memory store."""
        return self._shared_memory

    @property
    def pending_tasks(self) -> list[DelegatedTask]:
        """Get tasks that haven't completed."""
        return [t for t in self._tasks.values() if t.status in ("pending", "running")]


@dataclass
class DiscussionResult:
    """Result of a multi-agent discussion."""

    topic: str
    rounds: int
    contributions: list[dict[str, Any]]
    consensus: Optional[str] = None
    participants: list[str] = field(default_factory=list)

    @property
    def total_contributions(self) -> int:
        return len(self.contributions)

    def get_contributions_by_agent(self, agent_name: str) -> list[dict[str, Any]]:
        """Get all contributions from a specific agent."""
        return [c for c in self.contributions if c["agent"] == agent_name]
