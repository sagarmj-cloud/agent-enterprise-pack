"""
Context Window Manager
======================
Manages context window limits for LLM conversations.

Features:
- Token counting with multiple tokenizers
- 4 truncation strategies
- Priority-based message retention
- Automatic context management
"""

import logging
from typing import Optional, List, Dict, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class TruncationStrategy(Enum):
    """Strategies for truncating conversation history."""
    FIFO = "fifo"                    # First in, first out (drop oldest)
    LIFO = "lifo"                    # Last in, first out (drop newest)
    SLIDING_WINDOW = "sliding_window"  # Keep recent N messages
    PRIORITY = "priority"             # Keep high-priority messages
    SUMMARIZE = "summarize"           # Summarize old messages


class MessageRole(Enum):
    """Message roles in conversation."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    FUNCTION = "function"


@dataclass
class Message:
    """Conversation message with metadata."""
    role: MessageRole
    content: str
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    priority: int = 0  # Higher = more important to keep
    token_count: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to API-compatible dict."""
        result = {
            "role": self.role.value,
            "content": self.content,
        }
        if self.name:
            result["name"] = self.name
        if self.tool_call_id:
            result["tool_call_id"] = self.tool_call_id
        return result


@dataclass
class ContextConfig:
    """Configuration for context management."""
    max_tokens: int = 128000           # Model's context window
    target_tokens: int = 100000        # Target to stay under
    reserve_tokens: int = 4000         # Reserved for response
    system_prompt_tokens: int = 2000   # Estimated system prompt size
    truncation_strategy: TruncationStrategy = TruncationStrategy.SLIDING_WINDOW
    sliding_window_size: int = 50      # Messages to keep in sliding window
    min_messages: int = 4              # Minimum messages to keep
    preserve_system: bool = True       # Always keep system message
    preserve_latest_user: bool = True  # Always keep latest user message


class TokenCounter(ABC):
    """Abstract base class for token counters."""
    
    @abstractmethod
    def count(self, text: str) -> int:
        """Count tokens in text."""
        pass
    
    @abstractmethod
    def count_messages(self, messages: List[Message]) -> int:
        """Count tokens in message list."""
        pass


class ApproximateTokenCounter(TokenCounter):
    """
    Approximate token counter using character-based estimation.
    Fast but less accurate. Use for development/testing.
    """
    
    def __init__(self, chars_per_token: float = 4.0):
        """
        Initialize with chars-per-token ratio.
        
        Args:
            chars_per_token: Average characters per token
        """
        self.chars_per_token = chars_per_token
    
    def count(self, text: str) -> int:
        """Count tokens approximately."""
        return int(len(text) / self.chars_per_token)
    
    def count_messages(self, messages: List[Message]) -> int:
        """Count tokens in messages."""
        total = 0
        for msg in messages:
            # Add overhead for message structure
            total += 4  # Role, formatting tokens
            total += self.count(msg.content)
            if msg.name:
                total += self.count(msg.name) + 1
        return total


class TiktokenCounter(TokenCounter):
    """
    Accurate token counter using tiktoken (for OpenAI-compatible models).
    """
    
    def __init__(self, model: str = "gpt-4"):
        """
        Initialize with model name.
        
        Args:
            model: Model name for encoding
        """
        self.model = model
        self._encoding = None
    
    def _get_encoding(self):
        """Lazy load tiktoken encoding."""
        if self._encoding is None:
            try:
                import tiktoken
                try:
                    self._encoding = tiktoken.encoding_for_model(self.model)
                except KeyError:
                    self._encoding = tiktoken.get_encoding("cl100k_base")
            except ImportError:
                logger.warning("tiktoken not available, falling back to approximate counting")
                return None
        return self._encoding
    
    def count(self, text: str) -> int:
        """Count tokens accurately."""
        encoding = self._get_encoding()
        if encoding:
            return len(encoding.encode(text))
        return int(len(text) / 4)
    
    def count_messages(self, messages: List[Message]) -> int:
        """Count tokens in messages."""
        encoding = self._get_encoding()
        if not encoding:
            return sum(int(len(m.content) / 4) + 4 for m in messages)
        
        total = 0
        for msg in messages:
            total += 4  # Message overhead
            total += len(encoding.encode(msg.content))
            if msg.name:
                total += len(encoding.encode(msg.name)) + 1
        total += 2  # Conversation overhead
        return total


