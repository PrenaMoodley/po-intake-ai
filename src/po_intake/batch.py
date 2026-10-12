"""Backlog extraction with the Message Batches API.

Use this when a folder of POs can wait: batches run asynchronously at half the
price of normal requests. A batch request cannot run a tool loop, so instead of
lookup tools, the customer list and catalogue go into the system prompt. That
block is identical for every request in the batch and is marked for caching.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import anthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request

from .extract import MODEL, OUTPUT_FORMAT, document_block
from .models import PurchaseOrder
from .prompts import EXTRACTION_RULES
from .reference import ReferenceData


def custom_id_for(path: Path) -> str:
    # custom_id allows 1-64 chars of [a-zA-Z0-9_-]; results come back in any
    # order and are matched to files by this id, never by position.
    return re.sub(r"[^a-zA-Z0-9_-]", "_", path.stem)[:64]


def build_system(ref: ReferenceData) -> list[dict]:
    return [
        {"type": "text", "text": EXTRACTION_RULES},
        {
            "type": "text",
            "text": (
                "Match customers and products against this reference data.\n\n"
                f"<customers>\n{ref.customers_as_text()}\n</customers>\n\n"
                f"<catalogue>\n{ref.catalogue_as_text()}\n</catalogue>"
            ),
            "cache_control": {"type": "ephemeral"},
        },
    ]


def build_requests(paths: list[Path], ref: ReferenceData) -> list[Request]:
    system = build_system(ref)
    ids = [custom_id_for(p) for p in paths]
    if len(set(ids)) != len(ids):
        raise ValueError("Two files map to the same custom_id; rename one of them.")
    return [
        Request(
            custom_id=cid,
            params=MessageCreateParamsNonStreaming(
                model=MODEL,
                max_tokens=16000,
                system=system,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            document_block(p),
                            {"type": "text", "text": "Extract this purchase order."},
                        ],
                    }
                ],
                output_config={"effort": "medium", "format": OUTPUT_FORMAT},
            ),
        )
        for cid, p in zip(ids, paths, strict=True)
    ]


def submit(paths: list[Path], ref: ReferenceData, client: anthropic.Anthropic | None = None) -> str:
    client = client or anthropic.Anthropic()
    batch = client.messages.batches.create(requests=build_requests(paths, ref))
    return batch.id


def status(batch_id: str, client: anthropic.Anthropic | None = None) -> str:
    client = client or anthropic.Anthropic()
    batch = client.messages.batches.retrieve(batch_id)
    c = batch.request_counts
    return (
        f"{batch.processing_status}: {c.succeeded} succeeded, {c.errored} errored, "
        f"{c.processing} processing, {c.expired} expired"
    )


def collect(
    batch_id: str, client: anthropic.Anthropic | None = None
) -> tuple[dict[str, PurchaseOrder], dict[str, str]]:
    """Returns (orders by custom_id, failures by custom_id)."""
    client = client or anthropic.Anthropic()
    orders: dict[str, PurchaseOrder] = {}
    failures: dict[str, str] = {}
    for item in client.messages.batches.results(batch_id):
        result = item.result
        if result.type != "succeeded":
            failures[item.custom_id] = result.type
            continue
        if result.message.stop_reason != "end_turn":
            failures[item.custom_id] = f"stop_reason={result.message.stop_reason}"
            continue
        text = next((b.text for b in result.message.content if b.type == "text"), "")
        try:
            orders[item.custom_id] = PurchaseOrder.model_validate(json.loads(text))
        except ValueError as e:
            failures[item.custom_id] = f"invalid JSON: {e}"
    return orders, failures
