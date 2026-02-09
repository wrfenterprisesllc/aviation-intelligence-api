"""
SEC EDGAR Handler for Aviation Finance Company Filings
Monitors SEC filings from public aviation companies
"""

import logging
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import json
import time

from app.models.news_article import NewsArticle, SEC_TARGET_COMPANIES
from app.utils.retry import make_request_with_retry

logger = logging.getLogger(__name__)

class SECEdgarHandler:
    """Handles fetching SEC filings from public aviation companies"""
    
    def __init__(self, user_agent: str = None):
        """
        Initialize SEC EDGAR handler
        
        Args:
            user_agent: Custom user agent string (required by SEC)
        """
        self.user_agent = user_agent or 'Aviation-Intelligence-Platform/1.0 (admin@wrfenterprisesllc.com)'
        
        # SEC API base URLs
        self.submissions_base = "https://data.sec.gov/submissions"
        self.filings_base = "https://data.sec.gov/api/xbrl/companyconcept"
        
        # Configure requests session with required headers
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.user_agent,
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip, deflate',
            'Host': 'data.sec.gov'
        })
        
        # Filing types we're interested in
        self.target_filings = {
            '10-K': 'Annual Report',
            '10-Q': 'Quarterly Report', 
            '8-K': 'Current Report',
            '10-K/A': 'Annual Report Amendment',
            '10-Q/A': 'Quarterly Report Amendment',
            'DEF 14A': 'Proxy Statement',
            'S-1': 'Registration Statement',
            'S-3': 'Registration Statement',
            '424B2': 'Prospectus',
            '424B5': 'Prospectus'
        }
        
        # Rate limiting (SEC requires 10 requests per second max)
        self.request_delay = 0.11  # Slightly over 0.1 seconds
        self.last_request_time = 0
    
    def fetch_recent_filings(self, days_back: int = 7) -> List[NewsArticle]:
        """
        Fetch recent SEC filings from target aviation companies
        
        Args:
            days_back: Number of days back to search for filings
            
        Returns:
            List of NewsArticle objects for relevant filings
        """
        logger.info("Fetching recent SEC filings for aviation companies")
        
        all_articles = []
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)
        
        for ticker, company_info in SEC_TARGET_COMPANIES.items():
            try:
                logger.debug(f"Fetching filings for {company_info['name']} ({ticker})")
                
                # Get company submissions
                filings = self._get_company_filings(company_info['cik'])
                
                # Filter and parse recent filings
                for filing in filings:
                    try:
                        filing_date = self._parse_sec_date(filing.get('filingDate', ''))
                        
                        # Skip if too old
                        if filing_date < cutoff_date:
                            continue
                        
                        # Skip if not a target filing type
                        form_type = filing.get('form', '').upper()
                        if form_type not in self.target_filings:
                            continue
                        
                        # Create NewsArticle from filing
                        article = self._parse_sec_filing(filing, company_info, ticker)
                        if article:
                            all_articles.append(article)
                    
                    except Exception as e:
                        logger.error(f"Error parsing filing for {ticker}: {e}")
                        continue
                
                # Rate limiting
                self._rate_limit()
                
            except Exception as e:
                logger.error(f"Error fetching filings for {ticker}: {e}")
                continue
        
        logger.info(f"Fetched {len(all_articles)} SEC filings")
        return all_articles
    
    def _get_company_filings(self, cik: str) -> List[Dict[str, Any]]:
        """
        Get filings for a specific company by CIK
        
        Args:
            cik: Central Index Key for the company
            
        Returns:
            List of filing dictionaries
        """
        try:
            # Format CIK (remove leading zeros, then pad to 10 digits)
            clean_cik = str(int(cik)).zfill(10)
            url = f"{self.submissions_base}/CIK{clean_cik}.json"

            self._rate_limit()
            response = make_request_with_retry(
                url,
                method='GET',
                timeout=30,
                max_retries=3,
                headers=dict(self.session.headers)
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Extract recent filings from the response
            filings = []
            filings_data = data.get('filings', {}).get('recent', {})
            
            if filings_data:
                # The SEC API returns parallel arrays for filing data
                forms = filings_data.get('form', [])
                filing_dates = filings_data.get('filingDate', [])
                accession_numbers = filings_data.get('accessionNumber', [])
                primary_documents = filings_data.get('primaryDocument', [])
                
                # Combine into filing records
                for i in range(len(forms)):
                    if i < len(filing_dates) and i < len(accession_numbers):
                        filing = {
                            'form': forms[i] if i < len(forms) else '',
                            'filingDate': filing_dates[i] if i < len(filing_dates) else '',
                            'accessionNumber': accession_numbers[i] if i < len(accession_numbers) else '',
                            'primaryDocument': primary_documents[i] if i < len(primary_documents) else '',
                            'cik': clean_cik
                        }
                        filings.append(filing)
            
            return filings
            
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP error fetching SEC data for CIK {cik}: {e}")
            return []
        except Exception as e:
            logger.error(f"Error parsing SEC data for CIK {cik}: {e}")
            return []
    
    def _parse_sec_filing(self, 
                         filing: Dict[str, Any], 
                         company_info: Dict[str, str], 
                         ticker: str) -> Optional[NewsArticle]:
        """
        Parse SEC filing data into a NewsArticle
        
        Args:
            filing: SEC filing data dictionary
            company_info: Company information dictionary
            ticker: Stock ticker symbol
            
        Returns:
            NewsArticle object or None if parsing fails
        """
        try:
            form_type = filing.get('form', '')
            filing_date = filing.get('filingDate', '')
            accession_number = filing.get('accessionNumber', '')
            primary_document = filing.get('primaryDocument', '')
            
            # Build filing URL
            clean_accession = accession_number.replace('-', '')
            filing_url = f"https://www.sec.gov/Archives/edgar/data/{filing['cik']}/{clean_accession}/{primary_document}"
            
            # Create title
            form_description = self.target_filings.get(form_type.upper(), form_type)
            title = f"{company_info['name']} ({ticker}) Filed {form_type}: {form_description}"
            
            # Create summary
            summary = f"{company_info['name']} has filed a {form_type} ({form_description}) with the SEC on {filing_date}. This filing may contain important information about the company's financial performance, operations, and strategic direction in the aviation finance sector."
            
            # Create content with more details
            content = f"""
SEC Filing Details:
- Company: {company_info['name']} ({ticker})
- Form Type: {form_type} - {form_description}
- Filing Date: {filing_date}
- Accession Number: {accession_number}
- Primary Document: {primary_document}

This SEC filing was automatically identified as relevant to the aviation finance industry. {form_type} forms typically contain:

{self._get_form_description(form_type)}

For complete filing details, view the original document on the SEC website.
            """.strip()
            
            # Parse filing date
            try:
                published_at = self._parse_sec_date(filing_date)
            except:
                published_at = datetime.utcnow()
            
            # Generate tags
            tags = [
                'sec_filing',
                f'form_{form_type.lower().replace("-", "_")}',
                f'company_{ticker.lower()}',
                'aviation_finance',
                'regulatory_disclosure'
            ]
            
            # Add form-specific tags
            if form_type in ['10-K', '10-K/A']:
                tags.append('annual_report')
            elif form_type in ['10-Q', '10-Q/A']:
                tags.append('quarterly_report')
            elif form_type == '8-K':
                tags.append('current_report')
            elif 'DEF 14A' in form_type:
                tags.append('proxy_statement')
            
            # Create entities
            entities = [
                {
                    'type': 'company',
                    'name': company_info['name'],
                    'ticker': ticker,
                    'cik': filing['cik'],
                    'confidence': 1.0
                },
                {
                    'type': 'filing_type',
                    'name': form_type,
                    'description': form_description,
                    'confidence': 1.0
                }
            ]
            
            # Build raw payload
            raw_payload = {
                'sec_filing': filing,
                'company_info': company_info,
                'ticker': ticker,
                'filing_url': filing_url,
                'edgar_url': f"https://www.sec.gov/edgar/browse/?CIK={filing['cik']}"
            }
            
            # Create NewsArticle
            article = NewsArticle(
                source='sec_edgar',
                source_url=filing_url,
                title=title,
                summary=summary,
                content=content,
                published_at=published_at,
                ingested_at=datetime.utcnow(),
                tags=tags,
                entities=entities,
                raw_payload=raw_payload
            )
            
            return article
            
        except Exception as e:
            logger.error(f"Error parsing SEC filing: {e}")
            return None
    
    def _parse_sec_date(self, date_string: str) -> datetime:
        """
        Parse SEC date format (YYYY-MM-DD) to datetime
        
        Args:
            date_string: Date string in YYYY-MM-DD format
            
        Returns:
            datetime object
        """
        try:
            return datetime.strptime(date_string, '%Y-%m-%d')
        except ValueError:
            # Fallback to current time if parsing fails
            logger.warning(f"Could not parse SEC date: {date_string}")
            return datetime.utcnow()
    
    def _get_form_description(self, form_type: str) -> str:
        """Get detailed description of SEC form type"""
        descriptions = {
            '10-K': "Annual reports providing a comprehensive overview of the company's financial performance, business operations, risk factors, and market conditions. This includes detailed financial statements, management discussion and analysis, and information about aircraft portfolios and lease agreements.",
            
            '10-Q': "Quarterly reports containing unaudited financial statements and updates on the company's financial position. These reports provide insights into quarterly leasing activity, portfolio changes, and market conditions affecting the aviation finance sector.",
            
            '8-K': "Current reports filed to announce significant events or corporate changes that may be important to shareholders. This could include acquisitions, dispositions of aircraft, changes in executive leadership, or material agreements.",
            
            'DEF 14A': "Proxy statements filed before annual shareholder meetings, containing information about executive compensation, board members, and matters to be voted on by shareholders.",
            
            'S-1': "Registration statements for new securities offerings, which may indicate company expansion plans or capital raising activities.",
            
            '424B2': "Prospectus supplements providing details about specific securities offerings or debt instruments."
        }
        
        return descriptions.get(form_type, "SEC regulatory filing containing information relevant to company operations and financial performance.")
    
    def _rate_limit(self):
        """Implement rate limiting for SEC API requests"""
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        
        self.last_request_time = time.time()
    
    def get_company_info(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get basic company information from SEC
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Company information dictionary or None
        """
        if ticker.upper() not in SEC_TARGET_COMPANIES:
            logger.warning(f"Ticker {ticker} not in target companies")
            return None
        
        company_info = SEC_TARGET_COMPANIES[ticker.upper()]
        
        try:
            # Get company facts
            self._rate_limit()
            cik = company_info['cik']
            clean_cik = str(int(cik)).zfill(10)
            
            url = f"{self.submissions_base}/CIK{clean_cik}.json"
            response = make_request_with_retry(
                url,
                method='GET',
                timeout=30,
                max_retries=3,
                headers=dict(self.session.headers)
            )
            response.raise_for_status()

            data = response.json()

            return {
                'name': data.get('name', company_info['name']),
                'cik': clean_cik,
                'ticker': ticker.upper(),
                'sic': data.get('sic', ''),
                'sic_description': data.get('sicDescription', ''),
                'business_address': data.get('addresses', {}).get('business', {}),
                'former_names': data.get('formerNames', []),
                'recent_filings_count': len(data.get('filings', {}).get('recent', {}).get('form', []))
            }
            
        except Exception as e:
            logger.error(f"Error getting company info for {ticker}: {e}")
            return None
    
    def test_sec_connection(self) -> Dict[str, Any]:
        """
        Test SEC API connection
        
        Returns:
            Dictionary with test results
        """
        try:
            # Test with a known company (AerCap)
            test_cik = SEC_TARGET_COMPANIES['AER']['cik']
            clean_cik = str(int(test_cik)).zfill(10)
            
            url = f"{self.submissions_base}/CIK{clean_cik}.json"

            self._rate_limit()
            response = make_request_with_retry(
                url,
                method='GET',
                timeout=30,
                max_retries=3,
                headers=dict(self.session.headers)
            )
            response.raise_for_status()
            
            data = response.json()
            
            return {
                'success': True,
                'company_name': data.get('name', ''),
                'cik': clean_cik,
                'recent_filings_count': len(data.get('filings', {}).get('recent', {}).get('form', [])),
                'message': 'SEC EDGAR connection successful'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': 'SEC EDGAR connection failed'
            }