#!/usr/bin/env python3
"""
Backtest Optimizer - Weight Optimization via Grid Search
Finds optimal dimension weights by testing combinations against historical data.
"""

import logging
from datetime import datetime
from typing import Dict, Optional, Any, List
from itertools import product

logger = logging.getLogger(__name__)


class BacktestOptimizer:
    """Service for optimizing credit score weights via backtesting"""

    # Weight search space (must sum to 1.0, qualitative = 0 for backtest)
    WEIGHT_RANGES = {
        'financial': [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70],
        'signals': [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40],
        'operational': [0.05, 0.10, 0.15, 0.20, 0.25, 0.30],
    }

    # Optimization objective weights
    OBJECTIVE_WEIGHTS = {
        'spearman': 0.50,        # Maximize rank correlation with agencies
        'detection': 0.35,       # Maximize pre-event detection
        'false_positive': 0.15,  # Minimize false positives (subtracted)
    }

    def __init__(
        self,
        backtest_runner,
        db_service=None
    ):
        """
        Initialize Backtest Optimizer.

        Args:
            backtest_runner: BacktestRunner instance
            db_service: DatabaseService for persistence
        """
        self.runner = backtest_runner
        self.db_service = db_service
        logger.info("✅ Backtest Optimizer initialized")

    def _generate_weight_combinations(self) -> List[Dict[str, float]]:
        """
        Generate all valid weight combinations that sum to 1.0.

        Returns:
            List of weight dictionaries
        """
        combinations = []

        for fin in self.WEIGHT_RANGES['financial']:
            for sig in self.WEIGHT_RANGES['signals']:
                for ops in self.WEIGHT_RANGES['operational']:
                    # Check if they sum to 1.0 (allow small tolerance)
                    total = fin + sig + ops
                    if abs(total - 1.0) < 0.001:
                        combinations.append({
                            'financial': fin,
                            'signals': sig,
                            'operational': ops,
                            'qualitative': 0.0
                        })

        logger.info(f"📊 Generated {len(combinations)} valid weight combinations")
        return combinations

    def _calculate_combined_score(
        self,
        spearman: float,
        detection_rate: float,
        false_positive_rate: float
    ) -> float:
        """
        Calculate combined optimization objective.

        Formula: (spearman × 0.50) + (detection × 0.35) - (false_positive × 0.15)

        Args:
            spearman: Spearman rank correlation (0-1)
            detection_rate: Pre-event detection rate (0-1)
            false_positive_rate: False positive rate (0-1)

        Returns:
            Combined score (higher is better)
        """
        score = (
            spearman * self.OBJECTIVE_WEIGHTS['spearman'] +
            detection_rate * self.OBJECTIVE_WEIGHTS['detection'] -
            false_positive_rate * self.OBJECTIVE_WEIGHTS['false_positive']
        )
        return round(score, 4)

    def optimize_weights(
        self,
        start_year: int = 2015,
        end_year: int = None
    ) -> Dict[str, Any]:
        """
        Run grid search to find optimal weights.

        Args:
            start_year: Start year for backtest
            end_year: End year for backtest

        Returns:
            Optimization results with optimal weights and all tested configs
        """
        if end_year is None:
            end_year = datetime.now().year

        start_time = datetime.now()

        logger.info(f"🔄 Starting weight optimization: {start_year}-{end_year}")

        # Generate all valid combinations
        weight_combos = self._generate_weight_combinations()

        if not weight_combos:
            return {
                'success': False,
                'error': 'No valid weight combinations generated'
            }

        results = {
            'optimization_id': f"opt_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'date_range': {
                'start_year': start_year,
                'end_year': end_year
            },
            'objective_weights': self.OBJECTIVE_WEIGHTS,
            'started_at': start_time.isoformat(),
            'all_results': [],
            'optimal_weights': None,
            'optimal_score': None,
            'top_5_configs': [],
        }

        # Test each combination
        total_combos = len(weight_combos)
        for i, weights in enumerate(weight_combos):
            try:
                logger.info(f"📊 Testing config {i+1}/{total_combos}: "
                           f"fin={weights['financial']:.2f}, sig={weights['signals']:.2f}, ops={weights['operational']:.2f}")

                # Run backtest with these weights
                backtest = self.runner.run_full_backtest(
                    weights=weights,
                    start_year=start_year,
                    end_year=end_year
                )

                metrics = backtest.get('summary_metrics', {})

                spearman = metrics.get('spearman_rank_correlation', 0)
                detection = metrics.get('pre_event_detection_rate', 0)
                false_pos = metrics.get('false_positive_rate', 0)
                mae = metrics.get('mean_absolute_error_vs_rating', 0)

                combined = self._calculate_combined_score(spearman, detection, false_pos)

                config_result = {
                    'weights': weights,
                    'metrics': {
                        'spearman_correlation': spearman,
                        'pre_event_detection': detection,
                        'false_positive_rate': false_pos,
                        'mean_absolute_error': mae,
                    },
                    'combined_score': combined,
                }

                results['all_results'].append(config_result)

            except Exception as e:
                logger.warning(f"⚠️ Error testing config {i+1}: {e}")
                results['all_results'].append({
                    'weights': weights,
                    'error': str(e),
                    'combined_score': -1,
                })

        # Sort by combined score (descending)
        results['all_results'].sort(key=lambda x: x.get('combined_score', -1), reverse=True)

        # Extract optimal and top 5
        if results['all_results'] and results['all_results'][0].get('combined_score', -1) >= 0:
            best = results['all_results'][0]
            results['optimal_weights'] = best['weights']
            results['optimal_score'] = best.get('metrics', {})
            results['optimal_combined_score'] = best['combined_score']

            results['top_5_configs'] = [
                {
                    'rank': i + 1,
                    'weights': r['weights'],
                    'combined_score': r['combined_score'],
                    'spearman': r.get('metrics', {}).get('spearman_correlation', 0),
                    'detection_rate': r.get('metrics', {}).get('pre_event_detection', 0),
                }
                for i, r in enumerate(results['all_results'][:5])
            ]

        # Calculate runtime
        end_time = datetime.now()
        runtime = (end_time - start_time).total_seconds()

        results['completed_at'] = end_time.isoformat()
        results['runtime_seconds'] = round(runtime, 1)
        results['total_combinations_tested'] = len(weight_combos)
        results['success'] = results['optimal_weights'] is not None

        # Save to database if available
        if self.db_service:
            try:
                self.db_service.save_backtest_run({
                    **results,
                    'run_type': 'optimization'
                })
            except Exception as e:
                logger.warning(f"⚠️ Could not save optimization results: {e}")

        logger.info(f"✅ Optimization complete in {runtime:.1f}s")
        logger.info(f"📊 Optimal weights: {results.get('optimal_weights')}")
        logger.info(f"📊 Optimal combined score: {results.get('optimal_combined_score')}")

        return results

    def quick_optimize(
        self,
        start_year: int = 2020,
        end_year: int = None,
        sample_size: int = 20
    ) -> Dict[str, Any]:
        """
        Quick optimization with reduced search space.
        Useful for testing or when full optimization takes too long.

        Args:
            start_year: Start year (later = faster)
            end_year: End year
            sample_size: Number of random configurations to test

        Returns:
            Optimization results
        """
        import random

        if end_year is None:
            end_year = datetime.now().year

        start_time = datetime.now()

        logger.info(f"🔄 Starting quick optimization: {start_year}-{end_year} ({sample_size} samples)")

        # Generate and sample combinations
        all_combos = self._generate_weight_combinations()
        sample_combos = random.sample(all_combos, min(sample_size, len(all_combos)))

        results = {
            'optimization_id': f"qopt_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'is_quick_optimization': True,
            'date_range': {
                'start_year': start_year,
                'end_year': end_year
            },
            'started_at': start_time.isoformat(),
            'all_results': [],
            'optimal_weights': None,
            'optimal_score': None,
        }

        for i, weights in enumerate(sample_combos):
            try:
                logger.info(f"📊 Quick test {i+1}/{len(sample_combos)}")

                backtest = self.runner.run_full_backtest(
                    weights=weights,
                    start_year=start_year,
                    end_year=end_year
                )

                metrics = backtest.get('summary_metrics', {})
                combined = self._calculate_combined_score(
                    metrics.get('spearman_rank_correlation', 0),
                    metrics.get('pre_event_detection_rate', 0),
                    metrics.get('false_positive_rate', 0)
                )

                results['all_results'].append({
                    'weights': weights,
                    'metrics': metrics,
                    'combined_score': combined,
                })

            except Exception as e:
                logger.warning(f"⚠️ Error: {e}")

        # Sort and extract best
        results['all_results'].sort(key=lambda x: x.get('combined_score', -1), reverse=True)

        if results['all_results'] and results['all_results'][0].get('combined_score', -1) >= 0:
            best = results['all_results'][0]
            results['optimal_weights'] = best['weights']
            results['optimal_score'] = best.get('metrics', {})
            results['optimal_combined_score'] = best['combined_score']

        end_time = datetime.now()
        results['completed_at'] = end_time.isoformat()
        results['runtime_seconds'] = round((end_time - start_time).total_seconds(), 1)
        results['combinations_tested'] = len(sample_combos)
        results['success'] = results['optimal_weights'] is not None

        return results

    def get_recommended_weights(
        self,
        optimization_result: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Extract recommended weights from optimization result.
        For use in updating the live scoring config.

        Args:
            optimization_result: Result from optimize_weights()

        Returns:
            Weight dictionary for production use
        """
        if not optimization_result.get('success'):
            # Return default weights if optimization failed
            return {
                'financial': 0.44,
                'signals': 0.25,
                'operational': 0.31,
                'qualitative': 0.00
            }

        # Get optimized weights and add back qualitative component
        # Adjust proportionally for production use (include 20% qualitative)
        opt_weights = optimization_result.get('optimal_weights', {})

        # Scale down quantitative dimensions to make room for qualitative
        # Current total is 1.0, we want them to sum to 0.80
        scale_factor = 0.80

        return {
            'financial': round(opt_weights.get('financial', 0.44) * scale_factor, 2),
            'signals': round(opt_weights.get('signals', 0.25) * scale_factor, 2),
            'operational': round(opt_weights.get('operational', 0.31) * scale_factor, 2),
            'qualitative': 0.20  # Restore qualitative for live scoring
        }
