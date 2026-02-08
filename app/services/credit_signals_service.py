#!/usr/bin/env python3
"""
Credit Signals Service - Published Ratings & Market Signals
Handles external credit signals: agency ratings, rating trends, stock momentum.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)

# Import yfinance for stock momentum
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    logger.warning("⚠️ yfinance not available for stock momentum")


class CreditSignalsService:
    """Service for external credit signals and market momentum"""

    # Rating to numeric score mapping (0-100 scale)
    # Investment grade: 70-100, Speculative: 30-69, Distressed: 0-29
    RATING_SCORES = {
        # S&P / Fitch scale
        'AAA': 100, 'AA+': 97, 'AA': 94, 'AA-': 91,
        'A+': 88, 'A': 85, 'A-': 82,
        'BBB+': 79, 'BBB': 76, 'BBB-': 73,
        'BB+': 67, 'BB': 61, 'BB-': 55,
        'B+': 49, 'B': 43, 'B-': 37,
        'CCC+': 31, 'CCC': 25, 'CCC-': 19,
        'CC': 13, 'C': 7, 'D': 0,

        # Moody's scale
        'Aaa': 100, 'Aa1': 97, 'Aa2': 94, 'Aa3': 91,
        'A1': 88, 'A2': 85, 'A3': 82,
        'Baa1': 79, 'Baa2': 76, 'Baa3': 73,
        'Ba1': 67, 'Ba2': 61, 'Ba3': 55,
        'B1': 49, 'B2': 43, 'B3': 37,
        'Caa1': 31, 'Caa2': 25, 'Caa3': 19,
        'Ca': 13, 'C': 7,
    }

    # Outlook trend modifiers (added to base rating score)
    TREND_MODIFIERS = {
        'positive': 5,
        'stable': 0,
        'negative': -5,
        'watch_positive': 3,
        'watch_negative': -3,
        'developing': -2,
    }

    # Ticker mapping for stock momentum
    AIRLINE_TICKERS = {
        'DAL': 'DAL',
        'UAL': 'UAL',
        'AAL': 'AAL',
        'LUV': 'LUV',
        'JBLU': 'JBLU',
        'ALK': 'ALK',
        'SAVE': 'SAVE',
        'ULCC': 'ULCC',
    }

    def __init__(self, db_service=None):
        """
        Initialize Credit Signals service.

        Args:
            db_service: DatabaseService for published ratings lookup
        """
        self.db_service = db_service
        logger.info("✅ Credit Signals service initialized")

    def get_published_rating_score(
        self,
        airline_code: str,
        as_of_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get published credit rating and convert to numeric score.

        Args:
            airline_code: Airline ticker
            as_of_date: Optional date for backtesting

        Returns:
            Dict with rating_score, ratings, trend_modifier
        """
        # Try to get from database
        rating_data = None
        if self.db_service:
            rating_data = self.db_service.get_published_rating(airline_code.upper())

        if not rating_data:
            # Return default mid-range speculative
            logger.info(f"📊 No published ratings found for {airline_code}, using default")
            return {
                'airline_code': airline_code.upper(),
                'rating_score': 55,  # Default BB range
                'adjusted_score': 55,
                'confidence': 'low',
                'reason': 'No published ratings found in database',
                'ratings': {},
                'trend_modifier': 0,
                'trend_direction': 'unknown',
                'as_of_date': as_of_date
            }

        # Calculate average score from available ratings
        scores = []
        ratings = {}

        for agency in ['moodys', 'sp', 'fitch']:
            rating = rating_data.get(agency)
            if rating and rating in self.RATING_SCORES:
                scores.append(self.RATING_SCORES[rating])
                ratings[agency] = rating
            elif rating:
                logger.warning(f"⚠️ Unknown rating format: {rating}")

        if not scores:
            avg_score = 55
            confidence = 'low'
        elif len(scores) >= 2:
            avg_score = sum(scores) / len(scores)
            confidence = 'high'
        else:
            avg_score = scores[0]
            confidence = 'medium'

        # Calculate trend modifier (average of available outlooks)
        trend_modifiers = []
        for outlook_field in ['moodys_outlook', 'sp_outlook', 'fitch_outlook']:
            outlook = rating_data.get(outlook_field, '').lower()
            if outlook in self.TREND_MODIFIERS:
                trend_modifiers.append(self.TREND_MODIFIERS[outlook])

        trend_modifier = sum(trend_modifiers) / len(trend_modifiers) if trend_modifiers else 0

        # Determine trend direction
        if trend_modifier > 2:
            trend_direction = 'positive'
        elif trend_modifier < -2:
            trend_direction = 'negative'
        else:
            trend_direction = 'stable'

        return {
            'airline_code': airline_code.upper(),
            'rating_score': round(avg_score, 1),
            'adjusted_score': round(avg_score + trend_modifier, 1),
            'confidence': confidence,
            'ratings': ratings,
            'trend_modifier': round(trend_modifier, 1),
            'trend_direction': trend_direction,
            'as_of_date': rating_data.get('as_of_date', as_of_date),
            'data_source': 'firestore'
        }

    def get_stock_momentum(
        self,
        airline_code: str,
        days: int = 90,
        as_of_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate stock momentum score from price performance.

        Args:
            airline_code: Airline ticker
            days: Lookback period (default 90 days)
            as_of_date: Optional date for backtesting

        Returns:
            Dict with momentum_score, price_change_pct, volatility
        """
        code = airline_code.upper()

        if not YFINANCE_AVAILABLE:
            logger.warning(f"⚠️ yfinance not available, using default momentum for {code}")
            return {
                'airline_code': code,
                'momentum_score': 50,
                'reason': 'yfinance library not available',
                'as_of_date': as_of_date
            }

        ticker = self.AIRLINE_TICKERS.get(code)
        if not ticker:
            logger.warning(f"⚠️ Unknown airline code: {code}")
            return {
                'airline_code': code,
                'momentum_score': 50,
                'reason': f'Unknown airline code: {code}',
                'as_of_date': as_of_date
            }

        try:
            stock = yf.Ticker(ticker)

            # Get historical data
            if as_of_date:
                end_date = datetime.strptime(as_of_date, '%Y-%m-%d')
            else:
                end_date = datetime.now()

            start_date = end_date - timedelta(days=days)

            hist = stock.history(
                start=start_date.strftime('%Y-%m-%d'),
                end=end_date.strftime('%Y-%m-%d')
            )

            if hist.empty or len(hist) < 10:
                logger.warning(f"⚠️ Insufficient stock data for {code}")
                return {
                    'airline_code': code,
                    'momentum_score': 50,
                    'reason': 'Insufficient historical data',
                    'as_of_date': as_of_date
                }

            # Calculate metrics
            start_price = float(hist['Close'].iloc[0])
            end_price = float(hist['Close'].iloc[-1])
            price_change_pct = ((end_price - start_price) / start_price) * 100

            # Calculate volatility (annualized standard deviation)
            daily_returns = hist['Close'].pct_change().dropna()
            volatility = float(daily_returns.std() * (252 ** 0.5) * 100)  # Annualized %

            # Convert to score (0-100)
            # +30% or more = 95, -30% or worse = 5, linear between
            momentum_score = 50 + (price_change_pct / 30) * 45
            momentum_score = max(5, min(95, momentum_score))

            # Apply volatility penalty (>50% annualized = penalty)
            if volatility > 50:
                volatility_penalty = min(15, (volatility - 50) / 3)
                momentum_score = max(5, momentum_score - volatility_penalty)

            logger.info(f"📈 {code} momentum: {price_change_pct:+.1f}% over {days}d → score {momentum_score:.1f}")

            return {
                'airline_code': code,
                'ticker': ticker,
                'momentum_score': round(momentum_score, 1),
                'price_change_pct': round(price_change_pct, 2),
                'volatility_annualized': round(volatility, 2),
                'start_price': round(start_price, 2),
                'end_price': round(end_price, 2),
                'days': days,
                'data_points': len(hist),
                'as_of_date': as_of_date or end_date.strftime('%Y-%m-%d'),
                'data_source': 'yfinance'
            }

        except Exception as e:
            logger.error(f"❌ Error calculating stock momentum for {code}: {e}")
            return {
                'airline_code': code,
                'momentum_score': 50,
                'error': str(e),
                'as_of_date': as_of_date
            }

    def calculate_signals_score(
        self,
        airline_code: str,
        as_of_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate combined signals score from ratings and momentum.

        Weights:
        - Published rating (adjusted for trend): 75%
        - Stock momentum: 25%

        Args:
            airline_code: Airline ticker
            as_of_date: Optional date for backtesting

        Returns:
            Dict with signals_score and breakdown
        """
        code = airline_code.upper()

        # Get rating score
        rating_result = self.get_published_rating_score(code, as_of_date)

        # Get momentum score
        momentum_result = self.get_stock_momentum(code, 90, as_of_date)

        # Extract scores
        rating_score = rating_result.get('rating_score', 55)
        trend_modifier = rating_result.get('trend_modifier', 0)
        momentum_score = momentum_result.get('momentum_score', 50)

        # Weighted combination
        # Use adjusted rating (includes trend modifier) with 75% weight
        adjusted_rating = rating_score + trend_modifier
        signals_score = (adjusted_rating * 0.75) + (momentum_score * 0.25)

        # Clamp to 0-100
        signals_score = max(0, min(100, signals_score))

        logger.info(f"📊 {code} signals score: {signals_score:.1f} (rating {adjusted_rating:.1f}, momentum {momentum_score:.1f})")

        return {
            'airline_code': code,
            'signals_score': round(signals_score, 1),
            'rating_component': {
                'score': rating_score,
                'trend_modifier': trend_modifier,
                'adjusted_score': round(adjusted_rating, 1),
                'weight': 0.75,
                'ratings': rating_result.get('ratings', {}),
                'confidence': rating_result.get('confidence', 'low'),
                'trend_direction': rating_result.get('trend_direction', 'stable')
            },
            'momentum_component': {
                'score': momentum_score,
                'weight': 0.25,
                'price_change_pct': momentum_result.get('price_change_pct'),
                'volatility': momentum_result.get('volatility_annualized'),
                'data_points': momentum_result.get('data_points')
            },
            'as_of_date': as_of_date
        }
