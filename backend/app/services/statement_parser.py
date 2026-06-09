"""Bank statement parser engine — extracts transactions from PDF, CSV, and Excel files.

Supports 10+ Indian banks with auto-detection of column formats.
Architecture is extensible — add new banks by adding entries to BANK_COLUMN_MAPS.
"""

import re
import io
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import Optional

import pandas as pd


# ─── Bank Column Mappings ─────────────────────────────────
# Each bank maps its column header variants → our canonical field names.
# The parser tries each variant (case-insensitive) to auto-detect columns.

BANK_COLUMN_MAPS: dict[str, dict[str, list[str]]] = {
    "SBI": {
        "date": ["txn date", "transaction date", "value date", "date"],
        "description": ["description", "narration", "particulars", "remarks"],
        "credit": ["credit", "credit amount", "credit(inr)", "deposit", "cr"],
        "debit": ["debit", "debit amount", "debit(inr)", "withdrawal", "dr"],
        "reference": ["ref no", "reference", "ref number", "chq/ref no", "chq./ref.no."],
    },
    "HDFC": {
        "date": ["date", "txn date", "value date", "transaction date"],
        "description": ["narration", "description", "particulars"],
        "credit": ["credit", "credit amount", "deposit amt", "cr"],
        "debit": ["debit", "debit amount", "withdrawal amt", "dr"],
        "reference": ["chq./ref.no.", "ref no.", "reference no", "chq/ref no"],
    },
    "ICICI": {
        "date": ["value date", "transaction date", "date", "txn date"],
        "description": ["transaction remarks", "remarks", "description", "narration", "particulars"],
        "credit": ["credit amount", "credit", "cr amount", "deposit", "cr"],
        "debit": ["debit amount", "debit", "dr amount", "withdrawal", "dr"],
        "reference": ["cheque number", "ref no", "reference", "chq no"],
    },
    "AXIS": {
        "date": ["tran date", "transaction date", "date", "value date"],
        "description": ["particulars", "narration", "description"],
        "credit": ["cr", "credit", "credit amount", "deposit"],
        "debit": ["dr", "debit", "debit amount", "withdrawal"],
        "reference": ["chq no", "ref no", "reference"],
    },
    "KOTAK": {
        "date": ["date", "transaction date", "value date", "sl date"],
        "description": ["description", "narration", "particulars"],
        "credit": ["credit", "cr", "credit amount", "deposit"],
        "debit": ["debit", "dr", "debit amount", "withdrawal"],
        "reference": ["chq/ref no", "ref no", "reference"],
    },
    "BOB": {
        "date": ["txn date", "date", "value date", "transaction date"],
        "description": ["narration", "description", "particulars"],
        "credit": ["credit", "cr", "deposit"],
        "debit": ["debit", "dr", "withdrawal"],
        "reference": ["ref no", "reference", "chq no"],
    },
    "CANARA": {
        "date": ["trans date", "date", "value date"],
        "description": ["narration", "description", "particulars"],
        "credit": ["credit", "cr", "deposit amount"],
        "debit": ["debit", "dr", "withdrawal amount"],
        "reference": ["ref no", "reference"],
    },
    "UNION": {
        "date": ["transaction date", "date", "value date"],
        "description": ["narration", "description", "particulars"],
        "credit": ["credit", "cr", "deposit"],
        "debit": ["debit", "dr", "withdrawal"],
        "reference": ["ref no", "reference", "chq no"],
    },
    "PNB": {
        "date": ["date", "transaction date", "value date"],
        "description": ["narration", "description", "particulars"],
        "credit": ["credit", "cr", "deposit"],
        "debit": ["debit", "dr", "withdrawal"],
        "reference": ["ref no", "reference"],
    },
    "INDUSIND": {
        "date": ["transaction date", "date", "value date"],
        "description": ["transaction particulars", "description", "narration", "particulars"],
        "credit": ["credit", "cr", "deposit"],
        "debit": ["debit", "dr", "withdrawal"],
        "reference": ["chq/ref no", "ref no", "reference"],
    },
}

