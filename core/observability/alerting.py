"""
Alerting
========
Multi-channel alerting for AI agent systems.

Channels:
- Slack
- PagerDuty
- Email
- Google Cloud Monitoring
- Webhooks

Features:
- Alert deduplication
- Rate limiting
- Severity levels
- Alert routing
"""

import time
import asyncio
import logging
import hashlib
import json
from typing import Optional, Dict, Any, List, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertStatus(Enum):
    """Alert status."""
    FIRING = "firing"
    RESOLVED = "resolved"


@dataclass
class Alert:
    """Alert definition."""
    name: str
    severity: AlertSeverity
    summary: str
    description: str = ""
    source: str = "agent"
    status: AlertStatus = AlertStatus.FIRING
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    fingerprint: str = ""
    
    def __post_init__(self):
        if not self.fingerprint:
            # Generate fingerprint for deduplication
            content = f"{self.name}:{self.source}:{sorted(self.labels.items())}"
            self.fingerprint = hashlib.md5(content.encode()).hexdigest()[:12]


@dataclass
class AlertResult:
    """Result of sending an alert."""
    success: bool
    channel: str
    error: Optional[str] = None
    response: Optional[Dict[str, Any]] = None


class AlertChannel(ABC):
    """Abstract alert channel."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Channel name."""
        pass
    
    @abstractmethod
    async def send(self, alert: Alert) -> AlertResult:
        """Send alert to channel."""
        pass


class SlackChannel(AlertChannel):
    """
    Slack webhook alert channel.
    
    Example:
        channel = SlackChannel(
            webhook_url="https://hooks.slack.com/services/...",
            channel="#alerts",
        )
    """
    
    SEVERITY_COLORS = {
        AlertSeverity.INFO: "#36a64f",
        AlertSeverity.WARNING: "#ffcc00",
        AlertSeverity.ERROR: "#ff6600",
        AlertSeverity.CRITICAL: "#ff0000",
    }
    
    SEVERITY_EMOJI = {
        AlertSeverity.INFO: ":information_source:",
        AlertSeverity.WARNING: ":warning:",
        AlertSeverity.ERROR: ":x:",
        AlertSeverity.CRITICAL: ":rotating_light:",
    }
    
    def __init__(
        self,
        webhook_url: str,
        channel: Optional[str] = None,
        username: str = "Agent Alerts",
    ):
        """
        Initialize Slack channel.
        
        Args:
            webhook_url: Slack webhook URL
            channel: Override channel
            username: Bot username
        """
        self.webhook_url = webhook_url
        self.channel = channel
        self.username = username
    
    @property
    def name(self) -> str:
        return "slack"
    
    async def send(self, alert: Alert) -> AlertResult:
        """Send alert to Slack."""
        try:
            import httpx
            
            emoji = self.SEVERITY_EMOJI.get(alert.severity, ":bell:")
            color = self.SEVERITY_COLORS.get(alert.severity, "#808080")
            
            # Build message
            attachment = {
                "color": color,
                "title": f"{emoji} {alert.summary}",
                "text": alert.description,
                "fields": [
                    {"title": "Severity", "value": alert.severity.value, "short": True},
                    {"title": "Source", "value": alert.source, "short": True},
                    {"title": "Status", "value": alert.status.value, "short": True},
                ],
                "footer": f"Fingerprint: {alert.fingerprint}",
                "ts": int(alert.timestamp),
            }
            
            # Add labels as fields
            for key, value in alert.labels.items():
                attachment["fields"].append({
                    "title": key,
                    "value": value,
                    "short": True,
                })
            
            payload = {
                "username": self.username,
                "attachments": [attachment],
            }
            
            if self.channel:
                payload["channel"] = self.channel
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    timeout=10.0,
                )
                
                if response.status_code == 200:
                    return AlertResult(success=True, channel=self.name)
                else:
                    return AlertResult(
                        success=False,
                        channel=self.name,
                        error=f"Slack API error: {response.status_code}",
                    )
                    
        except Exception as e:
            return AlertResult(success=False, channel=self.name, error=str(e))


