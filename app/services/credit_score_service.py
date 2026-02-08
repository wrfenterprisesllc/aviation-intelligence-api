#!/usr/bin/env python3
"""
Credit Score Service - Main Orchestrator
Coordinates all credit scoring dimensions and produces final composite scores.
"""

import logging
import time
from datetime import datetime
from typing import Dict, Optional, Any, List

logger = logging.getLogger(__name__)


class CreditScoreService:
    """Main orchestrator for airline credit scoring"""

    # Default weights (can be overridden from Firestore config)
    DEFAULT_WEIGHTS = {
        'financial': 0.35,
        'signals': 0.20,
        'operational': 0.25,
        'qualitative': 0.20
    }

    # Backtest weights (no Gemini, redistribute qualitative weight)
    BACKTEST_WEIGHTS = {
        'financial': 0.44,
        'signals': 0.25,
        'operational': 0.31,
        'qualitative': 0.00
    }

    # Score to letter grade thresholds
    GRADE_THRESHOLDS = [
        (95, 'AAA'),
        (90, 'AA+'),
        (87, 'AA'),
        (84, 'AA-'),
        (81, 'A+'),
        (78, 'A'),
        (75, 'A-'),
        (72, 'BBB+'),
        (69, 'BBB'),
        (66, 'BBB-'),
        (62, 'BB+'),
        (58, 'BB'),
        (54, 'BB-'),
        (50, 'B+'),
        (45, 'B'),
        (40, 'B-'),
        (35, 'CCC+'),
        (30, 'CCC'),
        (25, 'CCC-'),
        (15, 'CC'),
        (5, 'C'),
        (0, 'D')
    ]

    # Hurdle rate adjustment by grade (basis points above base rate)
    HURDLE_ADJUSTMENTS = {
        'AAA': 0, 'AA+': 10, 'AA': 20, 'AA-': 30,
        'A+': 50, 'A': 75, 'A-': 100,
        'BBB+': 150, 'BBB': 200, 'BBB-': 250,
        'BB+': 350, 'BB': 450, 'BB-': 550,
        'B+': 650, 'B': 750, 'B-': 850,
        'CCC+': 950, 'CCC': 1050, 'CCC-': 1150,
        'CC': 1300, 'C': 1500, 'D': 2000
    }

    # Supported airlines
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

    def __init__(
        self,
        db_service,
        xbrl_service,
        signals_service,
        operational_service,
        qualitative_service
    ):
        """
        Initialize Credit Score service.

        Args:
            db_service: DatabaseService for persistence
            xbrl_service: XBRLService for financial data
            signals_service: CreditSignalsService for ratings/momentum
            operational_service: OperationalService for ops metrics
            qualitative_service: CreditQualitativeService for AI analysis
        """
        self.db_service = db_service
        self.xbrl = xbrl_service
        self.signals = signals_service
        self.operational = operational_service
        self.qualitative = qualitative_service

        logger.info("✅ Credit Score orchestrator service initialized")

    def _get_weights(self, backtest_mode: bool = False) -> Dict[str, float]:
        """
        Get scoring weights from config or use defaults.

        Args:
            backtest_mode: If True, use backtest weights (no qualitative)

        Returns:
            Dict with weight values
        """
        if backtest_mode:
            return self.BACKTEST_WEIGHTS.copy()

        # Try to load from Firestore config
        if self.db_service:
            try:
                weights = self.db_service.get_credit_score_weights()
                if weights:
                    logger.info("📊 Using weights from Firestore config")
                    return weights
            except Exception as e:
                logger.warning(f"⚠️ Error loading weights from config: {e}")

        return self.DEFAULT_WEIGHTS.copy()

    def _score_to_grade(self, score: float) -> str:
        """Convert numeric score (0-100) to letter grade."""
        for threshold, grade in self.GRADE_THRESHOLDS:
            if score >= threshold:
                return grade
        return 'D'

    def calculate_credit_score(
        self,
        airline_code: str,
        weights: Optional[Dict[str, float]] = None,
        as_of_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate complete credit score for an airline.

        Args:
            airline_code: Airline ticker (e.g., 'DAL')
            weights: Optional custom weights (default from config)
            as_of_date: Optional date for backtesting (YYYY-MM-DD)

        Returns:
            Complete credit score with all dimensions and breakdowns
        """
        start_time = datetime.now()
        code = airline_code.upper()

        if code not in self.AIRLINES:
            raise ValueError(f"Unsupported airline: {code}. Supported: {', '.join(self.AIRLINES)}")

        # Determine if backtest mode
        backtest_mode = as_of_date is not None

        # Get weights
        if weights is None:
            weights = self._get_weights(backtest_mode=backtest_mode)

        logger.info(f"📊 Calculating credit score for {code} (backtest={backtest_mode})")

        # 1. Financial Score (XBRL)
        xbrl_metrics = None
        financial_result = {'financial_score': 50, 'sub_scores': {}, 'metrics_used': {}}
        try:
            xbrl_metrics = self.xbrl.get_financial_metrics(code, as_of_date)
            if xbrl_metrics:
                financial_result = self.xbrl.calculate_financial_score(xbrl_metrics)
        except Exception as e:
            logger.error(f"❌ Error getting XBRL data for {code}: {e}")

        financial_score = financial_result.get('financial_score', 50)

        # 2. Signals Score (Ratings + Momentum)
        signals_result = {'signals_score': 50, 'rating_component': {}, 'momentum_component': {}}
        try:
            signals_result = self.signals.calculate_signals_score(code, as_of_date)
        except Exception as e:
            logger.error(f"❌ Error getting signals for {code}: {e}")

        signals_score = signals_result.get('signals_score', 50)

        # 3. Operational Score
        operational_result = {'operational_score': 50, 'sub_scores': {}, 'metrics': {}}
        try:
            operational_result = self.operational.calculate_operational_score(code, as_of_date)
        except Exception as e:
            logger.error(f"❌ Error getting operational data for {code}: {e}")

        operational_score = operational_result.get('operational_score', 50)

        # 4. Qualitative Score (skip in backtest mode)
        if backtest_mode or weights.get('qualitative', 0) == 0:
            qualitative_result = {
                'qualitative_score': 50,
                'key_risks': ['Backtest mode - AI assessment skipped'],
                'key_strengths': [],
                'sentiment_summary': 'AI assessment skipped in backtest mode.',
                'outlook': 'stable',
                'narrative': 'Qualitative assessment was skipped because this is a backtest calculation. The default neutral score of 50 is applied.',
                'is_backtest': True
            }
        else:
            try:
                airline_name = self.AIRLINE_NAMES.get(code, code)
                qualitative_result = self.qualitative.generate_qualitative_assessment(
                    airline_code=code,
                    airline_name=airline_name,
                    financial_score=financial_score,
                    signals_score=signals_score,
                    operational_score=operational_score,
                    financial_breakdown=financial_result,
                    signals_breakdown=signals_result,
                    operational_breakdown=operational_result
                )
            except Exception as e:
                logger.error(f"❌ Error generating qualitative assessment for {code}: {e}")
                qualitative_result = {
                    'qualitative_score': 50,
                    'key_risks': [f'AI assessment error: {str(e)}'],
                    'key_strengths': [],
                    'sentiment_summary': 'AI assessment failed.',
                    'outlook': 'stable',
                    'narrative': 'Qualitative assessment could not be generated due to an error.',
                    'is_default': True
                }

        qualitative_score = qualitative_result.get('qualitative_score', 50)

        # 5. Calculate weighted overall score
        overall_score = (
            financial_score * weights['financial'] +
            signals_score * weights['signals'] +
            operational_score * weights['operational'] +
            qualitative_score * weights['qualitative']
        )

        # 6. Determine letter grade and hurdle adjustment
        letter_grade = self._score_to_grade(overall_score)
        hurdle_adjustment = self.HURDLE_ADJUSTMENTS.get(letter_grade, 500)

        # Determine if investment grade
        is_investment_grade = letter_grade in ['AAA', 'AA+', 'AA', 'AA-', 'A+', 'A', 'A-', 'BBB+', 'BBB', 'BBB-']

        # Build response
        calc_time = (datetime.now() - start_time).total_seconds() * 1000

        result = {
            'airline_code': code,
            'airline_name': self.AIRLINE_NAMES.get(code),
            'ticker': code,

            'overall_score': round(overall_score, 1),
            'letter_grade': letter_grade,
            'is_investment_grade': is_investment_grade,
            'hurdle_adjustment_bps': hurdle_adjustment,

            'financial_score': round(financial_score, 1),
            'signals_score': round(signals_score, 1),
            'operational_score': round(operational_score, 1),
            'qualitative_score': round(qualitative_score, 1),

            'financial_breakdown': financial_result,
            'signals_breakdown': signals_result,
            'operational_breakdown': operational_result,
            'qualitative_breakdown': qualitative_result,

            'weights_used': weights,
            'backtest_mode': backtest_mode,
            'as_of_date': as_of_date,
            'calculated_at': datetime.utcnow().isoformat(),
            'calculation_time_ms': round(calc_time, 1),

            'data_freshness': {
                'xbrl_as_of': xbrl_metrics.get('as_of_date') if xbrl_metrics else None,
                'ratings_as_of': signals_result.get('as_of_date'),
                'operational_as_of': operational_result.get('data_as_of')
            }
        }

        # Save to database
        if self.db_service:
            try:
                self.db_service.save_credit_score(result)

                # Also save to history
                history_entry = {
                    'airline_code': code,
                    'overall_score': result['overall_score'],
                    'letter_grade': letter_grade,
                    'financial_score': result['financial_score'],
                    'signals_score': result['signals_score'],
                    'operational_score': result['operational_score'],
                    'qualitative_score': result['qualitative_score'],
                    'calculated_at': datetime.utcnow(),
                    'snapshot_type': 'backtest' if backtest_mode else 'manual_refresh'
                }
                self.db_service.save_credit_score_history(history_entry)
            except Exception as e:
                logger.error(f"❌ Error saving credit score to database: {e}")

        logger.info(f"✅ Credit score for {code}: {overall_score:.1f} ({letter_grade}) in {calc_time:.0f}ms")

        return result

    def refresh_all_scores(self, delay_seconds: float = 2.0) -> Dict[str, Any]:
        """
        Refresh credit scores for all airlines.

        Args:
            delay_seconds: Delay between airlines (for SEC rate limiting)

        Returns:
            Summary of refresh operation
        """
        results = {
            'success': True,
            'airlines_processed': [],
            'airlines_failed': [],
            'started_at': datetime.utcnow().isoformat(),
            'total_airlines': len(self.AIRLINES)
        }

        for i, code in enumerate(self.AIRLINES):
            try:
                logger.info(f"📊 Refreshing {code} ({i+1}/{len(self.AIRLINES)})")

                score_result = self.calculate_credit_score(code)
                results['airlines_processed'].append({
                    'code': code,
                    'name': self.AIRLINE_NAMES.get(code),
                    'score': score_result['overall_score'],
                    'grade': score_result['letter_grade'],
                    'calculation_time_ms': score_result['calculation_time_ms']
                })

                # Rate limiting delay (except for last airline)
                if i < len(self.AIRLINES) - 1:
                    time.sleep(delay_seconds)

            except Exception as e:
                logger.error(f"❌ Failed to refresh {code}: {e}")
                results['airlines_failed'].append({
                    'code': code,
                    'name': self.AIRLINE_NAMES.get(code),
                    'error': str(e)
                })

        results['completed_at'] = datetime.utcnow().isoformat()
        results['success'] = len(results['airlines_failed']) == 0
        results['processed_count'] = len(results['airlines_processed'])
        results['failed_count'] = len(results['airlines_failed'])

        logger.info(f"✅ Refresh complete: {results['processed_count']} processed, {results['failed_count']} failed")

        return results

    def get_all_scores(self) -> List[Dict[str, Any]]:
        """
        Get current credit scores for all airlines.

        Returns:
            List of credit score dictionaries
        """
        if not self.db_service:
            logger.warning("⚠️ Database service not available")
            return []

        try:
            scores = self.db_service.get_all_credit_scores()

            # Sort by overall score descending
            scores.sort(key=lambda x: x.get('overall_score', 0), reverse=True)

            return scores
        except Exception as e:
            logger.error(f"❌ Error fetching all credit scores: {e}")
            return []

    def get_score(self, airline_code: str) -> Optional[Dict[str, Any]]:
        """
        Get current credit score for a single airline.

        Args:
            airline_code: Airline ticker

        Returns:
            Credit score dictionary or None if not found
        """
        if not self.db_service:
            logger.warning("⚠️ Database service not available")
            return None

        try:
            return self.db_service.get_credit_score(airline_code.upper())
        except Exception as e:
            logger.error(f"❌ Error fetching credit score for {airline_code}: {e}")
            return None

    def get_score_history(
        self,
        airline_code: str,
        limit: int = 52
    ) -> List[Dict[str, Any]]:
        """
        Get historical credit scores for an airline.

        Args:
            airline_code: Airline ticker
            limit: Maximum number of records (default 52 for ~1 year weekly)

        Returns:
            List of historical score dictionaries, newest first
        """
        if not self.db_service:
            logger.warning("⚠️ Database service not available")
            return []

        try:
            return self.db_service.get_credit_score_history(airline_code.upper(), limit=limit)
        except Exception as e:
            logger.error(f"❌ Error fetching credit score history for {airline_code}: {e}")
            return []