# Generic fallback — tries all common header names
GENERIC_MAP: dict[str, list[str]] = {
    "date": [
        "date", "txn date", "transaction date", "value date",
        "tran date", "trans date", "posting date", "sl date",
    ],
    "description": [
        "description", "narration", "particulars", "remarks",
        "transaction remarks", "transaction particulars", "details",
    ],
    "credit": [
        "credit", "credit amount", "cr", "deposit", "deposit amount",
        "credit(inr)", "deposit amt", "cr amount", "credit(rs)",
    ],
    "debit": [
        "debit", "debit amount", "dr", "withdrawal", "withdrawal amount",
        "debit(inr)", "withdrawal amt", "dr amount", "debit(rs)",
    ],
    "reference": [
        "ref no", "reference", "chq/ref no", "chq./ref.no.",
        "cheque number", "reference no", "chq no", "ref number",
        "utr", "utr no", "transaction id",
    ],
}

# ─── UTR / Reference Regex Patterns ──────────────────────

UTR_PATTERNS = [
    # NEFT/RTGS UTR: typically alphanumeric 16-22 chars starting with bank code
    r'(?:UTR[:\s]*)?([A-Z]{4}[A-Z0-9]{12,18})',
    # CMS/IMPS reference
    r'(?:IMPS|CMS)[/\-]?(\d{12,16})',
    # Pure numeric UTR (16+ digits)
    r'\b(\d{16,22})\b',
    # NEFT pattern
    r'(?:NEFT)[/\-\s]*([A-Z0-9]{10,22})',
    # RTGS pattern
    r'(?:RTGS)[/\-\s]*([A-Z0-9]{10,22})',
]

UPI_PATTERNS = [
    r'UPI[/\-](\d{12,16})',
    r'UPI-([A-Za-z0-9]+@[A-Za-z]+)',
]

INVOICE_PATTERNS = [
    r'(INV[-/]\d{4}[-/]\d{1,6})',
    r'(INVOICE\s*#?\s*\d+)',
]


# ─── Helper Functions ─────────────────────────────────────

