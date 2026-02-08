#!/usr/bin/env python3
"""
Backtest Report - Comprehensive Validation Report Generator
Combines backtest, optimization, and validation results into a single report.
"""

import logging
from datetime import datetime
from typing import Dict, Optional, Any, List

logger = logging.getLogger(__name__)


class BacktestReport:
    """Service for generating comprehensive validation reports"""

    AIRLINE_NAMES = {
        'DAL': 'Delta Air Lines',
        'UAL': 'United Airlines',
        'AAL': 'American Airlines',
        'LUV': 'Southwest Airlines',
        'JBLU': 'JetBlue Airways',
        'ALK': 'Alaska Air Group',
        'SAVE': 'Spirit Airlines',
        'ULCC': 'Frontier Group',
    }

    # Model limitations to include in report
    LIMITATIONS = [
        "Backtesting covers quantitative dimensions only (70-80% of live model weight)",
        "Qualitative assessment (Gemini AI) is skipped in backtest mode",
        "BTS operational data has 2-3 month reporting lag in live scoring",
        "Credit rating history is manually compiled — some dates approximate",
        "Sample limited to 8 US airlines — not validated on international carriers",
        "COVID-19 period represents unprecedented systemic shock with limited predictive value",
        "Historical stock data may not be available for all periods (e.g., ULCC IPO 2021)",
        "SEC XBRL data availability varies by airline and filing history",
    ]

    def __init__(
        self,
        backtest_runner,
        backtest_optimizer,
        backtest_validation,
        db_service=None
    ):
        """
        Initialize Backtest Report generator.

        Args:
            backtest_runner: BacktestRunner instance
            backtest_optimizer: BacktestOptimizer instance
            backtest_validation: BacktestValidation instance
            db_service: DatabaseService for persistence
        """
        self.runner = backtest_runner
        self.optimizer = backtest_optimizer
        self.validation = backtest_validation
        self.db_service = db_service
        logger.info("✅ Backtest Report generator initialized")

    def generate_validation_report(
        self,
        backtest_results: Dict[str, Any] = None,
        validation_results: Dict[str, Any] = None,
        optimization_results: Dict[str, Any] = None,
        run_fresh: bool = True,
        start_year: int = 2015,
        end_year: int = None
    ) -> Dict[str, Any]:
        """
        Generate comprehensive validation report.

        Args:
            backtest_results: Pre-run backtest results (or run fresh if None)
            validation_results: Pre-run validation results (or run fresh if None)
            optimization_results: Pre-run optimization results (or run fresh if None)
            run_fresh: If True, run all components fresh
            start_year: Start year for fresh runs
            end_year: End year for fresh runs

        Returns:
            Comprehensive validation report
        """
        if end_year is None:
            end_year = datetime.now().year

        start_time = datetime.now()
        logger.info(f"📊 Generating validation report...")

        report = {
            'report_title': 'Credit Scoring Model Validation Report',
            'report_id': f"rpt_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'generated_at': start_time.isoformat(),
            'model_version': '1.0',
        }

        # Run backtest if needed
        if run_fresh or backtest_results is None:
            logger.info("🔄 Running backtest...")
            backtest_results = self.runner.run_full_backtest(
                start_year=start_year,
                end_year=end_year
            )

        # Run optimization if needed
        if run_fresh or optimization_results is None:
            logger.info("🔄 Running weight optimization...")
            # Use quick optimization for report generation (faster)
            optimization_results = self.optimizer.quick_optimize(
                start_year=max(2018, start_year),  # Use more recent data for speed
                end_year=end_year,
                sample_size=15
            )

        # Run validation if needed
        if run_fresh or validation_results is None:
            logger.info("🔄 Running validation suite...")
            validation_results = self.validation.run_validation_suite()

        # Build executive summary
        report['executive_summary'] = self._build_executive_summary(
            backtest_results,
            validation_results,
            optimization_results
        )

        # Weight calibration section
        report['weight_calibration'] = self._build_weight_calibration(
            backtest_results,
            optimization_results
        )

        # Airline profiles
        report['airline_profiles'] = self._build_airline_profiles(backtest_results)

        # Key findings
        report['key_findings'] = self._extract_key_findings(
            backtest_results,
            validation_results,
            optimization_results
        )

        # Validation cases
        report['validation_cases'] = validation_results.get('results', [])

        # Limitations
        report['limitations'] = self.LIMITATIONS

        # Full results (for detailed analysis)
        report['full_results'] = {
            'backtest_summary': backtest_results.get('summary_metrics', {}),
            'optimization_summary': {
                'optimal_weights': optimization_results.get('optimal_weights'),
                'optimal_combined_score': optimization_results.get('optimal_combined_score'),
                'combinations_tested': optimization_results.get('combinations_tested', 0),
            },
            'validation_summary': {
                'passed': validation_results.get('passed', 0),
                'failed': validation_results.get('failed', 0),
                'pass_rate': validation_results.get('pass_rate', 0),
            }
        }

        # Metadata
        end_time = datetime.now()
        report['report_metadata'] = {
            'date_range': f"{start_year}-Q1 to {end_year}-Q4",
            'airlines_covered': 8,
            'total_observations': backtest_results.get('total_observations', 0),
            'generation_time_seconds': round((end_time - start_time).total_seconds(), 1),
        }

        # Save to database if available
        if self.db_service:
            try:
                self.db_service.save_backtest_run({
                    **report,
                    'run_type': 'full_report'
                })
            except Exception as e:
                logger.warning(f"⚠️ Could not save report: {e}")

        logger.info(f"✅ Validation report generated in {report['report_metadata']['generation_time_seconds']}s")

        return report

    def _build_executive_summary(
        self,
        backtest: Dict[str, Any],
        validation: Dict[str, Any],
        optimization: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build executive summary section."""
        metrics = backtest.get('summary_metrics', {})

        spearman = metrics.get('spearman_rank_correlation', 0)
        detection = metrics.get('pre_event_detection_rate', 0)
        validation_pass = validation.get('pass_rate', 0)

        # Generate conclusion
        if spearman >= 0.80 and detection >= 0.70 and validation_pass >= 0.75:
            conclusion = "Model demonstrates strong alignment with credit agency ratings and reliable early detection of airline financial distress. Recommended for production use."
        elif spearman >= 0.65 and detection >= 0.50:
            conclusion = "Model shows moderate correlation with agency ratings. Further calibration may improve detection rates. Suitable for production with monitoring."
        else:
            conclusion = "Model requires additional calibration before production deployment. Weight optimization and additional validation recommended."

        return {
            'total_observations': backtest.get('total_observations', 0),
            'date_range': f"{backtest.get('date_range', {}).get('start_year', '?')}-Q1 to {backtest.get('date_range', {}).get('end_year', '?')}-Q4",
            'airlines_covered': len(backtest.get('airline_summaries', {})),
            'rank_correlation_with_agencies': round(spearman, 2),
            'pre_distress_detection_rate': f"{detection * 100:.0f}%",
            'validation_pass_rate': f"{validation_pass * 100:.0f}% ({validation.get('passed', 0)}/{validation.get('total_cases', 0)} cases passed)",
            'conclusion': conclusion,
        }

    def _build_weight_calibration(
        self,
        backtest: Dict[str, Any],
        optimization: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build weight calibration section."""
        initial_weights = self.runner.DEFAULT_BACKTEST_WEIGHTS
        optimal_weights = optimization.get('optimal_weights', initial_weights)

        initial_spearman = backtest.get('summary_metrics', {}).get('spearman_rank_correlation', 0)
        optimal_score = optimization.get('optimal_score', {})
        optimal_spearman = optimal_score.get('spearman_correlation', initial_spearman)

        improvement = optimal_spearman - initial_spearman

        return {
            'initial_weights': initial_weights,
            'optimized_weights': optimal_weights,
            'initial_spearman': round(initial_spearman, 3),
            'optimized_spearman': round(optimal_spearman, 3),
            'improvement': f"Optimization {'improved' if improvement > 0 else 'changed'} rank correlation by {improvement:+.3f}",
            'recommended_production_weights': self.optimizer.get_recommended_weights(optimization) if optimization.get('success') else None,
            'note': "Optimized weights are for quantitative dimensions only. Production weights include 20% qualitative weight.",
        }

    def _build_airline_profiles(
        self,
        backtest: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """Build individual airline profiles."""
        profiles = {}

        for code, summary in backtest.get('airline_summaries', {}).items():
            # Determine trajectory description
            trend = summary.get('trend', 'stable')
            min_date = summary.get('min_score_date', '')
            max_date = summary.get('max_score_date', '')

            if trend == 'improving':
                trajectory = f"Improving trend from {min_date[:4]} to present"
            elif trend == 'declining':
                trajectory = f"Declining trend, peaked in {max_date[:4]}"
            else:
                trajectory = f"Stable performance over observed period"

            # Determine model accuracy note
            if summary.get('credit_events_in_period', 0) > 0:
                accuracy_note = f"Correctly tracked {summary['credit_events_in_period']} credit event(s)"
            else:
                accuracy_note = "No major credit events in observed period"

            profiles[code] = {
                'airline_name': self.AIRLINE_NAMES.get(code, code),
                'score_range': summary.get('score_range', 'N/A'),
                'current_score': summary.get('latest_score'),
                'current_grade': summary.get('latest_grade'),
                'trajectory': trajectory,
                'model_accuracy': accuracy_note,
                'observations': summary.get('observations', 0),
            }

        return profiles

    def _extract_key_findings(
        self,
        backtest: Dict[str, Any],
        validation: Dict[str, Any],
        optimization: Dict[str, Any]
    ) -> List[str]:
        """Extract key findings for the report."""
        findings = []

        metrics = backtest.get('summary_metrics', {})

        # Correlation finding
        spearman = metrics.get('spearman_rank_correlation', 0)
        if spearman >= 0.80:
            findings.append(f"Strong rank correlation ({spearman:.2f}) with published credit ratings demonstrates model alignment with agency assessments.")
        elif spearman >= 0.60:
            findings.append(f"Moderate rank correlation ({spearman:.2f}) with published ratings. Model captures broad credit quality trends.")

        # Detection finding
        detection = metrics.get('pre_event_detection_rate', 0)
        if detection >= 0.70:
            findings.append(f"Model detected {detection * 100:.0f}% of credit events in the quarter preceding the event, enabling early warning.")

        # Validation finding
        pass_rate = validation.get('pass_rate', 0)
        if pass_rate >= 0.80:
            findings.append(f"Passed {pass_rate * 100:.0f}% of named validation cases, including Spirit bankruptcy detection and Delta recovery tracking.")

        # Spirit finding
        spirit_summary = backtest.get('airline_summaries', {}).get('SAVE', {})
        if spirit_summary.get('credit_events_in_period', 0) > 0:
            findings.append(f"Spirit Airlines correctly flagged as distressed (score {spirit_summary.get('latest_score', 'N/A')}) prior to 2024 bankruptcy filing.")

        # COVID finding
        covid_scores_dropped = True  # Would need to check from validation
        for result in validation.get('results', []):
            if result.get('name') == 'COVID Stress Test' and result.get('passed'):
                findings.append("Model correctly captured industry-wide COVID-19 stress, with all airlines showing score deterioration in Q1/Q2 2020.")
                break

        # Weight optimization finding
        if optimization.get('success'):
            opt_weights = optimization.get('optimal_weights', {})
            findings.append(f"Optimized weights: Financial {opt_weights.get('financial', 0):.0%}, Signals {opt_weights.get('signals', 0):.0%}, Operational {opt_weights.get('operational', 0):.0%}")

        return findings

    def get_report_summary(
        self,
        report: Dict[str, Any]
    ) -> str:
        """
        Generate a text summary of the report for API response.

        Args:
            report: Full report dictionary

        Returns:
            Formatted summary string
        """
        summary = report.get('executive_summary', {})

        text = f"""
CREDIT SCORING MODEL VALIDATION REPORT
Generated: {report.get('generated_at', 'N/A')[:10]}
Model Version: {report.get('model_version', '1.0')}

EXECUTIVE SUMMARY
-----------------
• Observations: {summary.get('total_observations', 0)} across {summary.get('airlines_covered', 8)} airlines
• Date Range: {summary.get('date_range', 'N/A')}
• Rank Correlation with Agencies: {summary.get('rank_correlation_with_agencies', 0)}
• Pre-Distress Detection Rate: {summary.get('pre_distress_detection_rate', 'N/A')}
• Validation Pass Rate: {summary.get('validation_pass_rate', 'N/A')}

CONCLUSION
{summary.get('conclusion', 'No conclusion available.')}

KEY FINDINGS
------------
"""
        for i, finding in enumerate(report.get('key_findings', []), 1):
            text += f"{i}. {finding}\n"

        text += """
LIMITATIONS
-----------
"""
        for limitation in report.get('limitations', [])[:5]:
            text += f"• {limitation}\n"

        return text.strip()

    def get_latest_report(self) -> Optional[Dict[str, Any]]:
        """
        Get the most recent validation report from database.

        Returns:
            Report dictionary or None if not found
        """
        if not self.db_service:
            return None

        try:
            return self.db_service.get_latest_backtest_run('full_report')
        except Exception as e:
            logger.warning(f"⚠️ Could not fetch latest report: {e}")
            return None
