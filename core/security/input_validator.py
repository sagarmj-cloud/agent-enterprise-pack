"""
Input Validator
===============
Comprehensive input validation and sanitization for AI agent requests.

Features:
- Length validation with configurable limits
- Character encoding validation
- HTML/XSS sanitization
- SQL injection pattern detection
- Unicode normalization
- Whitespace normalization
- PII detection and masking (optional)
"""

import re
import html
import unicodedata
from typing import Optional, List, Dict, Any, Set, Pattern
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ValidationLevel(Enum):
    """Validation strictness levels."""
    PERMISSIVE = "permissive"  # Basic sanitization only
    STANDARD = "standard"      # Default validation
    STRICT = "strict"          # Maximum security


class ThreatType(Enum):
    """Types of detected threats."""
    XSS = "xss"
    SQL_INJECTION = "sql_injection"
    COMMAND_INJECTION = "command_injection"
    PATH_TRAVERSAL = "path_traversal"
    ENCODING_ATTACK = "encoding_attack"
    EXCESSIVE_LENGTH = "excessive_length"
    INVALID_CHARACTERS = "invalid_characters"


@dataclass
class ValidationResult:
    """Result of input validation."""
    is_valid: bool
    sanitized_text: str
    original_text: str
    threats_detected: List[ThreatType] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationConfig:
    """Configuration for input validation."""
    max_length: int = 32000
    min_length: int = 1
    max_line_count: int = 1000
    allowed_unicode_categories: Set[str] = field(default_factory=lambda: {
        'L', 'M', 'N', 'P', 'S', 'Z'  # Letters, Marks, Numbers, Punctuation, Symbols, Separators
    })
    strip_html: bool = True
    normalize_unicode: bool = True
    normalize_whitespace: bool = True
    block_control_characters: bool = True
    level: ValidationLevel = ValidationLevel.STANDARD