def _parse_amount(val) -> Decimal:
    """Parse an amount value, handling Indian formatting (commas, Cr/Dr suffixes)."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return Decimal("0")
    s = str(val).strip()
    if not s or s == "-" or s.lower() == "nan" or s.lower() == "none":
        return Decimal("0")
    # Remove currency symbols, commas, spaces
    s = re.sub(r'[₹,\s]', '', s)
    # Remove Cr/Dr suffixes
    s = re.sub(r'(Cr|Dr|CR|DR)\.?$', '', s).strip()
    # Handle brackets for negative
    if s.startswith('(') and s.endswith(')'):
        s = '-' + s[1:-1]
    try:
        return abs(Decimal(s))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _parse_date(val) -> Optional[date]:
    """Parse a date value from various Indian banking formats."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, (datetime, date)):
        return val if isinstance(val, date) else val.date()
    if isinstance(val, pd.Timestamp):
        return val.date()

    s = str(val).strip()
    if not s or s.lower() == 'nan':
        return None

    formats = [
        "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y",
        "%Y-%m-%d", "%Y/%m/%d",
        "%d %b %Y", "%d-%b-%Y", "%d %b %y", "%d-%b-%y",
        "%d %B %Y", "%m/%d/%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _find_column(df_columns: list[str], candidates: list[str]) -> Optional[str]:
    """Find the first matching column name (case-insensitive)."""
    col_map = {c.strip().lower(): c for c in df_columns}
    for candidate in candidates:
        if candidate.lower() in col_map:
            return col_map[candidate.lower()]
    return None


def _extract_utr(description: str) -> Optional[str]:
    """Extract UTR number from transaction description."""
    if not description:
        return None
    for pattern in UTR_PATTERNS:
        match = re.search(pattern, description, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _extract_upi_ref(description: str) -> Optional[str]:
    """Extract UPI reference from description."""
    if not description:
        return None
    for pattern in UPI_PATTERNS:
        match = re.search(pattern, description, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _extract_invoice_number(description: str) -> Optional[str]:
    """Extract invoice number from description."""
    if not description:
        return None
    for pattern in INVOICE_PATTERNS:
        match = re.search(pattern, description, re.IGNORECASE)
        if match:
            return match.group(1).upper().replace('/', '-')
    return None


def _extract_sender_name(description: str) -> Optional[str]:
    """Try to extract sender/payer name from description."""
    if not description:
        return None
    # Common patterns: "NEFT-...-SENDER NAME", "UPI/SENDER NAME/..."
    patterns = [
        r'(?:NEFT|RTGS|IMPS)[-/][^-/]+[-/]([A-Z][A-Z\s\.]+)',
        r'UPI/([A-Z][A-Z\s\.]+?)/',
        r'BY\s+TRANSFER[:\s-]+(.+)',
        r'FROM\s+(.+?)(?:\s+REF|\s+UTR|\s+NEFT|$)',
    ]
    for pat in patterns:
        m = re.search(pat, description.upper())
        if m:
            name = m.group(1).strip()
            if len(name) > 3 and not name.isdigit():
                return name.title()
    return None


# ─── Main Parser Class ────────────────────────────────────

class StatementParser:
    """Parse bank statements from various file formats."""

    @staticmethod
    def parse(file_bytes: bytes, filename: str, bank_name: str) -> list[dict]:
        """Parse a statement file and return a list of transaction dicts.

        Args:
            file_bytes: Raw file content
            filename: Original filename (for format detection)
            bank_name: Bank name (for column mapping)

        Returns:
            List of dicts with keys: transaction_date, description,
            credit_amount, debit_amount, utr_number, reference_number,
            sender_name
        """
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

        if ext == 'csv':
            df = StatementParser._parse_csv(file_bytes)
        elif ext in ('xlsx', 'xls'):
            df = StatementParser._parse_excel(file_bytes, ext)
        elif ext == 'pdf':
            df = StatementParser._parse_pdf(file_bytes)
        else:
            raise ValueError(f"Unsupported file format: .{ext}")

        if df is None or df.empty:
            return []

        return StatementParser._normalize(df, bank_name)

    @staticmethod
    def _parse_csv(file_bytes: bytes) -> Optional[pd.DataFrame]:
        """Parse a CSV bank statement."""
        text = file_bytes.decode('utf-8', errors='replace')

        # Try to find the header row (skip bank metadata rows)
        lines = text.strip().split('\n')
        header_idx = 0
        for i, line in enumerate(lines):
            lower = line.lower()
            if any(kw in lower for kw in ['date', 'narration', 'description', 'particulars', 'credit', 'debit']):
                header_idx = i
                break

        try:
            return pd.read_csv(io.StringIO(text), skiprows=header_idx, dtype=str)
        except Exception:
            return pd.read_csv(io.StringIO(text), dtype=str)

    @staticmethod
    def _parse_excel(file_bytes: bytes, ext: str) -> Optional[pd.DataFrame]:
        """Parse an Excel bank statement."""
        engine = 'openpyxl' if ext == 'xlsx' else 'xlrd'
        try:
            # Try reading with openpyxl first
            df = pd.read_excel(io.BytesIO(file_bytes), engine=engine, dtype=str)
        except Exception:
            df = pd.read_excel(io.BytesIO(file_bytes), dtype=str)

        if df is None or df.empty:
            return df

        # Find header row if first rows are metadata
        for i in range(min(10, len(df))):
            row = df.iloc[i]
            row_str = ' '.join(str(v).lower() for v in row.values if pd.notna(v))
            if any(kw in row_str for kw in ['date', 'narration', 'description', 'credit', 'debit']):
                # Re-read with this row as header
                try:
                    df = pd.read_excel(
                        io.BytesIO(file_bytes), engine=engine,
                        skiprows=i, dtype=str,
                    )
                except Exception:
                    pass
                break

        return df

    @staticmethod
    def _parse_pdf(file_bytes: bytes) -> Optional[pd.DataFrame]:
        """Parse a PDF bank statement using pdfplumber table extraction."""
        import pdfplumber

        all_rows = []
        header = None

        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    if not table:
                        continue
                    for row in table:
                        if not row or all(c is None or str(c).strip() == '' for c in row):
                            continue
                        row_clean = [str(c).strip() if c else '' for c in row]

                        # Detect header row
                        if header is None:
                            row_lower = ' '.join(row_clean).lower()
                            if any(kw in row_lower for kw in ['date', 'narration', 'description', 'credit', 'debit']):
                                header = row_clean
                                continue

                        if header:
                            # Pad row to match header length
                            while len(row_clean) < len(header):
                                row_clean.append('')
                            all_rows.append(row_clean[:len(header)])

        if not header or not all_rows:
            return None

        return pd.DataFrame(all_rows, columns=header)

    @staticmethod
    def _normalize(df: pd.DataFrame, bank_name: str) -> list[dict]:
        """Normalize a DataFrame into standardized transaction dicts."""
        # Get column mapping for this bank
        bank_key = bank_name.upper().split()[0]  # e.g., "State Bank of India" → "STATE"
        col_map = BANK_COLUMN_MAPS.get(bank_key, GENERIC_MAP)

        # Also try by common abbreviation
        abbrev_map = {
            "STATE": "SBI", "HDFC": "HDFC", "ICICI": "ICICI",
            "AXIS": "AXIS", "KOTAK": "KOTAK", "BANK": "BOB",
            "CANARA": "CANARA", "UNION": "UNION", "PUNJAB": "PNB",
            "INDUSIND": "INDUSIND",
        }
        if bank_key in abbrev_map:
            col_map = BANK_COLUMN_MAPS.get(abbrev_map[bank_key], col_map)

        # Try the bank name directly
        for key in BANK_COLUMN_MAPS:
            if key in bank_name.upper():
                col_map = BANK_COLUMN_MAPS[key]
                break

        # Fall back to generic if no specific mapping found
        if col_map is BANK_COLUMN_MAPS.get(bank_key):
            pass  # already set
        # Always merge with generic as fallback
        merged_map = {}
        for field in ["date", "description", "credit", "debit", "reference"]:
            bank_candidates = col_map.get(field, [])
            generic_candidates = GENERIC_MAP.get(field, [])
            merged_map[field] = bank_candidates + [
                g for g in generic_candidates if g not in bank_candidates
            ]

        cols = list(df.columns)
        date_col = _find_column(cols, merged_map["date"])
        desc_col = _find_column(cols, merged_map["description"])
        credit_col = _find_column(cols, merged_map["credit"])
        debit_col = _find_column(cols, merged_map["debit"])
        ref_col = _find_column(cols, merged_map["reference"])

        if not date_col and not credit_col:
            # Can't parse without at least date or credit column
            return []

        transactions = []
        for _, row in df.iterrows():
            desc = str(row.get(desc_col, '')).strip() if desc_col else ''
            credit = _parse_amount(row.get(credit_col)) if credit_col else Decimal("0")
            debit = _parse_amount(row.get(debit_col)) if debit_col else Decimal("0")

            # Skip rows with no amounts
            if credit == 0 and debit == 0:
                continue

            txn_date = _parse_date(row.get(date_col)) if date_col else None
            ref = str(row.get(ref_col, '')).strip() if ref_col else None
            if ref and (ref.lower() == 'nan' or ref == ''):
                ref = None

            utr = _extract_utr(desc)
            if not utr and ref:
                utr = _extract_utr(ref)

            upi_ref = _extract_upi_ref(desc)
            sender = _extract_sender_name(desc)

            transactions.append({
                "transaction_date": txn_date,
                "description": desc or None,
                "credit_amount": float(credit),
                "debit_amount": float(debit),
                "utr_number": utr or upi_ref,
                "reference_number": ref,
                "sender_name": sender,
            })

        return transactions
