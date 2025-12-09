"""
Cost Tracker
============
Token usage and cost tracking for AI agent operations.

Features:
- Per-model token counting
- Cost calculation
- Budget alerts
- Usage reporting
"""

import time
import logging
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import threading

logger = logging.getLogger(__name__)


class TokenType(Enum):
    """Types of tokens."""
    INPUT = "input"
    OUTPUT = "output"
    CACHED = "cached"
    TOTAL = "total"


@dataclass
class ModelPricing:
    """Pricing configuration for a model."""
    model_name: str
    input_price_per_1k: float      # Price per 1K input tokens
    output_price_per_1k: float     # Price per 1K output tokens
    cached_input_price_per_1k: float = 0.0  # Cached input price
    currency: str = "USD"


@dataclass
class UsageRecord:
    """Record of token usage."""
    timestamp: float
    model: str
    input_tokens: int
    output_tokens: int
    cached_tokens: int = 0
    cost: float = 0.0
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UsageSummary:
    """Summary of usage over a period."""
    period_start: float
    period_end: float
    total_input_tokens: int
    total_output_tokens: int
    total_cached_tokens: int
    total_cost: float
    request_count: int
    by_model: Dict[str, Dict[str, Any]]
    by_user: Dict[str, Dict[str, Any]]


@dataclass
class BudgetConfig:
    """Budget configuration."""
    daily_limit: Optional[float] = None
    monthly_limit: Optional[float] = None
    per_user_daily_limit: Optional[float] = None
    alert_thresholds: List[float] = field(default_factory=lambda: [0.5, 0.8, 0.95])


