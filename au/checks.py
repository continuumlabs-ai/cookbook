"""Australian checks, in plain code.

Small, dependable functions that recipes run before and after the model:
check digits for ABNs, ACNs, TFNs and Medicare numbers, GST arithmetic,
BSB and postcode checks, and redaction of tax file numbers before any text
reaches a model.

Standard library only. Copy this file into your own project if you like.
Each check follows the published algorithm. None of them confirm that a
number is registered to anyone. For that, use the ABN Lookup service.
"""

import re
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CENT = Decimal("0.01")
GST_RATE = Decimal("0.10")


def digits(value):
    """Only the digits of a value, as a string."""
    return re.sub(r"\D", "", str(value or ""))


# ---------------------------------------------------------------------------
# Business and identity numbers
# ---------------------------------------------------------------------------

ABN_WEIGHTS = [10, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19]


def abn_valid(abn):
    """True if an Australian Business Number passes the ATO check digit test.

    Subtract 1 from the first digit, weight each digit, and the total must divide by 89.
    """
    d = digits(abn)
    if len(d) != 11 or d[0] == "0":
        return False
    nums = [int(c) for c in d]
    nums[0] -= 1
    return sum(n * w for n, w in zip(nums, ABN_WEIGHTS)) % 89 == 0


def format_abn(abn):
    d = digits(abn)
    return f"{d[:2]} {d[2:5]} {d[5:8]} {d[8:]}" if len(d) == 11 else str(abn)


def acn_valid(acn):
    """True if an Australian Company Number passes the ASIC check digit test."""
    d = digits(acn)
    if len(d) != 9:
        return False
    total = sum(int(c) * w for c, w in zip(d[:8], range(8, 0, -1)))
    return (10 - total % 10) % 10 == int(d[8])


TFN_WEIGHTS = [1, 4, 3, 7, 5, 8, 6, 9, 10]


def tfn_valid(tfn):
    """True if a nine-digit tax file number passes the ATO check digit test."""
    d = digits(tfn)
    if len(d) != 9:
        return False
    return sum(int(c) * w for c, w in zip(d, TFN_WEIGHTS)) % 11 == 0


MEDICARE_WEIGHTS = [1, 3, 7, 9, 1, 3, 7, 9]


def medicare_valid(number):
    """True if a Medicare card number passes its check digit test.

    Accepts 10 digits, or 11 with the person's position on the card.
    """
    d = digits(number)
    if len(d) not in (10, 11) or d[0] not in "23456":
        return False
    return sum(int(c) * w for c, w in zip(d[:8], MEDICARE_WEIGHTS)) % 10 == int(d[8])


# Nine digits, optionally split 3-3-3 by spaces or hyphens, not part of a longer number.
_TFN_SHAPE = re.compile(r"(?<![\d-])(\d{3})[ -]?(\d{3})[ -]?(\d{3})(?![\d-])")


def redact_tfns(text):
    """Replace anything that looks like a valid tax file number. Returns (text, count).

    Run this before text reaches a model. Tax file numbers are protected by law,
    and most AI tasks never need them.
    """
    count = 0

    def swap(match):
        nonlocal count
        if tfn_valid("".join(match.groups())):
            count += 1
            return "[TFN REDACTED]"
        return match.group(0)

    return _TFN_SHAPE.sub(swap, text), count


def bsb_valid(bsb):
    """True if a BSB has the right shape: six digits, usually written 123-456."""
    return bool(re.fullmatch(r"\d{3}-?\d{3}", str(bsb or "").strip()))


# ---------------------------------------------------------------------------
# Money and GST
# ---------------------------------------------------------------------------

def money(value):
    """Parse '$1,234.50', 'A$1234.5' or 1234.5 into a Decimal rounded to the cent. None if it isn't money."""
    if value is None:
        return None
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value)).quantize(CENT, ROUND_HALF_UP)
    cleaned = re.sub(r"(?i)(aud|a\$|\$|,|\s)", "", str(value))
    try:
        return Decimal(cleaned).quantize(CENT, ROUND_HALF_UP)
    except InvalidOperation:
        return None


def gst_on(amount_ex_gst):
    """GST on a taxable amount: 10% of the price before GST, to the cent."""
    return (money(amount_ex_gst) * GST_RATE).quantize(CENT, ROUND_HALF_UP)


def gst_in(amount_inc_gst):
    """The GST inside a GST-inclusive price: one eleventh, to the cent."""
    return (money(amount_inc_gst) / 11).quantize(CENT, ROUND_HALF_UP)


def gst_problems(subtotal_ex_gst, gst, total_inc_gst, gst_free_amount=0, tolerance=CENT):
    """Check an invoice's GST arithmetic. Returns a list of plain-English problems, empty if it adds up.

    gst_free_amount is the part of the subtotal that carries no GST, such as basic food or some medical items.
    """
    sub, tax, total, free = (money(v) for v in (subtotal_ex_gst, gst, total_inc_gst, gst_free_amount or 0))
    if None in (sub, tax, total, free):
        return ["the subtotal, GST or total is missing or not a number"]
    problems = []
    expected_gst = gst_on(sub - free)
    if abs(tax - expected_gst) > tolerance:
        problems.append(f"GST is ${tax:,.2f} but 10% of the taxable amount (${sub - free:,.2f}) is ${expected_gst:,.2f}")
    if abs(total - (sub + tax)) > tolerance:
        problems.append(f"total is ${total:,.2f} but subtotal plus GST is ${sub + tax:,.2f}")
    return problems


# No-ABN withholding: if a supplier doesn't quote an ABN on an invoice over this
# amount (excluding GST), the payer may have to withhold tax at the top rate.
NO_ABN_THRESHOLD = Decimal("75.00")
NO_ABN_WITHHOLDING_RATE = Decimal("0.47")


# ---------------------------------------------------------------------------
# Places and dates
# ---------------------------------------------------------------------------

POSTCODE_RANGES = {
    "NSW": [(1000, 2599), (2619, 2899), (2921, 2999)],
    "ACT": [(200, 299), (2600, 2618), (2900, 2920)],
    "VIC": [(3000, 3999), (8000, 8999)],
    "QLD": [(4000, 4999), (9000, 9999)],
    "SA": [(5000, 5999)],
    "WA": [(6000, 6999)],
    "TAS": [(7000, 7999)],
    "NT": [(800, 999)],
}


def state_for_postcode(postcode):
    """The state or territory a postcode belongs to, or None."""
    d = digits(postcode)
    if not d or len(d) > 4:
        return None
    n = int(d)
    for state, ranges in POSTCODE_RANGES.items():
        if any(lo <= n <= hi for lo, hi in ranges):
            return state
    return None


def postcode_matches_state(postcode, state):
    return state_for_postcode(postcode) == str(state or "").strip().upper()


_DATE_FORMATS = ["%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d %B %Y", "%d %b %Y", "%Y-%m-%d", "%d/%m/%y"]


def au_date(text):
    """Read a date the Australian way, day first. Returns a date, or None.

    '03/10/2026' is 3 October, never 10 March.
    """
    if isinstance(text, date):
        return text
    cleaned = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", str(text or "").strip())
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None
