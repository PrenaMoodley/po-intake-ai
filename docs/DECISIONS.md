# Decision log

Short records of choices that are not obvious from the code.

## 1. Use AI only for reading the document

**Context.** POs arrive in many formats: structured PDFs, free-text emails,
scans with handwriting. A template or regex parser breaks on every new customer layout.

**Decision.** Claude extracts fields and matches wording to catalogue items.
Everything with a single correct answer stays in plain Python: line totals,
subtotal, 15% VAT, price-list comparison, date checks, account validation.

**Why.** Arithmetic and rules must be exact, repeatable and testable. A
language model is the right tool for messy input and the wrong tool for sums.

**When I would not use AI at all.** If a customer sends the same structured
CSV or EDI file every time, a plain import script (or a Power Automate flow
watching a mailbox) is cheaper, faster and easier to support.

## 2. Two paths: tool loop now, Batch API for backlogs

**Decision.** `extract.py` runs a tool-use loop per document. `batch.py` sends
many documents through the Message Batches API.

**Why.** Batches cost half as much but can take up to 24 hours, and a batch
request can't run a multi-turn tool loop. So the batch path puts the customer
list and catalogue in the system prompt instead of behind tools. That works
while the reference data is small. If the catalogue grew to thousands of items,
I would keep tools and run the interactive path overnight instead.

## 3. Structured outputs instead of a forced "record" tool

**Context.** A common pattern forces Claude to call a `record_order` tool to get
JSON back. `claude-opus-5-5` rejects forced `tool_choice`.

**Decision.** Use `output_config.format` with a JSON schema generated from the
Pydantic model, and keep real tools for real lookups.

## 4. Prompt caching layout

**Decision.** Prompts and tool definitions are static strings. The interactive
loop uses automatic caching so tool rounds 2+ read the document from cache. The
batch path marks the reference-data block for caching so every request in the
batch shares it.

**Check.** `po-intake extract` prints `cache_read` tokens per document. If it is
always 0, something in the prefix is changing between requests.

## 5. Excel output with live formulas

**Decision.** Line totals and subtotals in the workbook are Excel formulas, and
a `Check` column compares each with the Python result.

**Why.** The sales admin team works in Excel. Formulas let them audit the maths
and fix a quantity without the totals going stale. The Python column catches
any difference between the two calculations.
