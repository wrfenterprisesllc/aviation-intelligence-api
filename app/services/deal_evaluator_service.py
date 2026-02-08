#!/usr/bin/env python3
"""
Deal Evaluator Service - Aircraft Lease Economics Calculator

Provides DCF-based deal evaluation with:
- Dynamic hurdle rates from FRED credit spreads
- Auto-detection of lessee credit tier from Yahoo Finance
- Newton-Raphson IRR calculation
- Binary search price solver
- Sensitivity analysis matrices
- Gemini AI deal commentary
"""

import math
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


# Default aircraft data - loaded from database when available
# Uses half-life depreciation model for residual estimation
DEFAULT_AIRCRAFT_DATA = {
    "A320neo": {"residual_base": 28_000_000, "half_life": 12, "new_price": 110_000_000},
    "A321neo": {"residual_base": 32_000_000, "half_life": 12, "new_price": 129_000_000},
    "A330-900": {"residual_base": 45_000_000, "half_life": 15, "new_price": 264_000_000},
    "A350-900": {"residual_base": 65_000_000, "half_life": 18, "new_price": 317_000_000},
    "737 MAX 8": {"residual_base": 25_000_000, "half_life": 12, "new_price": 121_000_000},
    "737 MAX 9": {"residual_base": 28_000_000, "half_life": 12, "new_price": 128_000_000},
    "737-800": {"residual_base": 18_000_000, "half_life": 10, "new_price": 102_000_000},
    "777-300ER": {"residual_base": 55_000_000, "half_life": 16, "new_price": 375_000_000},
    "787-9": {"residual_base": 60_000_000, "half_life": 18, "new_price": 292_000_000},
    "E195-E2": {"residual_base": 15_000_000, "half_life": 11, "new_price": 60_000_000}
}

# Credit tier spreads over Treasury (basis points)
TIER_SPREADS = {
    "AAA/AA": {"spread_bps": 50, "label": "Sovereign-backed / Flag carrier", "color": "#10B981"},
    "A/BBB+": {"spread_bps": 150, "label": "Strong national carrier", "color": "#22C55E"},
    "BBB/BBB-": {"spread_bps": 250, "label": "Established carrier", "color": "#84CC16"},
    "BB+/BB": {"spread_bps": 400, "label": "Mid-tier / Regional", "color": "#EAB308"},
    "BB-/B+": {"spread_bps": 550, "label": "Startup / LCC", "color": "#F97316"},
    "B/CCC": {"spread_bps": 750, "label": "Distressed / Watch list", "color": "#EF4444"}
}

# Mapping from financial service ratings to our tiers
RATING_TO_TIER = {
    'A': 'A/BBB+', 'A-': 'A/BBB+',
    'BBB+': 'A/BBB+', 'BBB': 'BBB/BBB-', 'BBB-': 'BBB/BBB-',
    'BB+': 'BB+/BB', 'BB': 'BB+/BB',
    'BB-': 'BB-/B+', 'B+': 'BB-/B+', 'B': 'B/CCC', 'CCC': 'B/CCC'
}