class PagerDutyChannel(AlertChannel):
    """
    PagerDuty Events API v2 alert channel.
    
    Example:
        channel = PagerDutyChannel(
            routing_key="your-integration-key",
            source="production-agent",
        )
    """
    
    API_URL = "https://events.pagerduty.com/v2/enqueue"
    
    SEVERITY_MAP = {
        AlertSeverity.INFO: "info",
        AlertSeverity.WARNING: "warning",
        AlertSeverity.ERROR: "error",
        AlertSeverity.CRITICAL: "critical",
    }
    
    def __init__(
        self,
        routing_key: str,
        source: str = "agent",
    ):
        """
        Initialize PagerDuty channel.
        
        Args:
            routing_key: PagerDuty integration key
            source: Alert source identifier
        """
        self.routing_key = routing_key
        self.source = source
    
    @property
    def name(self) -> str:
        return "pagerduty"
    
    async def send(self, alert: Alert) -> AlertResult:
        """Send alert to PagerDuty."""
        try:
            import httpx
            
            event_action = "trigger" if alert.status == AlertStatus.FIRING else "resolve"
            
            payload = {
                "routing_key": self.routing_key,
                "event_action": event_action,
                "dedup_key": alert.fingerprint,
                "payload": {
                    "summary": alert.summary,
                    "severity": self.SEVERITY_MAP.get(alert.severity, "error"),
                    "source": alert.source or self.source,
                    "custom_details": {
                        "description": alert.description,
                        **alert.labels,
                        **alert.annotations,
                    },
                },
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.API_URL,
                    json=payload,
                    timeout=10.0,
                )
                
                if response.status_code == 202:
                    return AlertResult(
                        success=True,
                        channel=self.name,
                        response=response.json(),
                    )
                else:
                    return AlertResult(
                        success=False,
                        channel=self.name,
                        error=f"PagerDuty API error: {response.status_code}",
                    )
                    
        except Exception as e:
            return AlertResult(success=False, channel=self.name, error=str(e))


class EmailChannel(AlertChannel):
    """
    Email alert channel using SMTP.
    
    Example:
        channel = EmailChannel(
            smtp_host="smtp.gmail.com",
            smtp_port=587,
            username="alerts@company.com",
            password="app-password",
            from_addr="alerts@company.com",
            to_addrs=["oncall@company.com"],
        )
    """
    
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str,
        from_addr: str,
        to_addrs: List[str],
        use_tls: bool = True,
    ):
        """Initialize email channel."""
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_addr = from_addr
        self.to_addrs = to_addrs
        self.use_tls = use_tls
    
    @property
    def name(self) -> str:
        return "email"
    
    async def send(self, alert: Alert) -> AlertResult:
        """Send alert via email."""
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            # Build email
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"[{alert.severity.value.upper()}] {alert.summary}"
            msg['From'] = self.from_addr
            msg['To'] = ", ".join(self.to_addrs)
            
            # Plain text body
            text_body = f"""
Alert: {alert.name}
Severity: {alert.severity.value}
Status: {alert.status.value}
Source: {alert.source}

Summary: {alert.summary}

Description:
{alert.description}

Labels: {json.dumps(alert.labels, indent=2)}

Fingerprint: {alert.fingerprint}
Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(alert.timestamp))}
"""
            
            # HTML body
            html_body = f"""
<html>
<body>
<h2 style="color: {'red' if alert.severity == AlertSeverity.CRITICAL else 'orange'}">{alert.summary}</h2>
<table>
<tr><td><strong>Severity:</strong></td><td>{alert.severity.value}</td></tr>
<tr><td><strong>Status:</strong></td><td>{alert.status.value}</td></tr>
<tr><td><strong>Source:</strong></td><td>{alert.source}</td></tr>
</table>
<h3>Description</h3>
<p>{alert.description}</p>
<h3>Labels</h3>
<pre>{json.dumps(alert.labels, indent=2)}</pre>
<hr>
<small>Fingerprint: {alert.fingerprint}</small>
</body>
</html>
"""
            
            msg.attach(MIMEText(text_body, 'plain'))
            msg.attach(MIMEText(html_body, 'html'))
            
            # Send email
            def send_sync():
                with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                    if self.use_tls:
                        server.starttls()
                    server.login(self.username, self.password)
                    server.sendmail(self.from_addr, self.to_addrs, msg.as_string())
            
            await asyncio.get_event_loop().run_in_executor(None, send_sync)
            
            return AlertResult(success=True, channel=self.name)
            
        except Exception as e:
            return AlertResult(success=False, channel=self.name, error=str(e))