class InputValidator:
    """
    Validates and sanitizes user input for AI agent processing.
    
    Example:
        validator = InputValidator()
        result = validator.validate("Hello <script>alert('xss')</script>")
        if result.is_valid:
            safe_text = result.sanitized_text  # "Hello alert('xss')"
    """
    
    # Precompiled regex patterns for threat detection
    XSS_PATTERNS: List[Pattern] = [
        re.compile(r'<script[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL),
        re.compile(r'javascript:', re.IGNORECASE),
        re.compile(r'on\w+\s*=', re.IGNORECASE),
        re.compile(r'<iframe[^>]*>', re.IGNORECASE),
        re.compile(r'<object[^>]*>', re.IGNORECASE),
        re.compile(r'<embed[^>]*>', re.IGNORECASE),
        re.compile(r'<link[^>]*>', re.IGNORECASE),
        re.compile(r'<meta[^>]*>', re.IGNORECASE),
        re.compile(r'expression\s*\(', re.IGNORECASE),
        re.compile(r'vbscript:', re.IGNORECASE),
        re.compile(r'data:text/html', re.IGNORECASE),
    ]
    
    SQL_INJECTION_PATTERNS: List[Pattern] = [
        re.compile(r'\b(union\s+select|select\s+\*\s+from|insert\s+into|delete\s+from|drop\s+table|update\s+\w+\s+set)\b', re.IGNORECASE),
        re.compile(r'(\'\s*or\s+\'|\"\s*or\s+\")', re.IGNORECASE),
        re.compile(r'(--\s*$|;\s*--)', re.MULTILINE),
        re.compile(r'\b(exec|execute|xp_|sp_)\b', re.IGNORECASE),
        re.compile(r'0x[0-9a-fA-F]+'),  # Hex encoding
    ]
    
    COMMAND_INJECTION_PATTERNS: List[Pattern] = [
        re.compile(r'[;&|`$]'),
        re.compile(r'\$\([^)]+\)'),
        re.compile(r'`[^`]+`'),
        re.compile(r'\b(rm\s+-rf|wget|curl|nc\s|netcat|bash|sh\s+-c)\b', re.IGNORECASE),
    ]
    
    PATH_TRAVERSAL_PATTERNS: List[Pattern] = [
        re.compile(r'\.\./', re.IGNORECASE),
        re.compile(r'\.\.\\', re.IGNORECASE),
        re.compile(r'%2e%2e%2f', re.IGNORECASE),
        re.compile(r'%252e%252e%252f', re.IGNORECASE),
    ]
    
    # Control characters to block (except common whitespace)
    CONTROL_CHAR_PATTERN = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]')
    
    # HTML tag pattern for stripping
    HTML_TAG_PATTERN = re.compile(r'<[^>]+>')
    
    def __init__(self, config: Optional[ValidationConfig] = None):
        """Initialize validator with configuration."""
        self.config = config or ValidationConfig()
    
    def validate(self, text: str) -> ValidationResult:
        """
        Validate and sanitize input text.
        
        Args:
            text: Raw input text to validate
            
        Returns:
            ValidationResult with validation status and sanitized text
        """
        if not isinstance(text, str):
            return ValidationResult(
                is_valid=False,
                sanitized_text="",
                original_text=str(text),
                threats_detected=[ThreatType.INVALID_CHARACTERS],
                warnings=["Input must be a string"]
            )
        
        original_text = text
        threats: List[ThreatType] = []
        warnings: List[str] = []
        metadata: Dict[str, Any] = {
            "original_length": len(text),
            "original_line_count": text.count('\n') + 1
        }
        
        # Length validation
        if len(text) > self.config.max_length:
            threats.append(ThreatType.EXCESSIVE_LENGTH)
            warnings.append(f"Text exceeds max length ({len(text)} > {self.config.max_length})")
            text = text[:self.config.max_length]
        
        if len(text) < self.config.min_length:
            return ValidationResult(
                is_valid=False,
                sanitized_text="",
                original_text=original_text,
                warnings=["Text below minimum length"]
            )
        
        # Line count validation
        line_count = text.count('\n') + 1
        if line_count > self.config.max_line_count:
            warnings.append(f"Line count exceeds limit ({line_count} > {self.config.max_line_count})")
        
        # Unicode normalization
        if self.config.normalize_unicode:
            text = unicodedata.normalize('NFC', text)
        
        # Control character removal
        if self.config.block_control_characters:
            control_chars_found = self.CONTROL_CHAR_PATTERN.findall(text)
            if control_chars_found:
                warnings.append(f"Removed {len(control_chars_found)} control characters")
                text = self.CONTROL_CHAR_PATTERN.sub('', text)
        
        # Threat detection
        xss_detected = self._detect_xss(text)
        if xss_detected:
            threats.append(ThreatType.XSS)
            warnings.extend(xss_detected)
        
        sql_detected = self._detect_sql_injection(text)
        if sql_detected:
            threats.append(ThreatType.SQL_INJECTION)
            warnings.extend(sql_detected)
        
        cmd_detected = self._detect_command_injection(text)
        if cmd_detected and self.config.level == ValidationLevel.STRICT:
            threats.append(ThreatType.COMMAND_INJECTION)
            warnings.extend(cmd_detected)
        
        path_detected = self._detect_path_traversal(text)
        if path_detected:
            threats.append(ThreatType.PATH_TRAVERSAL)
            warnings.extend(path_detected)
        
        # Sanitization
        if self.config.strip_html:
            text = self._strip_html(text)
        
        if self.config.normalize_whitespace:
            text = self._normalize_whitespace(text)
        
        # Determine validity based on threats and level
        is_valid = self._determine_validity(threats)
        
        metadata["sanitized_length"] = len(text)
        metadata["threats_count"] = len(threats)
        
        return ValidationResult(
            is_valid=is_valid,
            sanitized_text=text,
            original_text=original_text,
            threats_detected=threats,
            warnings=warnings,
            metadata=metadata
        )
    
    def _detect_xss(self, text: str) -> List[str]:
        """Detect XSS patterns in text."""
        findings = []
        for pattern in self.XSS_PATTERNS:
            if pattern.search(text):
                findings.append(f"XSS pattern detected: {pattern.pattern[:50]}")
        return findings
    
    def _detect_sql_injection(self, text: str) -> List[str]:
        """Detect SQL injection patterns in text."""
        findings = []
        for pattern in self.SQL_INJECTION_PATTERNS:
            if pattern.search(text):
                findings.append(f"SQL injection pattern detected: {pattern.pattern[:50]}")
        return findings
    
    def _detect_command_injection(self, text: str) -> List[str]:
        """Detect command injection patterns in text."""
        findings = []
        for pattern in self.COMMAND_INJECTION_PATTERNS:
            if pattern.search(text):
                findings.append(f"Command injection pattern detected: {pattern.pattern[:50]}")
        return findings
    
    def _detect_path_traversal(self, text: str) -> List[str]:
        """Detect path traversal patterns in text."""
        findings = []
        for pattern in self.PATH_TRAVERSAL_PATTERNS:
            if pattern.search(text):
                findings.append(f"Path traversal pattern detected: {pattern.pattern[:50]}")
        return findings
    
    def _strip_html(self, text: str) -> str:
        """Remove HTML tags and decode entities."""
        # Remove HTML tags
        text = self.HTML_TAG_PATTERN.sub('', text)
        # Decode HTML entities
        text = html.unescape(text)
        return text
    
    def _normalize_whitespace(self, text: str) -> str:
        """Normalize whitespace in text."""
        # Replace multiple spaces with single space
        text = re.sub(r' +', ' ', text)
        # Replace multiple newlines with double newline
        text = re.sub(r'\n{3,}', '\n\n', text)
        # Strip leading/trailing whitespace
        text = text.strip()
        return text
    
    def _determine_validity(self, threats: List[ThreatType]) -> bool:
        """Determine if input is valid based on threats and validation level."""
        if not threats:
            return True
        
        if self.config.level == ValidationLevel.PERMISSIVE:
            # Only block the most severe threats
            blocking_threats = {ThreatType.XSS, ThreatType.SQL_INJECTION}
            return not any(t in blocking_threats for t in threats)
        
        elif self.config.level == ValidationLevel.STANDARD:
            # Block XSS, SQL injection, and path traversal
            blocking_threats = {ThreatType.XSS, ThreatType.SQL_INJECTION, ThreatType.PATH_TRAVERSAL}
            return not any(t in blocking_threats for t in threats)
        
        else:  # STRICT
            # Block any detected threat
            return False


