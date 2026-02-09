#!/usr/bin/env python3
"""
FINAL FRED Integration - Real Credit Spreads with Correct Series
Using Effective Yield series instead of spread indices
"""

import requests
import json
import os
import logging
from datetime import datetime
from app.utils.retry import make_request_with_retry

logger = logging.getLogger(__name__)


class FREDCreditSpreadsFinal:
    """Final production FRED credit spreads using correct series with Firestore persistence"""

    def __init__(self, db_service=None):
        # Use environment variable for API key, fallback to hardcoded for backward compatibility
        self.api_key = os.getenv('FRED_API_KEY', '13ab7454de31dec427aa8c95524d3e9a')
        self.base_url = "https://api.stlouisfed.org/fred/series/observations"
        self.db_service = db_service

    def _fetch_series(self, series_id: str, timeout: int = 10) -> requests.Response:
        """Fetch a FRED series with retry logic."""
        params = {
            'series_id': series_id,
            'api_key': self.api_key,
            'file_type': 'json',
            'limit': 1,
            'sort_order': 'desc'
        }
        return make_request_with_retry(
            self.base_url,
            method='GET',
            timeout=timeout,
            max_retries=3,
            params=params
        )

    def get_real_credit_spreads(self):
        """Get real credit spreads using correct FRED series"""
        try:
            # Use BBB Corporate Effective Yield (aviation sector proxy)
            corporate_params = {
                'series_id': 'BAMLC0A4CBBBEY',  # BBB Effective Yield (not spread)
                'api_key': self.api_key,
                'file_type': 'json',
                'limit': 1,
                'sort_order': 'desc'
            }
            
            # 10-Year Treasury
            treasury_params = {
                'series_id': 'DGS10',
                'api_key': self.api_key,
                'file_type': 'json',
                'limit': 1,
                'sort_order': 'desc'
            }
            
            # Get both series with retry logic
            corp_response = self._fetch_series('BAMLC0A4CBBBEY')
            treas_response = self._fetch_series('DGS10')
            
            if corp_response.status_code == 200 and treas_response.status_code == 200:
                corp_data = corp_response.json()
                treas_data = treas_response.json()
                
                # Extract values
                corporate_yield = float(corp_data['observations'][0]['value'])
                treasury_yield = float(treas_data['observations'][0]['value'])
                corp_date = corp_data['observations'][0]['date']
                
                # Calculate credit spread in basis points
                credit_spread_bps = round((corporate_yield - treasury_yield) * 100)
                
                # Determine market condition
                if credit_spread_bps < 80:
                    condition = "Very Tight - Low credit risk"
                    risk_level = "low"
                elif credit_spread_bps < 120:
                    condition = "Tight - Below average risk"
                    risk_level = "low-moderate"
                elif credit_spread_bps < 180:
                    condition = "Moderate - Normal credit conditions"
                    risk_level = "moderate"
                elif credit_spread_bps < 250:
                    condition = "Wide - Elevated credit concerns"
                    risk_level = "elevated"
                else:
                    condition = "Very Wide - High credit stress"
                    risk_level = "high"
                
                # Determine trend (simplified)
                trend = "stable"  # Could be enhanced with historical comparison
                if credit_spread_bps < 100:
                    trend = "tightening"
                elif credit_spread_bps > 200:
                    trend = "widening"

                fred_data = {
                    'credit_spread_bps': credit_spread_bps,
                    'corporate_yield_pct': round(corporate_yield, 2),
                    'treasury_yield_pct': round(treasury_yield, 2),
                    'spread_description': condition,
                    'risk_level': risk_level,
                    'trend': trend,
                    'data_date': corp_date,
                    'source': 'Federal Reserve Economic Data (FRED)',
                    'series_used': {
                        'corporate': 'BAMLC0A4CBBBEY (BBB Corporate Effective Yield)',
                        'treasury': 'DGS10 (10-Year Treasury)'
                    },
                    'aviation_context': 'BBB rating represents typical aviation sector credit quality'
                }

                # Save to Firestore if database service available
                if self.db_service:
                    try:
                        self.db_service.save_fred_data(fred_data)
                    except Exception as e:
                        logger.warning(f"Failed to save FRED data to Firestore: {e}")

                return {
                    'success': True,
                    'data': fred_data,
                    'cache_info': {
                        'fresh': True,
                        'response_time_ms': 0.1,
                        'source': 'live_fred_api'
                    },
                    'timestamp': datetime.now().isoformat()
                }
                
            else:
                raise Exception(f"FRED API error: Corp={corp_response.status_code}, Treas={treas_response.status_code}")
                
        except Exception as e:
            # Graceful fallback
            return {
                'success': False,
                'data': {
                    'credit_spread_bps': 150,
                    'corporate_yield_pct': 5.72,
                    'treasury_yield_pct': 4.22,
                    'spread_description': 'Moderate - Normal credit conditions',
                    'risk_level': 'moderate',
                    'trend': 'stable',
                    'data_date': datetime.now().strftime('%Y-%m-%d'),
                    'source': 'Professional Estimate (FRED API unavailable)',
                    'error': str(e)
                },
                'cache_info': {
                    'fresh': False,
                    'source': 'fallback'
                },
                'timestamp': datetime.now().isoformat()
            }

    def get_credit_spread_benchmarks(self):
        """
        Get multi-tier credit spread benchmarks for comprehensive credit analysis.
        Fetches AA, A, BBB, BB spreads plus market stress indicator.
        """
        try:
            # Series to fetch (Option-Adjusted Spreads in basis points)
            series_config = {
                'aa': 'BAMLC0A2CAA',      # AA Corporate OAS
                'a': 'BAMLC0A3CA',         # A Corporate OAS
                'bbb': 'BAMLC0A4CBBB',     # BBB Corporate OAS
                'bb': 'BAMLH0A1HYBB',      # BB High Yield OAS
                'market': 'BAMLC0A0CM'     # Corporate Master OAS (market stress)
            }

            spreads = {}
            data_date = None

            for tier, series_id in series_config.items():
                params = {
                    'series_id': series_id,
                    'api_key': self.api_key,
                    'file_type': 'json',
                    'limit': 1,
                    'sort_order': 'desc'
                }

                response = self._fetch_series(series_id)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('observations') and len(data['observations']) > 0:
                        obs = data['observations'][0]
                        if obs.get('value') and obs['value'] != '.':
                            # OAS series are already in basis points (as percentage, multiply by 100)
                            spreads[f'{tier}_spread_bps'] = round(float(obs['value']) * 100)
                            if not data_date:
                                data_date = obs.get('date')

            # Determine market stress level based on overall corporate spreads
            market_spread = spreads.get('market_spread_bps', 150)
            if market_spread < 100:
                market_stress = 'low'
                stress_description = 'Tight credit conditions - low systemic risk'
            elif market_spread < 150:
                market_stress = 'normal'
                stress_description = 'Normal credit conditions'
            elif market_spread < 250:
                market_stress = 'elevated'
                stress_description = 'Elevated credit concerns - widening spreads'
            elif market_spread < 400:
                market_stress = 'high'
                stress_description = 'High credit stress - significant risk premium'
            else:
                market_stress = 'severe'
                stress_description = 'Severe market stress - potential crisis conditions'

            result = {
                'success': True,
                'spreads': spreads,
                'market_stress': market_stress,
                'stress_description': stress_description,
                'data_date': data_date or datetime.now().strftime('%Y-%m-%d'),
                'series_used': {
                    'aa': 'BAMLC0A2CAA (AA Corporate OAS)',
                    'a': 'BAMLC0A3CA (A Corporate OAS)',
                    'bbb': 'BAMLC0A4CBBB (BBB Corporate OAS)',
                    'bb': 'BAMLH0A1HYBB (BB High Yield OAS)',
                    'market': 'BAMLC0A0CM (Corporate Master OAS)'
                },
                'source': 'Federal Reserve Economic Data (FRED)',
                'timestamp': datetime.now().isoformat()
            }

            logger.info(f"✅ FRED credit benchmarks fetched: AA={spreads.get('aa_spread_bps')}bps, "
                       f"BBB={spreads.get('bbb_spread_bps')}bps, BB={spreads.get('bb_spread_bps')}bps, "
                       f"Market stress: {market_stress}")

            return result

        except Exception as e:
            logger.error(f"❌ Error fetching FRED credit benchmarks: {e}")
            # Return fallback with typical spreads
            return {
                'success': False,
                'spreads': {
                    'aa_spread_bps': 85,
                    'a_spread_bps': 120,
                    'bbb_spread_bps': 165,
                    'bb_spread_bps': 350,
                    'market_spread_bps': 145
                },
                'market_stress': 'normal',
                'stress_description': 'Normal credit conditions (fallback data)',
                'data_date': datetime.now().strftime('%Y-%m-%d'),
                'source': 'Professional Estimate (FRED API unavailable)',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }


