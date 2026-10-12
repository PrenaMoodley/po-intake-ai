"""Command line entry point.

po-intake extract samples/po-1001.txt [--xlsx out/review.xlsx]
po-intake batch submit samples/
po-intake batch status <batch_id>
po-intake batch collect <batch_id> --xlsx out/review.xlsx
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import batch
from .excel import write_workbook
from .extract import ExtractionError, extract_po
from .models import IntakeResult
from .reference import ReferenceData
from .validate import check

SUPPORTED = {".txt", ".md", ".pdf"}


def _files(target: Path) -> list[Path]:
    if target.is_dir():
        return sorted(p for p in target.iterdir() if p.suffix.lower() in SUPPORTED)
    return [target]


def _report(results: list[IntakeResult], xlsx: Path | None) -> None:
    for r in results:
        print(f"{r.source}: {r.order.po_number} -> {r.status} ({len(r.issues)} issues)")
        for i in r.issues:
            where = f" line {i.line_no}" if i.line_no else ""
            print(f"  [{i.severity}]{where} {i.code}: {i.message}")
    if xlsx:
        print(f"Workbook: {write_workbook(results, xlsx)}")


def cmd_extract(args: argparse.Namespace) -> int:
    ref = ReferenceData.load()
    results, failed = [], 0
    for path in _files(args.target):
        try:
            order, usage = extract_po(path, ref)
        except ExtractionError as e:
            print(f"FAILED {e}", file=sys.stderr)
            failed += 1
            continue
        print(f"{path.name}: tokens {json.dumps(usage)}", file=sys.stderr)
        results.append(IntakeResult(source=path.name, order=order, issues=check(order, ref)))
    _report(results, args.xlsx)
    return 1 if failed else 0


def cmd_batch(args: argparse.Namespace) -> int:
    if args.action == "submit":
        files = _files(Path(args.value))
        batch_id = batch.submit(files, ReferenceData.load())
        print(f"Submitted {len(files)} documents. Batch id: {batch_id}")
    elif args.action == "status":
        print(batch.status(args.value))
    else:
        ref = ReferenceData.load()
        orders, failures = batch.collect(args.value)
        for cid, reason in failures.items():
            print(f"FAILED {cid}: {reason}", file=sys.stderr)
        results = [
            IntakeResult(source=cid, order=o, issues=check(o, ref)) for cid, o in sorted(orders.items())
        ]
        _report(results, args.xlsx)
        return 1 if failures else 0
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="po-intake", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("extract", help="Extract one PO, or every PO in a folder, now.")
    p.add_argument("target", type=Path)
    p.add_argument("--xlsx", type=Path, help="Write a review workbook here.")
    p.set_defaults(func=cmd_extract)

    b = sub.add_parser("batch", help="Process a backlog with the Message Batches API.")
    b.add_argument("action", choices=["submit", "status", "collect"])
    b.add_argument("value", help="Folder (submit) or batch id (status, collect).")
    b.add_argument("--xlsx", type=Path, help="Write a review workbook here (collect).")
    b.set_defaults(func=cmd_batch)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
