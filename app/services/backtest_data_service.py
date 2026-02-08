#!/usr/bin/env python3
"""
Backtest Data Service - Historical Data Collection for Credit Score Validation
Collects SEC XBRL, stock prices, operational data, and rating history for backtesting.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List

logger = logging.getLogger(__name__)

# Import yfinance for stock history
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    logger.warning("⚠️ yfinance not available for stock history")


class BacktestDataService:
    """Service for collecting historical data for credit score backtesting"""

    # Airline CIKs (same as XBRL service)
    AIRLINE_CIKS = {
        'DAL': '0000027904',
        'UAL': '0000100517',
        'AAL': '0000006201',
        'LUV': '0000092380',
        'JBLU': '0000898293',
        'ALK': '0000766421',
        'SAVE': '0001498710',
        'ULCC': '0001901231',
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

    # Historical credit rating timeline (ground truth for validation)
    # Dates are approximate based on public announcements
    RATING_HISTORY = {
        "DAL": [
            {"date": "2005-09-14", "action": "Chapter 11 filed", "sp": "D", "moodys": "Ca"},
            {"date": "2007-04-30", "action": "Emerged from bankruptcy", "sp": "B", "moodys": "B2"},
            {"date": "2010-01-01", "action": "Post-merger stability", "sp": "B+", "moodys": "B1"},
            {"date": "2014-10-01", "action": "Investment grade", "sp": "BBB-", "moodys": "Baa3"},
            {"date": "2019-01-01", "action": "Pre-COVID peak", "sp": "BBB-", "moodys": "Baa3"},
            {"date": "2020-03-20", "action": "COVID downgrade", "sp": "BB", "moodys": "Ba2"},
            {"date": "2021-10-01", "action": "Upgrade post-COVID", "sp": "BBB-", "moodys": "Baa3"},
            {"date": "2024-01-01", "action": "Current", "sp": "BBB-", "moodys": "Baa3"},
        ],
        "UAL": [
            {"date": "2002-12-09", "action": "Chapter 11 filed", "sp": "D", "moodys": "Ca"},
            {"date": "2006-02-01", "action": "Emerged from bankruptcy", "sp": "B-", "moodys": "B3"},
            {"date": "2010-10-01", "action": "Continental merger", "sp": "B", "moodys": "B2"},
            {"date": "2015-01-01", "action": "Improving", "sp": "BB-", "moodys": "Ba3"},
            {"date": "2018-10-01", "action": "Investment grade", "sp": "BBB-", "moodys": "Baa3"},
            {"date": "2020-03-25", "action": "COVID downgrade", "sp": "BB-", "moodys": "Ba2"},
            {"date": "2023-06-01", "action": "Current", "sp": "BB+", "moodys": "Ba1"},
        ],
        "AAL": [
            {"date": "2011-11-29", "action": "AMR Chapter 11", "sp": "D", "moodys": "Ca"},
            {"date": "2013-12-09", "action": "Emerged (US Airways merger)", "sp": "B-", "moodys": "B3"},
            {"date": "2015-01-01", "action": "Post-merger", "sp": "B", "moodys": "B2"},
            {"date": "2017-01-01", "action": "Improving", "sp": "BB-", "moodys": "Ba3"},
            {"date": "2020-03-25", "action": "COVID downgrade", "sp": "B-", "moodys": "B2"},
            {"date": "2024-01-01", "action": "Current", "sp": "B+", "moodys": "B1"},
        ],
        "LUV": [
            {"date": "2015-01-01", "action": "Baseline", "sp": "BBB+", "moodys": "A3"},
            {"date": "2019-01-01", "action": "Pre-COVID", "sp": "BBB+", "moodys": "A3"},
            {"date": "2020-04-01", "action": "COVID", "sp": "BBB", "moodys": "Baa1"},
            {"date": "2024-01-01", "action": "Current", "sp": "BBB", "moodys": "Baa1"},
        ],
        "JBLU": [
            {"date": "2015-01-01", "action": "Baseline", "sp": "B+", "moodys": "B1"},
            {"date": "2019-01-01", "action": "Upgrade", "sp": "BB-", "moodys": "Ba3"},
            {"date": "2020-03-25", "action": "COVID", "sp": "B", "moodys": "B2"},
            {"date": "2022-07-01", "action": "Spirit merger attempt stress", "sp": "B+", "moodys": "B1"},
            {"date": "2024-03-01", "action": "Post-merger-collapse", "sp": "B", "moodys": "B2"},
        ],
        "ALK": [
            {"date": "2015-01-01", "action": "Baseline", "sp": "BB+", "moodys": "Ba1"},
            {"date": "2016-12-01", "action": "Virgin America acquisition", "sp": "BB", "moodys": "Ba2"},
            {"date": "2019-01-01", "action": "Pre-COVID", "sp": "BB+", "moodys": "Ba1"},
            {"date": "2020-04-01", "action": "COVID", "sp": "BB-", "moodys": "Ba3"},
            {"date": "2024-01-01", "action": "Current (Hawaiian merger)", "sp": "BB-", "moodys": "Ba3"},
        ],
        "SAVE": [
            {"date": "2015-01-01", "action": "Baseline", "sp": "B+", "moodys": "B1"},
            {"date": "2019-01-01", "action": "Pre-COVID", "sp": "BB-", "moodys": "Ba3"},
            {"date": "2020-03-25", "action": "COVID", "sp": "B-", "moodys": "Caa1"},
            {"date": "2023-01-01", "action": "Merger uncertainty", "sp": "B-", "moodys": "Caa1"},
            {"date": "2024-06-01", "action": "Pre-bankruptcy distress", "sp": "CCC+", "moodys": "Caa2"},
            {"date": "2024-11-18", "action": "Chapter 11 filed", "sp": "D", "moodys": "Ca"},
        ],
        "ULCC": [
            {"date": "2021-04-01", "action": "IPO", "sp": "B", "moodys": "B2"},
            {"date": "2022-01-01", "action": "Post-IPO", "sp": "B", "moodys": "B2"},
            {"date": "2024-01-01", "action": "Current", "sp": "B-", "moodys": "B3"},
        ],
    }

    # Known credit events (ground truth labels for validation)
    CREDIT_EVENTS = [
        {"airline": "DAL", "date": "2005-09-14", "event": "chapter_11", "severity": "critical"},
        {"airline": "UAL", "date": "2002-12-09", "event": "chapter_11", "severity": "critical"},
        {"airline": "AAL", "date": "2011-11-29", "event": "chapter_11", "severity": "critical"},
        {"airline": "SAVE", "date": "2024-11-18", "event": "chapter_11", "severity": "critical"},
        {"airline": "SAVE", "date": "2024-06-01", "event": "going_concern_warning", "severity": "high"},
        {"airline": "JBLU", "date": "2022-07-28", "event": "rating_downgrade", "severity": "medium"},
        # COVID-era mass downgrades (March-April 2020)
        {"airline": "DAL", "date": "2020-03-20", "event": "rating_downgrade", "severity": "medium"},
        {"airline": "UAL", "date": "2020-03-25", "event": "rating_downgrade", "severity": "medium"},
        {"airline": "AAL", "date": "2020-03-25", "event": "rating_downgrade", "severity": "medium"},
        {"airline": "LUV", "date": "2020-04-01", "event": "rating_downgrade", "severity": "low"},
        {"airline": "ALK", "date": "2020-04-01", "event": "rating_downgrade", "severity": "medium"},
        {"airline": "SAVE", "date": "2020-03-25", "event": "rating_downgrade", "severity": "high"},
        {"airline": "JBLU", "date": "2020-03-25", "event": "rating_downgrade", "severity": "medium"},
    ]

    # Rating to numeric score mapping (same as CreditSignalsService)
    RATING_SCORES = {
        'AAA': 100, 'AA+': 97, 'AA': 94, 'AA-': 91,
        'A+': 88, 'A': 85, 'A-': 82,
        'BBB+': 79, 'BBB': 76, 'BBB-': 73,
        'BB+': 67, 'BB': 61, 'BB-': 55,
        'B+': 49, 'B': 43, 'B-': 37,
        'CCC+': 31, 'CCC': 25, 'CCC-': 19,
        'CC': 13, 'C': 7, 'D': 0,
        # Moody's
        'Aaa': 100, 'Aa1': 97, 'Aa2': 94, 'Aa3': 91,
        'A1': 88, 'A2': 85, 'A3': 82,
        'Baa1': 79, 'Baa2': 76, 'Baa3': 73,
        'Ba1': 67, 'Ba2': 61, 'Ba3': 55,
        'B1': 49, 'B2': 43, 'B3': 37,
        'Caa1': 31, 'Caa2': 25, 'Caa3': 19,
        'Ca': 13, 'C': 7,
    }

    def __init__(self, xbrl_service=None, db_service=None):
        """
        Initialize Backtest Data service.

        Args:
            xbrl_service: XBRLService for fetching SEC data
            db_service: DatabaseService for persistence
        """
        self.xbrl = xbrl_service
        self.db_service = db_service
        logger.info("✅ Backtest Data service initialized")

    def get_rating_at_date(self, airline_code: str, as_of_date: str) -> Dict[str, Any]:
        """
        Get the published rating for an airline at a specific date.

        Args:
            airline_code: Airline ticker
            as_of_date: Date string (YYYY-MM-DD)

        Returns:
            Dict with sp, moodys ratings and numeric score
        """
        code = airline_code.upper()
        history = self.RATING_HISTORY.get(code, [])

        if not history:
            return {
                'airline_code': code,
                'as_of_date': as_of_date,
                'sp': 'NR',
                'moodys': 'NR',
                'numeric_score': 50,
                'found': False
            }

        # Find most recent rating before as_of_date
        target_date = datetime.strptime(as_of_date, '%Y-%m-%d')
        applicable_rating = None

        for entry in sorted(history, key=lambda x: x['date']):
            entry_date = datetime.strptime(entry['date'], '%Y-%m-%d')
            if entry_date <= target_date:
                applicable_rating = entry
            else:
                break

        if not applicable_rating:
            # No rating before this date
            return {
                'airline_code': code,
                'as_of_date': as_of_date,
                'sp': 'NR',
                'moodys': 'NR',
                'numeric_score': 50,
                'found': False
            }

        # Calculate average numeric score
        sp_score = self.RATING_SCORES.get(applicable_rating.get('sp'), 50)
        moodys_score = self.RATING_SCORES.get(applicable_rating.get('moodys'), 50)
        avg_score = (sp_score + moodys_score) / 2

        return {
            'airline_code': code,
            'as_of_date': as_of_date,
            'sp': applicable_rating.get('sp'),
            'moodys': applicable_rating.get('moodys'),
            'action': applicable_rating.get('action'),
            'rating_date': applicable_rating.get('date'),
            'numeric_score': round(avg_score, 1),
            'found': True
        }

    def get_credit_event_in_window(
        self,
        airline_code: str,
        start_date: str,
        months_forward: int = 12
    ) -> Optional[Dict[str, Any]]:
        """
        Check if a credit event occurred within a time window.

        Args:
            airline_code: Airline ticker
            start_date: Start of window (YYYY-MM-DD)
            months_forward: Number of months to look ahead

        Returns:
            Credit event dict if found, None otherwise
        """
        code = airline_code.upper()
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = start + timedelta(days=months_forward * 30)

        for event in self.CREDIT_EVENTS:
            if event['airline'] != code:
                continue

            event_date = datetime.strptime(event['date'], '%Y-%m-%d')
            if start < event_date <= end:
                return event

        return None

    def collect_stock_history(
        self,
        airline_code: str,
        start_year: int = 2010
    ) -> Dict[str, Any]:
        """
        Collect historical stock prices and compute momentum at quarter ends.

        Args:
            airline_code: Airline ticker
            start_year: Start year for data collection

        Returns:
            Dict with quarterly momentum data
        """
        if not YFINANCE_AVAILABLE:
            logger.warning(f"⚠️ yfinance not available for {airline_code}")
            return {
                'airline_code': airline_code.upper(),
                'quarterly_momentum': [],
                'error': 'yfinance not available'
            }

        code = airline_code.upper()

        try:
            logger.info(f"📈 Collecting stock history for {code}...")
            stock = yf.Ticker(code)

            # Get full history
            hist = stock.history(period="max")

            if hist.empty:
                return {
                    'airline_code': code,
                    'quarterly_momentum': [],
                    'error': 'No stock data available'
                }

            # Calculate momentum at each quarter end
            quarter_ends = []
            current_year = datetime.now().year

            for year in range(start_year, current_year + 1):
                for month, day in [(3, 31), (6, 30), (9, 30), (12, 31)]:
                    try:
                        qe = datetime(year, month, day)
                        if qe <= datetime.now():
                            quarter_ends.append(qe)
                    except ValueError:
                        continue

            momentum_data = []
            for qe in quarter_ends:
                # Get 90-day window before quarter end
                start_window = qe - timedelta(days=90)

                # Filter history to this window
                mask = (hist.index >= start_window.strftime('%Y-%m-%d')) & \
                       (hist.index <= qe.strftime('%Y-%m-%d'))
                window_data = hist.loc[mask]

                if len(window_data) < 10:
                    continue

                try:
                    start_price = float(window_data['Close'].iloc[0])
                    end_price = float(window_data['Close'].iloc[-1])
                    momentum_pct = ((end_price - start_price) / start_price) * 100

                    # Convert momentum % to score (0-100)
                    # +30% = 95, -30% = 5, linear between
                    momentum_score = 50 + (momentum_pct / 30) * 45
                    momentum_score = max(5, min(95, momentum_score))

                    momentum_data.append({
                        'date': qe.strftime('%Y-%m-%d'),
                        'momentum_pct': round(momentum_pct, 2),
                        'momentum_score': round(momentum_score, 1),
                        'start_price': round(start_price, 2),
                        'end_price': round(end_price, 2),
                        'data_points': len(window_data)
                    })
                except Exception as e:
                    logger.warning(f"⚠️ Error calculating momentum for {code} at {qe}: {e}")

            logger.info(f"✅ Collected {len(momentum_data)} quarterly momentum points for {code}")

            return {
                'airline_code': code,
                'quarterly_momentum': momentum_data,
                'data_start': momentum_data[0]['date'] if momentum_data else None,
                'data_end': momentum_data[-1]['date'] if momentum_data else None,
                'total_quarters': len(momentum_data)
            }

        except Exception as e:
            logger.error(f"❌ Error collecting stock history for {code}: {e}")
            return {
                'airline_code': code,
                'quarterly_momentum': [],
                'error': str(e)
            }

    def collect_xbrl_history(
        self,
        airline_code: str,
        start_year: int = 2010
    ) -> Dict[str, Any]:
        """
        Collect historical XBRL financial data at quarter ends.

        Args:
            airline_code: Airline ticker
            start_year: Start year for data collection

        Returns:
            Dict with quarterly financial snapshots
        """
        if not self.xbrl:
            return {
                'airline_code': airline_code.upper(),
                'financial_snapshots': [],
                'error': 'XBRL service not available'
            }

        code = airline_code.upper()

        try:
            logger.info(f"📊 Collecting XBRL history for {code}...")

            # Generate quarter end dates
            quarter_ends = []
            current_year = datetime.now().year

            for year in range(start_year, current_year + 1):
                for month, day in [(3, 31), (6, 30), (9, 30), (12, 31)]:
                    try:
                        qe = datetime(year, month, day)
                        if qe <= datetime.now():
                            quarter_ends.append(qe.strftime('%Y-%m-%d'))
                    except ValueError:
                        continue

            # Get company facts (single API call)
            facts = self.xbrl.get_company_facts(code)

            if not facts:
                return {
                    'airline_code': code,
                    'financial_snapshots': [],
                    'error': 'No XBRL data available'
                }

            us_gaap = facts.get('facts', {}).get('us-gaap', {})

            # For each quarter end, extract metrics available at that time
            snapshots = []
            for qe_date in quarter_ends:
                metrics = self.xbrl.get_financial_metrics(code, as_of_date=qe_date)

                if metrics:
                    # Calculate financial score
                    score_result = self.xbrl.calculate_financial_score(metrics)

                    snapshots.append({
                        'date': qe_date,
                        'metrics': {
                            'debt_to_equity': metrics.get('debt_to_equity'),
                            'interest_coverage': metrics.get('interest_coverage'),
                            'operating_margin': metrics.get('operating_margin'),
                            'current_ratio': metrics.get('current_ratio'),
                        },
                        'financial_score': score_result.get('financial_score', 50),
                        'sub_scores': score_result.get('sub_scores', {}),
                    })

            logger.info(f"✅ Collected {len(snapshots)} quarterly XBRL snapshots for {code}")

            return {
                'airline_code': code,
                'financial_snapshots': snapshots,
                'data_start': snapshots[0]['date'] if snapshots else None,
                'data_end': snapshots[-1]['date'] if snapshots else None,
                'total_quarters': len(snapshots)
            }

        except Exception as e:
            logger.error(f"❌ Error collecting XBRL history for {code}: {e}")
            return {
                'airline_code': code,
                'financial_snapshots': [],
                'error': str(e)
            }

    def collect_all_historical_data(
        self,
        start_year: int = 2015,
        delay_seconds: float = 2.0
    ) -> Dict[str, Any]:
        """
        Collect all historical data for all 8 airlines.

        Args:
            start_year: Start year for data collection
            delay_seconds: Delay between airlines for rate limiting

        Returns:
            Summary of data collection
        """
        results = {
            'success': True,
            'started_at': datetime.utcnow().isoformat(),
            'airlines': {},
            'summary': {
                'total_airlines': len(self.AIRLINE_CIKS),
                'airlines_processed': 0,
                'airlines_failed': 0,
            }
        }

        for i, code in enumerate(self.AIRLINE_CIKS.keys()):
            try:
                logger.info(f"📊 Collecting data for {code} ({i+1}/{len(self.AIRLINE_CIKS)})...")

                airline_data = {
                    'airline_code': code,
                    'airline_name': self.AIRLINE_NAMES.get(code),
                    'rating_history': self.RATING_HISTORY.get(code, []),
                }

                # Collect XBRL history
                xbrl_data = self.collect_xbrl_history(code, start_year)
                airline_data['financial_snapshots'] = xbrl_data.get('financial_snapshots', [])

                # Collect stock history
                stock_data = self.collect_stock_history(code, start_year)
                airline_data['stock_momentum'] = stock_data.get('quarterly_momentum', [])

                # Store operational data (using current values as baseline - operational metrics change slowly)
                # In a production system, you'd collect historical BTS data here

                airline_data['collected_at'] = datetime.utcnow().isoformat()

                # Save to database if available
                if self.db_service:
                    try:
                        self.db_service.save_backtest_data(code, airline_data)
                    except Exception as e:
                        logger.warning(f"⚠️ Could not save to database: {e}")

                results['airlines'][code] = {
                    'name': self.AIRLINE_NAMES.get(code),
                    'financial_quarters': len(airline_data.get('financial_snapshots', [])),
                    'momentum_quarters': len(airline_data.get('stock_momentum', [])),
                    'rating_events': len(airline_data.get('rating_history', [])),
                }
                results['summary']['airlines_processed'] += 1

                # Rate limiting delay
                if i < len(self.AIRLINE_CIKS) - 1:
                    time.sleep(delay_seconds)

            except Exception as e:
                logger.error(f"❌ Failed to collect data for {code}: {e}")
                results['airlines'][code] = {'error': str(e)}
                results['summary']['airlines_failed'] += 1

        results['completed_at'] = datetime.utcnow().isoformat()
        results['success'] = results['summary']['airlines_failed'] == 0

        logger.info(f"✅ Data collection complete: {results['summary']['airlines_processed']} processed, "
                   f"{results['summary']['airlines_failed']} failed")

        return results

    def get_operational_data_at_date(
        self,
        airline_code: str,
        as_of_date: str,
        operational_service=None
    ) -> Dict[str, Any]:
        """
        Get operational metrics for an airline at a specific date.
        Falls back to current data if historical not available.

        Args:
            airline_code: Airline ticker
            as_of_date: Date string (YYYY-MM-DD)
            operational_service: OperationalService instance

        Returns:
            Dict with operational metrics and score
        """
        code = airline_code.upper()

        if operational_service:
            try:
                return operational_service.calculate_operational_score(code, as_of_date)
            except Exception as e:
                logger.warning(f"⚠️ Error getting operational data for {code}: {e}")

        # Fallback to default score
        return {
            'airline_code': code,
            'operational_score': 50,
            'as_of_date': as_of_date,
            'is_default': True
        }

    def get_stock_momentum_at_date(
        self,
        airline_code: str,
        as_of_date: str
    ) -> Dict[str, Any]:
        """
        Get stock momentum for an airline at a specific date.

        Args:
            airline_code: Airline ticker
            as_of_date: Date string (YYYY-MM-DD)

        Returns:
            Dict with momentum score and data
        """
        if not YFINANCE_AVAILABLE:
            return {
                'airline_code': airline_code.upper(),
                'momentum_score': 50,
                'as_of_date': as_of_date,
                'error': 'yfinance not available'
            }

        code = airline_code.upper()

        try:
            stock = yf.Ticker(code)

            # Calculate 90-day momentum ending at as_of_date
            end_date = datetime.strptime(as_of_date, '%Y-%m-%d')
            start_date = end_date - timedelta(days=90)

            hist = stock.history(
                start=start_date.strftime('%Y-%m-%d'),
                end=end_date.strftime('%Y-%m-%d')
            )

            if hist.empty or len(hist) < 10:
                return {
                    'airline_code': code,
                    'momentum_score': 50,
                    'as_of_date': as_of_date,
                    'error': 'Insufficient data'
                }

            start_price = float(hist['Close'].iloc[0])
            end_price = float(hist['Close'].iloc[-1])
            momentum_pct = ((end_price - start_price) / start_price) * 100

            # Convert to score
            momentum_score = 50 + (momentum_pct / 30) * 45
            momentum_score = max(5, min(95, momentum_score))

            return {
                'airline_code': code,
                'momentum_score': round(momentum_score, 1),
                'momentum_pct': round(momentum_pct, 2),
                'start_price': round(start_price, 2),
                'end_price': round(end_price, 2),
                'data_points': len(hist),
                'as_of_date': as_of_date
            }

        except Exception as e:
            logger.warning(f"⚠️ Error getting stock momentum for {code}: {e}")
            return {
                'airline_code': code,
                'momentum_score': 50,
                'as_of_date': as_of_date,
                'error': str(e)
            }

    def get_quarter_end_dates(
        self,
        start_year: int = 2015,
        end_year: int = None
    ) -> List[str]:
        """
        Generate list of quarter-end dates.

        Args:
            start_year: Start year
            end_year: End year (default: current year)

        Returns:
            List of date strings (YYYY-MM-DD)
        """
        if end_year is None:
            end_year = datetime.now().year

        dates = []
        for year in range(start_year, end_year + 1):
            for month, day in [(3, 31), (6, 30), (9, 30), (12, 31)]:
                try:
                    date = datetime(year, month, day)
                    if date <= datetime.now():
                        dates.append(date.strftime('%Y-%m-%d'))
                except ValueError:
                    continue

        return dates
