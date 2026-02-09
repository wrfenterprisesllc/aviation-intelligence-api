#!/usr/bin/env python3
"""
XBRL Service - SEC EDGAR XBRL API Integration
Fetches structured financial data from SEC EDGAR for airline credit analysis.

Uses the SEC EDGAR Company Facts API:
https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json
"""

import logging
import requests
import time
from datetime import datetime
from typing import Dict, Optional, Any, List
from app.utils.retry import make_request_with_retry

logger = logging.getLogger(__name__)


class XBRLService:
    """Service for fetching SEC XBRL financial data"""

    # CIK lookup for 8 airlines
    AIRLINE_CIKS = {
        'DAL': '0000027904',   # Delta Air Lines
        'UAL': '0000100517',   # United Airlines Holdings
        'AAL': '0000006201',   # American Airlines Group
        'LUV': '0000092380',   # Southwest Airlines
        'JBLU': '0000898293',  # JetBlue Airways
        'ALK': '0000766421',   # Alaska Air Group
        'SAVE': '0001498710',  # Spirit Airlines
        'ULCC': '0001901231',  # Frontier Group Holdings
    }

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

    # Alternative XBRL tags to try for each concept
    XBRL_ALTERNATIVES = {
        'total_debt': [
            'LongTermDebt',
            'LongTermDebtNoncurrent',
            'DebtLongtermAndShorttermCombinedAmount',
            'LongTermDebtAndCapitalLeaseObligations',
        ],
        'current_debt': [
            'LongTermDebtCurrent',
            'DebtCurrent',
            'ShortTermBorrowings',
        ],
        'equity': [
            'StockholdersEquity',
            'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest',
        ],
        'revenue': [
            'Revenues',
            'RevenueFromContractWithCustomerExcludingAssessedTax',
            'SalesRevenueNet',
        ],
        'operating_income': [
            'OperatingIncomeLoss',
            'IncomeLossFromContinuingOperationsBeforeInterestExpenseInterestIncomeIncomeTaxesExtraordinaryItemsNoncontrollingInterestsNet',
        ],
        'interest_expense': [
            'InterestExpense',
            'InterestExpenseDebt',
            'InterestAndDebtExpense',
        ],
        'depreciation': [
            'DepreciationAndAmortization',
            'DepreciationDepletionAndAmortization',
            'Depreciation',
        ],
        'current_assets': [
            'AssetsCurrent',
        ],
        'current_liabilities': [
            'LiabilitiesCurrent',
        ],
        'cash': [
            'CashAndCashEquivalentsAtCarryingValue',
            'CashCashEquivalentsAndShortTermInvestments',
            'Cash',
        ],
        'operating_expenses': [
            'OperatingExpenses',
            'CostsAndExpenses',
        ],
    }

    def __init__(self, user_agent: str = None):
        """
        Initialize XBRL service with SEC-required headers.

        Args:
            user_agent: SEC requires valid User-Agent with contact email
        """
        self.user_agent = user_agent or 'Aviation-Intelligence-Platform/1.0 (admin@wrfenterprisesllc.com)'
        self.base_url = "https://data.sec.gov/api/xbrl/companyfacts"
        self.request_delay = 0.11  # 10 req/sec limit
        self.last_request_time = 0

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.user_agent,
            'Accept': 'application/json',
        })

        logger.info("✅ XBRL service initialized")

    def _rate_limit(self):
        """Implement SEC rate limiting (10 requests/second max)."""
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        self.last_request_time = time.time()

    def get_company_facts(self, airline_code: str) -> Optional[Dict[str, Any]]:
        """
        Fetch all XBRL facts for a company from SEC EDGAR.

        Args:
            airline_code: Ticker symbol (e.g., 'DAL')

        Returns:
            Raw XBRL company facts JSON or None on error
        """
        cik = self.AIRLINE_CIKS.get(airline_code.upper())
        if not cik:
            logger.warning(f"⚠️ Unknown airline code: {airline_code}")
            return None

        try:
            self._rate_limit()

            # SEC expects CIK with leading zeros, 10 digits total
            clean_cik = str(int(cik)).zfill(10)
            url = f"{self.base_url}/CIK{clean_cik}.json"

            logger.info(f"📊 Fetching XBRL data for {airline_code} from SEC EDGAR...")
            response = make_request_with_retry(
                url,
                method='GET',
                timeout=30,
                max_retries=3,
                headers=dict(self.session.headers)
            )
            response.raise_for_status()

            data = response.json()
            logger.info(f"✅ Retrieved XBRL data for {airline_code}")
            return data

        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ HTTP error fetching XBRL for {airline_code}: {e}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Request error fetching XBRL for {airline_code}: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Error fetching XBRL for {airline_code}: {e}")
            return None

    def _extract_value(
        self,
        us_gaap: Dict,
        concept_alternatives: List[str],
        as_of_date: Optional[str] = None,
        prefer_annual: bool = True
    ) -> Optional[float]:
        """
        Extract the most recent value for a GAAP concept, trying alternatives.

        Args:
            us_gaap: US-GAAP facts dictionary
            concept_alternatives: List of XBRL tag names to try
            as_of_date: Optional date filter for backtesting (YYYY-MM-DD)
            prefer_annual: If True, prefer 10-K over 10-Q filings

        Returns:
            Most recent value or None
        """
        for concept in concept_alternatives:
            concept_data = us_gaap.get(concept, {})
            units = concept_data.get('units', {})

            # Try USD units first, then pure (for ratios)
            usd_values = units.get('USD', [])

            if not usd_values:
                continue

            # Filter and sort by end date
            valid_values = []
            for entry in usd_values:
                form = entry.get('form', '')
                # Accept 10-K, 10-Q, and their amendments
                if form not in ['10-K', '10-Q', '10-K/A', '10-Q/A']:
                    continue

                end_date = entry.get('end', '')
                filed_date = entry.get('filed', '')

                # Filter by as_of_date if provided (use filed date for backtesting)
                if as_of_date and filed_date > as_of_date:
                    continue

                valid_values.append({
                    'value': entry.get('val'),
                    'end': end_date,
                    'filed': filed_date,
                    'form': form,
                    'is_annual': form in ['10-K', '10-K/A']
                })

            if not valid_values:
                continue

            # Sort by end date descending, prefer annual if specified
            if prefer_annual:
                # Sort by: is_annual (True first), then end date descending
                valid_values.sort(key=lambda x: (not x['is_annual'], x['end']), reverse=True)
                valid_values.sort(key=lambda x: x['is_annual'], reverse=True)
            else:
                valid_values.sort(key=lambda x: x['end'], reverse=True)

            # Return most recent valid value
            if valid_values and valid_values[0]['value'] is not None:
                return float(valid_values[0]['value'])

        return None

    def get_financial_metrics(
        self,
        airline_code: str,
        as_of_date: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Extract credit-relevant financial metrics from XBRL data.

        Args:
            airline_code: Ticker symbol
            as_of_date: Optional date for backtesting (YYYY-MM-DD format)

        Returns:
            Dict with financial metrics or None on error
        """
        facts = self.get_company_facts(airline_code)
        if not facts:
            return None

        try:
            us_gaap = facts.get('facts', {}).get('us-gaap', {})

            if not us_gaap:
                logger.warning(f"⚠️ No US-GAAP data found for {airline_code}")
                return None

            # Extract raw values using alternative tags
            total_debt = self._extract_value(us_gaap, self.XBRL_ALTERNATIVES['total_debt'], as_of_date)
            current_debt = self._extract_value(us_gaap, self.XBRL_ALTERNATIVES['current_debt'], as_of_date)
            equity = self._extract_value(us_gaap, self.XBRL_ALTERNATIVES['equity'], as_of_date)
            revenue = self._extract_value(us_gaap, self.XBRL_ALTERNATIVES['revenue'], as_of_date)
            operating_income = self._extract_value(us_gaap, self.XBRL_ALTERNATIVES['operating_income'], as_of_date)
            interest_expense = self._extract_value(us_gaap, self.XBRL_ALTERNATIVES['interest_expense'], as_of_date)
            depreciation = self._extract_value(us_gaap, self.XBRL_ALTERNATIVES['depreciation'], as_of_date)
            current_assets = self._extract_value(us_gaap, self.XBRL_ALTERNATIVES['current_assets'], as_of_date)
            current_liabilities = self._extract_value(us_gaap, self.XBRL_ALTERNATIVES['current_liabilities'], as_of_date)
            cash = self._extract_value(us_gaap, self.XBRL_ALTERNATIVES['cash'], as_of_date)
            operating_expenses = self._extract_value(us_gaap, self.XBRL_ALTERNATIVES['operating_expenses'], as_of_date)

            # Combine long-term and current debt if both available
            if total_debt is not None and current_debt is not None:
                combined_debt = total_debt + current_debt
            elif total_debt is not None:
                combined_debt = total_debt
            elif current_debt is not None:
                combined_debt = current_debt
            else:
                combined_debt = None

            metrics = {
                'airline_code': airline_code.upper(),
                'airline_name': self.AIRLINE_NAMES.get(airline_code.upper()),
                'as_of_date': as_of_date or datetime.now().strftime('%Y-%m-%d'),

                # Raw values (in dollars)
                'total_debt': combined_debt,
                'stockholders_equity': equity,
                'current_assets': current_assets,
                'current_liabilities': current_liabilities,
                'cash': cash,
                'operating_income': operating_income,
                'interest_expense': interest_expense,
                'revenue': revenue,
                'depreciation': depreciation,
                'operating_expenses': operating_expenses,

                # Metadata
                'data_source': 'sec_xbrl',
                'fetched_at': datetime.utcnow().isoformat()
            }

            # Calculate derived ratios
            if equity and combined_debt and equity != 0:
                metrics['debt_to_equity'] = round(combined_debt / equity, 2)

            if interest_expense and operating_income and interest_expense != 0:
                # Use absolute value of interest expense (it's typically negative)
                metrics['interest_coverage'] = round(operating_income / abs(interest_expense), 2)

            if current_assets and current_liabilities and current_liabilities != 0:
                metrics['current_ratio'] = round(current_assets / current_liabilities, 2)

            if revenue and operating_income and revenue != 0:
                metrics['operating_margin'] = round((operating_income / revenue) * 100, 2)

            # EBITDAR approximation for airlines
            # EBITDAR = Operating Income + Depreciation + Aircraft Rent
            # Estimate aircraft rent as ~8% of revenue for airlines
            if operating_income is not None and depreciation is not None:
                estimated_rent = (revenue or 0) * 0.08
                metrics['ebitdar'] = operating_income + depreciation + estimated_rent

            # Monthly cash burn rate (operating expenses / 12)
            if operating_expenses:
                metrics['monthly_burn_rate'] = round(operating_expenses / 12, 0)

            # Log what we found
            found_metrics = [k for k, v in metrics.items() if v is not None and k not in ['airline_code', 'airline_name', 'as_of_date', 'data_source', 'fetched_at']]
            logger.info(f"📊 Extracted {len(found_metrics)} XBRL metrics for {airline_code}")

            return metrics

        except Exception as e:
            logger.error(f"❌ Error extracting XBRL metrics for {airline_code}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def calculate_financial_score(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate 0-100 financial score from XBRL metrics.

        Scoring bands based on airline industry benchmarks:
        - D/E: <2.0 excellent (90+), 2-3 good (70-89), 3-5 fair (50-69), >5 poor (<50)
        - Interest Coverage: >4 excellent, 2-4 good, 1-2 fair, <1 poor
        - Operating Margin: >12% excellent, 8-12% good, 4-8% fair, <4% poor
        - Current Ratio: >1.2 excellent, 0.9-1.2 good, 0.7-0.9 fair, <0.7 poor

        Args:
            metrics: Dictionary of financial metrics from get_financial_metrics()

        Returns:
            Dict with financial_score (0-100) and sub_scores breakdown
        """
        if not metrics:
            return {
                'financial_score': 50.0,
                'sub_scores': {},
                'metrics_used': {},
                'reason': 'No metrics provided'
            }

        sub_scores = {}
        weights = {
            'debt_equity': 0.30,
            'interest_coverage': 0.25,
            'operating_margin': 0.25,
            'current_ratio': 0.20
        }

        # Debt-to-Equity Score (30%)
        de = metrics.get('debt_to_equity')
        if de is not None:
            if de < 0:
                # Negative equity is very bad
                sub_scores['debt_equity'] = 10
            elif de < 1.5:
                sub_scores['debt_equity'] = 95
            elif de < 2.0:
                sub_scores['debt_equity'] = 85 + (2.0 - de) * 20
            elif de < 3.0:
                sub_scores['debt_equity'] = 70 + (3.0 - de) * 15
            elif de < 5.0:
                sub_scores['debt_equity'] = 50 + (5.0 - de) * 10
            else:
                sub_scores['debt_equity'] = max(15, 50 - (de - 5.0) * 5)

        # Interest Coverage Score (25%)
        ic = metrics.get('interest_coverage')
        if ic is not None:
            if ic < 0:
                # Negative coverage means operating losses
                sub_scores['interest_coverage'] = 10
            elif ic > 6.0:
                sub_scores['interest_coverage'] = 95
            elif ic > 4.0:
                sub_scores['interest_coverage'] = 85 + (ic - 4.0) * 5
            elif ic > 2.0:
                sub_scores['interest_coverage'] = 70 + (ic - 2.0) * 7.5
            elif ic > 1.0:
                sub_scores['interest_coverage'] = 50 + (ic - 1.0) * 20
            else:
                sub_scores['interest_coverage'] = max(10, ic * 50)

        # Operating Margin Score (25%)
        om = metrics.get('operating_margin')
        if om is not None:
            if om < 0:
                # Negative margin
                sub_scores['operating_margin'] = max(5, 30 + om)  # Gets worse as more negative
            elif om > 15:
                sub_scores['operating_margin'] = 95
            elif om > 12:
                sub_scores['operating_margin'] = 85 + (om - 12) * 3.33
            elif om > 8:
                sub_scores['operating_margin'] = 70 + (om - 8) * 3.75
            elif om > 4:
                sub_scores['operating_margin'] = 50 + (om - 4) * 5
            else:
                sub_scores['operating_margin'] = max(20, om * 12.5)

        # Current Ratio Score (20%)
        cr = metrics.get('current_ratio')
        if cr is not None:
            if cr > 1.5:
                sub_scores['current_ratio'] = 95
            elif cr > 1.2:
                sub_scores['current_ratio'] = 85 + (cr - 1.2) * 33.33
            elif cr > 0.9:
                sub_scores['current_ratio'] = 70 + (cr - 0.9) * 50
            elif cr > 0.7:
                sub_scores['current_ratio'] = 50 + (cr - 0.7) * 100
            else:
                sub_scores['current_ratio'] = max(20, cr * 71.4)

        # Calculate weighted average
        total_weight = sum(weights[k] for k in sub_scores.keys())
        if total_weight > 0:
            weighted_score = sum(sub_scores[k] * weights[k] for k in sub_scores.keys()) / total_weight
        else:
            weighted_score = 50  # Default if no metrics available

        return {
            'financial_score': round(weighted_score, 1),
            'sub_scores': {k: round(v, 1) for k, v in sub_scores.items()},
            'metrics_used': {
                'debt_to_equity': metrics.get('debt_to_equity'),
                'interest_coverage': metrics.get('interest_coverage'),
                'operating_margin': metrics.get('operating_margin'),
                'current_ratio': metrics.get('current_ratio'),
                'cash_millions': round(metrics.get('cash', 0) / 1_000_000, 1) if metrics.get('cash') else None,
                'total_debt_millions': round(metrics.get('total_debt', 0) / 1_000_000, 1) if metrics.get('total_debt') else None,
            },
            'weights': weights,
            'data_gaps': [k for k in weights.keys() if k not in sub_scores]
        }
