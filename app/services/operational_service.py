#!/usr/bin/env python3
"""
Operational Service - Airline Operational Metrics Scoring
Scores airlines on load factor, fleet age, route diversity, RASM-CASM spread.
"""

import logging
from datetime import datetime
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class OperationalService:
    """Service for scoring airline operational metrics"""

    # Hardcoded operational data for 8 airlines
    # Source: Company investor presentations, FlightGlobal, OAG, DOT BTS
    # Data as of Q3 2025 (to be updated quarterly)
    OPERATIONAL_DATA = {
        'DAL': {
            'airline_name': 'Delta Air Lines',
            'load_factor': 87.2,         # System load factor %
            'fleet_age_years': 15.8,     # Average fleet age
            'fleet_size': 915,           # Total aircraft
            'route_diversity': 0.82,     # Herfindahl diversity (1=diverse, 0=concentrated)
            'domestic_pct': 0.68,        # % of ASMs domestic
            'rasm_cents': 20.15,         # Revenue per ASM (cents)
            'casm_cents': 17.42,         # Cost per ASM (cents)
            'data_as_of': '2025-09-30'
        },
        'UAL': {
            'airline_name': 'United Airlines',
            'load_factor': 86.5,
            'fleet_age_years': 16.2,
            'fleet_size': 865,
            'route_diversity': 0.80,
            'domestic_pct': 0.58,
            'rasm_cents': 19.85,
            'casm_cents': 17.12,
            'data_as_of': '2025-09-30'
        },
        'AAL': {
            'airline_name': 'American Airlines',
            'load_factor': 85.1,
            'fleet_age_years': 13.4,
            'fleet_size': 950,
            'route_diversity': 0.78,
            'domestic_pct': 0.72,
            'rasm_cents': 18.92,
            'casm_cents': 17.68,
            'data_as_of': '2025-09-30'
        },
        'LUV': {
            'airline_name': 'Southwest Airlines',
            'load_factor': 83.0,
            'fleet_age_years': 12.1,
            'fleet_size': 800,
            'route_diversity': 0.55,     # Single fleet type, point-to-point network
            'domestic_pct': 0.98,        # Almost entirely domestic
            'rasm_cents': 16.12,
            'casm_cents': 15.08,
            'data_as_of': '2025-09-30'
        },
        'JBLU': {
            'airline_name': 'JetBlue Airways',
            'load_factor': 85.0,
            'fleet_age_years': 14.5,
            'fleet_size': 280,
            'route_diversity': 0.52,     # Northeast/Florida focused
            'domestic_pct': 0.85,
            'rasm_cents': 14.85,
            'casm_cents': 14.35,
            'data_as_of': '2025-09-30'
        },
        'ALK': {
            'airline_name': 'Alaska Air Group',
            'load_factor': 87.0,
            'fleet_age_years': 10.2,
            'fleet_size': 350,
            'route_diversity': 0.58,     # West Coast focused
            'domestic_pct': 0.92,
            'rasm_cents': 16.50,
            'casm_cents': 14.70,
            'data_as_of': '2025-09-30'
        },
        'SAVE': {
            'airline_name': 'Spirit Airlines',
            'load_factor': 81.0,
            'fleet_age_years': 6.5,      # Young fleet (all A320neo family)
            'fleet_size': 190,
            'route_diversity': 0.42,     # ULCC domestic leisure focused
            'domestic_pct': 0.92,
            'rasm_cents': 10.32,
            'casm_cents': 10.87,         # Negative spread (distress indicator)
            'data_as_of': '2025-09-30'
        },
        'ULCC': {
            'airline_name': 'Frontier Group',
            'load_factor': 83.0,
            'fleet_age_years': 5.8,      # Young fleet
            'fleet_size': 140,
            'route_diversity': 0.45,     # ULCC focused on leisure
            'domestic_pct': 0.95,
            'rasm_cents': 10.75,
            'casm_cents': 10.11,
            'data_as_of': '2025-09-30'
        },
    }

    # Industry benchmarks for scoring (based on US majors)
    BENCHMARKS = {
        'load_factor': {
            'excellent': 87,   # >87% = top tier
            'good': 83,        # 83-87% = solid
            'fair': 78,        # 78-83% = acceptable
            'poor': 70         # <70% = concerning
        },
        'fleet_age': {
            'excellent': 8,    # <8 years = very modern
            'good': 12,        # 8-12 = modern
            'fair': 16,        # 12-16 = average
            'poor': 20         # >20 = aging concerns
        },
        'route_diversity': {
            'excellent': 0.75, # High geographic/type diversity
            'good': 0.60,
            'fair': 0.45,
            'poor': 0.30       # Highly concentrated
        },
        'rasm_spread': {
            'excellent': 3.0,  # RASM-CASM > 3 cents = strong unit economics
            'good': 1.5,       # 1.5-3.0 = healthy
            'fair': 0.5,       # 0.5-1.5 = thin margins
            'poor': -0.5       # Negative = losing money per ASM
        }
    }

    def __init__(self, bts_service=None):
        """
        Initialize Operational service.

        Args:
            bts_service: BTSService for carrier financials (optional, for future updates)
        """
        self.bts_service = bts_service
        logger.info("✅ Operational service initialized")

    def get_operational_metrics(
        self,
        airline_code: str,
        as_of_date: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get operational metrics for an airline.

        Args:
            airline_code: Airline ticker
            as_of_date: Optional date for backtesting (uses current data for now)

        Returns:
            Dict with operational metrics or None
        """
        code = airline_code.upper()

        if code not in self.OPERATIONAL_DATA:
            logger.warning(f"⚠️ Unknown airline code: {code}")
            return None

        # Start with hardcoded data
        metrics = self.OPERATIONAL_DATA[code].copy()
        metrics['airline_code'] = code

        # Calculate RASM-CASM spread
        metrics['rasm_spread'] = round(metrics['rasm_cents'] - metrics['casm_cents'], 2)

        # Try to supplement with BTS data if available
        if self.bts_service:
            # Convert ticker to BTS carrier code
            ticker_to_bts = {
                'DAL': 'DL', 'UAL': 'UA', 'AAL': 'AA', 'LUV': 'WN',
                'JBLU': 'B6', 'ALK': 'AS', 'SAVE': 'NK', 'ULCC': 'F9'
            }
            bts_code = ticker_to_bts.get(code)

            if bts_code:
                try:
                    bts_data = self.bts_service.get_carrier_financials(bts_code)
                    if bts_data:
                        # Update with fresher BTS data if available
                        if 'load_factor_pct' in bts_data:
                            metrics['load_factor'] = bts_data['load_factor_pct']
                        if 'rasm_cents' in bts_data and bts_data['rasm_cents']:
                            metrics['rasm_cents'] = bts_data['rasm_cents']
                        if 'casm_cents' in bts_data and bts_data['casm_cents']:
                            metrics['casm_cents'] = bts_data['casm_cents']
                        # Recalculate spread
                        metrics['rasm_spread'] = round(metrics['rasm_cents'] - metrics['casm_cents'], 2)
                        metrics['bts_period'] = bts_data.get('period')
                        logger.info(f"📊 Updated {code} metrics from BTS data")
                except Exception as e:
                    logger.warning(f"⚠️ Could not fetch BTS data for {code}: {e}")

        return metrics

    def _score_metric(
        self,
        value: float,
        benchmarks: Dict[str, float],
        higher_is_better: bool = True
    ) -> float:
        """
        Score a metric value against benchmarks.

        Args:
            value: The metric value
            benchmarks: Dict with 'excellent', 'good', 'fair', 'poor' thresholds
            higher_is_better: If True, higher values score better

        Returns:
            Score 0-100
        """
        excellent = benchmarks['excellent']
        good = benchmarks['good']
        fair = benchmarks['fair']
        poor = benchmarks['poor']

        if higher_is_better:
            if value >= excellent:
                return 90 + min(10, (value - excellent) * 2)
            elif value >= good:
                return 70 + (value - good) / (excellent - good) * 20
            elif value >= fair:
                return 50 + (value - fair) / (good - fair) * 20
            elif value >= poor:
                return 30 + (value - poor) / (fair - poor) * 20
            else:
                return max(10, 30 - (poor - value) * 2)
        else:
            # Lower is better (e.g., fleet age)
            if value <= excellent:
                return 95
            elif value <= good:
                return 75 + (good - value) / (good - excellent) * 20
            elif value <= fair:
                return 55 + (fair - value) / (fair - good) * 20
            elif value <= poor:
                return 35 + (poor - value) / (poor - fair) * 20
            else:
                return max(15, 35 - (value - poor) * 2)

    def calculate_operational_score(
        self,
        airline_code: str,
        as_of_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate operational score from metrics.

        Scoring weights:
        - Load Factor: 25%
        - Fleet Age: 20%
        - Route Diversity: 25%
        - RASM Spread: 30%

        Args:
            airline_code: Airline ticker
            as_of_date: Optional date for backtesting

        Returns:
            Dict with operational_score and breakdown
        """
        metrics = self.get_operational_metrics(airline_code, as_of_date)

        if not metrics:
            return {
                'airline_code': airline_code.upper(),
                'operational_score': 50,
                'reason': f'No operational data for {airline_code}',
                'as_of_date': as_of_date
            }

        sub_scores = {}

        # Load Factor Score (25%)
        lf = metrics['load_factor']
        sub_scores['load_factor'] = self._score_metric(
            lf,
            self.BENCHMARKS['load_factor'],
            higher_is_better=True
        )

        # Fleet Age Score (20%) - lower is better
        fa = metrics['fleet_age_years']
        sub_scores['fleet_age'] = self._score_metric(
            fa,
            self.BENCHMARKS['fleet_age'],
            higher_is_better=False
        )

        # Route Diversity Score (25%)
        rd = metrics['route_diversity']
        sub_scores['route_diversity'] = self._score_metric(
            rd,
            self.BENCHMARKS['route_diversity'],
            higher_is_better=True
        )

        # RASM Spread Score (30%) - most important for profitability
        spread = metrics['rasm_spread']
        if spread < 0:
            # Negative spread is very concerning
            sub_scores['rasm_spread'] = max(5, 30 + spread * 10)
        else:
            sub_scores['rasm_spread'] = self._score_metric(
                spread,
                self.BENCHMARKS['rasm_spread'],
                higher_is_better=True
            )

        # Weighted average
        weights = {
            'load_factor': 0.25,
            'fleet_age': 0.20,
            'route_diversity': 0.25,
            'rasm_spread': 0.30
        }

        operational_score = sum(sub_scores[k] * weights[k] for k in sub_scores)

        logger.info(f"📊 {airline_code} operational score: {operational_score:.1f}")

        return {
            'airline_code': airline_code.upper(),
            'airline_name': metrics.get('airline_name'),
            'operational_score': round(operational_score, 1),
            'sub_scores': {k: round(v, 1) for k, v in sub_scores.items()},
            'weights': weights,
            'metrics': {
                'load_factor': metrics['load_factor'],
                'fleet_age_years': metrics['fleet_age_years'],
                'fleet_size': metrics.get('fleet_size'),
                'route_diversity': metrics['route_diversity'],
                'domestic_pct': metrics.get('domestic_pct'),
                'rasm_cents': metrics['rasm_cents'],
                'casm_cents': metrics['casm_cents'],
                'rasm_spread': metrics['rasm_spread'],
            },
            'data_as_of': metrics.get('data_as_of'),
            'bts_period': metrics.get('bts_period'),
            'as_of_date': as_of_date
        }
