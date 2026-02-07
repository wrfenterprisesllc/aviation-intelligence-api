"""
Carrier Financial Model
Stores airline financial data from BTS Form 41 filings
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, Any, Optional
import hashlib


@dataclass
class CarrierFinancial:
    """
    Airline financial data model for Firestore storage
    Data sourced from DOT Bureau of Transportation Statistics (BTS) Form 41

    Attributes:
        carrier_code: DOT carrier code (e.g., 'UA', 'DL', 'AA')
        carrier_name: Full carrier name (e.g., 'United Airlines')
        ticker: Stock ticker symbol (e.g., 'UAL')
        period: Reporting period (e.g., 'Q4-2025', 'FY-2025')
        period_type: 'quarterly' or 'annual'
        period_end_date: End date of the reporting period

        Financial metrics (from BTS Schedule P-1.2):
        operating_revenue: Total operating revenue ($)
        passenger_revenue: Revenue from passenger operations ($)
        cargo_revenue: Revenue from cargo operations ($)
        other_revenue: Other operating revenue ($)
        operating_expenses: Total operating expenses ($)
        fuel_expense: Fuel and oil expense ($)
        labor_expense: Wages, salaries, and benefits ($)
        operating_income: Operating revenue minus expenses ($)
        net_income: Net income after all expenses ($)

        Calculated metrics:
        operating_margin_pct: Operating income / Operating revenue (%)
        ebitda: Estimated EBITDA ($)

        Traffic metrics (from BTS T-100):
        asm: Available Seat Miles
        rpm: Revenue Passenger Miles
        load_factor_pct: RPM / ASM (%)
        rasm_cents: Revenue per ASM (cents)
        casm_cents: Cost per ASM (cents)

        Metadata:
        data_source: Source identifier (e.g., 'bts_form41')
        ingested_at: When this data was collected
        bts_report_date: Date of the BTS report
    """

    carrier_code: str
    carrier_name: str
    ticker: str
    period: str
    period_type: str
    period_end_date: datetime

    # Income Statement (from P-1.2)
    operating_revenue: float
    passenger_revenue: float
    cargo_revenue: float
    other_revenue: float
    operating_expenses: float
    fuel_expense: float
    labor_expense: float
    operating_income: float
    net_income: float

    # Calculated Metrics
    operating_margin_pct: float
    ebitda: Optional[float] = None

    # Traffic Metrics (from T-100)
    asm: Optional[float] = None
    rpm: Optional[float] = None
    load_factor_pct: Optional[float] = None
    rasm_cents: Optional[float] = None
    casm_cents: Optional[float] = None

    # Metadata
    data_source: str = 'bts_form41'
    ingested_at: Optional[datetime] = None
    bts_report_date: Optional[datetime] = None
    id: Optional[str] = None

    def __post_init__(self):
        """Post-initialization processing"""
        if not self.ingested_at:
            self.ingested_at = datetime.utcnow()

        # Generate ID if not provided
        if not self.id:
            self.id = self.generate_id()

        # Calculate derived metrics if traffic data available
        if self.asm and self.rpm:
            if not self.load_factor_pct:
                self.load_factor_pct = round((self.rpm / self.asm) * 100, 1)

        if self.operating_revenue and self.asm:
            if not self.rasm_cents:
                self.rasm_cents = round((self.operating_revenue / self.asm) * 100, 2)

        if self.operating_expenses and self.asm:
            if not self.casm_cents:
                self.casm_cents = round((self.operating_expenses / self.asm) * 100, 2)

    def generate_id(self) -> str:
        """Generate a consistent ID based on carrier_code and period"""
        unique_key = f"{self.carrier_code}_{self.period}"
        return hashlib.md5(unique_key.encode('utf-8')).hexdigest()

    def to_firestore_dict(self) -> Dict[str, Any]:
        """Convert to Firestore-compatible dictionary"""
        data = asdict(self)

        # Remove the id field for Firestore document creation
        if 'id' in data and data['id']:
            data.pop('id')

        return data

    @classmethod
    def from_firestore_dict(cls, doc_id: str, data: Dict[str, Any]) -> 'CarrierFinancial':
        """Create CarrierFinancial from Firestore document data"""
        # Handle Firestore timestamp conversion for period_end_date
        if 'period_end_date' in data:
            if hasattr(data['period_end_date'], 'timestamp'):
                data['period_end_date'] = datetime.fromtimestamp(data['period_end_date'].timestamp())
            elif isinstance(data['period_end_date'], str):
                try:
                    data['period_end_date'] = datetime.fromisoformat(data['period_end_date'].replace('Z', '+00:00'))
                except:
                    data['period_end_date'] = datetime.utcnow()

        # Handle ingested_at
        if 'ingested_at' in data:
            if hasattr(data['ingested_at'], 'timestamp'):
                data['ingested_at'] = datetime.fromtimestamp(data['ingested_at'].timestamp())
            elif isinstance(data['ingested_at'], str):
                try:
                    data['ingested_at'] = datetime.fromisoformat(data['ingested_at'].replace('Z', '+00:00'))
                except:
                    data['ingested_at'] = datetime.utcnow()

        # Handle bts_report_date
        if 'bts_report_date' in data and data['bts_report_date']:
            if hasattr(data['bts_report_date'], 'timestamp'):
                data['bts_report_date'] = datetime.fromtimestamp(data['bts_report_date'].timestamp())
            elif isinstance(data['bts_report_date'], str):
                try:
                    data['bts_report_date'] = datetime.fromisoformat(data['bts_report_date'].replace('Z', '+00:00'))
                except:
                    data['bts_report_date'] = None

        # Add the document ID
        data['id'] = doc_id

        # Filter to valid fields only
        valid_fields = {
            'carrier_code', 'carrier_name', 'ticker', 'period', 'period_type',
            'period_end_date', 'operating_revenue', 'passenger_revenue',
            'cargo_revenue', 'other_revenue', 'operating_expenses',
            'fuel_expense', 'labor_expense', 'operating_income', 'net_income',
            'operating_margin_pct', 'ebitda', 'asm', 'rpm', 'load_factor_pct',
            'rasm_cents', 'casm_cents', 'data_source', 'ingested_at',
            'bts_report_date', 'id'
        }
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}

        # Set defaults for optional fields
        defaults = {
            'ebitda': None,
            'asm': None,
            'rpm': None,
            'load_factor_pct': None,
            'rasm_cents': None,
            'casm_cents': None,
            'bts_report_date': None,
            'data_source': 'bts_form41'
        }

        for field, default_value in defaults.items():
            if field not in filtered_data:
                filtered_data[field] = default_value

        return cls(**filtered_data)

    def to_summary_dict(self) -> Dict[str, Any]:
        """Return a summary for display/reporting"""
        return {
            'carrier': f"{self.carrier_name} ({self.carrier_code})",
            'ticker': self.ticker,
            'period': self.period,
            'operating_revenue_billions': round(self.operating_revenue / 1_000_000_000, 2) if self.operating_revenue else None,
            'operating_margin_pct': self.operating_margin_pct,
            'load_factor_pct': self.load_factor_pct,
            'rasm_cents': self.rasm_cents,
            'casm_cents': self.casm_cents,
            'net_income_millions': round(self.net_income / 1_000_000, 1) if self.net_income else None
        }


# Carrier code mappings for major US airlines
CARRIER_MAPPINGS = {
    'UA': {'name': 'United Airlines', 'ticker': 'UAL', 'cik': '0000100517'},
    'DL': {'name': 'Delta Air Lines', 'ticker': 'DAL', 'cik': '0000027904'},
    'AA': {'name': 'American Airlines', 'ticker': 'AAL', 'cik': '0000006201'},
    'WN': {'name': 'Southwest Airlines', 'ticker': 'LUV', 'cik': '0000092380'},
    'B6': {'name': 'JetBlue Airways', 'ticker': 'JBLU', 'cik': '0001158463'},
    'AS': {'name': 'Alaska Airlines', 'ticker': 'ALK', 'cik': '0000766421'},
    'NK': {'name': 'Spirit Airlines', 'ticker': 'SAVE', 'cik': '0001498710'},
    'G4': {'name': 'Allegiant Air', 'ticker': 'ALGT', 'cik': '0001362468'},
    'HA': {'name': 'Hawaiian Airlines', 'ticker': 'HA', 'cik': '0000046619'},
    'F9': {'name': 'Frontier Airlines', 'ticker': 'ULCC', 'cik': '0001810997'}
}
