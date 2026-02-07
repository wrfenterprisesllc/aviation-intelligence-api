#!/usr/bin/env python3
"""
Financial Data Service - Comprehensive airline financial metrics
Combines Yahoo Finance balance sheet/cash flow data with BTS operational data

Provides:
- Balance Sheet: Total Debt, Net Debt, Cash, Equity
- Income Statement: EBITDA, Interest Expense
- Cash Flow: Free Cash Flow, Operating Cash Flow
- Credit Metrics: Debt-to-EBITDA, Interest Coverage, Liquidity Ratios
"""

import logging
from datetime import datetime
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)

# Import yfinance - if not available, service will gracefully degrade
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
    logger.info("✅ yfinance imported successfully")
except ImportError as e:
    YFINANCE_AVAILABLE = False
    logger.warning(f"yfinance not available - balance sheet data will be limited: {e}")


class FinancialDataService:
    """Service for fetching comprehensive airline financial data"""

    # Ticker symbols for major airlines
    AIRLINE_TICKERS = {
        'United Airlines': 'UAL',
        'Delta Air Lines': 'DAL',
        'American Airlines': 'AAL',
        'Southwest Airlines': 'LUV',
        'JetBlue Airways': 'JBLU',
        'Alaska Airlines': 'ALK',
        'Spirit Airlines': 'SAVE',
        'Allegiant Air': 'ALGT',
        'Hawaiian Airlines': 'HA',
        'Frontier Airlines': 'ULCC'
    }

    def __init__(self, bts_service=None):
        """
        Initialize financial data service

        Args:
            bts_service: Optional BTSService for operational data
        """
        self.bts_service = bts_service
        logger.info(f"✅ Financial data service initialized (yfinance: {YFINANCE_AVAILABLE})")

    def get_ticker(self, airline_name: str) -> Optional[str]:
        """Get ticker symbol from airline name"""
        # Exact match
        if airline_name in self.AIRLINE_TICKERS:
            return self.AIRLINE_TICKERS[airline_name]

        # Partial match
        for name, ticker in self.AIRLINE_TICKERS.items():
            if airline_name.lower() in name.lower() or name.lower() in airline_name.lower():
                return ticker

        return None

    def get_balance_sheet_data(self, airline_name: str) -> Optional[Dict[str, Any]]:
        """
        Fetch balance sheet and financial health metrics for an airline

        Args:
            airline_name: Airline name (e.g., 'United Airlines')

        Returns:
            Dictionary with balance sheet metrics or None if unavailable
        """
        if not YFINANCE_AVAILABLE:
            logger.warning("yfinance not available for balance sheet data")
            return None

        ticker_symbol = self.get_ticker(airline_name)
        if not ticker_symbol:
            logger.warning(f"No ticker found for: {airline_name}")
            return None

        try:
            logger.info(f"📊 Fetching balance sheet for {airline_name} ({ticker_symbol})")

            ticker = yf.Ticker(ticker_symbol)
            logger.info(f"📊 Created yfinance Ticker object for {ticker_symbol}")

            # Get financial statements
            logger.info(f"📊 Fetching balance_sheet...")
            balance_sheet = ticker.balance_sheet
            logger.info(f"📊 balance_sheet type: {type(balance_sheet)}, empty: {balance_sheet is None or (hasattr(balance_sheet, 'empty') and balance_sheet.empty)}")

            logger.info(f"📊 Fetching income_stmt...")
            income_stmt = ticker.income_stmt
            logger.info(f"📊 Fetching cashflow...")
            cash_flow = ticker.cashflow

            if balance_sheet is None or balance_sheet.empty:
                logger.warning(f"No balance sheet data for {ticker_symbol} - balance_sheet is None or empty")
                return None

            logger.info(f"📊 Balance sheet columns: {list(balance_sheet.columns)[:3] if hasattr(balance_sheet, 'columns') else 'N/A'}")

            # Get most recent period (usually latest fiscal year)
            latest_period = balance_sheet.columns[0]
            period_str = str(latest_period)[:10]

            # Extract balance sheet metrics
            def safe_get(df, key, default=None):
                """Safely get value from DataFrame"""
                try:
                    if df is not None and not df.empty and key in df.index:
                        val = df.loc[key, df.columns[0]]
                        return float(val) if val is not None else default
                except Exception:
                    pass
                return default

            # Balance Sheet items
            total_debt = safe_get(balance_sheet, 'Total Debt', 0)
            net_debt = safe_get(balance_sheet, 'Net Debt', 0)
            cash = safe_get(balance_sheet, 'Cash And Cash Equivalents')
            if cash is None:
                # Try alternative field
                cash = safe_get(balance_sheet, 'Cash Cash Equivalents And Short Term Investments', 0)
            stockholders_equity = safe_get(balance_sheet, 'Stockholders Equity', 0)
            working_capital = safe_get(balance_sheet, 'Working Capital', 0)
            total_assets = safe_get(balance_sheet, 'Total Assets', 0)

            # Income Statement items
            ebitda = safe_get(income_stmt, 'EBITDA', 0)
            ebit = safe_get(income_stmt, 'EBIT', 0)
            interest_expense = safe_get(income_stmt, 'Interest Expense', 0)
            net_income = safe_get(income_stmt, 'Net Income', 0)
            operating_income = safe_get(income_stmt, 'Operating Income', 0)
            total_revenue = safe_get(income_stmt, 'Total Revenue', 0)

            # Cash Flow items
            free_cash_flow = safe_get(cash_flow, 'Free Cash Flow', 0)
            operating_cash_flow = safe_get(cash_flow, 'Operating Cash Flow')
            if operating_cash_flow is None:
                operating_cash_flow = safe_get(cash_flow, 'Cash Flow From Continuing Operating Activities', 0)

            # Calculate credit metrics
            debt_to_ebitda = None
            if ebitda and ebitda > 0 and total_debt:
                debt_to_ebitda = round(total_debt / ebitda, 2)

            interest_coverage = None
            if interest_expense and interest_expense > 0 and ebit:
                interest_coverage = round(ebit / abs(interest_expense), 2)

            debt_to_equity = None
            if stockholders_equity and stockholders_equity > 0 and total_debt:
                debt_to_equity = round(total_debt / stockholders_equity, 2)

            current_ratio = None
            if working_capital is not None and total_assets:
                # Estimate current ratio (simplified)
                # Current Ratio = Current Assets / Current Liabilities
                # Working Capital = Current Assets - Current Liabilities
                # We'll estimate by looking at total_assets ratio
                pass  # Would need more data for accurate calculation

            result = {
                'ticker': ticker_symbol,
                'airline_name': airline_name,
                'period': period_str,
                'period_type': 'annual',

                # Balance Sheet
                'total_debt': total_debt,
                'net_debt': net_debt,
                'cash_and_equivalents': cash,
                'stockholders_equity': stockholders_equity,
                'working_capital': working_capital,
                'total_assets': total_assets,

                # Income Statement
                'ebitda': ebitda,
                'ebit': ebit,
                'interest_expense': abs(interest_expense) if interest_expense else 0,
                'net_income': net_income,
                'operating_income': operating_income,
                'total_revenue': total_revenue,

                # Cash Flow
                'free_cash_flow': free_cash_flow,
                'operating_cash_flow': operating_cash_flow,

                # Credit Metrics
                'debt_to_ebitda': debt_to_ebitda,
                'interest_coverage': interest_coverage,
                'debt_to_equity': debt_to_equity,

                # Metadata
                'data_source': 'yahoo_finance',
                'fetched_at': datetime.utcnow().isoformat()
            }

            logger.info(f"✅ Retrieved balance sheet for {ticker_symbol}: "
                       f"Debt={total_debt/1e9:.1f}B, EBITDA={ebitda/1e9:.1f}B, "
                       f"D/E={debt_to_ebitda}x")

            return result

        except Exception as e:
            logger.error(f"❌ Error fetching balance sheet for {airline_name}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def get_comprehensive_financials(self, airline_name: str) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive financial data combining balance sheet with BTS operational data

        Args:
            airline_name: Airline name

        Returns:
            Combined financial data dictionary
        """
        result = {
            'airline_name': airline_name,
            'balance_sheet': None,
            'operational_metrics': None,
            'credit_analysis_ready': False
        }

        # Get balance sheet data from Yahoo Finance
        balance_sheet = self.get_balance_sheet_data(airline_name)
        if balance_sheet:
            result['balance_sheet'] = balance_sheet
            result['ticker'] = balance_sheet.get('ticker')

        # Get operational data from BTS if available
        if self.bts_service:
            carrier_code = self.bts_service.get_carrier_by_name(airline_name)
            if carrier_code:
                bts_data = self.bts_service.get_carrier_financials(carrier_code)
                if bts_data:
                    result['operational_metrics'] = bts_data
                    result['carrier_code'] = carrier_code

        # Mark as ready for credit analysis if we have both data sources
        if result['balance_sheet'] and result['operational_metrics']:
            result['credit_analysis_ready'] = True

        return result

    def estimate_credit_rating(self, debt_to_ebitda: float, interest_coverage: float) -> dict:
        """
        Estimate credit rating from financial metrics.
        Based on industry-standard credit rating criteria from Moody's/S&P/Fitch.

        Args:
            debt_to_ebitda: Total Debt / EBITDA ratio
            interest_coverage: EBIT / Interest Expense ratio

        Returns:
            Dictionary with estimated rating and analysis
        """
        # Determine rating based on combined metrics
        # Using airline-specific thresholds (airlines typically have higher leverage)
        if debt_to_ebitda is None or interest_coverage is None:
            return {
                'estimated_rating': 'N/A',
                'rating_outlook': 'Insufficient data for rating estimation',
                'confidence': 'low',
                'methodology': 'Unable to calculate - missing financial metrics'
            }

        # Rating determination logic based on industry research
        # Airlines typically run higher leverage than other sectors
        if debt_to_ebitda < 2.0 and interest_coverage > 6.0:
            rating = 'A'
            outlook = 'Strong investment grade - conservative leverage profile'
            confidence = 'high'
        elif debt_to_ebitda < 2.5 and interest_coverage > 4.5:
            rating = 'A-'
            outlook = 'Solid investment grade - healthy credit metrics'
            confidence = 'high'
        elif debt_to_ebitda < 3.0 and interest_coverage > 3.5:
            rating = 'BBB+'
            outlook = 'Investment grade - adequate credit cushion'
            confidence = 'medium-high'
        elif debt_to_ebitda < 3.5 and interest_coverage > 3.0:
            rating = 'BBB'
            outlook = 'Investment grade - typical for major airlines'
            confidence = 'medium-high'
        elif debt_to_ebitda < 4.0 and interest_coverage > 2.5:
            rating = 'BBB-'
            outlook = 'Lower investment grade - moderate credit risk'
            confidence = 'medium'
        elif debt_to_ebitda < 5.0 and interest_coverage > 2.0:
            rating = 'BB+'
            outlook = 'Speculative grade - watch for deterioration'
            confidence = 'medium'
        elif debt_to_ebitda < 6.0 and interest_coverage > 1.5:
            rating = 'BB'
            outlook = 'Speculative grade - elevated credit risk'
            confidence = 'medium'
        elif debt_to_ebitda < 7.0 and interest_coverage > 1.0:
            rating = 'BB-'
            outlook = 'Lower speculative grade - significant credit concerns'
            confidence = 'medium'
        else:
            rating = 'B'
            outlook = 'High yield - elevated default risk'
            confidence = 'medium'

        return {
            'estimated_rating': rating,
            'rating_outlook': outlook,
            'confidence': confidence,
            'debt_to_ebitda': round(debt_to_ebitda, 2),
            'interest_coverage': round(interest_coverage, 2),
            'methodology': 'Synthetic rating based on Debt/EBITDA and Interest Coverage ratios',
            'note': 'This is an estimated rating based on publicly available financial metrics. Actual agency ratings may differ.'
        }

    def format_for_credit_report(self, airline_name: str) -> str:
        """
        Format comprehensive financial data for credit report prompt

        Args:
            airline_name: Airline name

        Returns:
            Formatted string for Gemini prompt
        """
        data = self.get_comprehensive_financials(airline_name)

        if not data:
            return "**Financial Data**: Not available."

        sections = []

        # Balance Sheet Section
        bs = data.get('balance_sheet')
        if bs:
            total_debt_b = bs.get('total_debt', 0) / 1e9
            cash_b = bs.get('cash_and_equivalents', 0) / 1e9
            equity_b = bs.get('stockholders_equity', 0) / 1e9
            ebitda_b = bs.get('ebitda', 0) / 1e9
            fcf_b = bs.get('free_cash_flow', 0) / 1e9
            int_exp_m = bs.get('interest_expense', 0) / 1e6

            sections.append(f"""**Balance Sheet & Credit Metrics** ({bs.get('ticker')} - {bs.get('period')}):

**Debt & Liquidity:**
- Total Debt: ${total_debt_b:.2f}B
- Net Debt: ${bs.get('net_debt', 0)/1e9:.2f}B
- Cash & Equivalents: ${cash_b:.2f}B
- Working Capital: ${bs.get('working_capital', 0)/1e9:.2f}B

**Profitability:**
- EBITDA: ${ebitda_b:.2f}B
- Operating Income: ${bs.get('operating_income', 0)/1e9:.2f}B
- Net Income: ${bs.get('net_income', 0)/1e9:.2f}B

**Cash Flow:**
- Free Cash Flow: ${fcf_b:.2f}B
- Operating Cash Flow: ${bs.get('operating_cash_flow', 0)/1e9:.2f}B

**Credit Ratios:**
- Debt-to-EBITDA: {bs.get('debt_to_ebitda', 'N/A')}x
- Interest Coverage: {bs.get('interest_coverage', 'N/A')}x
- Debt-to-Equity: {bs.get('debt_to_equity', 'N/A')}x
- Interest Expense (Annual): ${int_exp_m:.0f}M

Source: Yahoo Finance (Annual Report Data)""")

        # Operational Metrics Section (from BTS)
        ops = data.get('operational_metrics')
        if ops:
            sections.append(f"""**Operational Metrics** (BTS Form 41 - {ops.get('period')}):

**Traffic & Capacity:**
- Load Factor: {ops.get('load_factor_pct', 0):.1f}%
- RASM: {ops.get('rasm_cents', 0):.2f}¢
- CASM: {ops.get('casm_cents', 0):.2f}¢
- RASM-CASM Spread: {(ops.get('rasm_cents', 0) - ops.get('casm_cents', 0)):.2f}¢
- Operating Margin: {ops.get('operating_margin_pct', 0):.1f}%

**Cost Structure:**
- Fuel as % of OpEx: {ops.get('fuel_expense', 0)/ops.get('operating_expenses', 1)*100:.1f}%
- Labor as % of OpEx: {ops.get('labor_expense', 0)/ops.get('operating_expenses', 1)*100:.1f}%

Source: DOT Bureau of Transportation Statistics""")

        if not sections:
            return "**Financial Data**: Not available."

        return "\n\n".join(sections)


def test_financial_service():
    """Test the financial data service"""
    print("=== FINANCIAL DATA SERVICE TEST ===\n")

    service = FinancialDataService()

    # Test United Airlines
    print("📊 Testing United Airlines balance sheet...")
    bs = service.get_balance_sheet_data('United Airlines')

    if bs:
        print(f"✅ Success!")
        print(f"  Period: {bs['period']}")
        print(f"  Total Debt: ${bs['total_debt']/1e9:.2f}B")
        print(f"  Net Debt: ${bs['net_debt']/1e9:.2f}B")
        print(f"  Cash: ${bs['cash_and_equivalents']/1e9:.2f}B")
        print(f"  EBITDA: ${bs['ebitda']/1e9:.2f}B")
        print(f"  Debt/EBITDA: {bs['debt_to_ebitda']}x")
        print(f"  Interest Coverage: {bs['interest_coverage']}x")
        print(f"  Free Cash Flow: ${bs['free_cash_flow']/1e9:.2f}B")
    else:
        print("❌ Failed to fetch balance sheet")

    print("\n📄 Formatted for credit report:")
    print(service.format_for_credit_report('United Airlines'))


if __name__ == "__main__":
    test_financial_service()