class CostTracker:
    """
    Tracks token usage and costs for AI models.
    
    Example:
        # Configure pricing
        tracker = CostTracker()
        tracker.add_model_pricing(ModelPricing(
            model_name="gemini-1.5-pro",
            input_price_per_1k=0.00125,
            output_price_per_1k=0.005,
        ))
        
        # Track usage
        tracker.record_usage(
            model="gemini-1.5-pro",
            input_tokens=1000,
            output_tokens=500,
            user_id="user123",
        )
        
        # Get summary
        summary = tracker.get_daily_summary()
        print(f"Today's cost: ${summary.total_cost:.4f}")
    """
    
    # Default pricing for common models (as of 2024)
    DEFAULT_PRICING = {
        "gemini-1.5-pro": ModelPricing(
            model_name="gemini-1.5-pro",
            input_price_per_1k=0.00125,
            output_price_per_1k=0.005,
        ),
        "gemini-1.5-flash": ModelPricing(
            model_name="gemini-1.5-flash",
            input_price_per_1k=0.000075,
            output_price_per_1k=0.0003,
        ),
        "gemini-2.0-flash": ModelPricing(
            model_name="gemini-2.0-flash",
            input_price_per_1k=0.0001,
            output_price_per_1k=0.0004,
        ),
        "gpt-4-turbo": ModelPricing(
            model_name="gpt-4-turbo",
            input_price_per_1k=0.01,
            output_price_per_1k=0.03,
        ),
        "gpt-4o": ModelPricing(
            model_name="gpt-4o",
            input_price_per_1k=0.005,
            output_price_per_1k=0.015,
        ),
        "claude-3-opus": ModelPricing(
            model_name="claude-3-opus",
            input_price_per_1k=0.015,
            output_price_per_1k=0.075,
        ),
        "claude-3-sonnet": ModelPricing(
            model_name="claude-3-sonnet",
            input_price_per_1k=0.003,
            output_price_per_1k=0.015,
        ),
    }
    
    def __init__(
        self,
        budget_config: Optional[BudgetConfig] = None,
        on_budget_alert: Optional[Callable[[str, float, float], None]] = None,
        max_records: int = 100000,
    ):
        """
        Initialize cost tracker.
        
        Args:
            budget_config: Budget configuration
            on_budget_alert: Callback for budget alerts (threshold, current, limit)
            max_records: Maximum records to retain
        """
        self.budget_config = budget_config or BudgetConfig()
        self._on_budget_alert = on_budget_alert
        self._max_records = max_records
        
        self._pricing: Dict[str, ModelPricing] = dict(self.DEFAULT_PRICING)
        self._records: List[UsageRecord] = []
        self._lock = threading.Lock()
        
        # Quick access counters
        self._daily_costs: Dict[str, float] = defaultdict(float)  # date -> cost
        self._user_daily_costs: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self._last_alert_threshold: float = 0.0
    
    def add_model_pricing(self, pricing: ModelPricing):
        """Add or update model pricing."""
        self._pricing[pricing.model_name] = pricing
    
    def record_usage(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int = 0,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> UsageRecord:
        """
        Record token usage.
        
        Args:
            model: Model name
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            cached_tokens: Number of cached input tokens
            session_id: Optional session ID
            user_id: Optional user ID
            metadata: Optional metadata
            
        Returns:
            UsageRecord with calculated cost
        """
        # Calculate cost
        cost = self._calculate_cost(model, input_tokens, output_tokens, cached_tokens)
        
        record = UsageRecord(
            timestamp=time.time(),
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            cost=cost,
            session_id=session_id,
            user_id=user_id,
            metadata=metadata or {},
        )
        
        with self._lock:
            # Add record
            self._records.append(record)
            
            # Trim if over limit
            if len(self._records) > self._max_records:
                self._records = self._records[-self._max_records:]
            
            # Update counters
            date_key = time.strftime("%Y-%m-%d")
            self._daily_costs[date_key] += cost
            
            if user_id:
                self._user_daily_costs[user_id][date_key] += cost
        
        # Check budgets
        self._check_budgets(user_id)
        
        return record
    
    def _calculate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int,
    ) -> float:
        """Calculate cost for token usage."""
        pricing = self._pricing.get(model)
        if not pricing:
            # Use approximate pricing if model not found
            logger.warning(f"No pricing for model {model}, using estimate")
            return (input_tokens + output_tokens) * 0.00001
        
        input_cost = (input_tokens / 1000) * pricing.input_price_per_1k
        output_cost = (output_tokens / 1000) * pricing.output_price_per_1k
        cached_cost = (cached_tokens / 1000) * pricing.cached_input_price_per_1k
        
        return input_cost + output_cost + cached_cost
    
    def _check_budgets(self, user_id: Optional[str] = None):
        """Check budget limits and trigger alerts."""
        date_key = time.strftime("%Y-%m-%d")
        
        # Check daily limit
        if self.budget_config.daily_limit:
            daily_cost = self._daily_costs.get(date_key, 0.0)
            self._check_threshold(
                "daily",
                daily_cost,
                self.budget_config.daily_limit,
            )
        
        # Check per-user limit
        if user_id and self.budget_config.per_user_daily_limit:
            user_cost = self._user_daily_costs[user_id].get(date_key, 0.0)
            self._check_threshold(
                f"user_{user_id}_daily",
                user_cost,
                self.budget_config.per_user_daily_limit,
            )
    
    def _check_threshold(self, budget_type: str, current: float, limit: float):
        """Check if threshold exceeded and trigger alert."""
        if not self._on_budget_alert:
            return
        
        ratio = current / limit if limit > 0 else 0
        
        for threshold in self.budget_config.alert_thresholds:
            if ratio >= threshold and threshold > self._last_alert_threshold:
                try:
                    self._on_budget_alert(budget_type, current, limit)
                except Exception as e:
                    logger.error(f"Budget alert callback error: {e}")
                self._last_alert_threshold = threshold
                break
    
    def get_daily_summary(self, date: Optional[str] = None) -> UsageSummary:
        """
        Get usage summary for a day.
        
        Args:
            date: Date string (YYYY-MM-DD) or None for today
        """
        date = date or time.strftime("%Y-%m-%d")
        
        with self._lock:
            # Filter records for the day
            day_records = [
                r for r in self._records
                if time.strftime("%Y-%m-%d", time.localtime(r.timestamp)) == date
            ]
        
        return self._create_summary(day_records, date)
    
    def get_monthly_summary(self, year_month: Optional[str] = None) -> UsageSummary:
        """
        Get usage summary for a month.
        
        Args:
            year_month: Month string (YYYY-MM) or None for current
        """
        year_month = year_month or time.strftime("%Y-%m")
        
        with self._lock:
            # Filter records for the month
            month_records = [
                r for r in self._records
                if time.strftime("%Y-%m", time.localtime(r.timestamp)) == year_month
            ]
        
        return self._create_summary(month_records, year_month)
    
    def _create_summary(self, records: List[UsageRecord], period: str) -> UsageSummary:
        """Create usage summary from records."""
        by_model: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "input_tokens": 0,
            "output_tokens": 0,
            "cached_tokens": 0,
            "cost": 0.0,
            "requests": 0,
        })
        
        by_user: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "input_tokens": 0,
            "output_tokens": 0,
            "cost": 0.0,
            "requests": 0,
        })
        
        total_input = 0
        total_output = 0
        total_cached = 0
        total_cost = 0.0
        
        for record in records:
            total_input += record.input_tokens
            total_output += record.output_tokens
            total_cached += record.cached_tokens
            total_cost += record.cost
            
            by_model[record.model]["input_tokens"] += record.input_tokens
            by_model[record.model]["output_tokens"] += record.output_tokens
            by_model[record.model]["cached_tokens"] += record.cached_tokens
            by_model[record.model]["cost"] += record.cost
            by_model[record.model]["requests"] += 1
            
            if record.user_id:
                by_user[record.user_id]["input_tokens"] += record.input_tokens
                by_user[record.user_id]["output_tokens"] += record.output_tokens
                by_user[record.user_id]["cost"] += record.cost
                by_user[record.user_id]["requests"] += 1
        
        # Parse period for timestamps
        if len(period) == 10:  # Date
            start = time.mktime(time.strptime(period, "%Y-%m-%d"))
            end = start + 86400
        else:  # Month
            start = time.mktime(time.strptime(f"{period}-01", "%Y-%m-%d"))
            # End of month approximation
            end = start + 32 * 86400
        
        return UsageSummary(
            period_start=start,
            period_end=end,
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            total_cached_tokens=total_cached,
            total_cost=round(total_cost, 6),
            request_count=len(records),
            by_model=dict(by_model),
            by_user=dict(by_user),
        )
    
    def get_user_usage(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """Get usage for a specific user."""
        cutoff = time.time() - (days * 86400)
        
        with self._lock:
            user_records = [
                r for r in self._records
                if r.user_id == user_id and r.timestamp >= cutoff
            ]
        
        total_cost = sum(r.cost for r in user_records)
        total_input = sum(r.input_tokens for r in user_records)
        total_output = sum(r.output_tokens for r in user_records)
        
        return {
            "user_id": user_id,
            "days": days,
            "total_cost": round(total_cost, 6),
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "request_count": len(user_records),
            "average_cost_per_request": round(total_cost / len(user_records), 6) if user_records else 0,
        }
    
    def get_remaining_budget(self) -> Dict[str, Optional[float]]:
        """Get remaining budget for current period."""
        date_key = time.strftime("%Y-%m-%d")
        month_key = time.strftime("%Y-%m")
        
        daily_spent = self._daily_costs.get(date_key, 0.0)
        
        # Calculate monthly spent
        monthly_spent = sum(
            cost for date, cost in self._daily_costs.items()
            if date.startswith(month_key)
        )
        
        return {
            "daily_remaining": (
                self.budget_config.daily_limit - daily_spent
                if self.budget_config.daily_limit else None
            ),
            "monthly_remaining": (
                self.budget_config.monthly_limit - monthly_spent
                if self.budget_config.monthly_limit else None
            ),
            "daily_spent": daily_spent,
            "monthly_spent": monthly_spent,
        }
    
    def export_records(
        self,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Export records as list of dicts."""
        with self._lock:
            records = self._records
            
            if start_time:
                records = [r for r in records if r.timestamp >= start_time]
            if end_time:
                records = [r for r in records if r.timestamp <= end_time]
            
            return [
                {
                    "timestamp": r.timestamp,
                    "model": r.model,
                    "input_tokens": r.input_tokens,
                    "output_tokens": r.output_tokens,
                    "cached_tokens": r.cached_tokens,
                    "cost": r.cost,
                    "session_id": r.session_id,
                    "user_id": r.user_id,
                    "metadata": r.metadata,
                }
                for r in records
            ]


# Export public API
__all__ = [
    'CostTracker',
    'ModelPricing',
    'UsageRecord',
    'UsageSummary',
    'BudgetConfig',
    'TokenType',
]
