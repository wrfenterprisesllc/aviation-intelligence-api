"""
Data Freshness Tracking Service
Aviation Intelligence Platform - Pipeline Monitoring (Epic 1.8)

Tracks how fresh each data source is and provides status reporting.
Used by staleness check job and frontend freshness indicators.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


# ============================================================================
# FRESHNESS THRESHOLDS
# ============================================================================

# Define expected freshness for each pipeline
# max_age_hours: After this many hours, data is considered stale
# schedule: When the pipeline normally runs
FRESHNESS_THRESHOLDS = {
    "news_ingestion": {
        "max_age_hours": 28,  # 24h + 4h buffer for daily at 6 AM
        "schedule": "daily",
        "description": "News articles from RSS, NewsAPI, SEC Edgar"
    },
    "financial_data": {
        "max_age_hours": 28,  # 24h + 4h buffer for daily at 7 AM
        "schedule": "daily",
        "description": "FRED credit spreads, TSA passengers, carrier financials"
    },
    "defense_contracts": {
        "max_age_hours": 28,  # 24h + 4h buffer for daily at 8 AM
        "schedule": "daily",
        "description": "DoD contract awards from defense.gov"
    },
    "credit_score_refresh": {
        "max_age_hours": 192,  # 8 days (weekly + buffer)
        "schedule": "weekly",
        "description": "Credit score calculation for all airlines"
    },
    "newsletter_generation": {
        "max_age_hours": 192,  # 8 days (weekly + buffer)
        "schedule": "weekly",
        "description": "Weekly outlook newsletter generation"
    }
}


class FreshnessService:
    """
    Service to check and report data freshness status.
    Queries pipeline_runs collection to determine when each pipeline last ran successfully.
    """

    def __init__(self, db_service):
        """
        Initialize freshness service.

        Args:
            db_service: DatabaseService instance for Firestore operations
        """
        self.db = db_service

    def get_freshness_status(self) -> Dict[str, Any]:
        """
        Check freshness of all tracked pipelines.

        Returns:
            Dictionary with:
            - overall_status: 'healthy' | 'degraded' | 'critical'
            - checked_at: ISO timestamp
            - pipelines: Dict of pipeline statuses
        """
        now = datetime.utcnow()
        pipelines = {}
        overall = "healthy"

        for pipeline_name, config in FRESHNESS_THRESHOLDS.items():
            threshold = config["max_age_hours"]

            # Get last successful run
            last_run = self.db.get_last_successful_run(pipeline_name)

            if not last_run:
                # No runs recorded - unknown status
                pipelines[pipeline_name] = {
                    "last_success": None,
                    "hours_ago": None,
                    "threshold_hours": threshold,
                    "status": "unknown",
                    "schedule": config["schedule"],
                    "description": config["description"],
                    "last_run_status": None,
                    "items_processed": None
                }
                # Unknown counts as degraded
                if overall == "healthy":
                    overall = "degraded"
            else:
                # Calculate hours since last success
                completed_at = last_run.get("completed_at")

                # Handle Firestore timestamp objects
                if completed_at:
                    if hasattr(completed_at, 'timestamp'):
                        completed_at = datetime.utcfromtimestamp(completed_at.timestamp())
                    elif isinstance(completed_at, str):
                        try:
                            completed_at = datetime.fromisoformat(completed_at.replace('Z', '+00:00').replace('+00:00', ''))
                        except ValueError:
                            completed_at = now

                    hours_ago = (now - completed_at).total_seconds() / 3600
                else:
                    hours_ago = None

                # Determine freshness status
                if hours_ago is None:
                    status = "unknown"
                elif hours_ago <= threshold:
                    status = "fresh"
                elif hours_ago <= threshold * 2:
                    status = "stale"
                    if overall == "healthy":
                        overall = "degraded"
                else:
                    status = "critical"
                    overall = "critical"

                # Extract summary metrics
                summary = last_run.get("summary", {})
                items_processed = summary.get("items_processed") or summary.get("items_new", 0)

                pipelines[pipeline_name] = {
                    "last_success": completed_at.isoformat() + "Z" if completed_at else None,
                    "hours_ago": round(hours_ago, 1) if hours_ago else None,
                    "threshold_hours": threshold,
                    "status": status,
                    "schedule": config["schedule"],
                    "description": config["description"],
                    "last_run_status": last_run.get("status", "success"),
                    "items_processed": items_processed,
                    "duration_seconds": last_run.get("duration_seconds")
                }

        return {
            "overall_status": overall,
            "checked_at": now.isoformat() + "Z",
            "pipelines": pipelines
        }

    def get_stale_pipelines(self) -> List[Dict[str, Any]]:
        """
        Get list of pipelines that are stale or critical.
        Used by alerting service to send notifications.

        Returns:
            List of dicts with pipeline_name, hours_ago, threshold_hours, status
        """
        status = self.get_freshness_status()
        stale = []

        for name, info in status.get("pipelines", {}).items():
            if info.get("status") in ("stale", "critical"):
                stale.append({
                    "pipeline_name": name,
                    "hours_ago": info.get("hours_ago"),
                    "threshold_hours": info.get("threshold_hours"),
                    "status": info.get("status"),
                    "description": info.get("description")
                })

        return stale

    def check_and_alert(self) -> Dict[str, Any]:
        """
        Check freshness and send alerts for stale pipelines.
        Called by Cloud Scheduler staleness check job.

        Returns:
            Dict with status, stale_count, alerts_sent
        """
        from app.utils.alerting import send_staleness_alert

        stale_pipelines = self.get_stale_pipelines()

        if stale_pipelines:
            alert_sent = send_staleness_alert(stale_pipelines)
            logger.warning(f"⚠️ {len(stale_pipelines)} stale pipelines detected, alert sent: {alert_sent}")
        else:
            alert_sent = False
            logger.info("✅ All pipelines are fresh")

        return {
            "checked_at": datetime.utcnow().isoformat() + "Z",
            "stale_count": len(stale_pipelines),
            "stale_pipelines": stale_pipelines,
            "alert_sent": alert_sent
        }

    def get_pipeline_detail(self, pipeline_name: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed status for a specific pipeline.

        Args:
            pipeline_name: Pipeline identifier

        Returns:
            Dict with config, recent runs, stats, or None if pipeline not found
        """
        config = FRESHNESS_THRESHOLDS.get(pipeline_name)
        if not config:
            return None

        # Get recent runs
        recent_runs = self.db.get_pipeline_runs(pipeline_name=pipeline_name, limit=10)

        # Get stats
        stats = self.db.get_pipeline_stats(pipeline_name, days=7)

        # Get last successful run
        last_success = self.db.get_last_successful_run(pipeline_name)

        # Get freshness status for this pipeline
        freshness = self.get_freshness_status()
        pipeline_status = freshness.get("pipelines", {}).get(pipeline_name, {})

        return {
            "pipeline_name": pipeline_name,
            "config": config,
            "status": pipeline_status,
            "stats": stats,
            "last_success": last_success,
            "recent_runs": recent_runs
        }

    def get_all_pipeline_names(self) -> List[str]:
        """Get list of all tracked pipeline names."""
        return list(FRESHNESS_THRESHOLDS.keys())


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_freshness_thresholds() -> Dict[str, Any]:
    """Get the configured freshness thresholds."""
    return FRESHNESS_THRESHOLDS.copy()


def is_pipeline_tracked(pipeline_name: str) -> bool:
    """Check if a pipeline is tracked in the freshness system."""
    return pipeline_name in FRESHNESS_THRESHOLDS
