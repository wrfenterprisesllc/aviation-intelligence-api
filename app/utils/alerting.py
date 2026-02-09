"""
Alerting Service - Slack Webhook Integration
Aviation Intelligence Platform - Pipeline Monitoring (Epic 1.8)

Sends alerts to Slack when pipelines fail or data becomes stale.
Degrades gracefully when SLACK_WEBHOOK_URL is not configured.
"""

import os
import logging
from typing import Dict, List, Any, Optional
import requests

logger = logging.getLogger(__name__)

# Get Slack webhook URL from environment
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")


# ============================================================================
# PIPELINE FAILURE ALERTS
# ============================================================================

def send_pipeline_alert(run_doc: Dict[str, Any]) -> bool:
    """
    Send a Slack notification for pipeline failures.

    Args:
        run_doc: Pipeline run document with status, errors, etc.

    Returns:
        True if alert was sent successfully, False otherwise
    """
    if not SLACK_WEBHOOK_URL:
        logger.debug("SLACK_WEBHOOK_URL not set, skipping pipeline alert")
        return False

    status = run_doc.get("status", "unknown")
    pipeline = run_doc.get("pipeline_name", "unknown")
    duration = run_doc.get("duration_seconds", 0)
    run_id = run_doc.get("run_id", "unknown")
    trigger = run_doc.get("trigger", "unknown")
    errors = run_doc.get("errors", [])
    summary = run_doc.get("summary", {})

    # Color and emoji based on status
    if status == "failure":
        color = "#DC2626"  # Red
        emoji = "🔴"
    else:  # partial_failure
        color = "#F59E0B"  # Amber
        emoji = "🟡"

    # Build error text
    error_text = ""
    if errors:
        error_lines = []
        for e in errors[:5]:  # Limit to 5 errors
            source = e.get("source", "unknown")
            error_type = e.get("error_type", "error")
            message = e.get("message", "")[:100]  # Truncate message
            error_lines.append(f"• `{source}`: {error_type} — {message}")

        error_text = "\n".join(error_lines)
        if len(errors) > 5:
            error_text += f"\n... and {len(errors) - 5} more errors"

    # Build summary text
    summary_text = ""
    if summary:
        processed = summary.get("items_processed", "?")
        new = summary.get("items_new", "?")
        failed = summary.get("items_failed", "?")
        summary_text = f"Processed: {processed} | New: {new} | Failed: {failed}"

    # Build Slack payload
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{emoji} Pipeline Alert: {pipeline}",
                "emoji": True
            }
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Status:* {status}"},
                {"type": "mrkdwn", "text": f"*Duration:* {duration:.1f}s"},
                {"type": "mrkdwn", "text": f"*Run ID:* `{run_id}`"},
                {"type": "mrkdwn", "text": f"*Trigger:* {trigger}"},
            ]
        }
    ]

    if summary_text:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Summary:* {summary_text}"}
        })

    if error_text:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Errors:*\n{error_text}"}
        })

    # Add link to logs
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": "View logs in <https://console.cloud.google.com/run?project=ai-projects-485420|Cloud Run Console>"
            }
        ]
    })

    payload = {
        "attachments": [{
            "color": color,
            "blocks": blocks
        }]
    }

    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
        if response.status_code == 200:
            logger.info(f"✅ Slack alert sent for pipeline: {pipeline}")
            return True
        else:
            logger.error(f"Slack webhook returned {response.status_code}: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Failed to send Slack alert: {e}")
        return False


# ============================================================================
# DATA STALENESS ALERTS
# ============================================================================

def send_staleness_alert(stale_pipelines: List[Dict[str, Any]]) -> bool:
    """
    Send a Slack alert for stale data sources.

    Args:
        stale_pipelines: List of dicts with pipeline_name, hours_ago, threshold_hours

    Returns:
        True if alert was sent successfully, False otherwise
    """
    if not SLACK_WEBHOOK_URL:
        logger.debug("SLACK_WEBHOOK_URL not set, skipping staleness alert")
        return False

    if not stale_pipelines:
        return False

    # Build message lines
    lines = []
    for p in stale_pipelines:
        name = p.get("pipeline_name", "unknown")
        hours_ago = p.get("hours_ago", 0)
        threshold = p.get("threshold_hours", 0)
        status = p.get("status", "stale")

        if hours_ago is not None:
            status_emoji = "🔴" if status == "critical" else "🟡"
            lines.append(
                f"{status_emoji} *{name}*: last success {hours_ago:.0f}h ago "
                f"(threshold: {threshold}h)"
            )
        else:
            lines.append(f"❓ *{name}*: no successful runs recorded")

    payload = {
        "attachments": [{
            "color": "#F59E0B",  # Amber
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "⚠️ Stale Data Warning",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "The following pipelines have stale data:\n\n" + "\n".join(lines)
                    }
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "Check pipeline status at <https://ai.wrfenterprisesllc.com/admin/pipelines|Admin Dashboard>"
                        }
                    ]
                }
            ]
        }]
    }

    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
        if response.status_code == 200:
            logger.info(f"✅ Staleness alert sent for {len(stale_pipelines)} pipelines")
            return True
        else:
            logger.error(f"Slack webhook returned {response.status_code}: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Failed to send staleness alert: {e}")
        return False


# ============================================================================
# SUCCESS NOTIFICATION (Optional)
# ============================================================================

def send_success_notification(pipeline_name: str, summary: Dict[str, Any]) -> bool:
    """
    Send a success notification (optional, for critical pipelines).

    Args:
        pipeline_name: Name of the pipeline
        summary: Summary metrics

    Returns:
        True if notification was sent successfully
    """
    if not SLACK_WEBHOOK_URL:
        return False

    processed = summary.get("items_processed", 0)
    new = summary.get("items_new", 0)

    payload = {
        "attachments": [{
            "color": "#10B981",  # Green
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"✅ *{pipeline_name}* completed successfully\n"
                                f"Processed: {processed} | New: {new}"
                    }
                }
            ]
        }]
    }

    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
        return response.status_code == 200
    except Exception:
        return False


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def is_alerting_configured() -> bool:
    """Check if Slack alerting is configured."""
    return bool(SLACK_WEBHOOK_URL)


def test_slack_connection() -> Dict[str, Any]:
    """
    Test the Slack webhook connection.

    Returns:
        Dict with success status and message
    """
    if not SLACK_WEBHOOK_URL:
        return {
            "success": False,
            "message": "SLACK_WEBHOOK_URL not configured",
            "configured": False
        }

    try:
        payload = {
            "text": "🧪 Aviation Intelligence API - Slack connection test successful!"
        }
        response = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)

        if response.status_code == 200:
            return {
                "success": True,
                "message": "Slack webhook connection successful",
                "configured": True
            }
        else:
            return {
                "success": False,
                "message": f"Slack returned status {response.status_code}",
                "configured": True
            }
    except Exception as e:
        return {
            "success": False,
            "message": f"Connection error: {str(e)}",
            "configured": True
        }
