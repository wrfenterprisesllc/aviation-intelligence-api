"""
Defense Contracts Handler for DoD Contract Announcements
Fetches daily defense contract awards from defense.gov
"""

import logging
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import re
import time
import random
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class DefenseContractsHandler:
    """Handles fetching defense contract announcements from defense.gov"""

    def __init__(self):
        """Initialize Defense Contracts handler"""
        self.base_url = "https://www.defense.gov/News/Contracts/"
        self.article_base = "https://www.defense.gov"

        # Rotating user agents to avoid blocking
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        ]

        # Configure requests session
        self.session = requests.Session()
        self._rotate_user_agent()

        # Aviation-related keywords for filtering relevant contracts
        self.aviation_keywords = [
            'aircraft', 'aviation', 'airplane', 'jet', 'helicopter',
            'f-35', 'f-15', 'f-16', 'f-18', 'f-22', 'c-130', 'c-17', 'kc-46',
            'boeing', 'lockheed', 'northrop', 'raytheon', 'general dynamics',
            'general atomics', 'pratt & whitney', 'ge aviation', 'rolls-royce',
            'engine', 'propulsion', 'airframe', 'avionics', 'radar',
            'air force', 'navy', 'aerial', 'flight', 'pilot',
            'drone', 'uav', 'unmanned', 'mq-9', 'rq-4',
            'tanker', 'refueling', 'cargo', 'transport',
            'hawkeye', 'e-2d', 'awacs', 'surveillance',
            'missile', 'munition', 'weapon system'
        ]

        # Military branches
        self.military_branches = ['NAVY', 'AIR FORCE', 'ARMY', 'DEFENSE LOGISTICS AGENCY',
                                   'MISSILE DEFENSE AGENCY', 'MARINE CORPS', 'SPACE FORCE']

    def _rotate_user_agent(self):
        """Rotate to a random user agent"""
        ua = random.choice(self.user_agents)
        self.session.headers.update({
            'User-Agent': ua,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1'
        })

    def _make_request(self, url: str, max_retries: int = 3) -> Optional[requests.Response]:
        """
        Make HTTP request with retry logic and user agent rotation

        Args:
            url: URL to fetch
            max_retries: Maximum number of retry attempts

        Returns:
            Response object or None if all retries failed
        """
        for attempt in range(max_retries):
            try:
                self._rotate_user_agent()

                # Add random delay to appear more human-like
                delay = random.uniform(2, 5) if attempt > 0 else random.uniform(0.5, 1.5)
                time.sleep(delay)

                response = self.session.get(url, timeout=45)

                if response.status_code == 200:
                    # Add extra delay after successful request to avoid rate limiting
                    time.sleep(random.uniform(1, 2))
                    return response
                elif response.status_code == 403:
                    logger.warning(f"403 Forbidden on attempt {attempt + 1} for {url}")
                    # Longer delay on 403
                    time.sleep(random.uniform(3, 6))
                    continue
                else:
                    response.raise_for_status()

            except requests.exceptions.RequestException as e:
                logger.warning(f"Request failed on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(random.uniform(3, 6))
                continue

        return None

    def fetch_recent_contracts(self, days_back: int = 7, aviation_only: bool = True) -> List[Dict[str, Any]]:
        """
        Fetch recent defense contracts from defense.gov

        Args:
            days_back: Number of days back to fetch contracts
            aviation_only: If True, only return aviation-related contracts

        Returns:
            List of contract dictionaries
        """
        logger.info(f"Fetching defense contracts from last {days_back} days")

        all_contracts = []

        try:
            # Get the contracts listing page
            contract_links = self._get_contract_page_links(days_back)

            logger.info(f"Found {len(contract_links)} contract pages to process")

            for link_info in contract_links:
                try:
                    contracts = self._fetch_contracts_from_page(link_info['href'], link_info['date'])

                    if aviation_only:
                        contracts = [c for c in contracts if self._is_aviation_related(c)]

                    all_contracts.extend(contracts)
                    logger.info(f"Fetched {len(contracts)} contracts from {link_info['date']}")

                except Exception as e:
                    logger.error(f"Error fetching contracts from {link_info['href']}: {e}")
                    continue

            logger.info(f"Total contracts fetched: {len(all_contracts)}")
            return all_contracts

        except Exception as e:
            logger.error(f"Error fetching defense contracts: {e}")
            return []

    def _get_contract_page_links(self, days_back: int) -> List[Dict[str, str]]:
        """
        Get links to individual contract pages from the contracts listing

        Args:
            days_back: Number of days back to include

        Returns:
            List of dicts with 'href' and 'date' keys
        """
        try:
            response = self._make_request(self.base_url)
            if not response:
                logger.error("Failed to fetch contracts listing page after retries")
                return []

            soup = BeautifulSoup(response.text, 'html.parser')

            links = []
            cutoff_date = datetime.now() - timedelta(days=days_back)

            # Find all contract page links
            for a_tag in soup.find_all('a'):
                text = a_tag.get_text(strip=True)
                href = a_tag.get('href', '')

                if 'Contracts for' in text and '/News/Contracts/Contract/Article/' in href:
                    # Parse the date from the text
                    date_str = self._extract_date_from_text(text)

                    if date_str:
                        contract_date = self._parse_contract_date(date_str)

                        if contract_date and contract_date >= cutoff_date:
                            full_href = href if href.startswith('http') else f"{self.article_base}{href}"
                            links.append({
                                'href': full_href,
                                'date': date_str,
                                'parsed_date': contract_date
                            })

            # Sort by date (newest first)
            links.sort(key=lambda x: x.get('parsed_date', datetime.min), reverse=True)

            return links

        except Exception as e:
            logger.error(f"Error getting contract page links: {e}")
            return []

    def _fetch_contracts_from_page(self, url: str, date_str: str) -> List[Dict[str, Any]]:
        """
        Fetch individual contracts from a contract page

        Args:
            url: URL of the contracts page
            date_str: Date string for this contracts page

        Returns:
            List of contract dictionaries
        """
        try:
            response = self._make_request(url)
            if not response:
                logger.error(f"Failed to fetch contract page: {url}")
                return []

            soup = BeautifulSoup(response.text, 'html.parser')

            # Get the main content area
            content = soup.get_text(separator='\n')

            contracts = []
            current_branch = None
            current_contract_text = []

            lines = content.split('\n')

            for line in lines:
                line = line.strip()

                if not line:
                    continue

                # Check if this is a branch header
                upper_line = line.upper()
                if upper_line in self.military_branches:
                    # Save previous contract if exists
                    if current_contract_text and current_branch:
                        contract = self._parse_contract_text(
                            '\n'.join(current_contract_text),
                            current_branch,
                            date_str,
                            url
                        )
                        if contract:
                            contracts.append(contract)

                    current_branch = line
                    current_contract_text = []
                    continue

                # Check if this is a new contract (starts with company name pattern)
                if current_branch and self._is_contract_start(line):
                    # Save previous contract
                    if current_contract_text:
                        contract = self._parse_contract_text(
                            '\n'.join(current_contract_text),
                            current_branch,
                            date_str,
                            url
                        )
                        if contract:
                            contracts.append(contract)

                    current_contract_text = [line]
                elif current_branch and current_contract_text:
                    # Continue current contract
                    current_contract_text.append(line)

            # Don't forget the last contract
            if current_contract_text and current_branch:
                contract = self._parse_contract_text(
                    '\n'.join(current_contract_text),
                    current_branch,
                    date_str,
                    url
                )
                if contract:
                    contracts.append(contract)

            return contracts

        except Exception as e:
            logger.error(f"Error fetching contracts from page {url}: {e}")
            return []

    def _is_contract_start(self, line: str) -> bool:
        """
        Check if a line starts a new contract (company name pattern)

        Args:
            line: Text line to check

        Returns:
            True if this appears to be the start of a contract
        """
        # Contracts typically start with "Company Name, City, State" pattern
        # or "Company Name Inc., City, State" pattern

        # Must have a comma (for city/state)
        if ',' not in line:
            return False

        # Must have a dollar amount somewhere in the contract
        # This helps filter out headers and navigation

        # Check for company name patterns
        company_patterns = [
            r'^[A-Z][A-Za-z\s\.\&\-]+(?:Inc\.|Corp\.|LLC|Co\.|Ltd\.)?,'
        ]

        for pattern in company_patterns:
            if re.match(pattern, line):
                return True

        return False

    def _parse_contract_text(self, text: str, branch: str, date_str: str, source_url: str) -> Optional[Dict[str, Any]]:
        """
        Parse contract text into structured data

        Args:
            text: Full contract text
            branch: Military branch (e.g., "NAVY", "AIR FORCE")
            date_str: Date string
            source_url: Source URL

        Returns:
            Contract dictionary or None if parsing fails
        """
        try:
            # Extract contractor name (first part before city/state)
            contractor_match = re.match(r'^([^,]+(?:Inc\.|Corp\.|LLC|Co\.|Ltd\.)?)', text)
            contractor = contractor_match.group(1).strip() if contractor_match else 'Unknown Contractor'

            # Extract contract value
            value_match = re.search(r'\$([0-9,]+(?:\.[0-9]+)?)\s*(?:million|billion)?', text, re.IGNORECASE)
            if value_match:
                value_str = value_match.group(0)
                value_amount = self._parse_contract_value(value_str)
            else:
                value_amount = 0

            # Extract contract number
            contract_num_match = re.search(r'\(([A-Z0-9\-]+(?:-[A-Z0-9\-]+)+)\)', text)
            contract_number = contract_num_match.group(1) if contract_num_match else None

            # Extract location
            location_match = re.search(r'Work will be performed (?:in|at)\s+([^,]+(?:,[^,]+)?)', text, re.IGNORECASE)
            work_location = location_match.group(1).strip() if location_match else None

            # Extract completion date
            completion_match = re.search(r'(?:completed|completion) (?:by |date[:\s]+)?([A-Za-z]+\.?\s+\d{1,2},?\s+\d{4}|\d{4})', text, re.IGNORECASE)
            completion_date = completion_match.group(1).strip() if completion_match else None

            # Extract contracting activity
            activity_match = re.search(r'(?:contracting activity|issued by)[:\s]+([^\.]+)', text, re.IGNORECASE)
            contracting_activity = activity_match.group(1).strip() if activity_match else None

            # Determine contract type
            contract_type = self._determine_contract_type(text)

            # Parse the announcement date
            parsed_date = self._parse_contract_date(date_str)

            contract = {
                'contractor': contractor,
                'branch': branch,
                'contract_value': value_amount,
                'contract_value_formatted': self._format_contract_value(value_amount),
                'contract_number': contract_number,
                'work_location': work_location,
                'completion_date': completion_date,
                'contracting_activity': contracting_activity,
                'contract_type': contract_type,
                'description': text[:1000],  # First 1000 chars of description
                'full_text': text,
                'announcement_date': parsed_date.strftime('%Y-%m-%d') if parsed_date else date_str,
                'source_url': source_url,
                'source': 'defense.gov',
                'ingested_at': datetime.utcnow().isoformat()
            }

            return contract

        except Exception as e:
            logger.error(f"Error parsing contract text: {e}")
            return None

    def _parse_contract_value(self, value_str: str) -> float:
        """
        Parse contract value string to float

        Args:
            value_str: Value string like "$198,000,000" or "$15.6 million"

        Returns:
            Contract value as float
        """
        try:
            # Remove $ and commas
            clean = value_str.replace('$', '').replace(',', '').strip()

            # Check for million/billion
            multiplier = 1
            if 'billion' in value_str.lower():
                multiplier = 1_000_000_000
                clean = re.sub(r'\s*billion.*', '', clean, flags=re.IGNORECASE)
            elif 'million' in value_str.lower():
                multiplier = 1_000_000
                clean = re.sub(r'\s*million.*', '', clean, flags=re.IGNORECASE)

            value = float(clean) * multiplier
            return value

        except Exception as e:
            logger.warning(f"Could not parse contract value '{value_str}': {e}")
            return 0

    def _format_contract_value(self, value: float) -> str:
        """Format contract value for display"""
        if value >= 1_000_000_000:
            return f"${value/1_000_000_000:.2f}B"
        elif value >= 1_000_000:
            return f"${value/1_000_000:.1f}M"
        elif value >= 1_000:
            return f"${value/1_000:.1f}K"
        else:
            return f"${value:,.0f}"

    def _determine_contract_type(self, text: str) -> str:
        """Determine contract type from description"""
        text_lower = text.lower()

        if 'modification' in text_lower:
            return 'modification'
        elif 'delivery order' in text_lower:
            return 'delivery_order'
        elif 'task order' in text_lower:
            return 'task_order'
        elif 'indefinite-quantity' in text_lower or 'idiq' in text_lower:
            return 'idiq'
        elif 'firm-fixed-price' in text_lower:
            return 'firm_fixed_price'
        elif 'cost-plus' in text_lower:
            return 'cost_plus'
        else:
            return 'contract'

    def _is_aviation_related(self, contract: Dict[str, Any]) -> bool:
        """
        Check if a contract is aviation-related

        Args:
            contract: Contract dictionary

        Returns:
            True if aviation-related
        """
        text = (contract.get('full_text', '') + ' ' + contract.get('contractor', '')).lower()

        for keyword in self.aviation_keywords:
            if keyword.lower() in text:
                return True

        return False

    def _extract_date_from_text(self, text: str) -> Optional[str]:
        """
        Extract date from contract page title

        Args:
            text: Text like "Contracts for Feb. 6, 2026"

        Returns:
            Date string or None
        """
        # Pattern for "Contracts for Feb. 6, 2026"
        match = re.search(r'Contracts for\s+(.+)', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None

    def _parse_contract_date(self, date_str: str) -> Optional[datetime]:
        """
        Parse contract date string to datetime

        Args:
            date_str: Date string like "Feb. 6, 2026" or "Feb. 2, 2026, Through Feb. 4, 2026"

        Returns:
            datetime object or None
        """
        try:
            # Handle date ranges - take the first date
            if 'Through' in date_str or 'through' in date_str:
                date_str = re.split(r',?\s*[Tt]hrough', date_str)[0].strip()

            # Try various date formats
            formats = [
                '%b. %d, %Y',   # Feb. 6, 2026
                '%B %d, %Y',   # February 6, 2026
                '%b %d, %Y',   # Feb 6, 2026
                '%m/%d/%Y',    # 02/06/2026
            ]

            for fmt in formats:
                try:
                    return datetime.strptime(date_str.strip(), fmt)
                except ValueError:
                    continue

            logger.warning(f"Could not parse date: {date_str}")
            return None

        except Exception as e:
            logger.error(f"Error parsing date '{date_str}': {e}")
            return None

    def get_aviation_contract_summary(self, contracts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate summary statistics for aviation contracts

        Args:
            contracts: List of contract dictionaries

        Returns:
            Summary dictionary
        """
        if not contracts:
            return {
                'total_contracts': 0,
                'total_value': 0,
                'by_branch': {},
                'by_contractor': {},
                'avg_contract_value': 0
            }

        total_value = sum(c.get('contract_value', 0) for c in contracts)

        # Group by branch
        by_branch = {}
        for c in contracts:
            branch = c.get('branch', 'Unknown')
            if branch not in by_branch:
                by_branch[branch] = {'count': 0, 'value': 0}
            by_branch[branch]['count'] += 1
            by_branch[branch]['value'] += c.get('contract_value', 0)

        # Group by contractor
        by_contractor = {}
        for c in contracts:
            contractor = c.get('contractor', 'Unknown')
            if contractor not in by_contractor:
                by_contractor[contractor] = {'count': 0, 'value': 0}
            by_contractor[contractor]['count'] += 1
            by_contractor[contractor]['value'] += c.get('contract_value', 0)

        # Sort by total value
        by_contractor = dict(sorted(
            by_contractor.items(),
            key=lambda x: x[1]['value'],
            reverse=True
        )[:10])  # Top 10 contractors

        return {
            'total_contracts': len(contracts),
            'total_value': total_value,
            'total_value_formatted': self._format_contract_value(total_value),
            'by_branch': by_branch,
            'top_contractors': by_contractor,
            'avg_contract_value': total_value / len(contracts) if contracts else 0,
            'avg_contract_value_formatted': self._format_contract_value(total_value / len(contracts)) if contracts else '$0'
        }

    def test_connection(self) -> Dict[str, Any]:
        """
        Test connection to defense.gov

        Returns:
            Test result dictionary
        """
        try:
            response = self._make_request(self.base_url)

            if response and response.status_code == 200:
                # Check if we got the contracts page
                if 'Contracts' in response.text:
                    return {
                        'success': True,
                        'status_code': response.status_code,
                        'message': 'Successfully connected to defense.gov contracts page'
                    }
                else:
                    return {
                        'success': False,
                        'status_code': response.status_code,
                        'message': 'Connected but contracts page not found'
                    }
            else:
                return {
                    'success': False,
                    'status_code': response.status_code if response else None,
                    'message': 'Failed to connect after retries (403 Forbidden likely)'
                }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': f'Failed to connect to defense.gov: {e}'
            }
