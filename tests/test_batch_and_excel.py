from pathlib import Path
from types import SimpleNamespace

from openpyxl import load_workbook
from test_validate import TODAY, make_order

from po_intake import batch
from po_intake.excel import write_workbook
from po_intake.models import IntakeResult
from po_intake.validate import check

SAMPLES = Path(__file__).resolve().parents[1] / "samples"


def test_batch_requests_share_one_cached_system_prompt(ref):
    paths = sorted(SAMPLES.glob("*.txt"))
    requests = batch.build_requests(paths, ref)

    assert [r["custom_id"] for r in requests] == [batch.custom_id_for(p) for p in paths]
    systems = [r["params"]["system"] for r in requests]
    assert all(s == systems[0] for s in systems)  # identical prefix -> cache hits
    assert systems[0][-1]["cache_control"] == {"type": "ephemeral"}
    assert "BOX-CAKE-10" in systems[0][-1]["text"]
    assert "tools" not in requests[0]["params"]


def test_collect_keys_by_custom_id_and_reports_failures():
    good = make_order().model_dump_json()
    items = [
        SimpleNamespace(custom_id="b", result=SimpleNamespace(type="errored")),
        SimpleNamespace(
            custom_id="a",
            result=SimpleNamespace(
                type="succeeded",
                message=SimpleNamespace(
                    stop_reason="end_turn", content=[SimpleNamespace(type="text", text=good)]
                ),
            ),
        ),
    ]
    client = SimpleNamespace(messages=SimpleNamespace(batches=SimpleNamespace(results=lambda _id: items)))
    orders, failures = batch.collect("msgbatch_x", client=client)
    assert list(orders) == ["a"]
    assert failures == {"b": "errored"}


def test_workbook_uses_formulas_and_flags_status(ref, tmp_path):
    clean = make_order()
    broken = make_order(po_number="X-1", subtotal_excl_vat=1.00)
    results = [
        IntakeResult(source="clean.txt", order=clean, issues=check(clean, ref, today=TODAY)),
        IntakeResult(source="broken.txt", order=broken, issues=check(broken, ref, today=TODAY)),
    ]
    path = write_workbook(results, tmp_path / "review.xlsx")

    wb = load_workbook(path)
    lines, orders, issues = wb["Lines"], wb["Orders"], wb["Issues"]
    assert lines["I2"].value == '=IF(H2="","",ROUND(F2*H2,2))'
    assert orders["G2"].value == "=SUM(Lines!I2:I4)"
    assert orders["K2"].value == "ready"
    assert orders["K3"].value == "blocked"
    assert issues["D2"].value == "subtotal_mismatch"
