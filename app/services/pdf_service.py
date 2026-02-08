#!/usr/bin/env python3
"""
PDF Generation Service for Aviation Intelligence Platform

Generates professional PDF reports for:
1. Airline Intelligence Reports - AI-generated credit analysis
2. Deal Evaluation Memos - DCF analysis with IRR, NPV, sensitivity tables
"""

import logging
from datetime import datetime
from io import BytesIO
from typing import Dict, Any, List, Optional

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

logger = logging.getLogger(__name__)


class PDFService:
    """
    Service for generating professional PDF documents.

    Uses ReportLab for pure-Python PDF generation compatible with Cloud Run.
    """

    # Brand colors
    NAVY = HexColor('#0F2B46')
    DARK_GRAY = HexColor('#374151')
    LIGHT_GRAY = HexColor('#9CA3AF')
    GREEN_BG = HexColor('#D1FAE5')
    GREEN_BORDER = HexColor('#10B981')
    GREEN_TEXT = HexColor('#047857')
    RED_BG = HexColor('#FEE2E2')
    RED_BORDER = HexColor('#EF4444')
    RED_TEXT = HexColor('#DC2626')
    LIGHT_BLUE = HexColor('#DBEAFE')
    WHITE = white
    BLACK = black

    # Page setup
    PAGE_WIDTH, PAGE_HEIGHT = letter
    MARGIN = 1 * inch

    def __init__(self):
        """Initialize PDF service with custom styles."""
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
        logger.info("✅ PDF Service initialized")

    def _setup_custom_styles(self):
        """Create custom paragraph styles for reports."""
        # Title styles
        self.styles.add(ParagraphStyle(
            name='CoverTitle',
            parent=self.styles['Title'],
            fontSize=28,
            textColor=self.NAVY,
            spaceAfter=20,
            alignment=TA_CENTER
        ))

        self.styles.add(ParagraphStyle(
            name='CoverSubtitle',
            parent=self.styles['Normal'],
            fontSize=14,
            textColor=self.DARK_GRAY,
            spaceAfter=10,
            alignment=TA_CENTER
        ))

        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading1'],
            fontSize=14,
            textColor=self.NAVY,
            spaceBefore=20,
            spaceAfter=10,
            fontName='Helvetica-Bold'
        ))

        self.styles.add(ParagraphStyle(
            name='ReportBody',
            parent=self.styles['Normal'],
            fontSize=11,
            textColor=self.DARK_GRAY,
            leading=16,
            spaceAfter=8
        ))

        self.styles.add(ParagraphStyle(
            name='SmallText',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=self.LIGHT_GRAY,
            alignment=TA_CENTER
        ))

        self.styles.add(ParagraphStyle(
            name='MetricLabel',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=self.LIGHT_GRAY
        ))

        self.styles.add(ParagraphStyle(
            name='MetricValue',
            parent=self.styles['Normal'],
            fontSize=12,
            textColor=self.NAVY,
            fontName='Helvetica-Bold'
        ))

        self.styles.add(ParagraphStyle(
            name='VerdictPass',
            parent=self.styles['Normal'],
            fontSize=16,
            textColor=self.GREEN_TEXT,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER
        ))

        self.styles.add(ParagraphStyle(
            name='VerdictFail',
            parent=self.styles['Normal'],
            fontSize=16,
            textColor=self.RED_TEXT,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER
        ))

    def _add_header_footer(self, canvas, doc):
        """Add header and footer to each page."""
        canvas.saveState()

        # Header
        canvas.setFillColor(self.NAVY)
        canvas.rect(0, self.PAGE_HEIGHT - 0.5*inch, self.PAGE_WIDTH, 0.5*inch, fill=True)
        canvas.setFillColor(self.WHITE)
        canvas.setFont('Helvetica', 9)
        canvas.drawString(self.MARGIN, self.PAGE_HEIGHT - 0.35*inch, "Aviation Intelligence Platform")
        canvas.drawRightString(self.PAGE_WIDTH - self.MARGIN, self.PAGE_HEIGHT - 0.35*inch,
                              f"Page {doc.page}")

        # Footer
        canvas.setFillColor(self.DARK_GRAY)
        canvas.setFont('Helvetica', 8)
        footer_text = "ai.wrfenterprisesllc.com  •  Confidential"
        canvas.drawCentredString(self.PAGE_WIDTH / 2, 0.35*inch, footer_text)

        canvas.restoreState()

    def _add_cover_header_footer(self, canvas, doc):
        """Add minimal footer to cover page (no header)."""
        canvas.saveState()

        # Footer only
        canvas.setFillColor(self.DARK_GRAY)
        canvas.setFont('Helvetica', 8)
        canvas.drawCentredString(self.PAGE_WIDTH / 2, 0.35*inch, "CONFIDENTIAL")

        canvas.restoreState()

    def _format_currency(self, value: float) -> str:
        """Format number as currency."""
        if value >= 1_000_000:
            return f"${value/1_000_000:,.1f}M"
        elif value >= 1_000:
            return f"${value:,.0f}"
        else:
            return f"${value:.2f}"

    def _format_percentage(self, value: float, decimal_places: int = 2) -> str:
        """Format number as percentage."""
        return f"{value:.{decimal_places}f}%"

    # ========== AIRLINE REPORT PDF ==========

    def generate_airline_report_pdf(self, report_data: Dict[str, Any]) -> bytes:
        """
        Generate PDF for airline intelligence report.

        Args:
            report_data: Report data from Firestore with:
                - subject: Airline name
                - report_type: Type of report
                - generated_at: Generation timestamp
                - period_start, period_end: Date range
                - sections: Dict of section content
                - metadata: Report metadata

        Returns:
            PDF file as bytes
        """
        buffer = BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=self.MARGIN,
            rightMargin=self.MARGIN,
            topMargin=0.75*inch,  # Space for header
            bottomMargin=0.6*inch   # Space for footer
        )

        elements = []

        # Cover page
        elements.extend(self._build_report_cover(report_data))
        elements.append(PageBreak())

        # Metadata section
        elements.extend(self._build_report_metadata(report_data))
        elements.append(Spacer(1, 20))

        # Report sections
        sections = report_data.get('sections', {})
        section_order = [
            ('executive_summary', 'Executive Summary'),
            ('news_analysis', 'News Analysis'),
            ('financial_performance', 'Financial Performance'),
            ('market_data_insights', 'Market Data Insights'),
            ('key_developments', 'Key Developments'),
            ('risk_assessment', 'Risk Assessment'),
            ('outlook_recommendations', 'Outlook & Recommendations')
        ]

        for section_key, section_title in section_order:
            content = sections.get(section_key, '')
            if content:
                elements.extend(self._build_report_section(section_title, content))

        # Build PDF
        doc.build(
            elements,
            onFirstPage=self._add_cover_header_footer,
            onLaterPages=self._add_header_footer
        )

        pdf_bytes = buffer.getvalue()
        buffer.close()

        logger.info(f"📄 Generated airline report PDF: {len(pdf_bytes)} bytes")
        return pdf_bytes

    def _build_report_cover(self, report_data: Dict[str, Any]) -> List:
        """Build cover page elements for airline report."""
        elements = []

        # Add spacing to center content vertically
        elements.append(Spacer(1, 2.5*inch))

        # Company branding
        elements.append(Paragraph("WRF Enterprises LLC", self.styles['CoverSubtitle']))
        elements.append(Spacer(1, 30))

        # Report title
        subject = report_data.get('subject', 'Unknown')
        report_type = report_data.get('report_type', 'Analysis')
        report_type_display = report_type.replace('_', ' ').title()

        title = f"{subject}"
        elements.append(Paragraph(title, self.styles['CoverTitle']))
        elements.append(Paragraph(f"{report_type_display} Report", self.styles['CoverSubtitle']))

        elements.append(Spacer(1, 40))

        # Date range
        period_start = report_data.get('period_start')
        period_end = report_data.get('period_end')
        if period_start and period_end:
            if hasattr(period_start, 'strftime'):
                start_str = period_start.strftime('%B %d, %Y')
                end_str = period_end.strftime('%B %d, %Y')
            else:
                start_str = str(period_start)
                end_str = str(period_end)
            date_range = f"Analysis Period: {start_str} — {end_str}"
            elements.append(Paragraph(date_range, self.styles['CoverSubtitle']))

        # Generation timestamp
        generated_at = report_data.get('generated_at')
        if generated_at:
            if hasattr(generated_at, 'strftime'):
                gen_str = generated_at.strftime('%B %d, %Y at %I:%M %p')
            else:
                gen_str = str(generated_at)
            elements.append(Paragraph(f"Generated: {gen_str}", self.styles['SmallText']))

        elements.append(Spacer(1, 60))

        # Platform subtitle
        elements.append(Paragraph("Aviation Intelligence Platform", self.styles['CoverSubtitle']))

        return elements

    def _build_report_metadata(self, report_data: Dict[str, Any]) -> List:
        """Build metadata section for airline report."""
        elements = []

        elements.append(Paragraph("Report Information", self.styles['SectionHeader']))

        metadata = report_data.get('metadata', {})

        # Build metadata table
        data = [
            ['Subject:', report_data.get('subject', 'N/A')],
            ['Report Type:', report_data.get('report_type', 'N/A').replace('_', ' ').title()],
            ['Articles Analyzed:', str(metadata.get('articles_analyzed', 'N/A'))],
            ['AI Model:', metadata.get('model', 'N/A')]
        ]

        # Add data sources
        sources = []
        if metadata.get('fred_included'):
            sources.append('FRED')
        if metadata.get('stock_included'):
            sources.append('Stock Data')
        if metadata.get('sec_filings_included'):
            sources.append('SEC Filings')
        if metadata.get('bts_included'):
            sources.append('BTS')
        if metadata.get('balance_sheet_included'):
            sources.append('Balance Sheet')
        if sources:
            data.append(['Data Sources:', ', '.join(sources)])

        table = Table(data, colWidths=[1.5*inch, 5*inch])
        table.setStyle(TableStyle([
            ('FONT', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONT', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), self.NAVY),
            ('TEXTCOLOR', (1, 0), (1, -1), self.DARK_GRAY),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))

        elements.append(table)

        # Horizontal rule
        elements.append(Spacer(1, 10))

        return elements

    def _build_report_section(self, title: str, content: str) -> List:
        """Build a report section with title and content."""
        elements = []

        # Section header
        elements.append(Paragraph(title.upper(), self.styles['SectionHeader']))

        # Horizontal rule under header
        hr_table = Table([['']],  colWidths=[6.5*inch])
        hr_table.setStyle(TableStyle([
            ('LINEBELOW', (0, 0), (-1, -1), 1, self.NAVY),
        ]))
        elements.append(hr_table)
        elements.append(Spacer(1, 10))

        # Content paragraphs
        # Split content into paragraphs and render
        paragraphs = content.split('\n\n')
        for para in paragraphs:
            para = para.strip()
            if para:
                # Clean up markdown-style formatting
                para = para.replace('**', '')
                para = para.replace('*', '')
                para = para.replace('###', '')
                para = para.replace('##', '')
                para = para.replace('#', '')

                # Handle bullet points
                if para.startswith('- ') or para.startswith('• '):
                    para = '• ' + para[2:]

                elements.append(Paragraph(para, self.styles['ReportBody']))

        elements.append(Spacer(1, 15))

        return elements

    # ========== DEAL MEMO PDF ==========

    def generate_deal_memo_pdf(
        self,
        deal_params: Dict[str, Any],
        results: Dict[str, Any],
        mode: str = 'evaluate'
    ) -> bytes:
        """
        Generate PDF for deal evaluation memo.

        Args:
            deal_params: Input parameters (aircraft_type, lessee_name, etc.)
            results: Evaluation/pricing results (irr, npv, verdict, sensitivity_matrix)
            mode: 'evaluate' or 'price'

        Returns:
            PDF file as bytes
        """
        buffer = BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=self.MARGIN,
            rightMargin=self.MARGIN,
            topMargin=0.75*inch,
            bottomMargin=0.6*inch
        )

        elements = []

        # Page 1: Cover + Verdict + Summary
        elements.extend(self._build_deal_cover(deal_params, results, mode))
        elements.append(PageBreak())

        # Page 2: Sensitivity Analysis + Cash Flow
        elements.extend(self._build_sensitivity_section(deal_params, results, mode))

        # Build PDF
        doc.build(
            elements,
            onFirstPage=self._add_header_footer,
            onLaterPages=self._add_header_footer
        )

        pdf_bytes = buffer.getvalue()
        buffer.close()

        logger.info(f"📄 Generated deal memo PDF: {len(pdf_bytes)} bytes")
        return pdf_bytes

    def _build_deal_cover(
        self,
        params: Dict[str, Any],
        results: Dict[str, Any],
        mode: str
    ) -> List:
        """Build cover page for deal memo."""
        elements = []

        # Company branding
        elements.append(Paragraph("WRF Enterprises LLC", self.styles['CoverSubtitle']))
        elements.append(Spacer(1, 10))
        elements.append(Paragraph("DEAL EVALUATION MEMO", self.styles['CoverTitle']))
        elements.append(Spacer(1, 20))

        # Aircraft and lessee info
        aircraft_type = params.get('aircraft_type', 'Unknown')
        aircraft_age = params.get('current_age', params.get('aircraft_age', 0))
        lessee_name = params.get('lessee_name', 'Unknown')
        credit_tier = params.get('credit_tier', 'N/A')

        info_text = f"Aircraft: {aircraft_type} ({aircraft_age} years old)"
        elements.append(Paragraph(info_text, self.styles['CoverSubtitle']))
        info_text = f"Lessee: {lessee_name} ({credit_tier})"
        elements.append(Paragraph(info_text, self.styles['CoverSubtitle']))
        info_text = f"Date: {datetime.now().strftime('%B %d, %Y')}"
        elements.append(Paragraph(info_text, self.styles['CoverSubtitle']))

        elements.append(Spacer(1, 25))

        # Verdict box
        elements.extend(self._build_verdict_box(results, mode))
        elements.append(Spacer(1, 25))

        # Deal summary
        elements.extend(self._build_deal_summary(params, results, mode))
        elements.append(Spacer(1, 20))

        # Key metrics
        elements.extend(self._build_key_metrics(params, results, mode))

        return elements

    def _build_verdict_box(self, results: Dict[str, Any], mode: str) -> List:
        """Build the verdict box (green for pass, red for fail)."""
        elements = []

        if mode == 'evaluate':
            passes = results.get('passes', False)
            irr_pct = results.get('irr_pct', 0)
            hurdle = results.get('hurdle_rate', 0)

            if passes:
                cushion = irr_pct - hurdle
                verdict_text = f"✓ DEAL PASSES HURDLE"
                detail_text = f"IRR: {irr_pct:.2f}% vs {hurdle:.2f}% required ({cushion*100:.0f}bps cushion)"
                bg_color = self.GREEN_BG
                border_color = self.GREEN_BORDER
                text_style = self.styles['VerdictPass']
            else:
                shortfall = hurdle - irr_pct
                verdict_text = f"✗ DEAL FAILS HURDLE"
                detail_text = f"IRR: {irr_pct:.2f}% vs {hurdle:.2f}% required ({shortfall*100:.0f}bps shortfall)"
                bg_color = self.RED_BG
                border_color = self.RED_BORDER
                text_style = self.styles['VerdictFail']
        else:  # price mode
            max_price = results.get('max_price', 0)
            target_irr = results.get('target_irr', 0)
            verdict_text = f"MAX PURCHASE PRICE"
            detail_text = f"{self._format_currency(max_price)} at {target_irr:.2f}% target IRR"
            bg_color = self.LIGHT_BLUE
            border_color = self.NAVY
            text_style = self.styles['SectionHeader']

        # Create verdict table (acts as a box)
        verdict_data = [
            [Paragraph(verdict_text, text_style)],
            [Paragraph(detail_text, self.styles['ReportBody'])]
        ]

        verdict_table = Table(verdict_data, colWidths=[5*inch])
        verdict_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), bg_color),
            ('BOX', (0, 0), (-1, -1), 2, border_color),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 15),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
            ('LEFTPADDING', (0, 0), (-1, -1), 20),
            ('RIGHTPADDING', (0, 0), (-1, -1), 20),
        ]))

        elements.append(verdict_table)

        return elements

    def _build_deal_summary(
        self,
        params: Dict[str, Any],
        results: Dict[str, Any],
        mode: str
    ) -> List:
        """Build deal summary table."""
        elements = []

        elements.append(Paragraph("DEAL SUMMARY", self.styles['SectionHeader']))

        # Build summary data
        purchase_price = params.get('purchase_price', results.get('max_price', 0))
        monthly_rent = params.get('monthly_rent', 0)
        lease_term = params.get('lease_term', params.get('lease_term_years', 0))
        step_up = params.get('step_up_pct', 0)
        maint_reserve = params.get('maintenance_reserve', params.get('monthly_maintenance_reserve', 0))
        transition_cost = params.get('transition_cost', 0)
        residual = results.get('estimated_residual', params.get('residual_value', 0))
        credit_tier = params.get('credit_tier', 'N/A')
        hurdle = results.get('hurdle_rate', results.get('target_irr', 0))

        data = [
            ['Purchase Price:', self._format_currency(purchase_price)],
            ['Monthly Rent:', self._format_currency(monthly_rent)],
            ['Lease Term:', f"{lease_term} years ({lease_term * 12} months)"],
            ['Step-Up:', f"{step_up:.1f}% annually"],
            ['Maint Reserve:', f"{self._format_currency(maint_reserve)}/month"],
            ['Transition Cost:', self._format_currency(transition_cost)],
            ['Residual Value:', self._format_currency(residual)],
            ['Credit Tier:', f"{credit_tier} (Hurdle: {hurdle:.2f}%)"],
        ]

        table = Table(data, colWidths=[2*inch, 3*inch])
        table.setStyle(TableStyle([
            ('FONT', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONT', (1, 0), (1, -1), 'Courier'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), self.DARK_GRAY),
            ('TEXTCOLOR', (1, 0), (1, -1), self.NAVY),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
        ]))

        elements.append(table)

        return elements

    def _build_key_metrics(
        self,
        params: Dict[str, Any],
        results: Dict[str, Any],
        mode: str
    ) -> List:
        """Build key metrics section."""
        elements = []

        elements.append(Paragraph("KEY METRICS", self.styles['SectionHeader']))

        if mode == 'evaluate':
            irr = results.get('irr_pct', 0)
            npv = results.get('npv', 0)
            breakeven = results.get('breakeven_residual', 0)
            estimated = results.get('estimated_residual', 0)
            cash_multiple = results.get('cash_multiple', 0)

            # Calculate residual cushion
            if breakeven > 0:
                cushion_pct = ((estimated - breakeven) / breakeven) * 100
            else:
                cushion_pct = 0

            data = [
                ['Implied IRR:', f"{irr:.2f}%"],
                ['NPV @ Hurdle:', self._format_currency(npv)],
                ['Breakeven Residual:', self._format_currency(breakeven)],
                ['Residual Cushion:', f"{cushion_pct:.1f}% above breakeven"],
                ['Cash Multiple:', f"{cash_multiple:.2f}x"],
            ]
        else:  # price mode
            max_price = results.get('max_price', 0)
            target_irr = results.get('target_irr', 0)
            actual_irr = results.get('actual_irr', 0)
            cash_multiple = results.get('cash_multiple', 0)
            estimated = results.get('estimated_residual', 0)

            data = [
                ['Max Purchase Price:', self._format_currency(max_price)],
                ['Target IRR:', f"{target_irr:.2f}%"],
                ['Verified IRR:', f"{actual_irr:.2f}%"],
                ['Estimated Residual:', self._format_currency(estimated)],
                ['Cash Multiple:', f"{cash_multiple:.2f}x"],
            ]

        table = Table(data, colWidths=[2*inch, 3*inch])
        table.setStyle(TableStyle([
            ('FONT', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONT', (1, 0), (1, -1), 'Courier'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), self.DARK_GRAY),
            ('TEXTCOLOR', (1, 0), (1, -1), self.NAVY),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
        ]))

        elements.append(table)

        return elements

    def _build_sensitivity_section(
        self,
        params: Dict[str, Any],
        results: Dict[str, Any],
        mode: str
    ) -> List:
        """Build sensitivity analysis section."""
        elements = []

        elements.append(Paragraph("SENSITIVITY ANALYSIS", self.styles['SectionHeader']))

        if mode == 'evaluate':
            elements.append(Paragraph(
                "IRR by Residual Value and Discount Rate",
                self.styles['ReportBody']
            ))
        else:
            elements.append(Paragraph(
                "Max Price by Residual Value and Target IRR",
                self.styles['ReportBody']
            ))

        elements.append(Spacer(1, 10))

        # Build sensitivity table
        sensitivity_matrix = results.get('sensitivity_matrix', [])

        if sensitivity_matrix:
            elements.append(self._build_sensitivity_table(sensitivity_matrix, mode))
        else:
            elements.append(Paragraph("Sensitivity data not available", self.styles['ReportBody']))

        elements.append(Spacer(1, 20))

        # Disclaimer
        elements.append(Paragraph("DISCLAIMER", self.styles['SectionHeader']))
        disclaimer_text = (
            "This analysis is for informational purposes only and does not constitute "
            "financial advice. Past performance does not guarantee future results. "
            "Actual returns may vary based on market conditions, aircraft condition, "
            "and lessee performance. All projections are based on assumptions that may "
            "not reflect actual outcomes."
        )
        elements.append(Paragraph(disclaimer_text, self.styles['SmallText']))

        return elements

    def _build_sensitivity_table(
        self,
        matrix: List[List[Dict]],
        mode: str
    ) -> Table:
        """Build the 5x5 sensitivity analysis table."""

        # Header row
        residual_labels = ['-20%', '-10%', 'Base', '+10%', '+20%']
        header_row = ['Res Δ \\ Rate Δ'] + residual_labels

        # Build data rows
        rate_labels = ['-2%', '-1%', 'Base', '+1%', '+2%']
        table_data = [header_row]

        for row_idx, row in enumerate(matrix):
            row_data = [rate_labels[row_idx]]
            for col_idx, cell in enumerate(row):
                if mode == 'evaluate':
                    irr = cell.get('irr')
                    if irr is not None:
                        cell_text = f"{irr * 100:.1f}%"
                    else:
                        cell_text = "N/A"
                else:
                    price = cell.get('price', 0)
                    cell_text = self._format_currency(price)
                row_data.append(cell_text)
            table_data.append(row_data)

        # Create table
        col_widths = [1*inch] + [1*inch] * 5
        table = Table(table_data, colWidths=col_widths)

        # Style the table
        style_commands = [
            # Header styling
            ('BACKGROUND', (0, 0), (-1, 0), self.NAVY),
            ('TEXTCOLOR', (0, 0), (-1, 0), self.WHITE),
            ('BACKGROUND', (0, 1), (0, -1), self.NAVY),
            ('TEXTCOLOR', (0, 1), (0, -1), self.WHITE),

            # General styling
            ('FONT', (0, 0), (-1, -1), 'Courier'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, self.DARK_GRAY),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]

        # Highlight base case cell (center cell: row 3, col 3)
        style_commands.append(('BACKGROUND', (3, 3), (3, 3), self.LIGHT_BLUE))
        style_commands.append(('FONT', (3, 3), (3, 3), 'Courier-Bold'))

        # Color code pass/fail for evaluate mode
        if mode == 'evaluate':
            for row_idx, row in enumerate(matrix):
                for col_idx, cell in enumerate(row):
                    passes = cell.get('pass', False)
                    table_row = row_idx + 1
                    table_col = col_idx + 1

                    if table_row == 3 and table_col == 3:
                        continue  # Skip base case (already styled)

                    if passes:
                        style_commands.append(('TEXTCOLOR', (table_col, table_row), (table_col, table_row), self.GREEN_TEXT))
                    else:
                        style_commands.append(('TEXTCOLOR', (table_col, table_row), (table_col, table_row), self.RED_TEXT))

        table.setStyle(TableStyle(style_commands))

        return table
