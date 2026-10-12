import json
from pathlib import Path

import pytest
from conftest import FakeClient, response, text_block, tool_use_block

from po_intake.extract import ExtractionError, extract_po

SAMPLE = Path(__file__).resolve().parents[1] / "samples" / "po-1001-clean.txt"

ORDER_JSON = json.dumps(
    {
        "po_number": "CB-2026-0418",
        "customer_name": "Coastal Bakeries (Pty) Ltd",
        "account_code": "C1001",
        "order_date": "2026-10-05",
        "delivery_date": "2026-10-19",
        "delivery_address": "22 Mill Lane, Pinetown, 3610",
        "lines": [
            {
                "line_no": 1,
                "customer_ref": "CBK-221",
                "sku": "BOX-CAKE-10",
                "description": 'Cake box 10" white, window',
                "quantity": 500,
                "unit": "each",
                "unit_price": 6.8,
            },
        ],
        "subtotal_excl_vat": 3400.0,
        "vat_amount": 510.0,
        "total_incl_vat": 3910.0,
        "notes": [],
    }
)


def test_tool_loop_runs_tools_and_returns_order(ref):
    client = FakeClient(
        [
            response(
                [
                    tool_use_block("t1", "find_customer", {"name": "Coastal Bakeries"}),
                    tool_use_block("t2", "search_catalogue", {"query": "cake box 10 inch"}),
                ],
                stop_reason="tool_use",
            ),
            response([text_block(ORDER_JSON)], cache_read=900),
        ]
    )

    order, usage = extract_po(SAMPLE, ref, client=client)

    assert order.po_number == "CB-2026-0418"
    assert usage["cache_read"] == 900

    second = client.beta.messages.requests[1]
    results = second["messages"][-1]["content"]
    # Both tool results come back in one user message, in call order.
    assert [r["tool_use_id"] for r in results] == ["t1", "t2"]
    assert json.loads(results[0]["content"])[0]["account_code"] == "C1001"
    assert json.loads(results[1]["content"])[0]["sku"] == "BOX-CAKE-10"


def test_request_shape_supports_caching_and_strict_tools(ref):
    client = FakeClient([response([text_block(ORDER_JSON)])])
    extract_po(SAMPLE, ref, client=client)
    req = client.beta.messages.requests[0]

    assert req["cache_control"] == {"type": "ephemeral"}
    assert req["output_config"]["format"]["type"] == "json_schema"
    assert all(t["strict"] for t in req["tools"])
    assert "tool_choice" not in req  # forced tool choice is rejected on this model
    assert "Coastal Bakeries" in req["messages"][0]["content"][0]["text"]


def test_unknown_tool_is_reported_as_error(ref):
    client = FakeClient(
        [
            response([tool_use_block("t1", "delete_everything", {})], stop_reason="tool_use"),
            response([text_block(ORDER_JSON)]),
        ]
    )
    extract_po(SAMPLE, ref, client=client)
    result = client.beta.messages.requests[1]["messages"][-1]["content"][0]
    assert result["is_error"] is True


def test_refusal_raises(ref):
    client = FakeClient([response([], stop_reason="refusal")])
    with pytest.raises(ExtractionError, match="declined"):
        extract_po(SAMPLE, ref, client=client)


def test_schema_mismatch_raises(ref):
    client = FakeClient([response([text_block('{"po_number": "x"}')])])
    with pytest.raises(ExtractionError, match="schema"):
        extract_po(SAMPLE, ref, client=client)
