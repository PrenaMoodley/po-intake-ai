from datetime import date

from po_intake.models import POLine, PurchaseOrder
from po_intake.validate import check

TODAY = date(2026, 10, 12)


def make_order(**overrides) -> PurchaseOrder:
    data = {
        "po_number": "CB-2026-0418",
        "customer_name": "Coastal Bakeries (Pty) Ltd",
        "account_code": "C1001",
        "order_date": "2026-10-05",
        "delivery_date": "2026-10-19",
        "delivery_address": "22 Mill Lane, Pinetown",
        "lines": [
            POLine(
                line_no=1,
                customer_ref="CBK-221",
                sku="BOX-CAKE-10",
                description="Cake box 10",
                quantity=500,
                unit="each",
                unit_price=6.80,
            ),
            POLine(
                line_no=2,
                customer_ref="CBK-223",
                sku="BOX-CAKE-12",
                description="Cake box 12",
                quantity=250,
                unit="each",
                unit_price=8.20,
            ),
            POLine(
                line_no=3,
                customer_ref="CBK-310",
                sku="NAP-2PLY-W",
                description="Serviettes",
                quantity=40,
                unit="pack of 100",
                unit_price=21.90,
            ),
        ],
        "subtotal_excl_vat": 6326.00,
        "vat_amount": 948.90,
        "total_incl_vat": 7274.90,
        "notes": [],
    }
    data.update(overrides)
    return PurchaseOrder(**data)


def codes(issues):
    return {i.code for i in issues}


def test_clean_order_has_no_issues(ref):
    assert check(make_order(), ref, today=TODAY) == []


def test_float_rounding_does_not_cause_false_mismatch(ref):
    # In floats 3 * 1.95 is 5.8500000000000005; Decimal maths must still say R5.85.
    line = POLine(
        line_no=1,
        customer_ref=None,
        sku="BAG-KRF-M",
        description="bag",
        quantity=3,
        unit="each",
        unit_price=1.95,
    )
    order = make_order(lines=[line], subtotal_excl_vat=5.85, vat_amount=0.88, total_incl_vat=6.73)
    assert "subtotal_mismatch" not in codes(check(order, ref, today=TODAY))


def test_subtotal_mismatch_blocks(ref):
    issues = check(make_order(subtotal_excl_vat=6000.00), ref, today=TODAY)
    assert "subtotal_mismatch" in codes(issues)


def test_wrong_vat_is_flagged(ref):
    issues = check(make_order(vat_amount=900.00, total_incl_vat=7226.00), ref, today=TODAY)
    assert "vat_mismatch" in codes(issues)


def test_price_variance_flagged(ref):
    order = make_order()
    order.lines[0].unit_price = 6.00
    order.subtotal_excl_vat = None
    assert "price_variance" in codes(check(order, ref, today=TODAY))


def test_unmatched_and_unknown_items(ref):
    order = make_order(subtotal_excl_vat=None)
    order.lines[0].sku = None
    order.lines[1].sku = "NOT-A-SKU"
    found = codes(check(order, ref, today=TODAY))
    assert {"unmatched_item", "unknown_sku"} <= found


def test_unknown_customer_blocks(ref):
    assert "unknown_customer" in codes(check(make_order(account_code=None), ref, today=TODAY))


def test_past_delivery_date_warns(ref):
    issues = check(make_order(delivery_date="2026-10-01"), ref, today=TODAY)
    assert "delivery_in_past" in codes(issues)


def test_reference_lookups(ref):
    assert ref.find_customer("Berea Fresh")[0]["account_code"] == "C1002"
    assert ref.search_catalogue("smoothie cup 500ml")[0]["sku"] == "CUP-PET-500"
