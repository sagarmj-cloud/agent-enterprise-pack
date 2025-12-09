"""
SLO Definitions
===============
Service Level Objective (SLO) management and monitoring.

Features:
- SLO/SLI definition and tracking
- Error budget calculation
- Burn rate alerting
- Compliance reporting
"""

import time
import logging
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import threading

logger = logging.getLogger(__name__)


class SLIType(Enum):
    """Types of Service Level Indicators."""
    AVAILABILITY = "availability"      # Uptime percentage
    LATENCY = "latency"                # Response time
    ERROR_RATE = "error_rate"          # Error percentage
    THROUGHPUT = "throughput"          # Requests per second
    QUALITY = "quality"                # Custom quality metric


class ComplianceStatus(Enum):
    """SLO compliance status."""
    COMPLIANT = "compliant"
    AT_RISK = "at_risk"
    VIOLATED = "violated"


@dataclass
class SLI:
    """Service Level Indicator definition."""
    name: str
    type: SLIType
    description: str = ""
    unit: str = ""


@dataclass
class SLO:
    """Service Level Objective definition."""
    name: str
    sli: SLI
    target: float                      # Target value (e.g., 99.9 for 99.9%)
    window_seconds: int = 2592000      # Default 30 days
    description: str = ""
    is_upper_bound: bool = True        # True for metrics where lower is better


@dataclass
class SLOStatus:
    """Current status of an SLO."""
    slo: SLO
    current_value: float
    target: float
    error_budget_remaining: float      # Percentage remaining
    compliance: ComplianceStatus
    burn_rate: float                   # Current error budget burn rate
    time_remaining: float              # Seconds until window ends
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SLOEvent:
    """Individual SLO measurement event."""
    timestamp: float
    value: float
    is_good: bool
    metadata: Dict[str, Any] = field(default_factory=dict)


