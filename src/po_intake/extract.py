"""Interactive extraction: one PO at a time, with tool use.

Claude reads the document, calls find_customer / search_catalogue as often as
it needs, then answers in the PurchaseOrder JSON schema. Our code runs the
tools; Claude never touches the reference data directly.
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

import anthropic

from .models import PurchaseOrder
from .prompts import EXTRACTION_RULES, TOOL_INSTRUCTIONS, TOOLS
from .reference import ReferenceData

MODEL = os.environ.get("PO_INTAKE_MODEL", "claude-opus-5-5")
MAX_TOOL_ROUNDS = 8
OUTPUT_FORMAT = {"type": "json_schema", "schema": anthropic.transform_schema(PurchaseOrder)}


class ExtractionError(Exception):
    pass


def document_block(path: Path) -> dict[str, Any]:
    """A content block for the PO file: PDFs go in as documents, text as text."""
    if path.suffix.lower() == ".pdf":
        data = base64.standard_b64encode(path.read_bytes()).decode("ascii")
        return {
            "type": "document",
            "source": {"type": "base64", "media_type": "application/pdf", "data": data},
        }
    return {"type": "text", "text": f"<purchase_order>\n{path.read_text('utf-8')}\n</purchase_order>"}


def run_tool(ref: ReferenceData, name: str, tool_input: dict[str, Any]) -> tuple[str, bool]:
    """Execute one tool call. Returns (result_json, is_error)."""
    if name == "find_customer":
        return json.dumps(ref.find_customer(tool_input["name"])), False
    if name == "search_catalogue":
        return json.dumps(ref.search_catalogue(tool_input["query"])), False
    return f"Unknown tool: {name}", True


def extract_po(
    path: Path,
    ref: ReferenceData,
    client: anthropic.Anthropic | None = None,
) -> tuple[PurchaseOrder, dict[str, int]]:
    """Extract one purchase order. Returns the order and token usage totals."""
    client = client or anthropic.Anthropic()
    messages: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": [document_block(path), {"type": "text", "text": "Extract this purchase order."}],
        }
    ]
    usage = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}

    for _ in range(MAX_TOOL_ROUNDS):
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=f"{EXTRACTION_RULES}\n{TOOL_INSTRUCTIONS}",
            tools=TOOLS,
            messages=messages,
            output_config={"effort": "medium", "format": OUTPUT_FORMAT},
            # Each tool round re-sends the whole document. Caching the growing
            # prefix means rounds 2+ read it from cache at a fraction of the price.
            cache_control={"type": "ephemeral"},
            # If a safety classifier declines, retry on a suitable fallback model.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        u = response.usage
        usage["input"] += u.input_tokens
        usage["output"] += u.output_tokens
        usage["cache_read"] += u.cache_read_input_tokens or 0
        usage["cache_write"] += u.cache_creation_input_tokens or 0

        if response.stop_reason == "refusal":
            raise ExtractionError(f"{path.name}: request declined ({response.stop_details})")
        if response.stop_reason == "max_tokens":
            raise ExtractionError(f"{path.name}: response hit max_tokens")

        tool_calls = [b for b in response.content if b.type == "tool_use"]
        if not tool_calls:
            text = next((b.text for b in response.content if b.type == "text"), "")
            try:
                return PurchaseOrder.model_validate_json(text), usage
            except ValueError as e:
                raise ExtractionError(f"{path.name}: response did not match schema: {e}") from e

        messages.append({"role": "assistant", "content": response.content})
        results = []
        for call in tool_calls:
            content, is_error = run_tool(ref, call.name, call.input)
            results.append(
                {"type": "tool_result", "tool_use_id": call.id, "content": content, "is_error": is_error}
            )
        # All results for one turn go back in a single user message.
        messages.append({"role": "user", "content": results})

    raise ExtractionError(f"{path.name}: no answer after {MAX_TOOL_ROUNDS} tool rounds")
