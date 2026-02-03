#!/usr/bin/env python3
"""
Stock Data Service - Fetch airline stock prices and financial data
Uses yfinance to retrieve real-time stock data for airline analysis
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import yfinance as yf

logger = logging.getLogger(__name__)


class StockDataService:
    """Service for fetching airline stock price data"""

    # Airline ticker symbol mapping
    AIRLINE_TICKERS = {
        'United Airlines': 'UAL',
        'Delta Air Lines': 'DAL',
        'American Airlines': 'AAL',
        'Southwest Airlines': 'LUV',
        'JetBlue Airways': 'JBLU',
        'Alaska Airlines': 'ALK',
        'Spirit Airlines': 'SAVE',
        'Frontier Airlines': 'ULCC',
        'Hawaiian Airlines': 'HA',
        'Allegiant Air': 'ALGT'
    }

    def __init__(self):
        """Initialize stock data service"""
        logger.info("✅ Stock data service initialized")

    def get_ticker_symbol(self, airline_name: str) -> Optional[str]:
        """
        Get stock ticker symbol for an airline

        Args:
            airline_name: Full airline name

        Returns:
            Ticker symbol or None if not found
        """
        # Try exact match
        if airline_name in self.AIRLINE_TICKERS:
            return self.AIRLINE_TICKERS[airline_name]

        # Try partial match
        for name, ticker in self.AIRLINE_TICKERS.items():
            if airline_name.lower() in name.lower() or name.lower() in airline_name.lower():
                logger.info(f"📍 Matched '{airline_name}' to ticker {ticker}")
                return ticker

        logger.warning(f"⚠️ No ticker found for airline: {airline_name}")
        return None

    def get_stock_data(
        self,
        airline_name: str,
        period: str = "1mo",
        include_history: bool = True
    ) -> Optional[Dict]:
        """
        Fetch stock data for an airline

        Args:
            airline_name: Airline name (e.g., "Delta Air Lines")
            period: Period to fetch (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, ytd, max)
            include_history: Whether to include historical price data

        Returns:
            Dictionary with stock data or None if fetch failed
        """
        try:
            ticker_symbol = self.get_ticker_symbol(airline_name)
            if not ticker_symbol:
                return None

            logger.info(f"📈 Fetching stock data for {airline_name} ({ticker_symbol})")

            # Create ticker object
            ticker = yf.Ticker(ticker_symbol)

            # Get current info
            info = ticker.info

            # Get historical data
            history = None
            if include_history:
                history_df = ticker.history(period=period)
                if not history_df.empty:
                    # Convert to list of dicts for JSON serialization
                    history = []
                    for date, row in history_df.iterrows():
                        history.append({
                            'date': date.strftime('%Y-%m-%d'),
                            'open': float(row['Open']),
                            'high': float(row['High']),
                            'low': float(row['Low']),
                            'close': float(row['Close']),
                            'volume': int(row['Volume'])
                        })

            # Calculate performance metrics
            performance = self._calculate_performance(history) if history else None

            stock_data = {
                'ticker': ticker_symbol,
                'airline_name': airline_name,
                'current_price': info.get('currentPrice') or info.get('regularMarketPrice'),
                'previous_close': info.get('previousClose'),
                'day_change': info.get('regularMarketChange'),
                'day_change_percent': info.get('regularMarketChangePercent'),
                'market_cap': info.get('marketCap'),
                'pe_ratio': info.get('trailingPE'),
                'forward_pe': info.get('forwardPE'),
                'dividend_yield': info.get('dividendYield'),
                'beta': info.get('beta'),
                'fifty_two_week_high': info.get('fiftyTwoWeekHigh'),
                'fifty_two_week_low': info.get('fiftyTwoWeekLow'),
                'avg_volume': info.get('averageVolume'),
                'currency': info.get('currency', 'USD'),
                'performance': performance,
                'history': history if include_history else None,
                'fetched_at': datetime.now().isoformat()
            }

            logger.info(f"✅ Stock data fetched for {ticker_symbol}: ${stock_data.get('current_price'):.2f}")
            return stock_data

        except Exception as e:
            logger.error(f"❌ Error fetching stock data for {airline_name}: {e}")
            return None

    def get_multiple_stocks(
        self,
        airline_names: List[str],
        period: str = "1mo"
    ) -> Dict[str, Optional[Dict]]:
        """
        Fetch stock data for multiple airlines

        Args:
            airline_names: List of airline names
            period: Period to fetch data for

        Returns:
            Dictionary mapping airline names to stock data
        """
        results = {}
        for airline in airline_names:
            results[airline] = self.get_stock_data(
                airline_name=airline,
                period=period,
                include_history=False  # Don't include full history for bulk requests
            )

        logger.info(f"✅ Fetched stock data for {len(results)} airlines")
        return results

    def _calculate_performance(self, history: List[Dict]) -> Optional[Dict]:
        """
        Calculate performance metrics from historical data

        Args:
            history: List of historical price data

        Returns:
            Dictionary with performance metrics
        """
        if not history or len(history) < 2:
            return None

        try:
            # Get first and last prices
            first_price = history[0]['close']
            last_price = history[-1]['close']

            # Calculate returns
            total_return = ((last_price - first_price) / first_price) * 100

            # Calculate high and low
            prices = [day['close'] for day in history]
            period_high = max(prices)
            period_low = min(prices)

            # Calculate volatility (simple standard deviation)
            avg_price = sum(prices) / len(prices)
            variance = sum((p - avg_price) ** 2 for p in prices) / len(prices)
            volatility = (variance ** 0.5 / avg_price) * 100

            return {
                'period_return_pct': round(total_return, 2),
                'period_high': round(period_high, 2),
                'period_low': round(period_low, 2),
                'volatility_pct': round(volatility, 2),
                'days_analyzed': len(history)
            }

        except Exception as e:
            logger.error(f"❌ Error calculating performance metrics: {e}")
            return None