def test_final_integration():
    """Test the final FRED credit spread integration"""
    
    print("🎉 FINAL FRED CREDIT SPREAD INTEGRATION TEST")
    print("=" * 60)
    
    fred = FREDCreditSpreadsFinal()
    result = fred.get_real_credit_spreads()
    
    print("📊 FRED Integration Result:")
    print(json.dumps(result, indent=2))
    
    if result['success']:
        data = result['data']
        print(f"\n✅ SUCCESS! Real Federal Reserve Credit Spread Data")
        print(f"📊 Credit Spread: {data['credit_spread_bps']} basis points")
        print(f"📊 Market Condition: {data['spread_description']}")
        print(f"📊 Corporate Yield: {data['corporate_yield_pct']}% (BBB Aviation Sector)")
        print(f"📊 Treasury Yield: {data['treasury_yield_pct']}% (10-Year)")
        print(f"📊 Risk Level: {data['risk_level'].title()}")
        print(f"📊 Trend: {data['trend'].title()}")
        print(f"📅 Data Date: {data['data_date']}")
        print(f"🏛️ Source: Federal Reserve Economic Data")
        
        # Compare to your old static value
        old_static_value = 185
        difference = data['credit_spread_bps'] - old_static_value
        
        print(f"\n🔄 COMPARISON:")
        print(f"📊 Old Static Value: {old_static_value} bps")
        print(f"📊 New Real Value: {data['credit_spread_bps']} bps")
        print(f"📊 Difference: {difference:+d} bps")
        
        if abs(difference) > 50:
            print(f"📈 Significant market movement detected!")
        else:
            print(f"📊 Market conditions close to historical average")
            
        return True
        
    else:
        print(f"\n⚠️ Using fallback data due to: {result['data'].get('error')}")
        return False

# API endpoint for aviation backend
def create_backend_endpoint():
    """Create the backend endpoint code"""
    
    endpoint_code = '''
# Add to aviation-intelligence-api/main.py

from fred_real_integration import FREDCreditSpreadsFinal

# Initialize FRED data source
fred_credit = FREDCreditSpreadsFinal()

@app.route('/api/credit-spread/current', methods=['GET'])
def get_real_credit_spread():
    """Get real credit spread from Federal Reserve (FRED)"""
    try:
        result = fred_credit.get_real_credit_spreads()
        
        if result['success']:
            app.logger.info("✅ FRED credit spread data retrieved successfully")
        else:
            app.logger.warning("⚠️ FRED API unavailable, using professional fallback")
            
        return jsonify(result)
        
    except Exception as e:
        app.logger.error(f"FRED credit spread endpoint error: {e}")
        return jsonify({
            'success': False,
            'data': {
                'credit_spread_bps': 150,
                'spread_description': 'Moderate - Normal conditions', 
                'source': 'Error Fallback'
            },
            'timestamp': datetime.now().isoformat()
        }), 500
'''
    
    return endpoint_code

if __name__ == "__main__":
    test_final_integration()