class WebhookChannel(AlertChannel):
    """
    Generic webhook alert channel.
    
    Example:
        channel = WebhookChannel(
            url="https://api.example.com/alerts",
            headers={"Authorization": "Bearer token"},
        )
    """
    
    def __init__(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        method: str = "POST",
    ):
        """Initialize webhook channel."""
        self.url = url
        self.headers = headers or {}
        self.method = method
    
    @property
    def name(self) -> str:
        return "webhook"
    
    async def send(self, alert: Alert) -> AlertResult:
        """Send alert to webhook."""
        try:
            import httpx
            
            payload = {
                "name": alert.name,
                "severity": alert.severity.value,
                "status": alert.status.value,
                "summary": alert.summary,
                "description": alert.description,
                "source": alert.source,
                "labels": alert.labels,
                "annotations": alert.annotations,
                "fingerprint": alert.fingerprint,
                "timestamp": alert.timestamp,
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    self.method,
                    self.url,
                    json=payload,
                    headers=self.headers,
                    timeout=10.0,
                )
                
                return AlertResult(
                    success=response.status_code < 300,
                    channel=self.name,
                    response={"status_code": response.status_code},
                    error=None if response.status_code < 300 else f"HTTP {response.status_code}",
                )
                
        except Exception as e:
            return AlertResult(success=False, channel=self.name, error=str(e))


class CloudMonitoringChannel(AlertChannel):
    """
    Google Cloud Monitoring alert channel.
    Uses custom metrics to trigger Cloud Monitoring alerting policies.
    """
    
    def __init__(
        self,
        project_id: str,
        metric_type: str = "custom.googleapis.com/agent/alerts",
    ):
        """Initialize Cloud Monitoring channel."""
        self.project_id = project_id
        self.metric_type = metric_type
    
    @property
    def name(self) -> str:
        return "cloud_monitoring"
    
    async def send(self, alert: Alert) -> AlertResult:
        """Send alert metric to Cloud Monitoring."""
        try:
            from google.cloud import monitoring_v3
            from google.protobuf import timestamp_pb2
            
            client = monitoring_v3.MetricServiceClient()
            project_name = f"projects/{self.project_id}"
            
            series = monitoring_v3.TimeSeries()
            series.metric.type = self.metric_type
            series.metric.labels["alert_name"] = alert.name
            series.metric.labels["severity"] = alert.severity.value
            series.resource.type = "global"
            
            # Create data point
            now = time.time()
            seconds = int(now)
            nanos = int((now - seconds) * 10**9)
            
            interval = monitoring_v3.TimeInterval(
                {"end_time": {"seconds": seconds, "nanos": nanos}}
            )
            point = monitoring_v3.Point({
                "interval": interval,
                "value": {"double_value": 1.0 if alert.status == AlertStatus.FIRING else 0.0},
            })
            series.points = [point]
            
            client.create_time_series(name=project_name, time_series=[series])
            
            return AlertResult(success=True, channel=self.name)
            
        except Exception as e:
            return AlertResult(success=False, channel=self.name, error=str(e))


