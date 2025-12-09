"""
Memory Compressor
=================
LLM-based conversation summarization and compression.

Features:
- Automatic conversation summarization
- Semantic compression
- Key information extraction
- Hierarchical summarization
"""

import logging
import hashlib
import time
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class CompressionLevel(Enum):
    """Compression aggressiveness levels."""
    MINIMAL = "minimal"       # Keep most detail
    MODERATE = "moderate"     # Balanced compression
    AGGRESSIVE = "aggressive" # Maximum compression


@dataclass
class CompressionResult:
    """Result of compression operation."""
    original_tokens: int
    compressed_tokens: int
    compression_ratio: float
    summary: str
    key_points: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CompressorConfig:
    """Configuration for memory compression."""
    level: CompressionLevel = CompressionLevel.MODERATE
    max_summary_tokens: int = 500
    preserve_recent_messages: int = 5
    include_key_points: bool = True
    max_key_points: int = 10


class MemoryCompressor:
    """
    Compresses conversation memory using LLM summarization.
    
    Example:
        compressor = MemoryCompressor(llm_client=vertex_client)
        
        # Compress conversation
        result = await compressor.compress(messages)
        print(f"Compressed from {result.original_tokens} to {result.compressed_tokens} tokens")
        print(f"Summary: {result.summary}")
    """
    
    # Summarization prompts
    SUMMARY_PROMPT = """Summarize the following conversation concisely while preserving key information:

Conversation:
{conversation}

Provide a summary that captures:
1. Main topics discussed
2. Key decisions or conclusions
3. Important facts mentioned
4. Any action items or next steps

Summary:"""

    KEY_POINTS_PROMPT = """Extract the key points from this conversation:

{conversation}

List up to {max_points} key points, each on a new line starting with "- ":"""

    HIERARCHICAL_PROMPT = """You have these summaries of previous conversation segments:

{summaries}

Create a unified summary that combines these while removing redundancy:"""

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        llm_func: Optional[Callable[[str], str]] = None,
        config: Optional[CompressorConfig] = None,
        token_counter: Optional[Callable[[str], int]] = None,
    ):
        """
        Initialize memory compressor.
        
        Args:
            llm_client: LLM client for summarization
            llm_func: Alternative function for LLM calls
            config: Compression configuration
            token_counter: Function to count tokens
        """
        self._client = llm_client
        self._llm_func = llm_func
        self.config = config or CompressorConfig()
        self._token_counter = token_counter or (lambda x: len(x) // 4)
        self._cache: Dict[str, CompressionResult] = {}
    
    async def compress(
        self,
        messages: List[Dict[str, Any]],
        level: Optional[CompressionLevel] = None,
    ) -> CompressionResult:
        """
        Compress conversation messages.
        
        Args:
            messages: List of conversation messages
            level: Optional override compression level
            
        Returns:
            CompressionResult with summary and metadata
        """
        level = level or self.config.level
        
        # Create cache key
        cache_key = self._get_cache_key(messages)
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Format conversation
        conversation_text = self._format_conversation(messages)
        original_tokens = self._token_counter(conversation_text)
        
        # Generate summary
        summary = await self._generate_summary(conversation_text, level)
        
        # Extract key points if enabled
        key_points = []
        if self.config.include_key_points:
            key_points = await self._extract_key_points(conversation_text)
        
        # Count compressed tokens
        compressed_text = summary + "\n" + "\n".join(key_points)
        compressed_tokens = self._token_counter(compressed_text)
        
        result = CompressionResult(
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            compression_ratio=compressed_tokens / original_tokens if original_tokens > 0 else 0,
            summary=summary,
            key_points=key_points,
            metadata={
                "level": level.value,
                "message_count": len(messages),
                "timestamp": time.time(),
            },
        )
        
        self._cache[cache_key] = result
        return result
    
    async def compress_hierarchical(
        self,
        message_chunks: List[List[Dict[str, Any]]],
    ) -> CompressionResult:
        """
        Compress using hierarchical summarization.
        
        First summarizes each chunk, then combines summaries.
        Good for very long conversations.
        
        Args:
            message_chunks: List of message lists (chunks)
            
        Returns:
            CompressionResult with unified summary
        """
        # Summarize each chunk
        chunk_summaries = []
        total_original = 0
        
        for chunk in message_chunks:
            result = await self.compress(chunk)
            chunk_summaries.append(result.summary)
            total_original += result.original_tokens
        
        # Combine summaries
        if len(chunk_summaries) > 1:
            combined_text = "\n\n---\n\n".join(chunk_summaries)
            unified_summary = await self._generate_unified_summary(combined_text)
        else:
            unified_summary = chunk_summaries[0] if chunk_summaries else ""
        
        compressed_tokens = self._token_counter(unified_summary)
        
        return CompressionResult(
            original_tokens=total_original,
            compressed_tokens=compressed_tokens,
            compression_ratio=compressed_tokens / total_original if total_original > 0 else 0,
            summary=unified_summary,
            key_points=[],
            metadata={
                "chunks": len(message_chunks),
                "hierarchical": True,
            },
        )
    
    def _format_conversation(self, messages: List[Dict[str, Any]]) -> str:
        """Format messages into conversation text."""
        lines = []
        for msg in messages:
            role = msg.get("role", "unknown").upper()
            content = msg.get("content", "")
            lines.append(f"{role}: {content}")
        return "\n\n".join(lines)
    
    async def _generate_summary(self, conversation: str, level: CompressionLevel) -> str:
        """Generate summary using LLM."""
        # Adjust prompt based on compression level
        if level == CompressionLevel.AGGRESSIVE:
            max_words = 100
        elif level == CompressionLevel.MODERATE:
            max_words = 250
        else:
            max_words = 500
        
        prompt = self.SUMMARY_PROMPT.format(conversation=conversation)
        prompt += f"\n\nKeep the summary under {max_words} words."
        
        return await self._call_llm(prompt)
    
    async def _extract_key_points(self, conversation: str) -> List[str]:
        """Extract key points from conversation."""
        prompt = self.KEY_POINTS_PROMPT.format(
            conversation=conversation,
            max_points=self.config.max_key_points,
        )
        
        response = await self._call_llm(prompt)
        
        # Parse bullet points
        points = []
        for line in response.split("\n"):
            line = line.strip()
            if line.startswith("- "):
                points.append(line[2:])
            elif line.startswith("• "):
                points.append(line[2:])
            elif line and len(points) < self.config.max_key_points:
                points.append(line)
        
        return points[:self.config.max_key_points]
    
    async def _generate_unified_summary(self, summaries_text: str) -> str:
        """Generate unified summary from multiple summaries."""
        prompt = self.HIERARCHICAL_PROMPT.format(summaries=summaries_text)
        return await self._call_llm(prompt)
    
    async def _call_llm(self, prompt: str) -> str:
        """Call LLM for generation."""
        if self._llm_func:
            return await self._llm_func(prompt)
        elif self._client:
            # Generic client interface
            try:
                response = await self._client.generate(prompt)
                return response.text if hasattr(response, 'text') else str(response)
            except Exception as e:
                logger.error(f"LLM call failed: {e}")
                return ""
        else:
            logger.warning("No LLM configured for compression")
            return ""
    
    def _get_cache_key(self, messages: List[Dict[str, Any]]) -> str:
        """Generate cache key for messages."""
        content = str([(m.get("role"), m.get("content", "")[:100]) for m in messages])
        return hashlib.md5(content.encode()).hexdigest()
    
    def clear_cache(self):
        """Clear compression cache."""
        self._cache.clear()


class IncrementalCompressor:
    """
    Incrementally compresses conversation as it grows.
    
    Maintains a running summary that gets updated periodically.
    
    Example:
        compressor = IncrementalCompressor(llm_func=call_llm)
        
        # Add messages over time
        compressor.add_message({"role": "user", "content": "Hello"})
        compressor.add_message({"role": "assistant", "content": "Hi there!"})
        
        # Get current context (includes summary of old messages)
        context = compressor.get_context()
    """
    
    def __init__(
        self,
        llm_func: Optional[Callable[[str], str]] = None,
        compression_threshold: int = 20,
        max_recent_messages: int = 10,
    ):
        """
        Initialize incremental compressor.
        
        Args:
            llm_func: Function to call LLM
            compression_threshold: Messages before triggering compression
            max_recent_messages: Recent messages to keep uncompressed
        """
        self._llm_func = llm_func
        self._threshold = compression_threshold
        self._max_recent = max_recent_messages
        
        self._messages: List[Dict[str, Any]] = []
        self._summary: str = ""
        self._compressor = MemoryCompressor(llm_func=llm_func)
    
    def add_message(self, message: Dict[str, Any]):
        """Add a message and trigger compression if needed."""
        self._messages.append(message)
        
        if len(self._messages) >= self._threshold:
            # Run compression asynchronously
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self._compress())
                else:
                    loop.run_until_complete(self._compress())
            except RuntimeError:
                # No event loop, skip compression
                pass
    
    async def _compress(self):
        """Compress older messages into summary."""
        if len(self._messages) <= self._max_recent:
            return
        
        # Messages to compress (exclude recent ones)
        to_compress = self._messages[:-self._max_recent]
        
        # Include existing summary in compression
        if self._summary:
            to_compress.insert(0, {
                "role": "system",
                "content": f"Previous summary: {self._summary}"
            })
        
        result = await self._compressor.compress(to_compress)
        
        # Update summary and trim messages
        self._summary = result.summary
        self._messages = self._messages[-self._max_recent:]
    
    def get_context(self) -> List[Dict[str, Any]]:
        """Get context with summary and recent messages."""
        context = []
        
        if self._summary:
            context.append({
                "role": "system",
                "content": f"Conversation summary so far:\n{self._summary}"
            })
        
        context.extend(self._messages)
        return context
    
    def get_summary(self) -> str:
        """Get current summary."""
        return self._summary
    
    def clear(self):
        """Clear all messages and summary."""
        self._messages = []
        self._summary = ""


# Export public API
__all__ = [
    'MemoryCompressor',
    'IncrementalCompressor',
    'CompressionResult',
    'CompressorConfig',
    'CompressionLevel',
]
