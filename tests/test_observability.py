"""
Tests for observability module
===============================
"""

import pytest
from core.observability import (
    SLOManager,
    CostTracker,
    AlertManager,
    Alert,
    AlertSeverity,
    AgentSLOPresets,
)


class TestSLOManager:
    """Tests for SLOManager."""

    def test_add_slo(self):
        manager = SLOManager()
        slo = AgentSLOPresets.availability_999()
        manager.add_slo(slo)

        # SLO name is "agent_availability_999" from the preset
        assert "agent_availability_999" in manager.get_all_statuses()

    def test_record_event(self):
        manager = SLOManager()
        slo = AgentSLOPresets.availability_999()
        manager.add_slo(slo)

        # Use record() method with is_good parameter
        manager.record("agent_availability_999", is_good=True)
        status = manager.get_status("agent_availability_999")
        assert status is not None


class TestCostTracker:
    """Tests for CostTracker."""

    def test_record_usage(self):
        tracker = CostTracker()

        tracker.record_usage(
            model="gemini-1.5-pro",
            input_tokens=100,
            output_tokens=50,
            session_id="session123",
            user_id="user123"
        )

        summary = tracker.get_daily_summary()
        # UsageSummary has total_input_tokens and total_output_tokens, not total_tokens
        assert summary.total_input_tokens + summary.total_output_tokens == 150
        assert summary.total_cost > 0

    def test_get_user_usage(self):
        tracker = CostTracker()

        tracker.record_usage(
            model="gemini-1.5-pro",
            input_tokens=100,
            output_tokens=50,
            user_id="user123"
        )

        # get_user_usage returns a dict, not a list
        usage = tracker.get_user_usage("user123")
        assert isinstance(usage, dict)
        assert usage["total_input_tokens"] == 100


@pytest.mark.asyncio
class TestAlertManager:
    """Tests for AlertManager."""

    async def test_send_alert(self):
        manager = AlertManager()

        # Alert uses 'name' and 'summary' instead of 'title' and 'message'
        alert = Alert(
            name="Test Alert",
            summary="This is a test",
            severity=AlertSeverity.INFO,
            source="test"
        )

        # Should not raise even with no channels
        await manager.send_alert(alert)

