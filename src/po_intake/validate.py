"""Deterministic checks on an extracted PO.

Claude reads the document; plain Python checks the arithmetic and the business
rules. Sums, VAT and price comparisons must be exact and repeatable, which is
a job for code, not a language model.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from .models import Issue, PurchaseOrder
from .reference import ReferenceData

VAT_RATE = Decimal("0.15")  # South African standard rate
CENT = Decimal("0.01")
PRICE_TOLERANCE = Decimal("0.02")  # flag prices more than 2% off list


def money(value: float | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def line_total(quantity: float, unit_price: float | None) -> Decimal | None:
    if unit_price is None:
        return None
    return (Decimal(str(quantity)) * Decimal(str(unit_price))).quantize(CENT, rounding=ROUND_HALF_UP)


def check(order: PurchaseOrder, ref: ReferenceData, today: date | None = None) -> list[Issue]:
    issues: list[Issue] = []
    today = today or date.today()

    def add(severity: str, code: str, message: str, line_no: int | None = None) -> None:
        issues.append(Issue(severity=severity, code=code, message=message, line_no=line_no))

    if not order.po_number.strip():
        add("error", "missing_po_number", "PO number is missing.")
    if order.account_code is None:
        add("error", "unknown_customer", f"No account matched '{order.customer_name}'.")
    elif order.account_code not in {c.account_code for c in ref.customers}:
        add("error", "invalid_account", f"Account code {order.account_code} does not exist.")
    if not order.lines:
        add("error", "no_lines", "The PO has no order lines.")

    if order.delivery_date:
        try:
            if date.fromisoformat(order.delivery_date) < today:
                add("warning", "delivery_in_past", f"Delivery date {order.delivery_date} has passed.")
        except ValueError:
            add("warning", "bad_date", f"Delivery date '{order.delivery_date}' is not a valid date.")

    subtotal = Decimal("0.00")
    for line in order.lines:
        if line.quantity <= 0:
            add("error", "bad_quantity", f"Quantity {line.quantity} is not positive.", line.line_no)
        product = ref.products.get(line.sku) if line.sku else None
        if line.sku is None:
            add("error", "unmatched_item", f"'{line.description}' has no catalogue match.", line.line_no)
        elif product is None:
            add("error", "unknown_sku", f"SKU {line.sku} is not in the catalogue.", line.line_no)
        if line.unit_price is None:
            add("warning", "missing_price", "No unit price on the PO; list price will apply.", line.line_no)
        elif product is not None:
            price = money(line.unit_price)
            variance = abs(price - product.list_price) / product.list_price
            if variance > PRICE_TOLERANCE:
                add(
                    "warning",
                    "price_variance",
                    f"PO price R{price} vs list R{product.list_price} ({variance:.0%} difference).",
                    line.line_no,
                )
        total = line_total(line.quantity, line.unit_price)
        if total is not None:
            subtotal += total

    stated_subtotal = money(order.subtotal_excl_vat)
    if stated_subtotal is not None and stated_subtotal != subtotal:
        add("error", "subtotal_mismatch", f"Lines add up to R{subtotal}, PO states R{stated_subtotal}.")

    stated_vat = money(order.vat_amount)
    if stated_vat is not None and stated_subtotal is not None:
        expected_vat = (stated_subtotal * VAT_RATE).quantize(CENT, rounding=ROUND_HALF_UP)
        if abs(stated_vat - expected_vat) > CENT:
            add("warning", "vat_mismatch", f"VAT should be R{expected_vat} at 15%, PO states R{stated_vat}.")

    stated_total = money(order.total_incl_vat)
    if stated_total is not None and stated_subtotal is not None and stated_vat is not None:
        expected_total = stated_subtotal + stated_vat
        if stated_total != expected_total:
            add("error", "total_mismatch", f"Subtotal + VAT is R{expected_total}, PO states R{stated_total}.")

    for note in order.notes:
        add("warning", "extractor_note", note)

    return issues
