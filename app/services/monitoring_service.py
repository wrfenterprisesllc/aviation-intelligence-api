#!/usr/bin/env python3
"""
Aviation Intelligence Monitoring Service
Basic monitoring and alerting for the aviation intelligence platform
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any

logger = logging.getLogger(__name__)

class MonitoringService:
    """Basic monitoring for aviation intelligence services"""
    
    def __init__(self):
        self.alerts = []
        self.metrics = {
            'fred_api_calls': 0,
            'fred_failures': 0,
            'tsa_scrapes': 0,
            'tsa_failures': 0,
            'total_requests': 0,
            'error_count': 0
        }
        self.start_time = datetime.now()
        
    def record_fred_call(self, success: bool, response_time_ms: float = 0):
        """Record FRED API call metrics"""
        self.metrics['fred_api_calls'] += 1
        if not success:
            self.metrics['fred_failures'] += 1
            
        # Check for alert conditions
        failure_rate = self.metrics['fred_failures'] / max(self.metrics['fred_api_calls'], 1)
        if failure_rate > 0.5 and self.metrics['fred_api_calls'] > 5:
            self._add_alert('fred_high_failure_rate', f"FRED API failure rate: {failure_rate:.1%}")
            
        logger.info(f"📊 FRED call recorded: success={success}, time={response_time_ms}ms")
        
    def record_tsa_call(self, success: bool, data_quality: str = 'unknown'):
        """Record TSA scraping metrics"""
        self.metrics['tsa_scrapes'] += 1
        if not success:
            self.metrics['tsa_failures'] += 1
            
        logger.info(f"🛂 TSA call recorded: success={success}, quality={data_quality}")
        
    def record_request(self, endpoint: str, status_code: int, response_time_ms: float):
        """Record API request metrics"""
        self.metrics['total_requests'] += 1
        
        if status_code >= 400:
            self.metrics['error_count'] += 1
            
        # Check for high error rate
        error_rate = self.metrics['error_count'] / max(self.metrics['total_requests'], 1)
        if error_rate > 0.1 and self.metrics['total_requests'] > 10:
            self._add_alert('high_error_rate', f"High error rate: {error_rate:.1%}")
            
        logger.info(f"📈 Request recorded: {endpoint} - {status_code} in {response_time_ms}ms")
        
    def _add_alert(self, alert_type: str, message: str):
        """Add alert if not already present"""
        # Avoid duplicate alerts
        existing = [a for a in self.alerts if a['type'] == alert_type and a['message'] == message]
        if not existing:
            alert = {
                'type': alert_type,
                'message': message,
                'timestamp': datetime.now().isoformat(),
                'severity': 'warning'
            }
            self.alerts.append(alert)
            logger.warning(f"🚨 ALERT: {alert_type} - {message}")
            
        # Keep only recent alerts (last hour)
        cutoff = datetime.now() - timedelta(hours=1)
        self.alerts = [a for a in self.alerts if datetime.fromisoformat(a['timestamp']) > cutoff]
        
    def get_health_status(self) -> Dict[str, Any]:
        """Get overall system health status"""
        uptime_seconds = (datetime.now() - self.start_time).total_seconds()
        
        # Calculate service health
        fred_health = 'healthy'
        if self.metrics['fred_api_calls'] > 0:
            fred_failure_rate = self.metrics['fred_failures'] / self.metrics['fred_api_calls']
            if fred_failure_rate > 0.5:
                fred_health = 'degraded'
            elif fred_failure_rate > 0.8:
                fred_health = 'unhealthy'
                
        tsa_health = 'healthy'
        if self.metrics['tsa_scrapes'] > 0:
            tsa_failure_rate = self.metrics['tsa_failures'] / self.metrics['tsa_scrapes']
            if tsa_failure_rate > 0.8:
                tsa_health = 'degraded'
                
        overall_health = 'healthy'
        if fred_health == 'unhealthy' or tsa_health == 'unhealthy':
            overall_health = 'unhealthy'
        elif fred_health == 'degraded' or tsa_health == 'degraded':
            overall_health = 'degraded'
            
        return {
            'overall': overall_health,
            'services': {
                'fred_api': fred_health,
                'tsa_scraping': tsa_health
            },
            'metrics': self.metrics.copy(),
            'alerts': self.alerts.copy(),
            'uptime_seconds': round(uptime_seconds),
            'start_time': self.start_time.isoformat(),
            'last_check': datetime.now().isoformat()
        }
        
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get metrics summary for monitoring dashboard"""
        uptime_hours = (datetime.now() - self.start_time).total_seconds() / 3600
        
        return {
            'uptime_hours': round(uptime_hours, 1),
            'total_requests': self.metrics['total_requests'],
            'requests_per_hour': round(self.metrics['total_requests'] / max(uptime_hours, 0.1)),
            'error_rate': round(self.metrics['error_count'] / max(self.metrics['total_requests'], 1) * 100, 1),
            'fred_success_rate': round((self.metrics['fred_api_calls'] - self.metrics['fred_failures']) / max(self.metrics['fred_api_calls'], 1) * 100, 1),
            'tsa_success_rate': round((self.metrics['tsa_scrapes'] - self.metrics['tsa_failures']) / max(self.metrics['tsa_scrapes'], 1) * 100, 1),
            'active_alerts': len(self.alerts)
        }

# Global monitoring instance
monitor = MonitoringService()
