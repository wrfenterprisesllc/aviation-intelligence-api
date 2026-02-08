#!/usr/bin/env python3
"""
Backtest Runner - Retrospective Credit Score Calculation
Runs the scoring model across all airlines at quarterly intervals.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List
from scipy import stats

logger = logging.getLogger(__name__)


class BacktestRunner:
    """Service for running credit score backtests"""

    # Airlines to backtest
    AIRLINES = ['DAL', 'UAL', 'AAL', 'LUV', 'JBLU', 'ALK', 'SAVE', 'ULCC']

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

    # Default backtest weights (no Gemini qualitative - 0%)
    # Redistribute the 20% qualitative weight proportionally
    DEFAULT_BACKTEST_WEIGHTS = {
        'financial': 0.44,      # 35% / 80% = 0.4375 ≈ 0.44
        'signals': 0.25,        # 20% / 80% = 0.25
        'operational': 0.31,    # 25% / 80% = 0.3125 ≈ 0.31
        'qualitative': 0.00     # Skipped in backtest
    }

    def __init__(
        self,
        credit_score_service,
        backtest_data_service,
        db_service=None
    ):
        """
        Initialize Backtest Runner.

        Args:
            credit_score_service: CreditScoreService for scoring
            backtest_data_service: BacktestDataService for historical data
            db_service: DatabaseService for persistence
        """
        self.credit_score = credit_score_service
        self.backtest_data = backtest_data_service
        self.db_service = db_service
        logger.info("✅ Backtest Runner initialized")

    def run_full_backtest(
        self,
        weights: Dict[str, float] = None,
        start_year: int = 2015,
        end_year: int = None
    ) -> Dict[str, Any]:
        """
        Run full backtest across all airlines and quarter ends.

        Args:
            weights: Optional weight overrides (defaults to backtest weights)
            start_year: Start year for backtest
            end_year: End year for backtest (default: current year)

        Returns:
            Complete backtest results with summary metrics
        """
        if end_year is None:
            end_year = datetime.now().year

        if weights is None:
            weights = self.DEFAULT_BACKTEST_WEIGHTS.copy()

        run_id = f"bt_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        logger.info(f"🔄 Starting backtest run {run_id}: {start_year}-{end_year}")
        logger.info(f"📊 Weights: {weights}")

        # Generate quarter-end dates
        quarter_ends = self.backtest_data.get_quarter_end_dates(start_year, end_year)

        results = {
            'run_id': run_id,
            'weights': weights,
            'date_range': {
                'start_year': start_year,
                'end_year': end_year,
                'quarters': len(quarter_ends)
            },
            'started_at': datetime.utcnow().isoformat(),
            'observations': [],
            'summary_metrics': {},
            'airline_summaries': {},
        }

        # Run backtest for each airline × quarter
        for qe_date in quarter_ends:
            for code in self.AIRLINES:
                try:
                    obs = self._calculate_observation(code, qe_date, weights)
                    if obs:
                        results['observations'].append(obs)
                except Exception as e:
                    logger.warning(f"⚠️ Error calculating {code} at {qe_date}: {e}")

        # Calculate summary metrics
        results['summary_metrics'] = self._calculate_summary_metrics(results['observations'])

        # Calculate per-airline summaries
        for code in self.AIRLINES:
            airline_obs = [o for o in results['observations'] if o['airline_code'] == code]
            if airline_obs:
                results['airline_summaries'][code] = self._calculate_airline_summary(airline_obs)

        results['completed_at'] = datetime.utcnow().isoformat()
        results['total_observations'] = len(results['observations'])

        # Save to database if available
        if self.db_service:
            try:
                self.db_service.save_backtest_run(results)
            except Exception as e:
                logger.warning(f"⚠️ Could not save backtest run: {e}")

        logger.info(f"✅ Backtest {run_id} complete: {len(results['observations'])} observations")

        return results

    def _calculate_observation(
        self,
        airline_code: str,
        as_of_date: str,
        weights: Dict[str, float]
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate a single backtest observation.

        Args:
            airline_code: Airline ticker
            as_of_date: Quarter-end date
            weights: Scoring weights

        Returns:
            Observation dict or None if data unavailable
        """
        code = airline_code.upper()

        try:
            # Calculate credit score at this date
            score_result = self.credit_score.calculate_credit_score(
                airline_code=code,
                weights=weights,
                as_of_date=as_of_date
            )

            if not score_result:
                return None

            # Get actual rating at this date
            rating_data = self.backtest_data.get_rating_at_date(code, as_of_date)

            # Check for credit events in next 6 and 12 months
            event_6m = self.backtest_data.get_credit_event_in_window(code, as_of_date, 6)
            event_12m = self.backtest_data.get_credit_event_in_window(code, as_of_date, 12)

            return {
                'airline_code': code,
                'airline_name': self.AIRLINE_NAMES.get(code),
                'as_of_date': as_of_date,
                'composite_score': score_result.get('overall_score', 50),
                'letter_grade': score_result.get('letter_grade', 'NR'),
                'dimension_scores': {
                    'financial': score_result.get('financial_score', 50),
                    'signals': score_result.get('signals_score', 50),
                    'operational': score_result.get('operational_score', 50),
                    'qualitative': score_result.get('qualitative_score', 50),
                },
                'actual_rating_at_time': rating_data.get('sp'),
                'actual_rating_moodys': rating_data.get('moodys'),
                'actual_rating_numeric': rating_data.get('numeric_score', 50),
                'rating_found': rating_data.get('found', False),
                'had_credit_event_next_6m': event_6m is not None,
                'had_credit_event_next_12m': event_12m is not None,
                'credit_event_6m': event_6m,
                'credit_event_12m': event_12m,
                'is_investment_grade': score_result.get('is_investment_grade', False),
                'hurdle_adjustment_bps': score_result.get('hurdle_adjustment_bps', 200),
            }

        except Exception as e:
            logger.warning(f"⚠️ Error in observation for {code} at {as_of_date}: {e}")
            return None

    def _calculate_summary_metrics(
        self,
        observations: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calculate summary metrics from all observations.

        Returns:
            Dict with Spearman correlation, detection rates, etc.
        """
        if not observations:
            return {
                'spearman_rank_correlation': 0,
                'pre_event_detection_rate': 0,
                'false_positive_rate': 0,
                'mean_absolute_error_vs_rating': 0,
                'observations_with_ratings': 0,
            }

        # Filter observations with valid ratings
        rated_obs = [o for o in observations if o.get('rating_found')]

        if len(rated_obs) < 5:
            return {
                'spearman_rank_correlation': 0,
                'pre_event_detection_rate': 0,
                'false_positive_rate': 0,
                'mean_absolute_error_vs_rating': 0,
                'observations_with_ratings': len(rated_obs),
                'note': 'Insufficient rated observations for correlation'
            }

        # 1. Spearman Rank Correlation (at each quarter, rank airlines)
        # Group by quarter
        quarters = {}
        for obs in rated_obs:
            qe = obs['as_of_date']
            if qe not in quarters:
                quarters[qe] = []
            quarters[qe].append(obs)

        quarter_correlations = []
        for qe, qe_obs in quarters.items():
            if len(qe_obs) < 3:  # Need at least 3 airlines to rank
                continue

            model_scores = [o['composite_score'] for o in qe_obs]
            rating_scores = [o['actual_rating_numeric'] for o in qe_obs]

            try:
                corr, _ = stats.spearmanr(model_scores, rating_scores)
                if not (corr != corr):  # Check for NaN
                    quarter_correlations.append(corr)
            except Exception:
                pass

        avg_spearman = sum(quarter_correlations) / len(quarter_correlations) if quarter_correlations else 0

        # 2. Pre-event detection rate
        # For each credit event, check if score was < 50 in preceding quarter
        events_detected = 0
        total_events = 0

        for obs in observations:
            if obs.get('had_credit_event_next_6m'):
                total_events += 1
                if obs['composite_score'] < 50:
                    events_detected += 1

        pre_event_detection = events_detected / total_events if total_events > 0 else 0

        # 3. False positive rate
        # % of observations where we scored < 50 but no event in next 12 months
        low_scores_no_event = 0
        total_low_scores = 0

        for obs in observations:
            if obs['composite_score'] < 50:
                total_low_scores += 1
                if not obs.get('had_credit_event_next_12m'):
                    low_scores_no_event += 1

        false_positive_rate = low_scores_no_event / total_low_scores if total_low_scores > 0 else 0

        # 4. Mean Absolute Error vs Rating
        errors = []
        for obs in rated_obs:
            error = abs(obs['composite_score'] - obs['actual_rating_numeric'])
            errors.append(error)

        mae = sum(errors) / len(errors) if errors else 0

        return {
            'spearman_rank_correlation': round(avg_spearman, 3),
            'pre_event_detection_rate': round(pre_event_detection, 3),
            'false_positive_rate': round(false_positive_rate, 3),
            'mean_absolute_error_vs_rating': round(mae, 1),
            'observations_with_ratings': len(rated_obs),
            'total_observations': len(observations),
            'quarters_analyzed': len(quarter_correlations),
            'credit_events_detected': events_detected,
            'total_credit_events': total_events,
        }

    def _calculate_airline_summary(
        self,
        observations: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calculate summary for a single airline across all quarters.

        Args:
            observations: List of observations for one airline

        Returns:
            Summary dict
        """
        if not observations:
            return {}

        scores = [o['composite_score'] for o in observations]
        code = observations[0]['airline_code']

        # Find min/max scores with dates
        min_obs = min(observations, key=lambda x: x['composite_score'])
        max_obs = max(observations, key=lambda x: x['composite_score'])

        # Trend: compare first and last
        first_score = observations[0]['composite_score']
        last_score = observations[-1]['composite_score']
        trend = 'improving' if last_score > first_score + 5 else \
                'declining' if last_score < first_score - 5 else 'stable'

        # Credit events
        events = [o for o in observations if o.get('had_credit_event_next_12m')]

        return {
            'airline_code': code,
            'airline_name': self.AIRLINE_NAMES.get(code),
            'observations': len(observations),
            'score_range': f"{min(scores):.0f} - {max(scores):.0f}",
            'min_score': round(min(scores), 1),
            'min_score_date': min_obs['as_of_date'],
            'max_score': round(max(scores), 1),
            'max_score_date': max_obs['as_of_date'],
            'avg_score': round(sum(scores) / len(scores), 1),
            'latest_score': round(last_score, 1),
            'latest_grade': observations[-1]['letter_grade'],
            'trend': trend,
            'credit_events_in_period': len(events),
        }

    def run_single_backtest(
        self,
        airline_code: str,
        as_of_date: str,
        weights: Dict[str, float] = None
    ) -> Dict[str, Any]:
        """
        Run backtest for a single airline at a specific date.

        Args:
            airline_code: Airline ticker
            as_of_date: Date string (YYYY-MM-DD)
            weights: Optional weight overrides

        Returns:
            Single observation result
        """
        if weights is None:
            weights = self.DEFAULT_BACKTEST_WEIGHTS.copy()

        obs = self._calculate_observation(airline_code, as_of_date, weights)

        if obs:
            return {
                'success': True,
                'observation': obs,
                'weights_used': weights
            }
        else:
            return {
                'success': False,
                'error': f'Could not calculate score for {airline_code} at {as_of_date}',
                'weights_used': weights
            }

    def compare_weights(
        self,
        weight_configs: List[Dict[str, float]],
        start_year: int = 2015,
        end_year: int = None
    ) -> Dict[str, Any]:
        """
        Compare multiple weight configurations.

        Args:
            weight_configs: List of weight dictionaries to compare
            start_year: Start year
            end_year: End year

        Returns:
            Comparison results
        """
        results = {
            'configs_tested': len(weight_configs),
            'results': [],
            'best_config': None,
            'best_spearman': -1,
        }

        for i, weights in enumerate(weight_configs):
            logger.info(f"📊 Testing config {i+1}/{len(weight_configs)}: {weights}")

            backtest = self.run_full_backtest(
                weights=weights,
                start_year=start_year,
                end_year=end_year
            )

            config_result = {
                'config_index': i,
                'weights': weights,
                'spearman_correlation': backtest['summary_metrics'].get('spearman_rank_correlation', 0),
                'detection_rate': backtest['summary_metrics'].get('pre_event_detection_rate', 0),
                'false_positive_rate': backtest['summary_metrics'].get('false_positive_rate', 0),
                'mae': backtest['summary_metrics'].get('mean_absolute_error_vs_rating', 0),
            }
            results['results'].append(config_result)

            if config_result['spearman_correlation'] > results['best_spearman']:
                results['best_spearman'] = config_result['spearman_correlation']
                results['best_config'] = weights

        return results