class BatchValidator:
    """Validates batches of inputs efficiently."""
    
    def __init__(self, validator: Optional[InputValidator] = None):
        self.validator = validator or InputValidator()
    
    def validate_batch(self, texts: List[str]) -> List[ValidationResult]:
        """Validate a batch of texts."""
        return [self.validator.validate(text) for text in texts]
    
    def filter_valid(self, texts: List[str]) -> List[str]:
        """Return only valid texts from batch."""
        results = self.validate_batch(texts)
        return [r.sanitized_text for r in results if r.is_valid]


class PIIMasker:
    """
    Detects and masks Personally Identifiable Information.
    Use cautiously - may have false positives.
    """
    
    # Common PII patterns
    EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
    PHONE_PATTERN = re.compile(r'\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b')
    SSN_PATTERN = re.compile(r'\b[0-9]{3}[-\s]?[0-9]{2}[-\s]?[0-9]{4}\b')
    CREDIT_CARD_PATTERN = re.compile(r'\b(?:[0-9]{4}[-\s]?){3}[0-9]{4}\b')
    
    PATTERNS = {
        'email': (EMAIL_PATTERN, '[EMAIL]'),
        'phone': (PHONE_PATTERN, '[PHONE]'),
        'ssn': (SSN_PATTERN, '[SSN]'),
        'credit_card': (CREDIT_CARD_PATTERN, '[CREDIT_CARD]'),
    }
    
    def __init__(self, mask_types: Optional[Set[str]] = None):
        """
        Initialize PII masker.
        
        Args:
            mask_types: Set of PII types to mask. Defaults to all types.
        """
        self.mask_types = mask_types or set(self.PATTERNS.keys())
    
    def mask(self, text: str) -> str:
        """Mask PII in text."""
        for pii_type, (pattern, replacement) in self.PATTERNS.items():
            if pii_type in self.mask_types:
                text = pattern.sub(replacement, text)
        return text
    
    def detect(self, text: str) -> Dict[str, List[str]]:
        """Detect PII in text without masking."""
        findings = {}
        for pii_type, (pattern, _) in self.PATTERNS.items():
            matches = pattern.findall(text)
            if matches:
                findings[pii_type] = matches
        return findings


# Convenience functions
def validate_input(text: str, level: ValidationLevel = ValidationLevel.STANDARD) -> ValidationResult:
    """Quick validation with default settings."""
    config = ValidationConfig(level=level)
    validator = InputValidator(config)
    return validator.validate(text)


def sanitize(text: str) -> str:
    """Quick sanitization, returns sanitized text or raises ValueError."""
    result = validate_input(text)
    if not result.is_valid:
        raise ValueError(f"Invalid input: {', '.join(result.warnings)}")
    return result.sanitized_text


# Export public API
__all__ = [
    'InputValidator',
    'ValidationResult',
    'ValidationConfig',
    'ValidationLevel',
    'ThreatType',
    'BatchValidator',
    'PIIMasker',
    'validate_input',
    'sanitize',
]
