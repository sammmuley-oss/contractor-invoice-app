"""Validation utilities including GSTIN validation."""

import re


GSTIN_REGEX = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$")

# Indian state codes for GSTIN validation
VALID_STATE_CODES = {
    "01", "02", "03", "04", "05", "06", "07", "08", "09", "10",
    "11", "12", "13", "14", "15", "16", "17", "18", "19", "20",
    "21", "22", "23", "24", "25", "26", "27", "28", "29", "30",
    "31", "32", "33", "34", "35", "36", "37", "38",
    # Special categories
    "96", "97",
}


def validate_gstin(gst_number: str) -> tuple[bool, str]:
    """Validate a GSTIN (Goods and Services Tax Identification Number).

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not gst_number:
        return False, "GST Number is required."

    gst_number = gst_number.upper().strip()

    if len(gst_number) != 15:
        return False, "GST Number must be exactly 15 characters."

    if not GSTIN_REGEX.match(gst_number):
        return False, (
            "Invalid GST Number format. Expected format: "
            "2 digit state code + 10 char PAN + entity number + Z + checksum."
        )

    state_code = gst_number[:2]
    if state_code not in VALID_STATE_CODES:
        return False, f"Invalid state code '{state_code}' in GST Number."

    return True, ""


def validate_invoice_number(invoice_number: str) -> tuple[bool, str]:
    """Validate invoice number format."""
    if not invoice_number or not invoice_number.strip():
        return False, "Invoice number is required."

    invoice_number = invoice_number.strip()
    if len(invoice_number) > 50:
        return False, "Invoice number must be 50 characters or less."

    return True, ""
