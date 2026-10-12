"""Data shapes shared by the extractor, the validator and the Excel export.

The same Pydantic model is used three ways:
  1. as the JSON schema Claude must answer in (structured outputs),
  2. to validate what comes back,
  3. as the typed input to deterministic business checks.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class POLine(BaseModel):
    line_no: int = Field(description="Line number as it appears on the PO, starting at 1.")
    customer_ref: str | None = Field(
        description="The customer's own item code, if the PO shows one. Null if not."
    )
    sku: str | None = Field(
        description="Our catalogue SKU that this line matches. Null if no confident match."
    )
    description: str = Field(description="Item description exactly as written on the PO.")
    quantity: float = Field(description="Quantity ordered, in the unit of measure below.")
    unit: str = Field(description="Unit of measure, e.g. 'each', 'box', 'case'.")
    unit_price: float | None = Field(
        description="Price per unit excluding VAT, in ZAR. Null if the PO does not state it."
    )


class PurchaseOrder(BaseModel):
    po_number: str = Field(description="The customer's purchase order number.")
    customer_name: str = Field(description="Customer name as written on the PO.")
    account_code: str | None = Field(
        description="Our customer account code from find_customer. Null if not found."
    )
    order_date: str | None = Field(description="PO date as ISO 8601 (YYYY-MM-DD).")
    delivery_date: str | None = Field(description="Requested delivery date, ISO 8601.")
    delivery_address: str | None = Field(description="Delivery address, one line.")
    lines: list[POLine]
    subtotal_excl_vat: float | None = Field(description="PO subtotal excluding VAT, if stated.")
    vat_amount: float | None = Field(description="VAT amount, if stated.")
    total_incl_vat: float | None = Field(description="PO grand total including VAT, if stated.")
    notes: list[str] = Field(
        description="Anything a sales administrator should check: ambiguities, "
        "handwritten changes, items you could not match."
    )


class Issue(BaseModel):
    """A problem found by the deterministic checks in validate.py."""

    severity: str  # "error" blocks the order, "warning" needs a human look
    code: str
    message: str
    line_no: int | None = None


class IntakeResult(BaseModel):
    source: str
    order: PurchaseOrder
    issues: list[Issue] = []

    @property
    def status(self) -> str:
        if any(i.severity == "error" for i in self.issues):
            return "blocked"
        if self.issues:
            return "review"
        return "ready"
