# po-intake-ai

Turns customer purchase orders (text or PDF) into checked sales-order data and an
Excel review workbook. Claude reads the documents; Python does every calculation.

## Commands

- Install: `pip install -e ".[dev]"`
- Test: `python -m pytest -q` (no API key needed; the client is faked)
- Lint: `python -m ruff check . && python -m ruff format --check .`
- Real run (costs money, ask first): `po-intake extract samples/ --xlsx out/review.xlsx`

## Layout

- `extract.py`: interactive path. Tool-use loop with `find_customer` and `search_catalogue`.
- `batch.py`: backlog path. Message Batches API, reference data in a cached system prompt.
- `validate.py`: deterministic business checks. Money is `Decimal`, VAT is 15%.
- `excel.py`: review workbook with live formulas.
- `models.py`: one Pydantic model is the schema, the validator input and the export shape.

## Rules for this codebase

- Never do arithmetic in the prompt or trust totals from the model. Checks live in `validate.py`.
- Prompts and tool definitions must be static strings. Anything that changes per
  request (dates, IDs, file names) breaks the prompt cache.
- The model is `claude-opus-5-5`. It rejects forced `tool_choice` and disabled
  thinking, so steer tool calls from the prompt and control depth with `effort`.
- Batch results arrive in any order. Key them by `custom_id`, never by position.
- Tests must not call the real API. Extend `FakeClient` in `tests/conftest.py`.
- Customer and product data in `data/` and `samples/` is fictional. Keep it that way.

## When adding an extraction field

Use the `add-po-field` skill.
