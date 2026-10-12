"""Reference data: customer accounts and the product catalogue.

In production these would come from the ERP over its API. Here they are CSV
files so the project runs anywhere without credentials.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal
from difflib import SequenceMatcher
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


@dataclass(frozen=True)
class Customer:
    account_code: str
    name: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class Product:
    sku: str
    description: str
    unit: str
    list_price: Decimal


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


class ReferenceData:
    def __init__(self, customers: list[Customer], products: list[Product]):
        self.customers = customers
        self.products = {p.sku: p for p in products}

    @classmethod
    def load(cls, data_dir: Path = DATA_DIR) -> ReferenceData:
        with open(data_dir / "customers.csv", newline="", encoding="utf-8") as f:
            customers = [
                Customer(
                    account_code=row["account_code"],
                    name=row["name"],
                    aliases=tuple(a.strip() for a in row["aliases"].split("|") if a.strip()),
                )
                for row in csv.DictReader(f)
            ]
        with open(data_dir / "catalogue.csv", newline="", encoding="utf-8") as f:
            products = [
                Product(
                    sku=row["sku"],
                    description=row["description"],
                    unit=row["unit"],
                    list_price=Decimal(row["list_price"]),
                )
                for row in csv.DictReader(f)
            ]
        return cls(customers, products)

    def find_customer(self, name: str, limit: int = 3) -> list[dict]:
        """Best fuzzy matches for a customer name, scored 0-1."""
        scored = []
        for c in self.customers:
            score = max(_similarity(name, n) for n in (c.name, *c.aliases))
            scored.append((score, c))
        scored.sort(key=lambda s: s[0], reverse=True)
        return [
            {"account_code": c.account_code, "name": c.name, "score": round(s, 2)}
            for s, c in scored[:limit]
            if s >= 0.4
        ]

    def search_catalogue(self, query: str, limit: int = 5) -> list[dict]:
        """Best catalogue matches for a free-text item description or code."""
        scored = []
        for p in self.products.values():
            score = max(_similarity(query, p.description), _similarity(query, p.sku))
            scored.append((score, p))
        scored.sort(key=lambda s: s[0], reverse=True)
        return [
            {
                "sku": p.sku,
                "description": p.description,
                "unit": p.unit,
                "list_price": str(p.list_price),
                "score": round(s, 2),
            }
            for s, p in scored[:limit]
            if s >= 0.3
        ]

    def catalogue_as_text(self) -> str:
        """The catalogue as a stable, sorted table for a cached system prompt."""
        rows = ["sku | description | unit | list_price_zar"]
        rows += [
            f"{p.sku} | {p.description} | {p.unit} | {p.list_price}"
            for p in sorted(self.products.values(), key=lambda p: p.sku)
        ]
        return "\n".join(rows)

    def customers_as_text(self) -> str:
        rows = ["account_code | name | also_known_as"]
        rows += [
            f"{c.account_code} | {c.name} | {', '.join(c.aliases)}"
            for c in sorted(self.customers, key=lambda c: c.account_code)
        ]
        return "\n".join(rows)