class GeminiTokenCounter(TokenCounter):
    """
    Token counter for Google Gemini models.
    Uses the Vertex AI API for counting.
    """
    
    def __init__(self, model: str = "gemini-1.5-pro"):
        """Initialize with model name."""
        self.model = model
        self._client = None
    
    def count(self, text: str) -> int:
        """Count tokens using Gemini API."""
        # For now, use approximation
        # In production, use: client.count_tokens(text)
        return int(len(text) / 4)
    
    def count_messages(self, messages: List[Message]) -> int:
        """Count tokens in messages."""
        total = 0
        for msg in messages:
            total += self.count(msg.content) + 4
        return total


class ContextWindowManager:
    """
    Manages conversation context within token limits.
    
    Example:
        manager = ContextWindowManager(
            max_tokens=128000,
            target_tokens=100000,
            truncation_strategy=TruncationStrategy.SLIDING_WINDOW,
        )
        
        # Add messages
        manager.add_message(Message(role=MessageRole.USER, content="Hello!"))
        manager.add_message(Message(role=MessageRole.ASSISTANT, content="Hi there!"))
        
        # Get managed context
        messages = manager.get_context()
        token_count = manager.current_tokens
    """
    
    def __init__(
        self,
        max_tokens: int = 128000,
        target_tokens: int = 100000,
        reserve_tokens: int = 4000,
        truncation_strategy: TruncationStrategy = TruncationStrategy.SLIDING_WINDOW,
        sliding_window_size: int = 50,
        token_counter: Optional[TokenCounter] = None,
        summarizer: Optional[Callable[[List[Message]], str]] = None,
    ):
        """
        Initialize context manager.
        
        Args:
            max_tokens: Maximum context window size
            target_tokens: Target token count to stay under
            reserve_tokens: Tokens to reserve for response
            truncation_strategy: How to handle overflow
            sliding_window_size: Messages to keep in sliding window
            token_counter: Custom token counter
            summarizer: Function to summarize messages (for SUMMARIZE strategy)
        """
        self.config = ContextConfig(
            max_tokens=max_tokens,
            target_tokens=target_tokens,
            reserve_tokens=reserve_tokens,
            truncation_strategy=truncation_strategy,
            sliding_window_size=sliding_window_size,
        )
        
        self._counter = token_counter or ApproximateTokenCounter()
        self._summarizer = summarizer
        self._messages: List[Message] = []
        self._system_message: Optional[Message] = None
        self._summary: Optional[str] = None
    
    @property
    def current_tokens(self) -> int:
        """Get current token count."""
        messages = self._get_all_messages()
        return self._counter.count_messages(messages)
    
    @property
    def available_tokens(self) -> int:
        """Get available tokens for new content."""
        return self.config.target_tokens - self.current_tokens - self.config.reserve_tokens
    
    @property
    def message_count(self) -> int:
        """Get number of messages."""
        return len(self._messages) + (1 if self._system_message else 0)
    
    def _get_all_messages(self) -> List[Message]:
        """Get all messages including system."""
        messages = []
        if self._system_message:
            messages.append(self._system_message)
        if self._summary:
            messages.append(Message(
                role=MessageRole.SYSTEM,
                content=f"Previous conversation summary:\n{self._summary}",
                priority=5,
            ))
        messages.extend(self._messages)
        return messages
    
    def set_system_message(self, content: str, priority: int = 10):
        """Set the system message."""
        self._system_message = Message(
            role=MessageRole.SYSTEM,
            content=content,
            priority=priority,
        )
    
    def add_message(self, message: Message) -> bool:
        """
        Add a message to context.
        
        Args:
            message: Message to add
            
        Returns:
            True if added successfully, False if truncation occurred
        """
        # Count tokens for new message
        message.token_count = self._counter.count(message.content)
        
        self._messages.append(message)
        
        # Check if truncation needed
        if self.current_tokens > self.config.target_tokens:
            self._truncate()
            return False
        return True
    
    def add_messages(self, messages: List[Message]):
        """Add multiple messages."""
        for msg in messages:
            self.add_message(msg)
    
    def _truncate(self):
        """Truncate messages based on strategy."""
        strategy = self.config.truncation_strategy
        
        if strategy == TruncationStrategy.FIFO:
            self._truncate_fifo()
        elif strategy == TruncationStrategy.LIFO:
            self._truncate_lifo()
        elif strategy == TruncationStrategy.SLIDING_WINDOW:
            self._truncate_sliding_window()
        elif strategy == TruncationStrategy.PRIORITY:
            self._truncate_priority()
        elif strategy == TruncationStrategy.SUMMARIZE:
            self._truncate_summarize()
    
    def _truncate_fifo(self):
        """Remove oldest messages first."""
        while self.current_tokens > self.config.target_tokens and len(self._messages) > self.config.min_messages:
            # Skip high-priority messages
            for i, msg in enumerate(self._messages):
                if msg.priority < 5:  # Low priority threshold
                    self._messages.pop(i)
                    break
            else:
                # All remaining are high priority, remove oldest anyway
                self._messages.pop(0)
    
    def _truncate_lifo(self):
        """Remove newest messages first (except latest user message)."""
        while self.current_tokens > self.config.target_tokens and len(self._messages) > self.config.min_messages:
            # Keep at least the latest user message
            if self.config.preserve_latest_user:
                # Find latest user message index
                latest_user_idx = None
                for i in range(len(self._messages) - 1, -1, -1):
                    if self._messages[i].role == MessageRole.USER:
                        latest_user_idx = i
                        break
                
                # Remove from end, skipping latest user message
                for i in range(len(self._messages) - 1, -1, -1):
                    if i != latest_user_idx:
                        self._messages.pop(i)
                        break
            else:
                self._messages.pop()
    
    def _truncate_sliding_window(self):
        """Keep only recent N messages."""
        window_size = self.config.sliding_window_size
        if len(self._messages) > window_size:
            self._messages = self._messages[-window_size:]
    
    def _truncate_priority(self):
        """Remove lowest priority messages first."""
        while self.current_tokens > self.config.target_tokens and len(self._messages) > self.config.min_messages:
            # Find lowest priority message
            min_priority = float('inf')
            min_idx = 0
            for i, msg in enumerate(self._messages):
                if msg.priority < min_priority:
                    min_priority = msg.priority
                    min_idx = i
            self._messages.pop(min_idx)
    
    def _truncate_summarize(self):
        """Summarize old messages instead of removing."""
        if not self._summarizer:
            # Fall back to sliding window
            self._truncate_sliding_window()
            return
        
        # Keep recent messages, summarize older ones
        keep_count = self.config.min_messages
        if len(self._messages) > keep_count:
            to_summarize = self._messages[:-keep_count]
            self._messages = self._messages[-keep_count:]
            
            # Generate summary
            try:
                self._summary = self._summarizer(to_summarize)
            except Exception as e:
                logger.error(f"Summarization failed: {e}")
                # Continue without summary
    
    def get_context(self) -> List[Dict[str, Any]]:
        """
        Get context as list of message dicts.
        
        Returns:
            List of messages formatted for API
        """
        return [msg.to_dict() for msg in self._get_all_messages()]
    
    def get_messages(self) -> List[Message]:
        """Get all messages including system message."""
        return self._get_all_messages()
    
    def clear(self, keep_system: bool = True):
        """Clear conversation history."""
        self._messages = []
        self._summary = None
        if not keep_system:
            self._system_message = None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get context statistics."""
        messages = self._get_all_messages()
        return {
            "total_messages": len(messages),
            "user_messages": sum(1 for m in messages if m.role == MessageRole.USER),
            "assistant_messages": sum(1 for m in messages if m.role == MessageRole.ASSISTANT),
            "current_tokens": self.current_tokens,
            "available_tokens": self.available_tokens,
            "max_tokens": self.config.max_tokens,
            "target_tokens": self.config.target_tokens,
            "utilization": self.current_tokens / self.config.max_tokens,
            "has_summary": self._summary is not None,
        }


def create_context_manager(
    model: str = "gemini-1.5-pro",
    strategy: TruncationStrategy = TruncationStrategy.SLIDING_WINDOW,
) -> ContextWindowManager:
    """
    Create context manager with model-appropriate settings.
    
    Args:
        model: Model name
        strategy: Truncation strategy
        
    Returns:
        Configured ContextWindowManager
    """
    # Model-specific token limits
    model_limits = {
        "gemini-1.5-pro": 1000000,
        "gemini-1.5-flash": 1000000,
        "gemini-1.0-pro": 30720,
        "gpt-4-turbo": 128000,
        "gpt-4": 8192,
        "gpt-3.5-turbo": 16385,
        "claude-3-opus": 200000,
        "claude-3-sonnet": 200000,
    }
    
    max_tokens = model_limits.get(model, 128000)
    target_tokens = int(max_tokens * 0.8)  # 80% of max
    
    return ContextWindowManager(
        max_tokens=max_tokens,
        target_tokens=target_tokens,
        truncation_strategy=strategy,
    )


# Export public API
__all__ = [
    'ContextWindowManager',
    'ContextConfig',
    'TruncationStrategy',
    'Message',
    'MessageRole',
    'TokenCounter',
    'ApproximateTokenCounter',
    'TiktokenCounter',
    'GeminiTokenCounter',
    'create_context_manager',
]