class DealEvaluatorService:
    """
    Service for evaluating aircraft lease deals with DCF analysis.

    Features:
    - Dynamic hurdle rates from live FRED credit spreads
    - Auto-detection of lessee credit tier from balance sheet data
    - IRR calculation using Newton-Raphson iteration
    - Price solver using binary search
    - Sensitivity analysis matrices
    - AI-generated deal commentary
    """

    def __init__(
        self,
        db_service=None,
        fred_service=None,
        financial_service=None,
        gemini_service=None
    ):
        """
        Initialize the Deal Evaluator service.

        Args:
            db_service: Database service for aircraft defaults and persistence
            fred_service: FRED service for live credit spreads
            financial_service: Financial service for airline credit estimation
            gemini_service: Gemini service for AI commentary
        """
        self.db_service = db_service
        self.fred_service = fred_service
        self.financial_service = financial_service
        self.gemini_service = gemini_service

        logger.info("✅ Deal Evaluator service initialized")

    # ========== AIRCRAFT DATA ==========

    def get_aircraft_data(self) -> Dict[str, Any]:
        """
        Fetch aircraft defaults from database, fallback to static defaults.

        Returns:
            Dictionary of aircraft types with residual_base, half_life, new_price
        """
        if self.db_service:
            try:
                db_data = self.db_service.get_aircraft_defaults()
                if db_data:
                    logger.info(f"📊 Loaded {len(db_data)} aircraft types from database")
                    return db_data
            except Exception as e:
                logger.warning(f"⚠️ Could not load aircraft defaults from database: {e}")

        logger.info("📊 Using default aircraft data")
        return DEFAULT_AIRCRAFT_DATA

    def get_aircraft_types_list(self) -> List[Dict[str, Any]]:
        """
        Get list of aircraft types with their valuation data.

        Returns:
            List of dicts with type, residual_base, half_life, new_price
        """
        aircraft_data = self.get_aircraft_data()
        return [
            {
                'type': aircraft_type,
                'residual_base': data['residual_base'],
                'half_life': data['half_life'],
                'new_price': data['new_price']
            }
            for aircraft_type, data in aircraft_data.items()
        ]

    # ========== CREDIT & HURDLE RATES ==========

    def calculate_hurdle_rate(self, credit_tier: str) -> Dict[str, Any]:
        """
        Calculate hurdle rate dynamically from FRED data.

        Formula: hurdle = treasury_rate + tier_spread + market_adjustment

        Args:
            credit_tier: Credit tier string (e.g., "BBB/BBB-")

        Returns:
            Dictionary with hurdle_rate and components
        """
        # Get live FRED data
        fred_data = None
        treasury_rate = 4.5  # Fallback
        market_spread_bps = 150  # Fallback

        if self.fred_service:
            try:
                fred_result = self.fred_service.get_real_credit_spreads()
                if fred_result and fred_result.get('success'):
                    fred_data = fred_result.get('data', {})
                    treasury_rate = fred_data.get('treasury_yield_pct', 4.5)
                    market_spread_bps = fred_data.get('credit_spread_bps', 150)
                    logger.info(f"📈 FRED data: Treasury={treasury_rate}%, Market spread={market_spread_bps}bps")
            except Exception as e:
                logger.warning(f"⚠️ Could not fetch FRED data: {e}")

        # Get tier spread
        tier_info = TIER_SPREADS.get(credit_tier, TIER_SPREADS["BBB/BBB-"])
        tier_spread_bps = tier_info['spread_bps']

        # Calculate market adjustment based on current conditions
        if market_spread_bps < 100:
            market_adj = -0.25  # Tight spreads = lower hurdle
            market_condition = "tight"
        elif market_spread_bps > 200:
            market_adj = 0.50  # Wide spreads = higher hurdle
            market_condition = "wide"
        else:
            market_adj = 0.0
            market_condition = "normal"

        # Calculate final hurdle rate
        hurdle = treasury_rate + (tier_spread_bps / 100) + market_adj

        return {
            'hurdle_rate': round(hurdle, 2),
            'treasury_rate': round(treasury_rate, 2),
            'tier_spread_bps': tier_spread_bps,
            'market_adjustment': market_adj,
            'market_spread_bps': market_spread_bps,
            'market_condition': market_condition,
            'data_source': 'FRED' if fred_data else 'fallback'
        }

    def get_credit_tiers_with_hurdles(self) -> List[Dict[str, Any]]:
        """
        Get all credit tiers with live FRED-adjusted hurdle rates.

        Returns:
            List of credit tier dicts with dynamic hurdle rates
        """
        # Get current FRED data once
        fred_data = None
        treasury_rate = 4.5
        market_spread_bps = 150

        if self.fred_service:
            try:
                fred_result = self.fred_service.get_real_credit_spreads()
                if fred_result and fred_result.get('success'):
                    fred_data = fred_result.get('data', {})
                    treasury_rate = fred_data.get('treasury_yield_pct', 4.5)
                    market_spread_bps = fred_data.get('credit_spread_bps', 150)
            except Exception as e:
                logger.warning(f"⚠️ Could not fetch FRED data: {e}")

        # Calculate market adjustment
        if market_spread_bps < 100:
            market_adj = -0.25
            market_condition = "tight"
        elif market_spread_bps > 200:
            market_adj = 0.50
            market_condition = "wide"
        else:
            market_adj = 0.0
            market_condition = "normal"

        tiers = []
        for tier_name, tier_info in TIER_SPREADS.items():
            hurdle = treasury_rate + (tier_info['spread_bps'] / 100) + market_adj
            tiers.append({
                'tier': tier_name,
                'label': tier_info['label'],
                'color': tier_info['color'],
                'spread_bps': tier_info['spread_bps'],
                'hurdle_rate': round(hurdle, 2),
                'treasury_rate': round(treasury_rate, 2),
                'market_adjustment': market_adj,
                'market_condition': market_condition,
                'data_source': 'FRED' if fred_data else 'fallback'
            })

        return tiers

    def auto_detect_credit_tier(self, lessee_name: str) -> Dict[str, Any]:
        """
        Auto-detect credit tier from airline financials using Yahoo Finance.

        Args:
            lessee_name: Name of the airline (e.g., "United Airlines")

        Returns:
            Dictionary with suggested tier, confidence, and financial metrics
        """
        if not self.financial_service:
            return {
                'tier': None,
                'reason': 'Financial service not available',
                'data_source': None
            }

        try:
            balance_sheet = self.financial_service.get_balance_sheet_data(lessee_name)
            if not balance_sheet:
                return {
                    'tier': None,
                    'reason': f'No financial data found for {lessee_name}',
                    'data_source': None
                }

            d_to_ebitda = balance_sheet.get('debt_to_ebitda')
            int_coverage = balance_sheet.get('interest_coverage')

            if d_to_ebitda is None or int_coverage is None:
                return {
                    'tier': None,
                    'reason': 'Insufficient financial metrics for rating',
                    'debt_to_ebitda': d_to_ebitda,
                    'interest_coverage': int_coverage,
                    'data_source': 'yahoo_finance'
                }

            # Use financial service's rating estimation
            rating = self.financial_service.estimate_credit_rating(d_to_ebitda, int_coverage)
            estimated_rating = rating.get('estimated_rating', 'N/A')

            # Map to our tier
            tier = RATING_TO_TIER.get(estimated_rating)

            return {
                'tier': tier,
                'rating': estimated_rating,
                'confidence': rating.get('confidence', 'low'),
                'outlook': rating.get('rating_outlook', ''),
                'debt_to_ebitda': d_to_ebitda,
                'interest_coverage': int_coverage,
                'ticker': balance_sheet.get('ticker'),
                'data_source': 'yahoo_finance'
            }

        except Exception as e:
            logger.error(f"❌ Error detecting credit tier for {lessee_name}: {e}")
            return {
                'tier': None,
                'reason': str(e),
                'data_source': None
            }

    # ========== DCF CALCULATIONS ==========

    def estimate_residual(
        self,
        aircraft_type: str,
        current_age: float,
        lease_term: int
    ) -> Dict[str, Any]:
        """
        Estimate residual value using half-life depreciation model.

        Formula: residual = base * exp(-0.693 * age_at_end / half_life)

        Args:
            aircraft_type: Aircraft type (e.g., "A320neo")
            current_age: Current aircraft age in years
            lease_term: Lease term in years

        Returns:
            Dictionary with residual value and calculation details
        """
        aircraft_data = self.get_aircraft_data()

        if aircraft_type not in aircraft_data:
            raise ValueError(f"Unknown aircraft type: {aircraft_type}")

        info = aircraft_data[aircraft_type]
        age_at_end = current_age + lease_term

        # Half-life depreciation formula
        residual = info['residual_base'] * math.exp(-0.693 * age_at_end / info['half_life'])

        return {
            'residual_value': round(residual),
            'age_at_end': age_at_end,
            'half_life': info['half_life'],
            'residual_base': info['residual_base'],
            'depreciation_factor': round(math.exp(-0.693 * age_at_end / info['half_life']), 4)
        }

    def build_cash_flows(self, params: Dict[str, Any]) -> List[float]:
        """
        Build monthly cash flow array for DCF analysis.

        Cash flows:
        - Month 0: -purchase_price (outflow)
        - Months 1 to term*12: +monthly_rent (with annual step-up) + maintenance_reserve
        - Month term*12: +residual_value - transition_cost

        Args:
            params: Dictionary with purchase_price, monthly_rent, step_up_pct,
                   maintenance_reserve, lease_term, residual_value, transition_cost

        Returns:
            List of monthly cash flows
        """
        purchase_price = params.get('purchase_price', 0)
        monthly_rent = params.get('monthly_rent', 0)
        step_up_pct = params.get('step_up_pct', 0) / 100  # Convert to decimal
        maintenance_reserve = params.get('maintenance_reserve', 0)
        lease_term_years = params.get('lease_term', 8)
        residual_value = params.get('residual_value', 0)
        transition_cost = params.get('transition_cost', 0)

        total_months = lease_term_years * 12
        flows = [-purchase_price]  # Initial outflow

        current_rent = monthly_rent

        for month in range(1, total_months + 1):
            # Apply annual step-up at beginning of each year (after year 1)
            if month > 12 and (month - 1) % 12 == 0:
                current_rent *= (1 + step_up_pct)

            # Monthly inflow: rent + maintenance reserve
            monthly_inflow = current_rent + maintenance_reserve

            # Add residual and deduct transition cost at end
            if month == total_months:
                monthly_inflow += residual_value - transition_cost

            flows.append(monthly_inflow)

        return flows

    def calc_npv(self, flows: List[float], annual_rate: float) -> float:
        """
        Calculate NPV using monthly discounting.

        Args:
            flows: List of monthly cash flows
            annual_rate: Annual discount rate (decimal, e.g., 0.085 for 8.5%)

        Returns:
            Net Present Value
        """
        if annual_rate <= -1:
            return float('inf')

        monthly_rate = (1 + annual_rate) ** (1/12) - 1

        npv = sum(cf / ((1 + monthly_rate) ** i) for i, cf in enumerate(flows))

        return npv

    def calc_irr(self, flows: List[float], guess: float = 0.1) -> Optional[float]:
        """
        Calculate IRR using Newton-Raphson iteration.

        Args:
            flows: List of monthly cash flows
            guess: Initial guess for annual rate (default 10%)

        Returns:
            Annual IRR as decimal (e.g., 0.092 for 9.2%), or None if not converged
        """
        rate = guess
        max_iterations = 200
        tolerance = 1e-8

        for i in range(max_iterations):
            npv = self.calc_npv(flows, rate)

            # Calculate derivative numerically
            d_rate = rate * 0.0001 if abs(rate) > 0.0001 else 0.0001
            npv2 = self.calc_npv(flows, rate + d_rate)
            deriv = (npv2 - npv) / d_rate

            if abs(deriv) < 1e-12:
                break

            new_rate = rate - npv / deriv

            if abs(new_rate - rate) < tolerance:
                return new_rate

            rate = new_rate

        # Return last rate even if not fully converged
        return rate

    def solve_for_price(self, params: Dict[str, Any], target_irr: float) -> float:
        """
        Binary search for purchase price that yields target IRR.

        Args:
            params: Deal parameters (without purchase_price)
            target_irr: Target IRR as decimal (e.g., 0.085 for 8.5%)

        Returns:
            Maximum purchase price that achieves target IRR
        """
        lo = 1_000_000
        hi = 500_000_000
        max_iterations = 50

        for _ in range(max_iterations):
            mid = (lo + hi) / 2
            test_params = {**params, 'purchase_price': mid}
            flows = self.build_cash_flows(test_params)
            irr = self.calc_irr(flows)

            if irr is None:
                hi = mid
            elif irr > target_irr:
                lo = mid
            else:
                hi = mid

        return round((lo + hi) / 2)

    def calc_breakeven_residual(self, params: Dict[str, Any], hurdle_rate: float) -> float:
        """
        Calculate breakeven residual value (where NPV = 0 at hurdle rate).

        Args:
            params: Deal parameters
            hurdle_rate: Hurdle rate as decimal

        Returns:
            Breakeven residual value
        """
        lo = 0
        hi = params.get('purchase_price', 50_000_000) * 2
        max_iterations = 50

        for _ in range(max_iterations):
            mid = (lo + hi) / 2
            test_params = {**params, 'residual_value': mid}
            flows = self.build_cash_flows(test_params)
            npv = self.calc_npv(flows, hurdle_rate)

            if npv > 0:
                hi = mid
            else:
                lo = mid

        return round((lo + hi) / 2)

    def build_sensitivity_matrix(
        self,
        params: Dict[str, Any],
        base_hurdle: float,
        mode: str = 'evaluate'
    ) -> List[List[Dict[str, Any]]]:
        """
        Build 5x5 sensitivity matrix varying residual and discount rate.

        Residual deltas: -20%, -10%, 0%, +10%, +20%
        Rate deltas: -2%, -1%, 0%, +1%, +2%

        Args:
            params: Deal parameters
            base_hurdle: Base hurdle rate for comparison
            mode: 'evaluate' (outputs IRR) or 'price' (outputs max price)

        Returns:
            5x5 matrix of results
        """
        residual_deltas = [-0.20, -0.10, 0, 0.10, 0.20]
        rate_deltas = [-0.02, -0.01, 0, 0.01, 0.02]

        base_residual = params.get('residual_value', 0)
        target_irr = params.get('target_irr', base_hurdle)

        matrix = []

        for rate_delta in rate_deltas:
            row = []
            for residual_delta in residual_deltas:
                adjusted_residual = base_residual * (1 + residual_delta)
                adjusted_rate = (target_irr if mode == 'price' else base_hurdle) + rate_delta

                test_params = {**params, 'residual_value': adjusted_residual}

                if mode == 'evaluate':
                    flows = self.build_cash_flows(test_params)
                    irr = self.calc_irr(flows)
                    passes = irr is not None and irr >= adjusted_rate

                    row.append({
                        'irr': round(irr, 4) if irr else None,
                        'hurdle': round(adjusted_rate, 4),
                        'pass': passes,
                        'residual_delta': residual_delta,
                        'rate_delta': rate_delta
                    })
                else:  # price mode
                    max_price = self.solve_for_price(test_params, adjusted_rate)
                    row.append({
                        'price': max_price,
                        'target_irr': round(adjusted_rate, 4),
                        'residual_delta': residual_delta,
                        'rate_delta': rate_delta
                    })

            matrix.append(row)

        return matrix

    # ========== MAIN EVALUATION FUNCTIONS ==========

    def evaluate_deal(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate a deal - calculate IRR, NPV, verdict, sensitivity.

        Args:
            params: Dictionary with:
                - aircraft_type: str
                - current_age: float
                - lease_term: int
                - monthly_rent: float
                - step_up_pct: float (optional, default 0)
                - maintenance_reserve: float (optional, default 0)
                - transition_cost: float (optional, default 0)
                - purchase_price: float
                - residual_value: float (optional, auto-calculated if not provided)
                - credit_tier: str
                - lessee_name: str (optional)

        Returns:
            Evaluation results with IRR, NPV, verdict, sensitivity matrix
        """
        start_time = datetime.now()

        # Get aircraft data
        aircraft_type = params.get('aircraft_type')
        current_age = params.get('current_age', 0)
        lease_term = params.get('lease_term', 8)
        credit_tier = params.get('credit_tier', 'BBB/BBB-')

        # Calculate residual if not provided
        if not params.get('residual_value'):
            residual_info = self.estimate_residual(aircraft_type, current_age, lease_term)
            params['residual_value'] = residual_info['residual_value']

        # Get dynamic hurdle rate
        hurdle_info = self.calculate_hurdle_rate(credit_tier)
        hurdle_rate = hurdle_info['hurdle_rate'] / 100  # Convert to decimal

        # Build cash flows and calculate metrics
        flows = self.build_cash_flows(params)
        irr = self.calc_irr(flows)
        npv = self.calc_npv(flows, hurdle_rate)

        # Determine verdict
        passes = irr is not None and irr >= hurdle_rate
        verdict = 'PASS' if passes else 'FAIL'

        # Calculate breakeven residual
        breakeven_residual = self.calc_breakeven_residual(params, hurdle_rate)

        # Build sensitivity matrix
        sensitivity_matrix = self.build_sensitivity_matrix(params, hurdle_rate, 'evaluate')

        # Calculate cash multiple
        total_inflows = sum(f for f in flows[1:])
        purchase_price = params.get('purchase_price', 1)
        cash_multiple = total_inflows / purchase_price if purchase_price > 0 else 0

        calc_time = (datetime.now() - start_time).total_seconds() * 1000

        return {
            'irr': round(irr, 4) if irr else None,
            'irr_pct': round(irr * 100, 2) if irr else None,
            'npv': round(npv),
            'hurdle_rate': hurdle_info['hurdle_rate'],
            'hurdle_components': {
                'treasury_rate': hurdle_info['treasury_rate'],
                'tier_spread_bps': hurdle_info['tier_spread_bps'],
                'market_adjustment': hurdle_info['market_adjustment'],
                'market_condition': hurdle_info['market_condition'],
                'data_source': hurdle_info['data_source']
            },
            'verdict': verdict,
            'passes': passes,
            'breakeven_residual': breakeven_residual,
            'estimated_residual': params['residual_value'],
            'cash_multiple': round(cash_multiple, 2),
            'sensitivity_matrix': sensitivity_matrix,
            'calculation_time_ms': round(calc_time, 1)
        }

    def price_deal(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Price a deal - solve for max purchase price given target IRR.

        Args:
            params: Dictionary with:
                - aircraft_type: str
                - current_age: float
                - lease_term: int
                - monthly_rent: float
                - step_up_pct: float (optional)
                - maintenance_reserve: float (optional)
                - transition_cost: float (optional)
                - target_irr: float (as percentage, e.g., 8.5)
                - residual_value: float (optional, auto-calculated if not provided)
                - credit_tier: str
                - lessee_name: str (optional)

        Returns:
            Pricing results with max purchase price, sensitivity matrix
        """
        start_time = datetime.now()

        # Get aircraft data
        aircraft_type = params.get('aircraft_type')
        current_age = params.get('current_age', 0)
        lease_term = params.get('lease_term', 8)
        target_irr_pct = params.get('target_irr', 8.5)
        target_irr = target_irr_pct / 100  # Convert to decimal

        # Calculate residual if not provided
        if not params.get('residual_value'):
            residual_info = self.estimate_residual(aircraft_type, current_age, lease_term)
            params['residual_value'] = residual_info['residual_value']

        # Solve for max price
        params['target_irr'] = target_irr
        max_price = self.solve_for_price(params, target_irr)

        # Verify with actual IRR calculation
        verify_params = {**params, 'purchase_price': max_price}
        flows = self.build_cash_flows(verify_params)
        actual_irr = self.calc_irr(flows)

        # Calculate cash multiple
        total_inflows = sum(f for f in flows[1:])
        cash_multiple = total_inflows / max_price if max_price > 0 else 0

        # Build sensitivity matrix for price mode
        sensitivity_matrix = self.build_sensitivity_matrix(params, target_irr, 'price')

        calc_time = (datetime.now() - start_time).total_seconds() * 1000

        return {
            'max_price': max_price,
            'target_irr': target_irr_pct,
            'actual_irr': round(actual_irr * 100, 2) if actual_irr else None,
            'estimated_residual': params['residual_value'],
            'cash_multiple': round(cash_multiple, 2),
            'sensitivity_matrix': sensitivity_matrix,
            'calculation_time_ms': round(calc_time, 1)
        }

    # ========== AI COMMENTARY ==========

    def generate_deal_commentary(
        self,
        params: Dict[str, Any],
        results: Dict[str, Any]
    ) -> Optional[str]:
        """
        Generate AI commentary for deal assessment.

        Args:
            params: Deal parameters
            results: Evaluation/pricing results

        Returns:
            AI-generated commentary string, or None if unavailable
        """
        if not self.gemini_service:
            return None

        try:
            # Get market context from FRED if available
            market_context = ""
            if self.fred_service:
                try:
                    fred_result = self.fred_service.get_real_credit_spreads()
                    if fred_result and fred_result.get('success'):
                        fred_data = fred_result.get('data', {})
                        market_context = f"""
Current Market Context:
- BBB Corporate Spreads: {fred_data.get('credit_spread_bps', 'N/A')} bps
- 10-Year Treasury: {fred_data.get('treasury_yield_pct', 'N/A')}%
- Market Condition: {fred_data.get('spread_description', 'N/A')}
"""
                except Exception:
                    pass

            # Build prompt
            is_price_mode = 'max_price' in results

            if is_price_mode:
                prompt = f"""Generate a brief deal pricing assessment for aircraft leasing:

Deal Parameters:
- Aircraft: {params.get('aircraft_type')}, Age: {params.get('current_age')} years
- Lessee: {params.get('lessee_name', 'Unknown')}, Credit Tier: {params.get('credit_tier')}
- Target IRR: {results.get('target_irr')}%
- Lease Term: {params.get('lease_term')} years
- Monthly Rent: ${params.get('monthly_rent', 0):,.0f}

Calculated Metrics:
- Maximum Purchase Price: ${results.get('max_price', 0):,.0f}
- Estimated Residual: ${results.get('estimated_residual', 0):,.0f}
- Cash Multiple: {results.get('cash_multiple', 0):.2f}x

{market_context}

Provide:
1. One paragraph pricing assessment (2-3 sentences on the deal economics)
2. Key considerations (2-3 bullet points)
3. Recommendation (one sentence)

Keep response under 200 words. Use professional aviation finance terminology."""

            else:
                prompt = f"""Generate a brief deal evaluation assessment for aircraft leasing:

Deal Parameters:
- Aircraft: {params.get('aircraft_type')}, Age: {params.get('current_age')} years
- Lessee: {params.get('lessee_name', 'Unknown')}, Credit Tier: {params.get('credit_tier')}
- Purchase Price: ${params.get('purchase_price', 0):,.0f}
- Lease Term: {params.get('lease_term')} years
- Monthly Rent: ${params.get('monthly_rent', 0):,.0f}

Calculated Metrics:
- Implied IRR: {results.get('irr_pct', 0):.1f}%
- Hurdle Rate: {results.get('hurdle_rate', 0):.1f}%
- NPV at Hurdle: ${results.get('npv', 0):,.0f}
- Verdict: {results.get('verdict')}
- Breakeven Residual: ${results.get('breakeven_residual', 0):,.0f}

{market_context}

Provide:
1. One paragraph deal assessment (2-3 sentences on whether this is attractive)
2. Key risk factors (2-3 bullet points)
3. Recommendation (one sentence)

Keep response under 200 words. Use professional aviation finance terminology."""

            # Call Gemini
            response = self.gemini_service.generate_content(prompt, temperature=0.4)
            return response

        except Exception as e:
            logger.error(f"❌ Error generating deal commentary: {e}")
            return None