class SLOTracker:
    """
    Tracks individual SLO performance.
    
    Example:
        # Define SLO
        availability_sli = SLI(
            name="api_availability",
            type=SLIType.AVAILABILITY,
            unit="%",
        )
        availability_slo = SLO(
            name="99.9% API Availability",
            sli=availability_sli,
            target=99.9,
            window_seconds=2592000,  # 30 days
        )
        
        # Track
        tracker = SLOTracker(availability_slo)
        tracker.record_event(is_good=True)  # Successful request
        tracker.record_event(is_good=False) # Failed request
        
        # Check status
        status = tracker.get_status()
        print(f"Error budget remaining: {status.error_budget_remaining}%")
    """
    
    def __init__(self, slo: SLO, max_events: int = 100000):
        """
        Initialize SLO tracker.
        
        Args:
            slo: SLO to track
            max_events: Maximum events to store
        """
        self.slo = slo
        self._events: deque = deque(maxlen=max_events)
        self._lock = threading.Lock()
        
        # Counters for fast calculation
        self._total_events = 0
        self._good_events = 0
        self._window_start = time.time()
    
    def record_event(
        self,
        is_good: bool,
        value: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Record an SLO event.
        
        Args:
            is_good: Whether this event met the SLI
            value: Optional numeric value
            metadata: Optional event metadata
        """
        now = time.time()
        event = SLOEvent(
            timestamp=now,
            value=value or (1.0 if is_good else 0.0),
            is_good=is_good,
            metadata=metadata or {},
        )
        
        with self._lock:
            self._events.append(event)
            self._total_events += 1
            if is_good:
                self._good_events += 1
            
            # Cleanup old events outside window
            self._cleanup_old_events()
    
    def record_latency(self, latency_ms: float, threshold_ms: Optional[float] = None):
        """
        Record latency event.
        
        Args:
            latency_ms: Observed latency
            threshold_ms: Optional threshold (uses SLO target if not provided)
        """
        threshold = threshold_ms or self.slo.target
        is_good = latency_ms <= threshold
        self.record_event(is_good=is_good, value=latency_ms)
    
    def record_error(self, is_error: bool):
        """Record error event (is_good = not is_error)."""
        self.record_event(is_good=not is_error)
    
    def _cleanup_old_events(self):
        """Remove events outside the window."""
        cutoff = time.time() - self.slo.window_seconds
        
        while self._events and self._events[0].timestamp < cutoff:
            old_event = self._events.popleft()
            self._total_events -= 1
            if old_event.is_good:
                self._good_events -= 1
    
    def get_current_value(self) -> float:
        """Calculate current SLI value."""
        with self._lock:
            self._cleanup_old_events()
            
            if self._total_events == 0:
                return 100.0  # No data, assume good
            
            if self.slo.sli.type == SLIType.AVAILABILITY:
                return (self._good_events / self._total_events) * 100
            elif self.slo.sli.type == SLIType.ERROR_RATE:
                bad_events = self._total_events - self._good_events
                return (bad_events / self._total_events) * 100
            else:
                # For latency/throughput, calculate average
                values = [e.value for e in self._events]
                return sum(values) / len(values) if values else 0.0
    
    def get_error_budget_remaining(self) -> float:
        """
        Calculate remaining error budget as percentage.
        
        Error budget = allowed failures / total events
        """
        with self._lock:
            self._cleanup_old_events()
            
            if self._total_events == 0:
                return 100.0
            
            target = self.slo.target
            
            if self.slo.sli.type == SLIType.AVAILABILITY:
                # For 99.9% availability, error budget is 0.1%
                allowed_bad = self._total_events * (100 - target) / 100
                actual_bad = self._total_events - self._good_events
                
                if allowed_bad <= 0:
                    return 100.0 if actual_bad == 0 else 0.0
                
                remaining = ((allowed_bad - actual_bad) / allowed_bad) * 100
                return max(0.0, min(100.0, remaining))
            else:
                # For other SLI types
                current = self.get_current_value()
                if self.slo.is_upper_bound:
                    # Lower is better (e.g., latency)
                    return max(0.0, (target - current) / target * 100 + 100)
                else:
                    # Higher is better
                    return max(0.0, current / target * 100)
    
    def get_burn_rate(self, short_window_minutes: int = 60) -> float:
        """
        Calculate error budget burn rate.
        
        Burn rate > 1 means consuming budget faster than sustainable.
        """
        with self._lock:
            now = time.time()
            short_window_start = now - (short_window_minutes * 60)
            
            # Count events in short window
            short_total = 0
            short_good = 0
            for event in self._events:
                if event.timestamp >= short_window_start:
                    short_total += 1
                    if event.is_good:
                        short_good += 1
            
            if short_total == 0:
                return 0.0
            
            # Calculate error rate in short window
            short_error_rate = (short_total - short_good) / short_total
            
            # Sustainable error rate based on target
            sustainable_error_rate = (100 - self.slo.target) / 100
            
            if sustainable_error_rate <= 0:
                return float('inf') if short_error_rate > 0 else 0.0
            
            return short_error_rate / sustainable_error_rate
    
    def get_status(self) -> SLOStatus:
        """Get complete SLO status."""
        current_value = self.get_current_value()
        error_budget = self.get_error_budget_remaining()
        burn_rate = self.get_burn_rate()
        
        # Determine compliance
        if error_budget <= 0:
            compliance = ComplianceStatus.VIOLATED
        elif error_budget <= 20 or burn_rate > 1:
            compliance = ComplianceStatus.AT_RISK
        else:
            compliance = ComplianceStatus.COMPLIANT
        
        # Calculate time remaining in window
        elapsed = time.time() - self._window_start
        time_remaining = max(0, self.slo.window_seconds - elapsed)
        
        return SLOStatus(
            slo=self.slo,
            current_value=round(current_value, 4),
            target=self.slo.target,
            error_budget_remaining=round(error_budget, 2),
            compliance=compliance,
            burn_rate=round(burn_rate, 2),
            time_remaining=time_remaining,
            metadata={
                "total_events": self._total_events,
                "good_events": self._good_events,
            },
        )


class SLOManager:
    """
    Manages multiple SLOs.
    
    Example:
        manager = SLOManager()
        
        # Add SLOs
        manager.add_slo(availability_slo)
        manager.add_slo(latency_slo)
        
        # Record events
        manager.record("api_availability", is_good=True)
        manager.record("p99_latency", value=150)
        
        # Get all statuses
        statuses = manager.get_all_statuses()
    """
    
    def __init__(
        self,
        on_violation: Optional[Callable[[SLOStatus], None]] = None,
        on_at_risk: Optional[Callable[[SLOStatus], None]] = None,
    ):
        """
        Initialize SLO manager.
        
        Args:
            on_violation: Callback when SLO is violated
            on_at_risk: Callback when SLO is at risk
        """
        self._trackers: Dict[str, SLOTracker] = {}
        self._on_violation = on_violation
        self._on_at_risk = on_at_risk
        self._last_status: Dict[str, ComplianceStatus] = {}
    
    def add_slo(self, slo: SLO):
        """Add an SLO to manage."""
        self._trackers[slo.name] = SLOTracker(slo)
        self._last_status[slo.name] = ComplianceStatus.COMPLIANT
    
    def record(
        self,
        slo_name: str,
        is_good: Optional[bool] = None,
        value: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Record event for an SLO.
        
        Args:
            slo_name: Name of the SLO
            is_good: Whether event is good
            value: Numeric value
            metadata: Event metadata
        """
        if slo_name not in self._trackers:
            logger.warning(f"Unknown SLO: {slo_name}")
            return
        
        tracker = self._trackers[slo_name]
        
        if is_good is not None:
            tracker.record_event(is_good=is_good, value=value, metadata=metadata)
        elif value is not None:
            # Determine good/bad based on value and target
            if tracker.slo.is_upper_bound:
                is_good = value <= tracker.slo.target
            else:
                is_good = value >= tracker.slo.target
            tracker.record_event(is_good=is_good, value=value, metadata=metadata)
        
        # Check for status change
        self._check_status_change(slo_name)
    
    def _check_status_change(self, slo_name: str):
        """Check if SLO status changed and trigger callbacks."""
        tracker = self._trackers[slo_name]
        status = tracker.get_status()
        last_status = self._last_status.get(slo_name, ComplianceStatus.COMPLIANT)
        
        if status.compliance != last_status:
            self._last_status[slo_name] = status.compliance
            
            if status.compliance == ComplianceStatus.VIOLATED:
                if self._on_violation:
                    try:
                        self._on_violation(status)
                    except Exception as e:
                        logger.error(f"Violation callback error: {e}")
            
            elif status.compliance == ComplianceStatus.AT_RISK:
                if self._on_at_risk:
                    try:
                        self._on_at_risk(status)
                    except Exception as e:
                        logger.error(f"At-risk callback error: {e}")
    
    def get_status(self, slo_name: str) -> Optional[SLOStatus]:
        """Get status for specific SLO."""
        if slo_name in self._trackers:
            return self._trackers[slo_name].get_status()
        return None
    
    def get_all_statuses(self) -> Dict[str, SLOStatus]:
        """Get status for all SLOs."""
        return {name: tracker.get_status() for name, tracker in self._trackers.items()}
    
    def get_compliance_report(self) -> Dict[str, Any]:
        """Generate compliance report."""
        statuses = self.get_all_statuses()
        
        return {
            "timestamp": time.time(),
            "summary": {
                "total_slos": len(statuses),
                "compliant": sum(1 for s in statuses.values() if s.compliance == ComplianceStatus.COMPLIANT),
                "at_risk": sum(1 for s in statuses.values() if s.compliance == ComplianceStatus.AT_RISK),
                "violated": sum(1 for s in statuses.values() if s.compliance == ComplianceStatus.VIOLATED),
            },
            "slos": {
                name: {
                    "current_value": status.current_value,
                    "target": status.target,
                    "error_budget_remaining": status.error_budget_remaining,
                    "compliance": status.compliance.value,
                    "burn_rate": status.burn_rate,
                }
                for name, status in statuses.items()
            },
        }


# Preset SLOs for AI agents
class AgentSLOPresets:
    """Preset SLO definitions for AI agents."""
    
    @staticmethod
    def availability_999() -> SLO:
        """99.9% availability SLO."""
        return SLO(
            name="agent_availability_999",
            sli=SLI(
                name="availability",
                type=SLIType.AVAILABILITY,
                unit="%",
            ),
            target=99.9,
            window_seconds=2592000,  # 30 days
            description="99.9% of requests should succeed",
        )
    
    @staticmethod
    def latency_p99(threshold_ms: float = 5000) -> SLO:
        """P99 latency SLO."""
        return SLO(
            name="agent_latency_p99",
            sli=SLI(
                name="p99_latency",
                type=SLIType.LATENCY,
                unit="ms",
            ),
            target=threshold_ms,
            window_seconds=2592000,
            description=f"99% of requests under {threshold_ms}ms",
            is_upper_bound=True,
        )
    
    @staticmethod
    def error_rate(max_rate: float = 1.0) -> SLO:
        """Error rate SLO."""
        return SLO(
            name="agent_error_rate",
            sli=SLI(
                name="error_rate",
                type=SLIType.ERROR_RATE,
                unit="%",
            ),
            target=max_rate,
            window_seconds=2592000,
            description=f"Error rate under {max_rate}%",
            is_upper_bound=True,
        )


# Export public API
__all__ = [
    'SLOManager',
    'SLOTracker',
    'SLO',
    'SLI',
    'SLIType',
    'SLOStatus',
    'SLOEvent',
    'ComplianceStatus',
    'AgentSLOPresets',
]
