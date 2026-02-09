"""
Pipeline Tracker Context Manager
Aviation Intelligence Platform - Pipeline Monitoring (Epic 1.8)

Tracks pipeline execution and logs results to Firestore pipeline_runs collection.
Sends alerts on failures via Slack webhook.
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class PipelineTracker:
    """
    Context manager that tracks pipeline execution and logs to Firestore.

    Usage:
        with PipelineTracker("news_ingestion", trigger="scheduler", db_service=db) as tracker:
            result = news_service.ingest_all_sources()
            tracker.set_summary(
                items_processed=result.get('total', 0),
                items_new=result.get('saved', 0),
                items_skipped=result.get('duplicates', 0)
            )
            if some_error_occurred:
                tracker.record_error("rss_handler", "connection_timeout", "Timeout fetching feed")
    """

    def __init__(
        self,
        pipeline_name: str,
        trigger: str = "scheduler",
        db_service: Any = None
    ):
        """
        Initialize pipeline tracker.

        Args:
            pipeline_name: Unique identifier for the pipeline (e.g., 'news_ingestion')
            trigger: How the pipeline was triggered ('scheduler', 'manual', 'api')
            db_service: DatabaseService instance for Firestore operations
        """
        self.pipeline_name = pipeline_name
        self.trigger = trigger
        self.db = db_service

        # Generate unique run ID
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        short_uuid = str(uuid.uuid4())[:8]
        self.run_id = f"run_{timestamp}_{short_uuid}"

        # Tracking state
        self.started_at: Optional[datetime] = None
        self.errors: List[Dict[str, Any]] = []
        self.summary: Dict[str, Any] = {}
        self.metadata: Dict[str, Any] = {}

    def __enter__(self) -> 'PipelineTracker':
        """Start pipeline execution tracking."""
        self.started_at = datetime.utcnow()
        logger.info(f"🚀 Pipeline started: {self.pipeline_name} ({self.run_id})")
        return self

    def record_error(
        self,
        source: str,
        error_type: str,
        message: str,
        retried: bool = False,
        retry_succeeded: bool = False
    ) -> None:
        """
        Record an error that occurred during pipeline execution.

        Args:
            source: Component that failed (e.g., 'rss_handler', 'newsapi', 'sec_edgar')
            error_type: Type of error (e.g., 'connection_timeout', 'parse_error', 'api_error')
            message: Error message (truncated to 500 chars)
            retried: Whether retry was attempted
            retry_succeeded: Whether retry succeeded
        """
        self.errors.append({
            "source": source,
            "error_type": error_type,
            "message": str(message)[:500],  # Truncate long messages
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "retried": retried,
            "retry_succeeded": retry_succeeded
        })
        logger.warning(f"Pipeline error recorded: [{source}] {error_type}: {message[:100]}")

    def set_summary(self, **kwargs: Any) -> None:
        """
        Set summary metrics for the pipeline run.

        Common fields:
            items_processed: Total items processed
            items_new: New items saved
            items_skipped: Duplicate/skipped items
            items_failed: Items that failed to process
            sources_attempted: Number of sources tried
            sources_succeeded: Number of sources that succeeded
            sources_failed: Number of sources that failed
        """
        self.summary = kwargs

    def add_metadata(self, **kwargs: Any) -> None:
        """
        Add pipeline-specific metadata.

        Example:
            tracker.add_metadata(
                source_breakdown={
                    "flightglobal_rss": {"new": 3, "skipped": 4},
                    "aviation_week_rss": {"new": 2, "skipped": 5}
                }
            )
        """
        self.metadata.update(kwargs)

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """
        Complete pipeline tracking and save results.

        Returns:
            False to not suppress exceptions
        """
        completed_at = datetime.utcnow()
        duration = (completed_at - self.started_at).total_seconds() if self.started_at else 0

        # Determine final status
        if exc_type is not None:
            status = "failure"
            # Record the unhandled exception
            self.record_error(
                source="pipeline",
                error_type="unhandled_exception",
                message=f"{exc_type.__name__}: {exc_val}"
            )
        elif self.errors:
            status = "partial_failure"
        else:
            status = "success"

        # Build run document
        run_doc = {
            "pipeline_name": self.pipeline_name,
            "run_id": self.run_id,
            "trigger": self.trigger,
            "status": status,
            "started_at": self.started_at,
            "completed_at": completed_at,
            "duration_seconds": round(duration, 2),
            "summary": self.summary,
            "errors": self.errors,
            "error_count": len(self.errors),
            "metadata": self.metadata
        }

        # Save to Firestore
        if self.db:
            try:
                self.db.save_pipeline_run(run_doc)
                logger.info(f"📝 Pipeline run saved: {self.run_id}")
            except Exception as e:
                logger.error(f"Failed to save pipeline run: {e}")

        # Send alerts if needed
        if status in ("failure", "partial_failure"):
            try:
                from app.utils.alerting import send_pipeline_alert
                send_pipeline_alert(run_doc)
            except Exception as e:
                logger.error(f"Failed to send pipeline alert: {e}")

        # Log completion
        status_emoji = "✅" if status == "success" else "⚠️" if status == "partial_failure" else "❌"
        logger.info(
            f"{status_emoji} Pipeline {status}: {self.pipeline_name} "
            f"({duration:.1f}s, {len(self.errors)} errors)"
        )

        # Don't suppress exceptions
        return False

    @property
    def has_errors(self) -> bool:
        """Check if any errors have been recorded."""
        return len(self.errors) > 0

    def get_error_summary(self) -> str:
        """Get a brief summary of recorded errors."""
        if not self.errors:
            return "No errors"
        error_sources = set(e['source'] for e in self.errors)
        return f"{len(self.errors)} errors from: {', '.join(error_sources)}"


# ============================================================================
# HELPER FUNCTION FOR CLOUD SCHEDULER TRIGGER DETECTION
# ============================================================================

def detect_trigger_source(request) -> str:
    """
    Detect the source that triggered a pipeline.

    Args:
        request: Flask request object

    Returns:
        Trigger source: 'cloud_scheduler', 'manual', or 'api'
    """
    user_agent = request.headers.get('User-Agent', '')

    if 'Google-Cloud-Scheduler' in user_agent:
        return 'cloud_scheduler'
    elif 'curl' in user_agent.lower() or 'postman' in user_agent.lower():
        return 'manual'
    else:
        return 'api'