class AlertManager:
    """
    Manages alert routing and delivery.
    
    Example:
        manager = AlertManager()
        manager.add_channel(SlackChannel(webhook_url="..."))
        manager.add_channel(PagerDutyChannel(routing_key="..."))
        
        # Route by severity
        manager.add_route(
            severities=[AlertSeverity.CRITICAL],
            channels=["pagerduty", "slack"],
        )
        manager.add_route(
            severities=[AlertSeverity.WARNING, AlertSeverity.ERROR],
            channels=["slack"],
        )
        
        # Send alert
        await manager.send_alert(Alert(
            name="high_error_rate",
            severity=AlertSeverity.ERROR,
            summary="Error rate exceeded 5%",
        ))
    """
    
    def __init__(
        self,
        dedup_window_seconds: int = 3600,
        rate_limit_per_minute: int = 60,
    ):
        """
        Initialize alert manager.
        
        Args:
            dedup_window_seconds: Window for alert deduplication
            rate_limit_per_minute: Max alerts per minute
        """
        self.dedup_window = dedup_window_seconds
        self.rate_limit = rate_limit_per_minute
        
        self._channels: Dict[str, AlertChannel] = {}
        self._routes: List[Dict[str, Any]] = []
        self._seen_fingerprints: Dict[str, float] = {}  # fingerprint -> timestamp
        self._sent_count = 0
        self._sent_window_start = time.time()
    
    def add_channel(self, channel: AlertChannel):
        """Add an alert channel."""
        self._channels[channel.name] = channel
    
    def add_route(
        self,
        channels: List[str],
        severities: Optional[List[AlertSeverity]] = None,
        sources: Optional[List[str]] = None,
        labels: Optional[Dict[str, str]] = None,
    ):
        """
        Add routing rule.
        
        Args:
            channels: Channel names to route to
            severities: Severity filter
            sources: Source filter
            labels: Label filter (all must match)
        """
        self._routes.append({
            "channels": channels,
            "severities": severities,
            "sources": sources,
            "labels": labels,
        })
    
    def _should_dedupe(self, alert: Alert) -> bool:
        """Check if alert should be deduplicated."""
        now = time.time()
        
        # Clean old fingerprints
        cutoff = now - self.dedup_window
        self._seen_fingerprints = {
            fp: ts for fp, ts in self._seen_fingerprints.items()
            if ts > cutoff
        }
        
        # Check if seen recently
        if alert.fingerprint in self._seen_fingerprints:
            return True
        
        self._seen_fingerprints[alert.fingerprint] = now
        return False
    
    def _check_rate_limit(self) -> bool:
        """Check if rate limit exceeded."""
        now = time.time()
        
        # Reset window if needed
        if now - self._sent_window_start > 60:
            self._sent_count = 0
            self._sent_window_start = now
        
        if self._sent_count >= self.rate_limit:
            return False
        
        self._sent_count += 1
        return True
    
    def _get_channels_for_alert(self, alert: Alert) -> Set[str]:
        """Get channels that should receive this alert."""
        channels: Set[str] = set()
        
        for route in self._routes:
            # Check severity filter
            if route["severities"] and alert.severity not in route["severities"]:
                continue
            
            # Check source filter
            if route["sources"] and alert.source not in route["sources"]:
                continue
            
            # Check label filter
            if route["labels"]:
                if not all(
                    alert.labels.get(k) == v
                    for k, v in route["labels"].items()
                ):
                    continue
            
            # Route matches
            channels.update(route["channels"])
        
        # Default: send to all channels if no routes match
        if not channels and not self._routes:
            channels = set(self._channels.keys())
        
        return channels
    
    async def send_alert(
        self,
        alert: Alert,
        skip_dedupe: bool = False,
        skip_rate_limit: bool = False,
    ) -> Dict[str, AlertResult]:
        """
        Send alert to appropriate channels.
        
        Args:
            alert: Alert to send
            skip_dedupe: Skip deduplication check
            skip_rate_limit: Skip rate limit check
            
        Returns:
            Dict of channel name to result
        """
        results: Dict[str, AlertResult] = {}
        
        # Deduplication
        if not skip_dedupe and self._should_dedupe(alert):
            logger.debug(f"Alert deduplicated: {alert.fingerprint}")
            return results
        
        # Rate limiting
        if not skip_rate_limit and not self._check_rate_limit():
            logger.warning("Alert rate limit exceeded")
            return results
        
        # Get target channels
        target_channels = self._get_channels_for_alert(alert)
        
        # Send to each channel
        for channel_name in target_channels:
            channel = self._channels.get(channel_name)
            if not channel:
                logger.warning(f"Unknown channel: {channel_name}")
                continue
            
            try:
                result = await channel.send(alert)
                results[channel_name] = result
                
                if not result.success:
                    logger.error(f"Alert send failed to {channel_name}: {result.error}")
            except Exception as e:
                logger.error(f"Alert send error for {channel_name}: {e}")
                results[channel_name] = AlertResult(
                    success=False,
                    channel=channel_name,
                    error=str(e),
                )
        
        return results
    
    async def resolve_alert(self, alert: Alert) -> Dict[str, AlertResult]:
        """Send alert resolution."""
        alert.status = AlertStatus.RESOLVED
        return await self.send_alert(alert, skip_dedupe=True)


def create_observability_stack(
    slack_webhook: Optional[str] = None,
    pagerduty_key: Optional[str] = None,
    email_config: Optional[Dict[str, Any]] = None,
) -> AlertManager:
    """
    Create alert manager with common channels.
    
    Convenience function for quick setup.
    """
    manager = AlertManager()
    
    if slack_webhook:
        manager.add_channel(SlackChannel(webhook_url=slack_webhook))
        manager.add_route(
            channels=["slack"],
            severities=[AlertSeverity.INFO, AlertSeverity.WARNING, AlertSeverity.ERROR],
        )
    
    if pagerduty_key:
        manager.add_channel(PagerDutyChannel(routing_key=pagerduty_key))
        manager.add_route(
            channels=["pagerduty"],
            severities=[AlertSeverity.CRITICAL],
        )
    
    if email_config:
        manager.add_channel(EmailChannel(**email_config))
    
    return manager


# Export public API
__all__ = [
    'AlertManager',
    'Alert',
    'AlertResult',
    'AlertSeverity',
    'AlertStatus',
    'AlertChannel',
    'SlackChannel',
    'PagerDutyChannel',
    'EmailChannel',
    'WebhookChannel',
    'CloudMonitoringChannel',
    'create_observability_stack',
]
