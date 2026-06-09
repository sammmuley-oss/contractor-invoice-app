"""Indian currency formatting utilities.

Uses the Indian numbering system:
  1,000
  10,000
  1,00,000
  10,00,000
  1,00,00,000
"""

from decimal import Decimal, ROUND_HALF_UP


def format_indian_number(number: float | int | Decimal) -> str:
    """Format a number using Indian comma placement.

    Examples:
        1000       -> 1,000
        100000     -> 1,00,000
        10500000   -> 1,05,00,000
        12575000   -> 1,25,75,000
    """
    if isinstance(number, Decimal):
        number = float(number)

    is_negative = number < 0
    number = abs(number)

    # Split into integer and decimal parts
    int_part = int(number)
    dec_part = number - int_part

    if int_part == 0:
        formatted = "0"
    else:
        s = str(int_part)
        if len(s) <= 3:
            formatted = s
        else:
            # Last 3 digits
            last_three = s[-3:]
            remaining = s[:-3]

            # Group remaining in pairs from right
            groups = []
            while remaining:
                groups.append(remaining[-2:])
                remaining = remaining[:-2]

            groups.reverse()
            formatted = ",".join(groups) + "," + last_three

    # Add decimal part
    if dec_part > 0:
        dec_str = f"{dec_part:.2f}"[1:]  # Remove leading 0
        formatted += dec_str
    else:
        formatted += ".00"

    if is_negative:
        formatted = "-" + formatted

    return formatted


def format_inr(amount: float | int | Decimal) -> str:
    """Format amount as Indian Rupees with ₹ symbol.

    Examples:
        1000     -> ₹1,000.00
        100000   -> ₹1,00,000.00
        10500000 -> ₹1,05,00,000.00
    """
    return f"₹{format_indian_number(amount)}"


def format_inr_compact(amount: float | int | Decimal) -> str:
    """Format large amounts in compact form.

    Examples:
        100000    -> ₹1.00 L
        10000000  -> ₹1.00 Cr
    """
    if isinstance(amount, Decimal):
        amount = float(amount)

    abs_amount = abs(amount)
    sign = "-" if amount < 0 else ""

    if abs_amount >= 10_000_000:
        return f"{sign}₹{abs_amount / 10_000_000:.2f} Cr"
    elif abs_amount >= 100_000:
        return f"{sign}₹{abs_amount / 100_000:.2f} L"
    elif abs_amount >= 1_000:
        return f"{sign}₹{abs_amount / 1_000:.2f} K"
    else:
        return f"{sign}₹{abs_amount:.2f}"


def round_decimal(value: float, places: int = 2) -> float:
    """Round using banker's rounding (ROUND_HALF_UP)."""
    return float(Decimal(str(value)).quantize(Decimal(f"0.{'0' * places}"), rounding=ROUND_HALF_UP))
