#!/usr/bin/env python3
"""
Backtest Validation - Named Test Cases for Model Validation
Runs specific validation cases to ensure model calibration.
"""

import logging
from datetime import datetime
from typing import Dict, Optional, Any, List
from scipy import stats

logger = logging.getLogger(__name__)


class BacktestValidation:
    """Service for validating credit score model with named test cases"""

    # Validation test cases
    VALIDATION_CASES = [
        {
            "name": "Spirit Pre-Bankruptcy Detection",
            "description": "Model should flag Spirit as high-risk before Nov 2024 bankruptcy",
            "airline": "SAVE",
            "as_of_date": "2024-06-30",
            "assertion": "score < 40",
            "assertion_type": "score_threshold",
            "threshold": 40,
            "operator": "lt",
            "assertion_description": "Score should be below 40 (B or worse)"
        },
        {
            "name": "Spirit Deterioration Trend",
            "description": "Model should show Spirit deteriorating through 2023-2024",
            "airline": "SAVE",
            "as_of_dates": ["2023-03-31", "2023-09-30", "2024-03-31", "2024-06-30"],
            "assertion": "scores_declining",
            "assertion_type": "trend_declining",
            "assertion_description": "Scores should show declining trend"
        },
        {
            "name": "Delta Recovery Arc",
            "description": "Delta should improve from post-bankruptcy through investment grade",
            "airline": "DAL",
            "as_of_dates": ["2010-03-31", "2015-03-31", "2019-03-31", "2023-03-31"],
            "assertion": "scores_increasing",
            "assertion_type": "trend_increasing",
            "assertion_description": "Scores should show long-term improvement"
        },
        {
            "name": "Delta Strong Performer",
            "description": "Delta should consistently score 70+ in the 2022-2025 era",
            "airline": "DAL",
            "as_of_date": "2023-06-30",
            "assertion": "score >= 70",
            "assertion_type": "score_threshold",
            "threshold": 70,
            "operator": "gte",
            "assertion_description": "Score should be A or better (70+)"
        },
        {
            "name": "Southwest Stability",
            "description": "Southwest should never score below 50 in any non-COVID quarter",
            "airline": "LUV",
            "as_of_dates": "all_non_covid",
            "assertion": "all_scores >= 50",
            "assertion_type": "floor_check",
            "floor": 50,
            "exclude_dates": ["2020-03-31", "2020-06-30", "2020-09-30", "2020-12-31"],
            "assertion_description": "Score should never drop below BB (50) outside COVID"
        },
        {
            "name": "COVID Stress Test",
            "description": "All airlines should show score deterioration in Q1/Q2 2020",
            "airlines": ["DAL", "UAL", "AAL", "LUV", "JBLU", "ALK", "SAVE"],
            "compare_dates": ["2019-12-31", "2020-06-30"],
            "assertion": "all_scores_decreased",
            "assertion_type": "all_decreased",
            "assertion_description": "Every airline's score should drop from pre-COVID to mid-COVID"
        },
        {
            "name": "Rank Order Consistency",
            "description": "Our ranking should match agency ranking for stable periods",
            "as_of_date": "2023-06-30",
            "assertion": "spearman_vs_ratings >= 0.80",
            "assertion_type": "rank_correlation",
            "threshold": 0.80,
            "assertion_description": "Spearman rank correlation with agency ratings ≥ 0.80"
        },
        {
            "name": "JetBlue Merger Stress",
            "description": "JetBlue should show pressure during Spirit merger attempt",
            "airline": "JBLU",
            "compare_dates": ["2022-03-31", "2023-06-30"],
            "assertion": "score_decreased",
            "assertion_type": "comparison_decreased",
            "assertion_description": "Score should decline during merger stress"
        },
        {
            "name": "American Pre-Bankruptcy Sensitivity",
            "description": "AAL should show signs of stress before Nov 2011 filing",
            "airline": "AAL",
            "as_of_date": "2011-06-30",
            "assertion": "score < 45",
            "assertion_type": "score_threshold",
            "threshold": 45,
            "operator": "lt",
            "assertion_description": "Score should be below 45 (B range)"
        },
    ]

    def __init__(
        self,
        backtest_runner,
        backtest_data_service,
        db_service=None
    ):
        """
        Initialize Backtest Validation.

        Args:
            backtest_runner: BacktestRunner instance
            backtest_data_service: BacktestDataService instance
            db_service: DatabaseService for persistence
        """
        self.runner = backtest_runner
        self.data_service = backtest_data_service
        self.db_service = db_service
        logger.info("✅ Backtest Validation initialized")

    def run_validation_suite(
        self,
        weights: Dict[str, float] = None
    ) -> Dict[str, Any]:
        """
        Run all validation cases and produce pass/fail report.

        Args:
            weights: Optional weight overrides

        Returns:
            Validation report with pass/fail for each case
        """
        if weights is None:
            weights = self.runner.DEFAULT_BACKTEST_WEIGHTS.copy()

        start_time = datetime.now()

        logger.info(f"🧪 Starting validation suite with {len(self.VALIDATION_CASES)} test cases")

        results = {
            'validation_id': f"val_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'weights_used': weights,
            'started_at': start_time.isoformat(),
            'total_cases': len(self.VALIDATION_CASES),
            'passed': 0,
            'failed': 0,
            'skipped': 0,
            'results': [],
        }

        for case in self.VALIDATION_CASES:
            try:
                case_result = self._run_single_case(case, weights)
                results['results'].append(case_result)

                if case_result['passed']:
                    results['passed'] += 1
                elif case_result.get('skipped'):
                    results['skipped'] += 1
                else:
                    results['failed'] += 1

            except Exception as e:
                logger.error(f"❌ Error running case '{case['name']}': {e}")
                results['results'].append({
                    'name': case['name'],
                    'passed': False,
                    'skipped': False,
                    'error': str(e),
                    'expected': case.get('assertion_description'),
                })
                results['failed'] += 1

        # Calculate pass rate
        total_run = results['passed'] + results['failed']
        results['pass_rate'] = round(results['passed'] / total_run, 2) if total_run > 0 else 0

        end_time = datetime.now()
        results['completed_at'] = end_time.isoformat()
        results['runtime_seconds'] = round((end_time - start_time).total_seconds(), 1)

        # Save to database if available
        if self.db_service:
            try:
                self.db_service.save_backtest_run({
                    **results,
                    'run_type': 'validation'
                })
            except Exception as e:
                logger.warning(f"⚠️ Could not save validation results: {e}")

        logger.info(f"✅ Validation complete: {results['passed']}/{total_run} passed ({results['pass_rate']:.0%})")

        return results

    def _run_single_case(
        self,
        case: Dict[str, Any],
        weights: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Run a single validation case.

        Args:
            case: Validation case definition
            weights: Scoring weights

        Returns:
            Case result with pass/fail
        """
        assertion_type = case.get('assertion_type')
        result = {
            'name': case['name'],
            'description': case.get('description'),
            'passed': False,
            'skipped': False,
            'expected': case.get('assertion_description'),
            'actual_score': None,
            'details': None,
        }

        if assertion_type == 'score_threshold':
            return self._check_score_threshold(case, weights, result)

        elif assertion_type == 'trend_declining':
            return self._check_trend_declining(case, weights, result)

        elif assertion_type == 'trend_increasing':
            return self._check_trend_increasing(case, weights, result)

        elif assertion_type == 'floor_check':
            return self._check_floor(case, weights, result)

        elif assertion_type == 'all_decreased':
            return self._check_all_decreased(case, weights, result)

        elif assertion_type == 'rank_correlation':
            return self._check_rank_correlation(case, weights, result)

        elif assertion_type == 'comparison_decreased':
            return self._check_comparison_decreased(case, weights, result)

        else:
            result['skipped'] = True
            result['details'] = f"Unknown assertion type: {assertion_type}"
            return result

    def _get_score(
        self,
        airline_code: str,
        as_of_date: str,
        weights: Dict[str, float]
    ) -> Optional[float]:
        """Get score for an airline at a specific date."""
        try:
            obs = self.runner._calculate_observation(airline_code, as_of_date, weights)
            if obs:
                return obs['composite_score']
            return None
        except Exception as e:
            logger.warning(f"⚠️ Error getting score for {airline_code} at {as_of_date}: {e}")
            return None

    def _check_score_threshold(
        self,
        case: Dict[str, Any],
        weights: Dict[str, float],
        result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check if score meets threshold condition."""
        score = self._get_score(case['airline'], case['as_of_date'], weights)

        if score is None:
            result['skipped'] = True
            result['details'] = "Could not calculate score"
            return result

        result['actual_score'] = round(score, 1)
        threshold = case['threshold']
        operator = case['operator']

        if operator == 'lt':
            result['passed'] = score < threshold
        elif operator == 'lte':
            result['passed'] = score <= threshold
        elif operator == 'gt':
            result['passed'] = score > threshold
        elif operator == 'gte':
            result['passed'] = score >= threshold
        elif operator == 'eq':
            result['passed'] = abs(score - threshold) < 0.1

        result['details'] = f"Score {score:.1f} {'<' if operator.startswith('l') else '>='} {threshold}"

        return result

    def _check_trend_declining(
        self,
        case: Dict[str, Any],
        weights: Dict[str, float],
        result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check if scores show declining trend over dates."""
        dates = case['as_of_dates']
        scores = []

        for date in dates:
            score = self._get_score(case['airline'], date, weights)
            if score is not None:
                scores.append(score)

        if len(scores) < 2:
            result['skipped'] = True
            result['details'] = "Insufficient data points"
            return result

        result['actual_score'] = scores

        # Check if generally declining (last score < first score)
        is_declining = scores[-1] < scores[0] - 5  # Allow 5-point tolerance

        result['passed'] = is_declining
        result['details'] = f"Scores: {' → '.join([f'{s:.0f}' for s in scores])}"

        return result

    def _check_trend_increasing(
        self,
        case: Dict[str, Any],
        weights: Dict[str, float],
        result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check if scores show increasing trend over dates."""
        dates = case['as_of_dates']
        scores = []

        for date in dates:
            score = self._get_score(case['airline'], date, weights)
            if score is not None:
                scores.append(score)

        if len(scores) < 2:
            result['skipped'] = True
            result['details'] = "Insufficient data points"
            return result

        result['actual_score'] = scores

        # Check if generally increasing (last score > first score)
        is_increasing = scores[-1] > scores[0] + 5  # Allow 5-point tolerance

        result['passed'] = is_increasing
        result['details'] = f"Scores: {' → '.join([f'{s:.0f}' for s in scores])}"

        return result

    def _check_floor(
        self,
        case: Dict[str, Any],
        weights: Dict[str, float],
        result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check if all scores stay above a floor (excluding certain dates)."""
        airline = case['airline']
        floor = case['floor']
        exclude_dates = case.get('exclude_dates', [])

        # Get all quarters
        all_dates = self.data_service.get_quarter_end_dates(2015, 2025)
        check_dates = [d for d in all_dates if d not in exclude_dates]

        scores_below = []
        all_scores = []

        for date in check_dates:
            score = self._get_score(airline, date, weights)
            if score is not None:
                all_scores.append((date, score))
                if score < floor:
                    scores_below.append((date, score))

        if not all_scores:
            result['skipped'] = True
            result['details'] = "No valid scores found"
            return result

        result['actual_score'] = f"Checked {len(all_scores)} quarters"
        result['passed'] = len(scores_below) == 0
        result['details'] = f"Scores below {floor}: {len(scores_below)}"

        if scores_below:
            result['violations'] = [f"{d}: {s:.0f}" for d, s in scores_below[:3]]

        return result

    def _check_all_decreased(
        self,
        case: Dict[str, Any],
        weights: Dict[str, float],
        result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check if all airlines' scores decreased between two dates."""
        airlines = case['airlines']
        date_before, date_after = case['compare_dates']

        decreased_count = 0
        comparisons = []

        for airline in airlines:
            score_before = self._get_score(airline, date_before, weights)
            score_after = self._get_score(airline, date_after, weights)

            if score_before is not None and score_after is not None:
                decreased = score_after < score_before
                if decreased:
                    decreased_count += 1
                comparisons.append({
                    'airline': airline,
                    'before': round(score_before, 1),
                    'after': round(score_after, 1),
                    'decreased': decreased
                })

        if not comparisons:
            result['skipped'] = True
            result['details'] = "Could not get scores for comparison"
            return result

        result['passed'] = decreased_count == len(comparisons)
        result['details'] = f"{decreased_count}/{len(comparisons)} airlines decreased"
        result['comparisons'] = comparisons

        return result

    def _check_rank_correlation(
        self,
        case: Dict[str, Any],
        weights: Dict[str, float],
        result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check Spearman correlation with agency ratings at a date."""
        as_of_date = case['as_of_date']
        threshold = case['threshold']

        airlines = ['DAL', 'UAL', 'AAL', 'LUV', 'JBLU', 'ALK', 'SAVE', 'ULCC']

        model_scores = []
        rating_scores = []

        for airline in airlines:
            score = self._get_score(airline, as_of_date, weights)
            rating = self.data_service.get_rating_at_date(airline, as_of_date)

            if score is not None and rating.get('found'):
                model_scores.append(score)
                rating_scores.append(rating['numeric_score'])

        if len(model_scores) < 4:
            result['skipped'] = True
            result['details'] = "Insufficient airlines with ratings"
            return result

        try:
            corr, p_value = stats.spearmanr(model_scores, rating_scores)

            result['actual_score'] = round(corr, 3)
            result['passed'] = corr >= threshold
            result['details'] = f"Spearman correlation: {corr:.3f} (p={p_value:.4f})"

        except Exception as e:
            result['skipped'] = True
            result['details'] = f"Error calculating correlation: {e}"

        return result

    def _check_comparison_decreased(
        self,
        case: Dict[str, Any],
        weights: Dict[str, float],
        result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check if a single airline's score decreased between two dates."""
        airline = case['airline']
        date_before, date_after = case['compare_dates']

        score_before = self._get_score(airline, date_before, weights)
        score_after = self._get_score(airline, date_after, weights)

        if score_before is None or score_after is None:
            result['skipped'] = True
            result['details'] = "Could not get scores for comparison"
            return result

        result['actual_score'] = f"{score_before:.1f} → {score_after:.1f}"
        result['passed'] = score_after < score_before
        result['details'] = f"Score changed from {score_before:.1f} to {score_after:.1f}"

        return result

    def run_single_case(
        self,
        case_name: str,
        weights: Dict[str, float] = None
    ) -> Dict[str, Any]:
        """
        Run a single validation case by name.

        Args:
            case_name: Name of the case to run
            weights: Optional weight overrides

        Returns:
            Single case result
        """
        if weights is None:
            weights = self.runner.DEFAULT_BACKTEST_WEIGHTS.copy()

        for case in self.VALIDATION_CASES:
            if case['name'] == case_name:
                return self._run_single_case(case, weights)

        return {
            'name': case_name,
            'passed': False,
            'error': f"Case not found: {case_name}"
        }

    def list_cases(self) -> List[Dict[str, str]]:
        """List all available validation cases."""
        return [
            {
                'name': case['name'],
                'description': case.get('description'),
                'assertion': case.get('assertion_description')
            }
            for case in self.VALIDATION_CASES
        ]
