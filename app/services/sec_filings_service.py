#!/usr/bin/env python3
"""
SEC Filings Service - Fetch airline SEC filings and financial disclosures
Uses SEC EDGAR API to retrieve 10-K, 10-Q, and 8-K filings
"""

import logging
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class SECFilingsService:
    """Service for fetching SEC filings for airlines"""

    # SEC EDGAR API base URL
    SEC_API_BASE = "https://data.sec.gov"

    # Airline CIK (Central Index Key) mapping
    AIRLINE_CIKS = {
        'United Airlines': '0001045520',    # United Airlines Holdings
        'Delta Air Lines': '0000027904',    # Delta Air Lines Inc
        'American Airlines': '0001141166',   # American Airlines Group Inc
        'Southwest Airlines': '0000092380',  # Southwest Airlines Co
        'JetBlue Airways': '0001158463',    # JetBlue Airways Corp
        'Alaska Airlines': '0000766421',    # Alaska Air Group Inc
        'Spirit Airlines': '0001498710',    # Spirit Airlines Inc
        'Hawaiian Airlines': '0001171869',   # Hawaiian Holdings Inc
        'Allegiant Air': '0001362630'       # Allegiant Travel Co
    }

    # Filing types to fetch
    FILING_TYPES = ['10-K', '10-Q', '8-K', 'DEF 14A']

    def __init__(self, user_agent: str = "Aviation Intelligence API contact@wrfenterprises.com"):
        """
        Initialize SEC filings service

        Args:
            user_agent: User agent string for SEC API (required by SEC)
        """
        self.user_agent = user_agent
        self.headers = {
            'User-Agent': user_agent,
            'Accept-Encoding': 'gzip, deflate',
            'Host': 'data.sec.gov'
        }
        logger.info("✅ SEC filings service initialized")

    def get_cik(self, airline_name: str) -> Optional[str]:
        """
        Get SEC CIK number for an airline

        Args:
            airline_name: Full airline name

        Returns:
            CIK number or None if not found
        """
        # Try exact match
        if airline_name in self.AIRLINE_CIKS:
            return self.AIRLINE_CIKS[airline_name]

        # Try partial match
        for name, cik in self.AIRLINE_CIKS.items():
            if airline_name.lower() in name.lower() or name.lower() in airline_name.lower():
                logger.info(f"📍 Matched '{airline_name}' to CIK {cik}")
                return cik

        logger.warning(f"⚠️ No CIK found for airline: {airline_name}")
        return None

    def get_recent_filings(
        self,
        airline_name: str,
        filing_types: Optional[List[str]] = None,
        max_results: int = 10
    ) -> Optional[Dict]:
        """
        Fetch recent SEC filings for an airline

        Args:
            airline_name: Airline name (e.g., "Delta Air Lines")
            filing_types: List of filing types to include (default: all)
            max_results: Maximum number of filings to return

        Returns:
            Dictionary with filing data or None if fetch failed
        """
        try:
            cik = self.get_cik(airline_name)
            if not cik:
                return None

            if filing_types is None:
                filing_types = self.FILING_TYPES

            logger.info(f"📄 Fetching SEC filings for {airline_name} (CIK: {cik})")

            # Format CIK to 10 digits
            cik_formatted = cik.replace('0000', '').zfill(10)

            # Build API URL for company submissions
            url = f"{self.SEC_API_BASE}/submissions/CIK{cik_formatted}.json"

            # Fetch company filings
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()

            data = response.json()

            # Extract recent filings
            filings_data = data.get('filings', {}).get('recent', {})

            if not filings_data:
                logger.warning(f"⚠️ No filings found for {airline_name}")
                return None

            # Parse filings
            filings = []
            for i in range(len(filings_data.get('accessionNumber', []))):
                filing_type = filings_data['form'][i]

                # Filter by filing type
                if filing_type not in filing_types:
                    continue

                filing = {
                    'filing_type': filing_type,
                    'filing_date': filings_data['filingDate'][i],
                    'accession_number': filings_data['accessionNumber'][i],
                    'primary_document': filings_data['primaryDocument'][i],
                    'description': filings_data.get('primaryDocDescription', [''])[i] if i < len(filings_data.get('primaryDocDescription', [])) else '',
                    'filing_url': self._build_filing_url(
                        cik_formatted,
                        filings_data['accessionNumber'][i],
                        filings_data['primaryDocument'][i]
                    )
                }

                filings.append(filing)

                # Limit results
                if len(filings) >= max_results:
                    break

            result = {
                'airline_name': airline_name,
                'cik': cik,
                'company_name': data.get('name'),
                'sic_description': data.get('sicDescription'),
                'filings': filings,
                'total_count': len(filings),
                'fetched_at': datetime.now().isoformat()
            }

            logger.info(f"✅ Fetched {len(filings)} SEC filings for {airline_name}")
            return result

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error fetching SEC filings for {airline_name}: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected error fetching SEC filings for {airline_name}: {e}")
            return None

    def get_latest_filing_by_type(
        self,
        airline_name: str,
        filing_type: str = "10-K"
    ) -> Optional[Dict]:
        """
        Get the most recent filing of a specific type

        Args:
            airline_name: Airline name
            filing_type: Type of filing (10-K, 10-Q, 8-K, etc.)

        Returns:
            Filing data or None if not found
        """
        filings_data = self.get_recent_filings(
            airline_name=airline_name,
            filing_types=[filing_type],
            max_results=1
        )

        if filings_data and filings_data.get('filings'):
            return filings_data['filings'][0]

        return None

    def get_quarterly_reports(
        self,
        airline_name: str,
        quarters: int = 4
    ) -> Optional[List[Dict]]:
        """
        Get recent quarterly reports (10-Q)

        Args:
            airline_name: Airline name
            quarters: Number of quarters to retrieve

        Returns:
            List of 10-Q filings
        """
        filings_data = self.get_recent_filings(
            airline_name=airline_name,
            filing_types=['10-Q'],
            max_results=quarters
        )

        if filings_data and filings_data.get('filings'):
            return filings_data['filings']

        return []

    def get_annual_reports(
        self,
        airline_name: str,
        years: int = 3
    ) -> Optional[List[Dict]]:
        """
        Get recent annual reports (10-K)

        Args:
            airline_name: Airline name
            years: Number of years to retrieve

        Returns:
            List of 10-K filings
        """
        filings_data = self.get_recent_filings(
            airline_name=airline_name,
            filing_types=['10-K'],
            max_results=years
        )

        if filings_data and filings_data.get('filings'):
            return filings_data['filings']

        return []

    def _build_filing_url(self, cik: str, accession_number: str, primary_document: str) -> str:
        """
        Build URL to SEC filing document

        Args:
            cik: CIK number (10 digits)
            accession_number: Accession number
            primary_document: Primary document filename

        Returns:
            Full URL to filing
        """
        # Remove dashes from accession number for URL
        accession_clean = accession_number.replace('-', '')

        return f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/{primary_document}"
